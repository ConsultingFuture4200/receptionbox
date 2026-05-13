"""Plan 03-02: Wave 2 G2 + G3 driver.

Provisions a fresh RunPod H100 pod under the pinned image for gate G2 (G.711
dual-path WER A/B), waits for the pod to self-terminate, fetches results back
from the network volume, terminates the pod, records ledger spend. Then
repeats for G3 (silero + turn-detector threshold sweep). Each gate runs on
its own pod so isolation is preserved and a failure in one does not poison
the other's spend ledger row.

Why two pods, not one entrypoint? pod_entrypoint.sh dispatches on the single
``GATE`` env var. There is no multi-gate entrypoint, and authoring one is out
of scope for this brief (operator chose "Path 1: per-plan drivers reusing the
03-01 pattern"). A single provision() call commits exactly one ledger
authorization keyed on gate name; running both G2 and G3 in one pod would
mis-bucket spend.

Modes (mirror tools/audit_harness_health.py):
    default        — provision() routes to dry-run when RUNPOD_API_KEY is
                     unset OR --real-spend is not passed. Ledger row still
                     commits for each gate so operator sees the projection.
    --real-spend   — actually provision per-gate pods, wait for clean exit,
                     fetch results back.

Exit codes:
    0  all gates pass (or clean dry-run)
    1  any gate failed (no rows fetched, runner non-zero, etc.)
    2  BudgetExhausted — ledger refused the projected cost for any gate

Hard Constraint #1: authorize_spend(...) is the FIRST executable statement in
every code path leading to provision(). This module never calls
authorize_spend directly — provision() owns that contract — but each gate
loop iteration calls provision() before any other RunPod-touching side
effect.
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

DEFAULT_MAX_MINUTES_PER_GATE = 20
DEFAULT_STRATA = "config/sanity_strata.yaml"
GATES_IN_ORDER = ("g2", "g3")


def _fetch_gate_results(
    pr: ProvisionResult,
    gate: str,
    final_state: str,
    results_root: pathlib.Path,
) -> pathlib.Path:
    """Rsync results back from the network volume into results/<gate>/.

    Mirrors the v14 transport path used by tools/run_preflight.py. Skipped
    when no network volume is configured or pod did not exit cleanly. Fetch
    failure is logged but never raises — the manifest will simply observe
    zero rows and the gate will be marked failed.
    """
    gate_dir = results_root / gate
    network_volume_id = os.environ.get("RUNPOD_NETWORK_VOLUME_ID")
    if final_state not in ("EXITED", "GONE") or not network_volume_id:
        return gate_dir
    try:
        from tools.fetch_results import fetch as fetch_results

        tmp_dest = results_root / "_pulled"
        rc = fetch_results(pr.pod_id, gate, network_volume_id, tmp_dest)
        if rc != 0:
            logger.warning(f"[03-02] fetch_results rc={rc} gate={gate}")
            return gate_dir
        src = tmp_dest / pr.pod_id / gate
        gate_dir.mkdir(parents=True, exist_ok=True)
        if src.exists():
            for child in src.iterdir():
                target = gate_dir / child.name
                if target.exists() or not child.is_file():
                    continue
                target.write_bytes(child.read_bytes())
    except Exception as e:
        logger.warning(f"[03-02] fetch_results failed gate={gate}: {e}")
    return gate_dir


def _summarize_gate_results(gate_dir: pathlib.Path) -> dict:
    """Read JSONL rows + audit summary; build a per-gate verdict block."""
    jsonls = sorted(gate_dir.glob("*.jsonl"))
    audit_files = sorted(gate_dir.glob("*.audit.json"))
    rows: list[dict] = []
    if jsonls:
        rows = [json.loads(line) for line in jsonls[-1].open() if line.strip()]
    audit_clean = False
    if audit_files:
        try:
            doc = json.loads(audit_files[-1].read_text())
            audit_clean = int(doc.get("summary", {}).get("violations", 1)) == 0
        except Exception as e:
            logger.warning(f"[03-02] audit log unreadable: {e}")
    return {
        "rows_observed": len(rows),
        "jsonl_files": [p.name for p in jsonls],
        "audit_clean": audit_clean,
        "verdict": "pass" if rows and audit_clean else "fail",
    }


async def _run_one_gate(
    *,
    gate: str,
    max_minutes: int,
    strata: str,
    wants_real: bool,
    results_root: pathlib.Path,
) -> dict:
    """Single-gate orchestration step. Returns a manifest entry dict.

    Mirrors tools/audit_harness_health.main_async's structure but parametrized
    so we can compose it across multiple gates without duplicating the
    provision → wait → fetch → manifest loop.
    """
    projected_cost = _project_cost(max_minutes)
    saved_key: str | None = None
    if not wants_real:
        saved_key = os.environ.pop("RUNPOD_API_KEY", None)
    provision_kwargs: dict = {
        "gate": gate,
        "projected_cost": projected_cost,
        "max_minutes": max_minutes,
        "network_volume_id": os.environ.get("RUNPOD_NETWORK_VOLUME_ID"),
        "ssh_pubkey": os.environ.get("SSH_PUBKEY"),
        "operator_host": os.environ.get("OPERATOR_HOST"),
    }
    gpu_type_override = os.environ.get("RUNPOD_GPU_TYPE")
    if gpu_type_override:
        provision_kwargs["gpu_type"] = gpu_type_override
    # STRATA_PATH is honored by pod_entrypoint.sh v11+; pass through env on
    # provision (not as a runner CLI flag — the entrypoint owns that wiring).
    os.environ["STRATA_PATH"] = strata

    started_utc = datetime.datetime.utcnow().isoformat()
    try:
        pr: ProvisionResult = provision(**provision_kwargs)
    except BudgetExhausted as e:
        return {
            "gate": gate,
            "started_utc": started_utc,
            "error": f"BudgetExhausted: {e}",
            "projected_cost_usd": projected_cost,
            "max_minutes": max_minutes,
            "verdict": "budget-exhausted",
            "real_spend": False,
        }
    except RunPodProvisionError as e:
        return {
            "gate": gate,
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
            "gate": gate,
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
            f"[03-02] pod={pr.pod_id} gate={gate} TIMEOUT after {max_minutes}m+5m; "
            "force-terminating"
        )
        terminate(pr.pod_id)

    gate_dir = _fetch_gate_results(pr, gate, final_state, results_root)
    summary = _summarize_gate_results(gate_dir)
    final_spend_usd = await _final_spend()
    return {
        "gate": gate,
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
        prog="tools.run_03_02",
        description=(
            "Plan 03-02: provision v18 H100 pods for G2 then G3, wait, fetch "
            "results, emit per-gate verdicts. Each gate runs on its own pod."
        ),
    )
    p.add_argument("--real-spend", action="store_true")
    p.add_argument("--max-minutes-per-gate", type=int, default=DEFAULT_MAX_MINUTES_PER_GATE)
    p.add_argument("--strata", type=str, default=DEFAULT_STRATA)
    p.add_argument(
        "--gate",
        type=str,
        default="both",
        choices=["both", "g2", "g3"],
        help="Run only one gate (operator re-run after partial failure).",
    )
    p.add_argument("--out-dir", type=pathlib.Path, default=pathlib.Path("results/preflight"))
    args = p.parse_args(argv)

    ts = datetime.datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    args.out_dir.mkdir(parents=True, exist_ok=True)
    out_path = args.out_dir / f"03-02-wave2-g2g3-{ts}.json"

    wants_real = args.real_spend and os.environ.get("RUNPOD_API_KEY") is not None
    results_root = pathlib.Path("results")
    results_root.mkdir(parents=True, exist_ok=True)  # noqa: ASYNC240

    gates = GATES_IN_ORDER if args.gate == "both" else (args.gate,)
    gate_entries: list[dict] = []
    overall_rc = 0
    for g in gates:
        entry = await _run_one_gate(
            gate=g,
            max_minutes=args.max_minutes_per_gate,
            strata=args.strata,
            wants_real=wants_real,
            results_root=results_root,
        )
        gate_entries.append(entry)
        if entry["verdict"] == "budget-exhausted":
            overall_rc = 2
            # Do not provision subsequent gates after a budget refusal.
            break
        if entry["verdict"] == "fail":
            overall_rc = max(overall_rc, 1)
            # Continue to next gate — operator may want partial data.

    manifest = {
        "plan": "03-02",
        "started_utc": ts,
        "real_spend": wants_real,
        "hourly_rate_usd": H100_USD_PER_HR,
        "max_minutes_per_gate": args.max_minutes_per_gate,
        "strata": args.strata,
        "gates_requested": list(gates),
        "gates": gate_entries,
        "verdict": (
            "budget-exhausted" if overall_rc == 2 else ("pass" if overall_rc == 0 else "fail")
        ),
    }
    _write_manifest(out_path, manifest)
    logger.info(
        f"[03-02] verdict={manifest['verdict']} gates={[e['gate'] for e in gate_entries]} "
        f"manifest={out_path}"
    )
    return overall_rc


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    return asyncio.run(main_async(sys.argv[1:] if argv is None else argv))


if __name__ == "__main__":
    sys.exit(main())
