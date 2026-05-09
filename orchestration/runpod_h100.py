"""RunPod H100 orchestration (CLOUD-01 + Phase 2 real provisioning).

Phase 1 stub replaced. Hard Constraint #1 preserved: cost.ledger.authorize_spend
is the FIRST call in provision()'s body — enforced by the AST test in
tests/test_orchestration_skeletons.py::test_orchestration_modules_call_authorize_spend_first.

Dry-run mode: when RUNPOD_API_KEY is unset, provision() still authorizes spend
(so the operator sees the ledger row) and returns a ProvisionResult with
pod_id="dry-run". This lets the operator iterate offline without burning $.
"""

from __future__ import annotations

import datetime
import logging
import os
from dataclasses import dataclass

from cost.ledger import Authorization, authorize_spend

logger = logging.getLogger(__name__)

# Pod image. MUST be the rbox-pod custom image whose ENTRYPOINT is
# tools/pod_entrypoint.sh — the bare upstream vllm/vllm-openai image runs
# its own OpenAI-server CMD and IGNORES BOOTSTRAP_MODE/GATE env vars,
# leaving the pod RUNNING indefinitely (incident 2026-05-06, plan 02-06).
#
# Workflow: build with scripts/build_pod_image.sh, push, then paste the
# resolved @sha256 digest below per CLAUDE.md §2.3 (digest pinning, not
# tag pinning). The default sentinel below fails loudly at RunPod
# create_pod time so a missed pin can't silently recur.
_DEFAULT_IMAGE = (
    "ghcr.io/consultingfuture4200/rbox-pod"
    "@sha256:29a17ca8eaafbeba567a86a7b8a0c1ca15776d4d6c634c5b7cbc17f411c1b550"
)
_DEFAULT_GPU = "NVIDIA H100 PCIe"


class RunPodProvisionError(Exception):
    """Raised when SDK-level pod creation fails AFTER ledger authorization.

    Authorization is committed before this error is raised, so the caller knows
    the spend row exists in the ledger and may need to record/refund.
    """


@dataclass(frozen=True)
class ProvisionResult:
    authorization: Authorization
    pod_id: str
    pod_url: str | None
    image_ref: str
    gpu_type: str
    started_utc: str


def provision(
    *,
    gate: str,
    projected_cost: float,
    max_minutes: int | None = None,
    network_volume_id: str | None = None,
    ssh_pubkey: str | None = None,
    operator_host: str | None = None,
    image_ref: str = _DEFAULT_IMAGE,
    gpu_type: str = _DEFAULT_GPU,
) -> ProvisionResult:
    """Authorize spend, then provision an H100 pod.

    First executable statement MUST be authorize_spend(...) — Hard Constraint #1.
    AST-asserted by tests/test_orchestration_skeletons.py.

    Raises:
        cost.ledger.BudgetExhausted: if the request would breach the cap.
        RunPodProvisionError: SDK-level pod creation failed AFTER authorization.
    """
    auth = authorize_spend(provider="runpod", gate=gate, projected_cost=projected_cost)
    api_key = os.environ.get("RUNPOD_API_KEY")
    started = datetime.datetime.utcnow().isoformat()
    if not api_key:
        logger.warning(
            "[runpod] DRY RUN — RUNPOD_API_KEY not set. "
            f"WOULD create pod gate={gate} image={image_ref} gpu={gpu_type} "
            f"max_minutes={max_minutes} volume={network_volume_id}"
        )
        return ProvisionResult(
            authorization=auth,
            pod_id="dry-run",
            pod_url=None,
            image_ref=image_ref,
            gpu_type=gpu_type,
            started_utc=started,
        )
    try:
        import runpod  # type: ignore[import-untyped]

        runpod.api_key = api_key
        env: dict[str, str] = {
            "GATE": gate,
            "MAX_MINUTES": str(max_minutes) if max_minutes else "30",
            "RUN_ID_PREFIX": gate,
        }
        if gate == "bootstrap":
            # Plan 02-05 Task 2: pod_entrypoint.sh reads BOOTSTRAP_MODE=1 and
            # short-circuits to `python -m tools.cache_bootstrap` instead of
            # running a gate runner.
            env["BOOTSTRAP_MODE"] = "1"
        # Plan 02-07 fix: forward operator-side secrets/config to the pod env
        # for ALL gates (previously only bootstrap got RUNPOD_API_KEY). The
        # pod uses RUNPOD_API_KEY for cost-watch + self-stop; SSH_PRIVATE_KEY
        # for rsync to OPERATOR_HOST; OPERATOR_USER for the rsync target user.
        # All secrets are per-pod env (NOT baked into the image) so the public
        # GHCR image carries no credentials.
        env["RUNPOD_API_KEY"] = api_key
        operator_user = os.environ.get("OPERATOR_USER")
        if operator_user:
            env["OPERATOR_USER"] = operator_user
        ssh_private_key = os.environ.get("SSH_PRIVATE_KEY")
        if ssh_private_key:
            # RunPod's create_pod mutation interpolates env values directly into
            # a GraphQL string. Multi-line PEM-format keys (with embedded
            # newlines) trip the GraphQL parser ("Unterminated string"). Base64
            # the key on the operator side; pod_entrypoint.sh:_setup_ssh
            # decodes back to PEM before writing ~/.ssh/id_ed25519.
            import base64

            env["SSH_PRIVATE_KEY_B64"] = base64.b64encode(ssh_private_key.encode("utf-8")).decode(
                "ascii"
            )
        if ssh_pubkey:
            env["SSH_PUBKEY"] = ssh_pubkey
        if operator_host:
            env["OPERATOR_HOST"] = operator_host
        kwargs: dict = {
            "name": f"rbox-{gate}-{int(datetime.datetime.utcnow().timestamp())}",
            "image_name": image_ref,
            "gpu_type_id": gpu_type,
            "gpu_count": 1,
            "volume_in_gb": 50,
            "container_disk_in_gb": 50,
            "env": env,
            "ports": "8000/http,22/tcp",
        }
        if network_volume_id:
            kwargs["network_volume_id"] = network_volume_id
            kwargs["volume_mount_path"] = "/models"
        pod = runpod.create_pod(**kwargs)
    except Exception as e:
        logger.error(f"[runpod] SDK provision failed AFTER authorization: {e}")
        raise RunPodProvisionError(str(e)) from e
    pod_id = str(pod.get("id", "unknown"))
    host_id = pod.get("podHostId")
    pod_url = f"https://{host_id}-8000.proxy.runpod.net" if host_id else None
    logger.info(
        f"[runpod] PROVISIONED pod={pod_id} gate={gate} image={image_ref} "
        f"auth_id={auth.id} url={pod_url}"
    )
    return ProvisionResult(
        authorization=auth,
        pod_id=pod_id,
        pod_url=pod_url,
        image_ref=image_ref,
        gpu_type=gpu_type,
        started_utc=started,
    )


def terminate(pod_id: str) -> None:
    """Terminate a pod by id. Used by watchdog SIGTERM handler.

    Dry-runs when RUNPOD_API_KEY is unset or pod_id == 'dry-run'. Swallows SDK
    failures (consistent with cost adapter pattern: terminate must not raise
    in the SIGTERM trap).
    """
    api_key = os.environ.get("RUNPOD_API_KEY")
    if not api_key or pod_id == "dry-run":
        logger.info(f"[runpod] DRY RUN terminate pod={pod_id}")
        return
    try:
        import runpod  # type: ignore[import-untyped]

        runpod.api_key = api_key
        runpod.terminate_pod(pod_id)
        logger.info(f"[runpod] TERMINATED pod={pod_id}")
    except Exception as e:
        logger.warning(f"[runpod] terminate {pod_id} failed: {e}")
