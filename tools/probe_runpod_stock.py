"""Probe RunPod GPU availability for the rbox volume's region.

Lists volumes (so you see the region your network volume is in) and
the lowest-price stock for each GPU SKU we care about for Phase 02.

Usage:
    export RUNPOD_API_KEY=...
    python -m tools.probe_runpod_stock
"""

from __future__ import annotations

import os
import sys

import runpod

# GPUs we might use this phase, in priority order. Bootstrap needs no
# GPU compute (HF downloads only) so cheap/abundant SKUs are fine; gates
# need an H100 (PCIe or SXM).
CANDIDATES = [
    "NVIDIA H100 PCIe",
    "NVIDIA H100 SXM",
    "NVIDIA H100 NVL",
    "NVIDIA GeForce RTX 4090",
    "NVIDIA L4",
    "NVIDIA RTX A5000",
    "NVIDIA RTX A4000",
]


def main() -> int:
    api_key = os.environ.get("RUNPOD_API_KEY")
    if not api_key:
        print("ERROR: RUNPOD_API_KEY not set", file=sys.stderr)
        return 2
    runpod.api_key = api_key

    user = runpod.get_user()
    print("Network volumes:")
    for v in user.get("networkVolumes") or []:
        print(f"  name={v['name']:12s} id={v['id']} region={v['dataCenterId']} size={v['size']}GB")

    print("\nAll GPU SKUs visible (canonical id | displayName | memGB):")
    all_gpus = runpod.get_gpus()
    for g in all_gpus:
        gid = g.get("id", "?")
        name = g.get("displayName", "?")
        mem = g.get("memoryInGb", "?")
        print(f"  {gid:40s} | {name:30s} | {mem}")

    print("\nFiltered candidates (Secure Cloud, on-demand):")
    print(f"  {'GPU id':40s} {'secure?':10s} {'$/hr':>8s}")
    for gpu_id in CANDIDATES:
        try:
            info = runpod.get_gpu(gpu_id)
            secure_ok = info.get("secureCloud")
            price = info.get("securePrice")
            print(
                f"  {gpu_id:40s} {'yes' if secure_ok else 'no':10s} "
                f"{('$' + str(price)) if price else '—':>8s}"
            )
        except Exception as e:
            print(f"  {gpu_id:40s} ERROR: {e}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
