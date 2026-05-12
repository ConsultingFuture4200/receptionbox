"""Probe per-data-center GPU availability for the rbox network volume.

For each candidate GPU SKU, attempts to create a pod mounted on the rbox
volume (which locks the data center). Successful creates are terminated
immediately. Failed creates surface RunPod's "no instances available"
error, telling us the SKU has no stock in that data center right now.

WARNING: Each successful probe incurs ~1-3 seconds of billing before
termination (sub-penny per probe). Probes against cheap GPUs cost ~$0;
probes against H100 SXM may cost up to $0.005 per success.

Usage:
    export RUNPOD_API_KEY=...
    python -m tools.probe_runpod_dc

The volume name to probe defaults to "rbox"; pass a different name as
argv[1] to probe a different volume's data center.
"""

from __future__ import annotations

import os
import sys
import time

import runpod

CANDIDATES = [
    "NVIDIA H100 PCIe",
    "NVIDIA H100 80GB HBM3",  # canonical id for H100 SXM
    "NVIDIA H100 NVL",
    "NVIDIA L4",
    "NVIDIA L40S",
    "NVIDIA RTX A4000",
    "NVIDIA RTX A5000",
    "NVIDIA RTX A6000",
    "NVIDIA GeForce RTX 4090",
]

PROBE_IMAGE = "runpod/pytorch:2.4.0-py3.11-cuda12.4.1-base-ubuntu22.04"


def _resolve_volume_id(name: str) -> tuple[str, str]:
    """Return (volume_id, region). Raises if not found."""
    user = runpod.get_user()
    for v in user.get("networkVolumes") or []:
        if v["name"] == name:
            return v["id"], v["dataCenterId"]
    raise SystemExit(f"ERROR: no volume named {name!r}")


def _try(gpu: str, volume_id: str) -> tuple[str, str]:
    """Attempt one provision; terminate on success. Returns (status, detail)."""
    try:
        pod = runpod.create_pod(
            name=f"rbox-probe-{int(time.time())}",
            image_name=PROBE_IMAGE,
            gpu_type_id=gpu,
            gpu_count=1,
            container_disk_in_gb=10,
            network_volume_id=volume_id,
            volume_mount_path="/models",
            ports="22/tcp",
        )
    except Exception as e:
        msg = str(e)
        if "no longer any instances available" in msg or "no instances available" in msg:
            return ("no_stock", "")
        return ("error", msg.split("\n")[0][:120])
    pod_id = pod.get("id", "?")
    # Terminate as fast as possible.
    try:
        runpod.terminate_pod(pod_id)
    except Exception as e:
        return ("AVAILABLE_LEAKED", f"pod {pod_id} created but terminate failed: {e}")
    return ("AVAILABLE", f"pod {pod_id} created and terminated")


def main() -> int:
    if not os.environ.get("RUNPOD_API_KEY"):
        print("ERROR: RUNPOD_API_KEY not set", file=sys.stderr)
        return 2
    runpod.api_key = os.environ["RUNPOD_API_KEY"]
    name = sys.argv[1] if len(sys.argv) > 1 else "rbox"
    volume_id, region = _resolve_volume_id(name)
    print(f"Probing data center {region} via volume {name!r} ({volume_id}):")
    print(f"  {'GPU SKU':30s} | {'status':22s} | detail")
    for gpu in CANDIDATES:
        status, detail = _try(gpu, volume_id)
        print(f"  {gpu:30s} | {status:22s} | {detail}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
