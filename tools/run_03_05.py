"""Plan 03-05: Wave 2 AUDIT-01 + AUDIT-03 driver.

Provisions a fresh RunPod H100 pod under the pinned image for AUDIT-01
(co-residency stack-load), waits for the pod to self-terminate, fetches
results back, terminates the pod, records ledger spend. Then repeats for
AUDIT-03 (engine-swap + Ollama overhead). Each audit runs on its own pod so
spend bucketing per `gate="audit_01"` / `gate="audit_03"` in
config/budget.yaml is honored.

pod_entrypoint.sh has an explicit ``audit_*`` branch (around line 407) that
installs Ollama before launching ``python -m gates.audit_03.runner`` — no
modifications needed on the pod side.

Modes mirror tools/audit_harness_health.py.

Exit codes:
    0  both audits pass (or clean dry-run)
    1  any audit failed
    2  BudgetExhausted (for either audit; subsequent audits skipped)
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

DEFAULT_MAX_MINUTES_PER_AUDIT = 30
AUDITS_IN_ORDER = ("audit_01", "audit_03")


def _fetch_audit_results(
    pr: ProvisionResult,
    audit: str,
    final_state: str,
    results_root: pathlib.Path,
) -> pathlib.Path:
    """Rsync audit outputs back from the network volume into results/<audit>/."""
    audit_dir = results_root / audit
    network_volume_id = os.environ.get("RUNPOD_NETWORK_VOLUME_ID")
    if final_state not in ("EXITED", "GONE") or not network_volume_id:
        return audit_dir
    try:
        from tools.fetch_results import fetch as fetch_results

        tmp_dest = results_root / "_pulled"
        rc = fetch_results(pr.pod_id, audit, network_volume_id, tmp_dest)
        if rc != 0:
            logger.warning(f"[03-05] fetch_results rc={rc} audit={audit}")
            return audit_dir
        src = tmp_dest / pr.pod_id / audit
        audit_dir.mkdir(parents=True, exist_ok=True)
        if src.exists():
            for child in src.iterdir():
                target = audit_dir / child.name
                if target.exists() or not child.is_file():
                    continue
                target.write_bytes(child.read_bytes())
    except Exception as e:
        logger.warning(f"[03-05] fetch_results failed audit={audit}: {e}")
    return audit_dir


def _summarize_audit_results(audit_dir: pathlib.Path) -> dict:
    """Per-audit verdict: count JSONL rows, check audit.json violations."""
    jsonls = sorted(audit_dir.glob("*.jsonl"))
    audit_files = sorted(audit_dir.glob("*.audit.json"))
    rows: list[dict] = []
    if jsonls:
        rows = [json.loads(line) for line in jsonls[-1].open() if line.strip()]
    audit_clean = False
    if audit_files:
        try:
            doc = json.loads(audit_files[-1].read_text())
            audit_clean = int(doc.get("summary", {}).get("violations", 1)) == 0
        except Exception as e:
            logger.warning(f"[03-05] audit log unreadable: {e}")
    return {
        "rows_observed": len(rows),
        "jsonl_files": [p.name for p in jsonls],
        "audit_clean": audit_clean,
        "verdict": "pass" if rows and audit_clean else "fail",
    }


async def _run_one_audit(
    *,
    audit: str,
    max_minutes: int,
    wants_real: bool,
    results_root: pathlib.Path,
) -> dict:
    """Single-audit orchestration step. Returns a manifest entry dict.

    Ledger key matches the audit name so config/budget.yaml entries
    (audit_01, audit_03) are honored. The audits ignore --strata (the audit
    runners accept the flag but discard it — they have no corpus strata).
    """
    projected_cost = _project_cost(max_minutes)
    saved_key: str | None = None
    if not wants_real:
        saved_key = os.environ.pop("RUNPOD_API_KEY", None)
    provision_kwargs: dict = {
        "gate": audit,
        "projected_cost": projected_cost,
        "max_minutes": max_minutes,
        "network_volume_id": os.environ.get("RUNPOD_NETWORK_VOLUME_ID"),
        "ssh_pubkey": os.environ.get("SSH_PUBKEY"),
        "operator_host": os.environ.get("OPERATOR_HOST"),
    }
    gpu_type_override = os.environ.get("RUNPOD_GPU_TYPE")
    if gpu_type_override:
        provision_kwargs["gpu_type"] = gpu_type_override

    started_utc = datetime.datetime.utcnow().isoformat()
    try:
        pr: ProvisionResult = provision(**provision_kwargs)
    except BudgetExhausted as e:
        return {
            "audit": audit,
            "started_utc": started_utc,
            "error": f"BudgetExhausted: {e}",
            "projected_cost_usd": projected_cost,
            "max_minutes": max_minutes,
            "verdict": "budget-exhausted",
            "real_spend": False,
        }
    except RunPodProvisionError as e:
        return {
            "audit": audit,
            "started_utc": started_utc,
            "error": f"RunPodProvisionError: {e}",
            "projected_cost_usd": projected_cost,
            "max_minutes": max_minutes,
            "verdict": "fail",
            "real_spend": False,
        }
    finally:
        if saved_key is not None:
            os.environ["RUNPOD_API_KEY"] = saved_key

    if not wants_real or pr.pod_id == "dry-run":
        return {
            "audit": audit,
            "started_utc": started_utc,
            "real_spend": False,
            "pod_id": pr.pod_id,
            "image_ref": pr.image_ref,
            "image_digest": _split_image_digest(pr.image_ref),
            "auth_id": pr.authorization.id,
            "projected_cost_usd": projected_cost,
            "max_minutes": max_minutes,
            "verdict": "dry-run",
        }

    timeout_s = max_minutes * 60 + 300
    final_state = await _wait_for_pod_exit(pr.pod_id, timeout_s=timeout_s)
    if final_state == "TIMEOUT":
        logger.warning(
            f"[03-05] pod={pr.pod_id} audit={audit} TIMEOUT after "
            f"{max_minutes}m+5m; force-terminating"
        )
        terminate(pr.pod_id)

    audit_dir = _fetch_audit_results(pr, audit, final_state, results_root)
    summary = _summarize_audit_results(audit_dir)
    final_spend_usd = await _final_spend()
    return {
        "audit": audit,
        "started_utc": started_utc,
        "terminated_utc": datetime.datetime.utcnow().isoformat(),
        "real_spend": True,
        "pod_id": pr.pod_id,
        "pod_url": pr.pod_url,
        "image_ref": pr.image_ref,
        "image_digest": _split_image_digest(pr.image_ref),
        "gpu_type": pr.gpu_type,
        "auth_id": pr.authorization.id,
        "projected_cost_usd": projected_cost,
        "final_spend_usd": final_spend_usd,
        "max_minutes": max_minutes,
        "final_pod_state": final_state,
        **summary,
    }


async def main_async(argv: list[str]) -> int:
    p = argparse.ArgumentParser(
        prog="tools.run_03_05",
        description=(
            "Plan 03-05: provision v18 H100 pods for AUDIT-01 then AUDIT-03, "
            "wait, fetch results, emit per-audit verdicts."
        ),
    )
    p.add_argument("--real-spend", action="store_true")
    p.add_argument(
        "--max-minutes-per-audit",
        type=int,
        default=DEFAULT_MAX_MINUTES_PER_AUDIT,
    )
    p.add_argument(
        "--gate",
        type=str,
        default="both",
        choices=["both", "audit_01", "audit_03"],
        help="Run only one audit (operator re-run after partial failure).",
    )
    p.add_argument("--out-dir", type=pathlib.Path, default=pathlib.Path("results/preflight"))
    args = p.parse_args(argv)

    ts = datetime.datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    args.out_dir.mkdir(parents=True, exist_ok=True)
    out_path = args.out_dir / f"03-05-wave2-audits-{ts}.json"

    wants_real = args.real_spend and os.environ.get("RUNPOD_API_KEY") is not None
    results_root = pathlib.Path("results")
    results_root.mkdir(parents=True, exist_ok=True)  # noqa: ASYNC240

    audits = AUDITS_IN_ORDER if args.gate == "both" else (args.gate,)
    audit_entries: list[dict] = []
    overall_rc = 0
    for a in audits:
        entry = await _run_one_audit(
            audit=a,
            max_minutes=args.max_minutes_per_audit,
            wants_real=wants_real,
            results_root=results_root,
        )
        audit_entries.append(entry)
        if entry["verdict"] == "budget-exhausted":
            overall_rc = 2
            break
        if entry["verdict"] == "fail":
            overall_rc = max(overall_rc, 1)

    manifest = {
        "plan": "03-05",
        "started_utc": ts,
        "real_spend": wants_real,
        "hourly_rate_usd": H100_USD_PER_HR,
        "max_minutes_per_audit": args.max_minutes_per_audit,
        "audits_requested": list(audits),
        "audits": audit_entries,
        "verdict": (
            "budget-exhausted" if overall_rc == 2 else ("pass" if overall_rc == 0 else "fail")
        ),
    }
    _write_manifest(out_path, manifest)
    logger.info(
        f"[03-05] verdict={manifest['verdict']} audits={[e['audit'] for e in audit_entries]} "
        f"manifest={out_path}"
    )
    return overall_rc


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    return asyncio.run(main_async(sys.argv[1:] if argv is None else argv))


if __name__ == "__main__":
    sys.exit(main())
