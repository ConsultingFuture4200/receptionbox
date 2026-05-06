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

_DEFAULT_IMAGE = "vllm/vllm-openai:v0.10.0"
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
