"""Phase 2 pre-flight driver: provision -> wait -> validate -> teardown.

Modes:
  bootstrap  one-time HF cache pull on a small bootstrap pod
  smoke      5-call G1 smoke (PREFLIGHT-01)
  sanity     sequential G1+G2+G3+G5 sanity (PREFLIGHT-02)

Honors RUNPOD_API_KEY=unset by routing through orchestration.runpod_h100's
dry-run path. In dry-run mode no httpx/runpod calls are made; the ledger row
is still committed (visible to the operator) so spend projections stay honest.

Real-spend mode (RUNPOD_API_KEY set):
  1. Read config/budget.yaml phase2.max_minutes_per_gate -> projected_cost
  2. Call orchestration.runpod_h100.provision(...) (cost-ledger gated)
  3. Poll cost.adapters.runpod.poll(...) every 60s; print cumulative spend
  4. Wait for the pod to self-terminate (watchdog or SIGTERM trap exits)
  5. Read back rsynced JSONL + env.json + audit.json from results/
  6. For smoke: validate D-25 (a)-(f); print PASS/FAIL
  7. Write session manifest to results/preflight/{session_id}.json

The driver does NOT bypass orchestration.runpod_h100.provision() — Hard
Constraint #1 (cost-ledger gate) is preserved.
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
import time

import yaml

from harness.env_sidecar import read_env_sidecar
from orchestration.runpod_h100 import (
    ProvisionResult,
    RunPodProvisionError,
    provision,
    terminate,
)

logger = logging.getLogger(__name__)

# RunPod H100 SXM on-demand Secure Cloud (CLAUDE.md §1.1, May 2026).
H100_USD_PER_HR = 2.69


def _project_cost(max_minutes: int) -> float:
    return round(max_minutes / 60.0 * H100_USD_PER_HR, 2)


def _budget(path: pathlib.Path = pathlib.Path("config/budget.yaml")) -> dict:
    return yaml.safe_load(path.read_text())


async def _wait_for_pod_exit(pod_id: str, *, timeout_s: int) -> str:
    """Poll RunPod every 60s until the pod is gone or in a terminal state.

    Returns the final state: "GONE" | "EXITED" | "TERMINATED" | "STOPPED" |
    "TIMEOUT". Network errors during poll are logged WARNING but never
    abort the wait.
    """
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        try:
            import runpod  # type: ignore[import-untyped]

            runpod.api_key = os.environ.get("RUNPOD_API_KEY", "")
            pods = runpod.get_pods() or []
            found = next((p for p in pods if p.get("id") == pod_id), None)
            if found is None:
                return "GONE"
            status = found.get("desiredStatus") or found.get("runtimeStatus") or "UNKNOWN"
            if status in ("EXITED", "TERMINATED", "STOPPED"):
                return str(status)
            logger.info(f"[preflight] pod={pod_id} status={status}; waiting")
        except Exception as e:
            logger.warning(f"[preflight] poll error: {e}")
        await asyncio.sleep(60)
    return "TIMEOUT"


async def _final_spend() -> float:
    """One last cumulative-spend reading via cost.adapters.runpod.poll."""
    try:
        import httpx

        from cost.adapters import runpod as runpod_adapter

        async with httpx.AsyncClient() as client:
            spend, _projected = await runpod_adapter.poll(client)
            return float(spend)
    except Exception as e:
        logger.warning(f"[preflight] final-spend poll failed: {e}")
        return 0.0


def _validate_smoke(
    *,
    results_dir: pathlib.Path,
    run_id_glob: str,
    wall_clock_s: float,
    final_spend: float,
) -> dict:
    """Return D-25 verdict dict {criterion -> bool, "pass": bool}."""
    candidates = sorted(results_dir.glob(f"smoke/{run_id_glob}.jsonl"))
    if not candidates:
        return {
            "a_5_rows": False,
            "b_under_30min": False,
            "c_under_1usd": False,
            "d_per_stage_timings": False,
            "e_env_sidecar": False,
            "f_audit_clean": False,
            "pass": False,
            "error": "no JSONL found",
        }
    jsonl = candidates[-1]
    rows = [json.loads(line) for line in jsonl.open() if line.strip()]
    env_path = jsonl.with_name(jsonl.stem + ".env.json")
    audit_glob = sorted(results_dir.glob("smoke/*.audit.json"))

    e_sidecar = False
    if env_path.exists():
        try:
            read_env_sidecar(env_path)
            e_sidecar = True
        except Exception as e:
            logger.warning(f"[preflight] env_sidecar invalid: {e}")

    f_clean = False
    if audit_glob:
        try:
            doc = json.loads(audit_glob[-1].read_text())
            f_clean = int(doc.get("summary", {}).get("violations", 1)) == 0
        except Exception as e:
            logger.warning(f"[preflight] audit log unreadable: {e}")

    v: dict = {
        "a_5_rows": len(rows) == 5,
        "b_under_30min": wall_clock_s < 30 * 60,
        "c_under_1usd": final_spend < 1.0,
        "d_per_stage_timings": all(
            r.get("stt_ttft_ms") is not None
            and r.get("llm_ttft_ms") is not None
            and r.get("tts_first_audio_ms") is not None
            and r.get("e2e_ms") is not None
            for r in rows
        ),
        "e_env_sidecar": e_sidecar,
        "f_audit_clean": f_clean,
    }
    v["pass"] = all(
        v[k]
        for k in (
            "a_5_rows",
            "b_under_30min",
            "c_under_1usd",
            "d_per_stage_timings",
            "e_env_sidecar",
            "f_audit_clean",
        )
    )
    return v


async def _run_gate(
    *,
    gate: str,
    max_minutes: int,
    network_volume_id: str | None,
    ssh_pubkey: str | None,
    operator_host: str | None,
    results_dir: pathlib.Path,
) -> dict:
    """Provision one pod for `gate`, wait for it to exit, return verdict dict."""
    projected = _project_cost(max_minutes)
    started = time.time()
    gate_gpu_type = os.environ.get("RUNPOD_GPU_TYPE")
    provision_kwargs: dict = {
        "gate": gate,
        "projected_cost": projected,
        "max_minutes": max_minutes,
        "network_volume_id": network_volume_id,
        "ssh_pubkey": ssh_pubkey,
        "operator_host": operator_host,
    }
    if gate_gpu_type:
        provision_kwargs["gpu_type"] = gate_gpu_type
    try:
        result: ProvisionResult = provision(**provision_kwargs)
    except RunPodProvisionError as e:
        return {"gate": gate, "status": "provision_error", "error": str(e)}

    if result.pod_id == "dry-run":
        logger.info(f"[preflight] DRY RUN gate={gate}; ledger row committed")
        return {
            "gate": gate,
            "status": "dry-run",
            "pod_id": "dry-run",
            "auth_id": result.authorization.id,
            "projected_cost_usd": projected,
        }

    final_state = await _wait_for_pod_exit(result.pod_id, timeout_s=max_minutes * 60 + 300)
    # 2026-05-08: on TIMEOUT the pod is still RUNNING (the wait function gave
    # up but did not tear it down). Without an explicit terminate the pod
    # burns the full per-gate ceiling — observed wedge cost $3.33 on a
    # US-KS-2 host that never produced a JSONL row. Terminate fail-safe:
    # idempotent on already-EXITED pods, safe on dry-run / unset key per
    # orchestration.runpod_h100.terminate().
    if final_state == "TIMEOUT":
        logger.warning(
            f"[preflight] pod={result.pod_id} TIMEOUT after "
            f"{max_minutes}m+5m budget; force-terminating to stop burn"
        )
        terminate(result.pod_id)
    wall_clock_s = time.time() - started

    # 2026-05-09 v14 transport: gate pods persist results to
    # /models/_results/<pod_id>/<gate>/ (pod_entrypoint.sh shutdown trap).
    # Spawn a tiny fetch pod to pull them off the volume to local
    # results/<gate>/. Skipped on TIMEOUT (no useful data) and when no
    # network volume is configured. Fetch failure is logged but doesn't
    # invalidate the gate verdict — _validate_smoke just won't find rows.
    network_volume_id = os.environ.get("RUNPOD_NETWORK_VOLUME_ID")
    if final_state == "EXITED" and network_volume_id:
        try:
            from tools.fetch_results import fetch as fetch_results

            tmp_dest = results_dir / "_pulled"
            rc = fetch_results(result.pod_id, gate, network_volume_id, tmp_dest)
            if rc == 0:
                src = tmp_dest / result.pod_id / gate
                gate_dir = results_dir / gate
                gate_dir.mkdir(parents=True, exist_ok=True)
                # Flatten {pod_id}/{gate}/* -> results/{gate}/* so
                # _validate_smoke's existing glob still matches.
                if src.exists():
                    for child in src.iterdir():
                        target_path = gate_dir / child.name
                        if target_path.exists():
                            continue
                        target_path.write_bytes(child.read_bytes()) if child.is_file() else None
                logger.info(f"[preflight] fetched results to {gate_dir}")
            else:
                logger.warning(f"[preflight] fetch_results rc={rc}")
        except Exception as e:
            logger.warning(f"[preflight] fetch_results failed: {e}")

    final_spend = await _final_spend()
    verdict = {
        "gate": gate,
        "status": final_state,
        "wall_clock_s": wall_clock_s,
        "final_spend_usd": final_spend,
        "pod_id": result.pod_id,
        "auth_id": result.authorization.id,
        "projected_cost_usd": projected,
    }
    if gate == "smoke":
        verdict["smoke_verdict"] = _validate_smoke(
            results_dir=results_dir,
            run_id_glob="*",
            wall_clock_s=wall_clock_s,
            final_spend=final_spend,
        )
    return verdict


async def _run(mode: str) -> int:
    cfg = _budget()
    per = cfg["phase2"]["max_minutes_per_gate"]
    results_dir = pathlib.Path("results")
    network_volume_id = os.environ.get("RUNPOD_NETWORK_VOLUME_ID")
    ssh_pubkey = os.environ.get("SSH_PUBKEY")
    operator_host = os.environ.get("OPERATOR_HOST")
    session_id = datetime.datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    session: dict = {
        "session_id": session_id,
        "mode": mode,
        "started_utc": datetime.datetime.utcnow().isoformat(),
        "gates": [],
    }

    if mode == "bootstrap":
        # Bootstrap pod: small profile, mounts /models, entrypoint reads
        # BOOTSTRAP_MODE=1 and runs `python -m tools.cache_bootstrap`. Same
        # cost-ledger gate as smoke/sanity (Hard Constraint #1: provision()
        # calls authorize_spend FIRST). Plan 02-05 Task 2 closes
        # 02-VERIFICATION GAP-3 secondary by replacing the prior manual-CLI
        # stub with this SDK-driven path.
        bootstrap_max_min = int(per.get("bootstrap", 15))
        bootstrap_cost = float(cfg["phase2"].get("cache_bootstrap_one_time_usd", 0.67))
        # BOOTSTRAP_GPU_TYPE wins over RUNPOD_GPU_TYPE so operators can route
        # bootstrap (no GPU compute, just HF downloads) to a cheaper SKU while
        # smoke/sanity stay on H100. Both env vars optional; provision()'s
        # NVIDIA H100 PCIe default applies when neither is set.
        bootstrap_gpu_type = os.environ.get("BOOTSTRAP_GPU_TYPE") or os.environ.get(
            "RUNPOD_GPU_TYPE"
        )
        started = time.time()
        provision_kwargs: dict = {
            "gate": "bootstrap",
            "projected_cost": bootstrap_cost,
            "max_minutes": bootstrap_max_min,
            "network_volume_id": network_volume_id,
            "ssh_pubkey": ssh_pubkey,
            "operator_host": operator_host,
        }
        if bootstrap_gpu_type:
            provision_kwargs["gpu_type"] = bootstrap_gpu_type
        try:
            result: ProvisionResult = provision(**provision_kwargs)
        except RunPodProvisionError as e:
            session["gates"].append(
                {"gate": "bootstrap", "status": "provision_error", "error": str(e)}
            )
            _write_session(session, results_dir)
            return 1
        if result.pod_id == "dry-run":
            logger.info("[preflight] DRY RUN bootstrap; ledger row committed")
            session["gates"].append(
                {
                    "gate": "bootstrap",
                    "status": "dry-run",
                    "pod_id": "dry-run",
                    "auth_id": result.authorization.id,
                    "projected_cost_usd": bootstrap_cost,
                }
            )
            _write_session(session, results_dir)
            return 0
        final_state = await _wait_for_pod_exit(
            result.pod_id, timeout_s=bootstrap_max_min * 60 + 300
        )
        # 2026-05-08: terminate on TIMEOUT so a wedged bootstrap pod can't
        # burn the full 30-min ceiling silently. See _run_gate above for
        # the smoke-side incident this protects against.
        if final_state == "TIMEOUT":
            logger.warning(
                f"[preflight] bootstrap pod={result.pod_id} TIMEOUT after "
                f"{bootstrap_max_min}m+5m budget; force-terminating"
            )
            terminate(result.pod_id)
        wall_clock_s = time.time() - started
        final_spend = await _final_spend()
        session["gates"].append(
            {
                "gate": "bootstrap",
                "status": final_state,
                "wall_clock_s": wall_clock_s,
                "final_spend_usd": final_spend,
                "pod_id": result.pod_id,
                "auth_id": result.authorization.id,
                "projected_cost_usd": bootstrap_cost,
            }
        )
        _write_session(session, results_dir)
        terminal = {"EXITED", "GONE", "TERMINATED", "STOPPED"}
        return 0 if final_state in terminal else 1

    gates = ["smoke"] if mode == "smoke" else ["g1", "g2", "g3", "g5"]
    for g in gates:
        max_min = int(per.get(g, per.get("smoke", 30)))
        v = await _run_gate(
            gate=g,
            max_minutes=max_min,
            network_volume_id=network_volume_id,
            ssh_pubkey=ssh_pubkey,
            operator_host=operator_host,
            results_dir=results_dir,
        )
        session["gates"].append(v)
        if (
            mode == "smoke"
            and isinstance(v.get("smoke_verdict"), dict)
            and v["smoke_verdict"].get("pass") is False
        ):
            logger.error(f"[preflight] smoke FAILED: {v['smoke_verdict']}")
            break

    _write_session(session, results_dir)
    print(json.dumps(session, indent=2, default=str))

    terminal = {"EXITED", "GONE", "TERMINATED", "STOPPED", "dry-run"}
    any_fail = any(g.get("status") not in terminal for g in session["gates"])
    return 1 if any_fail else 0


def _write_session(session: dict, results_dir: pathlib.Path) -> pathlib.Path:
    out = results_dir / "preflight" / f"{session['session_id']}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(session, indent=2, sort_keys=True, default=str))
    return out


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="tools.run_preflight")
    p.add_argument("--mode", choices=["bootstrap", "smoke", "sanity"], required=True)
    args = p.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    return asyncio.run(_run(args.mode))


if __name__ == "__main__":
    sys.exit(main())
