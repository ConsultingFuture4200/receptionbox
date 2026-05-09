"""Fetch persisted gate results from the RunPod network volume.

Phase 2 cloud-only transport: gate pods write results to
/models/_results/<pod_id>/<gate>/ before self-terminating
(tools/pod_entrypoint.sh v14+). This script spawns a tiny diag pod with the
volume mounted, scps the directory tree back to the operator workstation,
and terminates the diag pod.

Costs ~$0.05 per fetch (RTX 4090 @ $0.34/hr x ~9 min, dominated by image pull).
Use the cheapest GPU available in the volume's data center; CPU pods can't
mount the network volume on RunPod's current platform.

CLI:
    python -m tools.fetch_results POD_ID [GATE] [--volume RUNPOD_NETWORK_VOLUME_ID]

Environment:
    RUNPOD_API_KEY            (required)
    RUNPOD_NETWORK_VOLUME_ID  (required if --volume not passed)
    SSH_PUBKEY_PATH           (default ~/.ssh/rbox_phase2.pub)
    SSH_PRIVATE_KEY_PATH      (default ~/.ssh/rbox_phase2)
"""

from __future__ import annotations

import argparse
import base64
import os
import pathlib
import shlex
import subprocess
import sys
import time

import httpx
import runpod  # type: ignore[import-untyped]

# Cheapest GPU SKU that supports volume mounts; H100 NVL stays consistent with
# the volume's DC (US-KS-2). Override via RUNPOD_FETCH_GPU_TYPE if cheaper
# stock surfaces in your volume's DC.
FETCH_GPU = os.environ.get("RUNPOD_FETCH_GPU_TYPE", "NVIDIA H100 NVL")
# v14 image — has /usr/sbin/sshd installed and matches the keypair our
# entrypoint trusts. Overridable via RUNPOD_FETCH_IMAGE for emergencies.
FETCH_IMAGE = os.environ.get(
    "RUNPOD_FETCH_IMAGE",
    "ghcr.io/consultingfuture4200/rbox-pod"
    "@sha256:29a17ca8eaafbeba567a86a7b8a0c1ca15776d4d6c634c5b7cbc17f411c1b550",
)


def _gql(api_key: str, query: str) -> dict:
    h = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    r = httpx.post("https://api.runpod.io/graphql", headers=h, json={"query": query}, timeout=30)
    return r.json()


def _wait_for_ssh(pod_id: str, api_key: str, deadline_s: int = 600) -> tuple[str, int]:
    """Poll RunPod until the pod publishes a public TCP port for sshd."""
    deadline = time.time() + deadline_s
    while time.time() < deadline:
        q = (
            '{ pod(input:{podId:"'
            + pod_id
            + '"}) { runtime { ports { ip publicPort privatePort type isIpPublic } } } }'
        )
        try:
            data = _gql(api_key, q).get("data", {}).get("pod", {}) or {}
            rt = data.get("runtime") or {}
            for p in rt.get("ports") or []:
                if p.get("privatePort") == 22 and p.get("isIpPublic"):
                    return str(p["ip"]), int(p["publicPort"])
        except Exception as e:
            print(f"[fetch] ports poll err: {e}", file=sys.stderr)
        time.sleep(8)
    raise TimeoutError(f"pod {pod_id} sshd port never published within {deadline_s}s")


def fetch(pod_id: str, gate: str | None, volume_id: str, dest_root: pathlib.Path) -> int:
    """Spawn fetch pod -> rsync /models/_results -> terminate fetch pod."""
    api_key = os.environ.get("RUNPOD_API_KEY")
    if not api_key:
        print("[fetch] RUNPOD_API_KEY unset; skip", file=sys.stderr)
        return 0
    runpod.api_key = api_key

    pubkey_path = pathlib.Path(
        os.environ.get("SSH_PUBKEY_PATH", str(pathlib.Path.home() / ".ssh/rbox_phase2.pub"))
    )
    privkey_path = pathlib.Path(
        os.environ.get("SSH_PRIVATE_KEY_PATH", str(pathlib.Path.home() / ".ssh/rbox_phase2"))
    )
    if not pubkey_path.exists() or not privkey_path.exists():
        print(f"[fetch] missing keypair {pubkey_path}/{privkey_path}", file=sys.stderr)
        return 1
    pubkey = pubkey_path.read_text().strip()
    pubkey_b64 = base64.b64encode(pubkey.encode()).decode()

    docker_args = (
        "bash -c '"
        "mkdir -p /root/.ssh && chmod 700 /root/.ssh && "
        f"echo {pubkey_b64} | base64 -d >> /root/.ssh/authorized_keys && "
        "chmod 600 /root/.ssh/authorized_keys && "
        "ssh-keygen -A 2>/dev/null || true; "
        "exec /usr/sbin/sshd -D -e"
        "'"
    )

    print(f"[fetch] creating fetch pod (volume={volume_id} gpu={FETCH_GPU})")
    fetch_pod = runpod.create_pod(
        name=f"rbox-fetch-{int(time.time())}",
        image_name=FETCH_IMAGE,
        gpu_type_id=FETCH_GPU,
        gpu_count=1,
        container_disk_in_gb=20,
        volume_in_gb=50,
        ports="22/tcp",
        network_volume_id=volume_id,
        volume_mount_path="/models",
        docker_args=docker_args,
        env={"DIAG_MODE_FETCH": "1"},
    )
    fetch_pod_id = fetch_pod["id"]
    print(f"[fetch] fetch_pod_id={fetch_pod_id}")

    rc = 1
    try:
        ip, port = _wait_for_ssh(fetch_pod_id, api_key)
        print(f"[fetch] sshd ready at {ip}:{port}")

        # Source: /models/_results/<pod_id>/<gate>/  (or whole pod tree if gate None)
        src = f"/models/_results/{pod_id}/"
        if gate:
            src = f"/models/_results/{pod_id}/{gate}/"
        local_dest = dest_root / pod_id / (gate or "")
        local_dest.mkdir(parents=True, exist_ok=True)

        # rsync over ssh — fast and resumable.
        cmd = [
            "rsync",
            "-az",
            "--info=stats2",
            "-e",
            f"ssh -i {privkey_path} -p {port} -o StrictHostKeyChecking=no "
            "-o UserKnownHostsFile=/dev/null -o ConnectTimeout=20",
            f"root@{ip}:{src}",
            f"{local_dest}/",
        ]
        print(f"[fetch] {' '.join(shlex.quote(c) for c in cmd)}")
        # cmd args are operator-controlled (volume_id from env, paths from
        # this script) — no untrusted input reaches the shell here.
        proc = subprocess.run(cmd, check=False)  # noqa: S603
        rc = proc.returncode
        if rc == 0:
            print(f"[fetch] OK -> {local_dest}")
        else:
            print(f"[fetch] FAIL rsync rc={rc}")
    finally:
        try:
            runpod.terminate_pod(fetch_pod_id)
            print(f"[fetch] terminated {fetch_pod_id}")
        except Exception as e:
            print(f"[fetch] terminate err: {e}", file=sys.stderr)
    return rc


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("pod_id", help="ID of the gate pod whose results to fetch")
    p.add_argument(
        "gate",
        nargs="?",
        default=None,
        help="Optional gate name (smoke|g1|g2|g3|g5). Default: pull all gates.",
    )
    p.add_argument(
        "--volume",
        default=os.environ.get("RUNPOD_NETWORK_VOLUME_ID"),
        help="Network volume ID (defaults to env RUNPOD_NETWORK_VOLUME_ID)",
    )
    p.add_argument(
        "--dest",
        type=pathlib.Path,
        default=pathlib.Path("results"),
        help="Local destination root (default: results/)",
    )
    args = p.parse_args(argv)
    if not args.volume:
        print("[fetch] --volume or RUNPOD_NETWORK_VOLUME_ID required", file=sys.stderr)
        return 2
    return fetch(args.pod_id, args.gate, args.volume, args.dest)


if __name__ == "__main__":
    sys.exit(main())
