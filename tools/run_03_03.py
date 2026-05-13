"""Plan 03-03: Wave 2 G5 (UPL probe gate) driver.

Provisions a fresh RunPod H100 pod under the pinned image for gate G5 (UPL
probes — 200 probe samples + 50 benign controls = 250 rows). Waits for the
pod to self-terminate, fetches results back from the network volume,
terminates the pod, records ledger spend.

Verifies after fetch:
    - row count == 250 (200 UPL + 50 controls)
    - probe_category populated on every row
    - vLLM xgrammar backend confirmed via env.json sidecar (image v18+
      stamps GUIDED_DECODING_BACKEND=xgrammar in env.json next to the JSONL)

Modes mirror tools/audit_harness_health.py:
    default        — dry-run; ledger row committed for visibility.
    --real-spend   — real pod provision + spend.

Exit codes:
    0  G5 pass (or clean dry-run)
    1  G5 fail (row count off, no rows, xgrammar marker absent, audit dirty)
    2  BudgetExhausted

Hard Constraint #1: authorize_spend is the FIRST executable statement in any
path that reaches provision() — owned by provision() itself.
"""

from __future__ import annotations

import argparse
import asyncio
import datetime
import json
import logging
import os
import pathlib
import sys

from cost.ledger import BudgetExhausted
from orchestration.runpod_h100 import (
    ProvisionResult,
    RunPodProvisionError,
    provision,
    terminate,
)
from tools.audit_harness_health import (
    H100_USD_PER_HR,
    _project_cost,
    _split_image_digest,
    _write_manifest,
)
from tools.run_preflight import _final_spend, _wait_for_pod_exit

logger = logging.getLogger(__name__)

DEFAULT_MAX_MINUTES = 30
DEFAULT_STRATA = "config/sanity_strata.yaml"
EXPECTED_ROW_COUNT = 250  # 200 UPL probes + 50 benign controls per plan 03-03
GATE = "g5"


def _fetch_results(
    pr: ProvisionResult, final_state: str, results_root: pathlib.Path
) -> pathlib.Path:
    """Rsync results back from the network volume into results/g5/."""
    gate_dir = results_root / GATE
    network_volume_id = os.environ.get("RUNPOD_NETWORK_VOLUME_ID")
    if final_state not in ("EXITED", "GONE") or not network_volume_id:
        return gate_dir
    try:
        from tools.fetch_results import fetch as fetch_results

        tmp_dest = results_root / "_pulled"
        rc = fetch_results(pr.pod_id, GATE, network_volume_id, tmp_dest)
        if rc != 0:
            logger.warning(f"[03-03] fetch_results rc={rc}")
            return gate_dir
        src = tmp_dest / pr.pod_id / GATE
        gate_dir.mkdir(parents=True, exist_ok=True)
        if src.exists():
            for child in src.iterdir():
                target = gate_dir / child.name
                if target.exists() or not child.is_file():
                    continue
                target.write_bytes(child.read_bytes())
    except Exception as e:
        logger.warning(f"[03-03] fetch_results failed: {e}")
    return gate_dir


def _verify_xgrammar_backend(gate_dir: pathlib.Path) -> bool:
    """Confirm vLLM xgrammar backend stamp in env.json or any log sidecar.

    Plan 03-03 hard requirement: UPL probes only have meaningful FPR data if
    structured-output decoding routed through xgrammar (not the legacy
    outlines backend). The pod's env.json captures vLLM's selected backend
    at startup; if absent we fall back to scanning any *.log or *.env file.
    """
    env_files = list(gate_dir.glob("*env.json")) + list(gate_dir.glob("env.json"))
    for ef in env_files:
        try:
            doc = json.loads(ef.read_text())
            backend = (
                doc.get("GUIDED_DECODING_BACKEND")
                or doc.get("guided_decoding_backend")
                or doc.get("env", {}).get("GUIDED_DECODING_BACKEND")
            )
            if backend and "xgrammar" in str(backend).lower():
                return True
        except Exception as e:
            logger.warning(f"[03-03] env.json unreadable {ef}: {e}")
    # Fallback: substring match in any text sidecar (logs, .env).
    for ext in ("*.log", "*.env", "*.txt"):
        for path in gate_dir.glob(ext):
            try:
                if "xgrammar" in path.read_text().lower():
                    return True
            except Exception as e:
                logger.debug(f"[03-03] sidecar scan skipped {path}: {e}")
                continue
    return False


def _summarize_g5_results(gate_dir: pathlib.Path) -> dict:
    """Parse G5 JSONL output: row count, probe_category coverage, audit clean."""
    jsonls = sorted(gate_dir.glob("*.jsonl"))
    audit_files = sorted(gate_dir.glob("*.audit.json"))
    rows: list[dict] = []
    if jsonls:
        rows = [json.loads(line) for line in jsonls[-1].open() if line.strip()]
    row_count = len(rows)
    probe_category_populated = bool(rows) and all(
        r.get("probe_category") not in (None, "") for r in rows
    )
    row_count_ok = row_count == EXPECTED_ROW_COUNT
    audit_clean = False
    if audit_files:
        try:
            doc = json.loads(audit_files[-1].read_text())
            audit_clean = int(doc.get("summary", {}).get("violations", 1)) == 0
        except Exception as e:
            logger.warning(f"[03-03] audit log unreadable: {e}")
    xgrammar_ok = _verify_xgrammar_backend(gate_dir)
    return {
        "rows_observed": row_count,
        "rows_expected": EXPECTED_ROW_COUNT,
        "row_count_ok": row_count_ok,
        "probe_category_populated": probe_category_populated,
        "xgrammar_backend_confirmed": xgrammar_ok,
        "audit_clean": audit_clean,
        "jsonl_files": [p.name for p in jsonls],
    }


async def main_async(argv: list[str]) -> int:
    p = argparse.ArgumentParser(
        prog="tools.run_03_03",
        description=(
            "Plan 03-03: provision a v18 H100 pod for gate G5 (UPL probes), "
            "wait, fetch results, verify row count + xgrammar backend."
        ),
    )
    p.add_argument("--real-spend", action="store_true")
    p.add_argument("--max-minutes", type=int, default=DEFAULT_MAX_MINUTES)
    p.add_argument("--strata", type=str, default=DEFAULT_STRATA)
    p.add_argument("--out-dir", type=pathlib.Path, default=pathlib.Path("results/preflight"))
    args = p.parse_args(argv)

    ts = datetime.datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    args.out_dir.mkdir(parents=True, exist_ok=True)
    out_path = args.out_dir / f"03-03-wave2-g5-{ts}.json"

    projected_cost = _project_cost(args.max_minutes)
    wants_real = args.real_spend and os.environ.get("RUNPOD_API_KEY") is not None

    saved_key: str | None = None
    if not wants_real:
        saved_key = os.environ.pop("RUNPOD_API_KEY", None)

    provision_kwargs: dict = {
        "gate": GATE,
        "projected_cost": projected_cost,
        "max_minutes": args.max_minutes,
        "network_volume_id": os.environ.get("RUNPOD_NETWORK_VOLUME_ID"),
        "ssh_pubkey": os.environ.get("SSH_PUBKEY"),
        "operator_host": os.environ.get("OPERATOR_HOST"),
    }
    gpu_type_override = os.environ.get("RUNPOD_GPU_TYPE")
    if gpu_type_override:
        provision_kwargs["gpu_type"] = gpu_type_override
    os.environ["STRATA_PATH"] = args.strata

    try:
        try:
            pr: ProvisionResult = provision(**provision_kwargs)
        except BudgetExhausted as e:
            _write_manifest(
                out_path,
                {
                    "plan": "03-03",
                    "started_utc": ts,
                    "gate": GATE,
                    "error": f"BudgetExhausted: {e}",
                    "projected_cost_usd": projected_cost,
                    "verdict": "budget-exhausted",
                },
            )
            return 2
        except RunPodProvisionError as e:
            _write_manifest(
                out_path,
                {
                    "plan": "03-03",
                    "started_utc": ts,
                    "gate": GATE,
                    "error": f"RunPodProvisionError: {e}",
                    "projected_cost_usd": projected_cost,
                    "verdict": "fail",
                },
            )
            return 1
    finally:
        if saved_key is not None:
            os.environ["RUNPOD_API_KEY"] = saved_key

    if not wants_real or pr.pod_id == "dry-run":
        _write_manifest(
            out_path,
            {
                "plan": "03-03",
                "started_utc": ts,
                "gate": GATE,
                "real_spend": False,
                "pod_id": pr.pod_id,
                "image_ref": pr.image_ref,
                "image_digest": _split_image_digest(pr.image_ref),
                "auth_id": pr.authorization.id,
                "projected_cost_usd": projected_cost,
                "max_minutes": args.max_minutes,
                "strata": args.strata,
                "verdict": "dry-run",
            },
        )
        logger.info(
            f"[03-03] DRY RUN manifest={out_path} pod={pr.pod_id} projected=${projected_cost}"
        )
        return 0

    timeout_s = args.max_minutes * 60 + 300
    final_state = await _wait_for_pod_exit(pr.pod_id, timeout_s=timeout_s)
    if final_state == "TIMEOUT":
        logger.warning(f"[03-03] pod={pr.pod_id} TIMEOUT after {args.max_minutes}m+5m; terminating")
        terminate(pr.pod_id)

    results_root = pathlib.Path("results")
    results_root.mkdir(parents=True, exist_ok=True)  # noqa: ASYNC240
    gate_dir = _fetch_results(pr, final_state, results_root)
    summary = _summarize_g5_results(gate_dir)
    final_spend_usd = await _final_spend()

    pass_ok = (
        summary["row_count_ok"]
        and summary["probe_category_populated"]
        and summary["xgrammar_backend_confirmed"]
        and summary["audit_clean"]
    )
    verdict = "pass" if pass_ok else "fail"

    manifest = {
        "plan": "03-03",
        "started_utc": ts,
        "terminated_utc": datetime.datetime.utcnow().isoformat(),
        "gate": GATE,
        "real_spend": True,
        "pod_id": pr.pod_id,
        "pod_url": pr.pod_url,
        "image_ref": pr.image_ref,
        "image_digest": _split_image_digest(pr.image_ref),
        "gpu_type": pr.gpu_type,
        "auth_id": pr.authorization.id,
        "projected_cost_usd": projected_cost,
        "final_spend_usd": final_spend_usd,
        "hourly_rate_usd": H100_USD_PER_HR,
        "max_minutes": args.max_minutes,
        "strata": args.strata,
        "final_pod_state": final_state,
        "verdict": verdict,
        **summary,
    }
    _write_manifest(out_path, manifest)
    logger.info(
        f"[03-03] G5 verdict={verdict} pod={pr.pod_id} spend=${final_spend_usd} "
        f"rows={summary['rows_observed']}/{EXPECTED_ROW_COUNT} manifest={out_path}"
    )
    return 0 if verdict == "pass" else 1


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    return asyncio.run(main_async(sys.argv[1:] if argv is None else argv))


if __name__ == "__main__":
    sys.exit(main())
