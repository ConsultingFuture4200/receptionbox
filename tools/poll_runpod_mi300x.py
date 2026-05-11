"""Poll RunPod for MI300X availability; notify and exit on first success.

Background: MI300X is listed on RunPod Secure Cloud (EU-RO-1, $1.99/GPU-hr,
192 GB HBM3) but stock is intermittent — the SDK `gpuAvailability` query
returns `available=True` even when actual provisioning fails with
`QueryError: no instances available`. This poller probes via the real
create_pod call (the only authoritative stock signal), terminates the pod
immediately on success, and writes a notification.

Why probe-then-terminate (not probe-then-keep): RunPod has no "dry-run"
provision path. Successful create_pod IS the stock signal. Cost per
successful probe: ~$0.03-$0.05 (pod runs for ~60 s before terminate).
Failed probes are free.

Usage:
    export RUNPOD_API_KEY=...
    python -m tools.poll_runpod_mi300x [--interval-min 15] [--gpu-count 1]

Stop with Ctrl+C. The script writes a marker file to
results/_pulled/mi300x_stock_check/<utc-ts>.json for every probe (success
or fail) so you can audit attempts later.
"""

from __future__ import annotations

import argparse
import datetime
import json
import logging
import os
import pathlib
import signal
import sys
import time

import runpod  # type: ignore[import-untyped]

logger = logging.getLogger(__name__)

DATA_CENTER = "EU-RO-1"  # Only RunPod DC that lists MI300X
GPU_TYPE_ID = "AMD Instinct MI300X OAM"
# Smallest ROCm-aware base image we know exists; minimizes pull time on probe.
PROBE_IMAGE = "rocm/pytorch:latest"
PROBE_DIR = pathlib.Path("results/_pulled/mi300x_stock_check")


def _ts() -> str:
    return datetime.datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")


def _write_probe_record(success: bool, detail: str, pod_id: str | None = None) -> None:
    PROBE_DIR.mkdir(parents=True, exist_ok=True)
    rec = {
        "utc": datetime.datetime.utcnow().isoformat(),
        "success": success,
        "detail": detail,
        "pod_id": pod_id,
        "gpu_type_id": GPU_TYPE_ID,
        "data_center": DATA_CENTER,
    }
    (PROBE_DIR / f"{_ts()}.json").write_text(json.dumps(rec, indent=2))


def _probe(gpu_count: int) -> tuple[bool, str, str | None]:
    """Returns (success, detail, pod_id)."""
    try:
        pod = runpod.create_pod(
            name=f"rbox-mi300x-stock-probe-{_ts()}",
            image_name=PROBE_IMAGE,
            gpu_type_id=GPU_TYPE_ID,
            gpu_count=gpu_count,
            cloud_type="SECURE",
            data_center_id=DATA_CENTER,
            container_disk_in_gb=20,
            volume_in_gb=0,
            ports="22/tcp",
        )
    except Exception as e:
        msg = str(e)
        if "no longer any instances" in msg.lower() or "no instances" in msg.lower():
            return (False, "no_stock", None)
        return (False, f"provision_error:{type(e).__name__}:{msg[:200]}", None)
    pod_id = pod["id"]
    # Give it ~60 s to settle (don't wait for image pull — stock is proven by create_pod ack)
    time.sleep(5)
    try:
        runpod.terminate_pod(pod_id)
    except Exception as e:
        logger.warning("terminate failed for %s: %s", pod_id, e)
    return (True, "AVAILABLE", pod_id)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--interval-min",
        type=float,
        default=15.0,
        help="Minutes between probes (default: 15)",
    )
    parser.add_argument(
        "--gpu-count",
        type=int,
        default=1,
        help="GPU count to probe for (default: 1)",
    )
    parser.add_argument(
        "--max-hours",
        type=float,
        default=72.0,
        help="Max wall-clock hours before giving up (default: 72)",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    api_key = os.environ.get("RUNPOD_API_KEY")
    if not api_key:
        logger.error("RUNPOD_API_KEY not set")
        return 2
    runpod.api_key = api_key

    interval_s = args.interval_min * 60
    deadline = time.time() + args.max_hours * 3600
    attempts = 0
    started = time.time()

    logger.info(
        "Polling MI300X (%d GPU) in %s every %.1f min, deadline %.1f hr",
        args.gpu_count,
        DATA_CENTER,
        args.interval_min,
        args.max_hours,
    )
    logger.info("Stop with Ctrl+C. Probe records: %s/", PROBE_DIR)

    # Graceful shutdown
    stop = {"flag": False}

    def _handle_sig(sig: int, _frame: object) -> None:
        logger.info("Received signal %d; will stop after current probe", sig)
        stop["flag"] = True

    signal.signal(signal.SIGINT, _handle_sig)
    signal.signal(signal.SIGTERM, _handle_sig)

    while time.time() < deadline and not stop["flag"]:
        attempts += 1
        attempt_t0 = time.time()
        success, detail, pod_id = _probe(args.gpu_count)
        elapsed_s = time.time() - attempt_t0
        _write_probe_record(success, detail, pod_id)

        if success:
            wall_hr = (time.time() - started) / 3600
            logger.info(
                "STOCK FOUND on attempt %d (wall %.2f hr). Pod %s provisioned + terminated. "
                "RunPod EU-RO-1 has MI300X capacity right now — fire your real provisioning "
                "within minutes before stock evaporates.",
                attempts,
                wall_hr,
                pod_id,
            )
            return 0

        logger.info(
            "attempt=%d %s elapsed=%.1fs — sleeping %.1f min",
            attempts,
            detail,
            elapsed_s,
            args.interval_min,
        )
        if stop["flag"]:
            break
        # Sleep with periodic stop checks so Ctrl+C is responsive
        sleep_until = time.time() + interval_s
        while time.time() < sleep_until and not stop["flag"]:
            time.sleep(min(5, sleep_until - time.time()))

    wall_hr = (time.time() - started) / 3600
    if stop["flag"]:
        logger.info("Stopped after %d attempts (%.2f hr).", attempts, wall_hr)
        return 1
    logger.warning(
        "Deadline reached after %d attempts (%.2f hr) with no stock. "
        "Consider pivoting to alternate provider or Framework Desktop.",
        attempts,
        wall_hr,
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
