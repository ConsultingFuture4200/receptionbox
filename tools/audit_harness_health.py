"""Plan 03-01: Harness-health audit driver.

Provisions a fresh RunPod H100 pod under image v18 via the existing Phase 02
smoke-gate path (orchestration.runpod_h100.provision), waits for the pod to
self-terminate, fetches results back from the network volume, and emits a
single PASS/FAIL verdict manifest at:

    results/preflight/03-01-harness-audit-{YYYYMMDDTHHMMSSZ}.json

Why route through the smoke gate, not a "harness-audit" gate? The v18 image
has no ``gates.harness_audit.runner`` module — pod_entrypoint.sh would FATAL
on ``python -m gates.harness-audit.runner`` (and ``-`` is not even a valid
Python module name). The smoke gate is the existing single-call shake-out
path that proves vLLM, faster-whisper, and Kokoro all serve traffic on a
freshly-provisioned pod. Chatterbox health is deferred to plan 03-04 (image
v19); substrate.cuda's DR-27 fallback routes TTS through Kokoro for now.
This driver re-presents the smoke session result as a substrate-audit
verdict so the operator gets a single-line go/no-go before Wave 2.

Modes:
    default        — provision() routes to its built-in dry-run when
                     RUNPOD_API_KEY is unset OR ``--real-spend`` is not
                     passed. Ledger row still commits (operator sees the
                     spend projection) but no SDK call is made.
    --real-spend   — actually provision a smoke pod, wait for clean exit,
                     fetch results, parse. ~$0.50-0.90 typical on a warm
                     host cache. Operator must explicitly opt in.

Exit codes:
    0  audit pass (or clean dry-run)
    1  audit fail (services unhealthy, audit dirty, or no result rows)
    2  BudgetExhausted — ledger refused the projected cost
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
from tools.run_preflight import _final_spend, _wait_for_pod_exit

logger = logging.getLogger(__name__)

# CLAUDE.md §1.1 — H100 SXM on-demand Secure Cloud, May 2026.
H100_USD_PER_HR = 2.69
DEFAULT_MAX_MINUTES = 15  # ~$0.67 envelope; plan's $1.20 hard ceiling


def _project_cost(max_minutes: int) -> float:
    return round(max_minutes / 60.0 * H100_USD_PER_HR, 2)


def _split_image_digest(image_ref: str) -> str:
    """Return the bare ``sha256:...`` segment of an image_ref, or 'unknown'."""
    if "@" in image_ref:
        return image_ref.split("@", 1)[1]
    return "unknown"


def _adapter_health_from_jsonl(rows: list[dict]) -> dict[str, bool]:
    """Derive {stt, llm, tts} health from smoke JSONL rows.

    A non-null per-stage timing in every row proves the adapter served
    traffic on the freshly-provisioned pod. Empty rows means no round-trip
    happened — all three False.
    """
    if not rows:
        return {"stt": False, "llm": False, "tts": False}
    return {
        "stt": all(r.get("stt_ttft_ms") is not None for r in rows),
        "llm": all(r.get("llm_ttft_ms") is not None for r in rows),
        "tts": all(r.get("tts_first_audio_ms") is not None for r in rows),
    }


def _audit_clean_from_dir(audit_files: list[pathlib.Path]) -> bool:
    """Read the latest audit.json's summary.violations; True iff 0."""
    if not audit_files:
        return False
    try:
        doc = json.loads(audit_files[-1].read_text())
        return int(doc.get("summary", {}).get("violations", 1)) == 0
    except Exception as e:
        logger.warning(f"[03-01] audit log unreadable: {e}")
        return False


def _build_verdict_manifest(
    *,
    pr: ProvisionResult,
    pod_results_dir: pathlib.Path,
    final_spend_usd: float,
) -> dict:
    jsonls = sorted(pod_results_dir.glob("*.jsonl"))
    audit_files = sorted(pod_results_dir.glob("*.audit.json"))
    rows: list[dict] = []
    if jsonls:
        rows = [json.loads(line) for line in jsonls[-1].open() if line.strip()]
    adapter_health = _adapter_health_from_jsonl(rows)
    audit_clean = _audit_clean_from_dir(audit_files)
    all_healthy = all(adapter_health.values())
    verdict = "pass" if all_healthy and audit_clean else "fail"
    return {
        "plan": "03-01",
        "real_spend": True,
        "pod_id": pr.pod_id,
        "pod_url": pr.pod_url,
        "image_ref": pr.image_ref,
        "image_digest": _split_image_digest(pr.image_ref),
        "gpu_type": pr.gpu_type,
        "auth_id": pr.authorization.id,
        "rows_observed": len(rows),
        "adapter_health": adapter_health,
        "audit_clean": audit_clean,
        "final_spend_usd": final_spend_usd,
        "verdict": verdict,
    }


def _write_manifest(out_path: pathlib.Path, manifest: dict) -> None:
    out_path.write_text(json.dumps(manifest, indent=2, default=str, sort_keys=True))


async def main_async(argv: list[str]) -> int:
    p = argparse.ArgumentParser(
        prog="tools.audit_harness_health",
        description=(
            "Plan 03-01: provision a v18 H100 pod, wait, fetch results, emit "
            "a harness-audit verdict. Routes through the smoke gate."
        ),
    )
    p.add_argument(
        "--real-spend",
        action="store_true",
        help="Required to provision a real pod. Default is dry-run even "
        "when RUNPOD_API_KEY is set, so operators must explicitly opt in.",
    )
    p.add_argument("--max-minutes", type=int, default=DEFAULT_MAX_MINUTES)
    p.add_argument("--out-dir", type=pathlib.Path, default=pathlib.Path("results/preflight"))
    args = p.parse_args(argv)

    ts = datetime.datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    args.out_dir.mkdir(parents=True, exist_ok=True)
    out_path = args.out_dir / f"03-01-harness-audit-{ts}.json"

    projected_cost = _project_cost(args.max_minutes)
    wants_real = args.real_spend and os.environ.get("RUNPOD_API_KEY") is not None

    # Force-dry-run path: temporarily mask RUNPOD_API_KEY so provision()
    # takes its built-in dry-run branch (returns pod_id="dry-run" without
    # making any SDK call) even when the env var is set. Without this,
    # `--real-spend` would just gate the parsing path while still creating
    # a real pod via the SDK.
    saved_key: str | None = None
    if not wants_real:
        saved_key = os.environ.pop("RUNPOD_API_KEY", None)

    # Honor RUNPOD_GPU_TYPE override (matches tools/run_preflight.py pattern)
    # so operators can route around stockouts of the default H100 PCIe SKU
    # without code changes. CLAUDE.md §1.1 names H100 SXM as the preferred
    # H100 substrate anyway. Unset → provision() default (H100 PCIe) applies.
    provision_kwargs: dict = {
        "gate": "smoke",
        "projected_cost": projected_cost,
        "max_minutes": args.max_minutes,
        "network_volume_id": os.environ.get("RUNPOD_NETWORK_VOLUME_ID"),
        "ssh_pubkey": os.environ.get("SSH_PUBKEY"),
        "operator_host": os.environ.get("OPERATOR_HOST"),
    }
    gpu_type_override = os.environ.get("RUNPOD_GPU_TYPE")
    if gpu_type_override:
        provision_kwargs["gpu_type"] = gpu_type_override

    try:
        try:
            pr: ProvisionResult = provision(**provision_kwargs)
        except BudgetExhausted as e:
            _write_manifest(
                out_path,
                {
                    "plan": "03-01",
                    "started_utc": ts,
                    "error": f"BudgetExhausted: {e}",
                    "projected_cost_usd": projected_cost,
                    "verdict": "fail",
                },
            )
            return 2
        except RunPodProvisionError as e:
            _write_manifest(
                out_path,
                {
                    "plan": "03-01",
                    "started_utc": ts,
                    "error": f"RunPodProvisionError: {e}",
                    "projected_cost_usd": projected_cost,
                    "verdict": "fail",
                },
            )
            return 1
    finally:
        if saved_key is not None:
            os.environ["RUNPOD_API_KEY"] = saved_key

    # Dry-run short-circuit.
    if not wants_real or pr.pod_id == "dry-run":
        _write_manifest(
            out_path,
            {
                "plan": "03-01",
                "started_utc": ts,
                "real_spend": False,
                "pod_id": pr.pod_id,
                "image_ref": pr.image_ref,
                "image_digest": _split_image_digest(pr.image_ref),
                "auth_id": pr.authorization.id,
                "projected_cost_usd": projected_cost,
                "verdict": "dry-run",
            },
        )
        logger.info(
            f"[03-01] DRY RUN manifest={out_path} pod={pr.pod_id} projected=${projected_cost}"
        )
        return 0

    # Real-spend path: wait for pod exit, fetch results, parse, verdict.
    timeout_s = args.max_minutes * 60 + 300
    final_state = await _wait_for_pod_exit(pr.pod_id, timeout_s=timeout_s)
    if final_state == "TIMEOUT":
        logger.warning(f"[03-01] pod={pr.pod_id} TIMEOUT after {args.max_minutes}m+5m; terminating")
        terminate(pr.pod_id)

    pod_results_dir = pathlib.Path("results") / "smoke"
    network_volume_id = os.environ.get("RUNPOD_NETWORK_VOLUME_ID")
    if final_state in ("EXITED", "GONE") and network_volume_id:
        try:
            from tools.fetch_results import fetch as fetch_results

            tmp_dest = pathlib.Path("results") / "_pulled"
            rc = fetch_results(pr.pod_id, "smoke", network_volume_id, tmp_dest)
            if rc == 0:
                src = tmp_dest / pr.pod_id / "smoke"
                pod_results_dir.mkdir(parents=True, exist_ok=True)
                if src.exists():
                    for child in src.iterdir():
                        target = pod_results_dir / child.name
                        if target.exists() or not child.is_file():
                            continue
                        target.write_bytes(child.read_bytes())
        except Exception as e:
            logger.warning(f"[03-01] fetch_results failed: {e}")

    final_spend_usd = await _final_spend()
    manifest = _build_verdict_manifest(
        pr=pr,
        pod_results_dir=pod_results_dir,
        final_spend_usd=final_spend_usd,
    )
    manifest["started_utc"] = ts
    manifest["projected_cost_usd"] = projected_cost
    manifest["max_minutes"] = args.max_minutes
    manifest["final_pod_state"] = final_state
    manifest["terminated_utc"] = datetime.datetime.utcnow().isoformat()
    _write_manifest(out_path, manifest)

    logger.info(
        f"[03-01] harness audit verdict={manifest['verdict']} pod={pr.pod_id} "
        f"spend=${final_spend_usd} duration={args.max_minutes}min manifest={out_path}"
    )
    return 0 if manifest["verdict"] == "pass" else 1


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    return asyncio.run(main_async(sys.argv[1:] if argv is None else argv))


if __name__ == "__main__":
    sys.exit(main())
