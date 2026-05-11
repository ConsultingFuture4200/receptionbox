"""Vultr MI300X orchestration (CLOUD-02 + Phase 3 Plan 03-01 real provisioning).

Replaces the Phase 1 stub. Hard Constraint #1 preserved: cost.ledger.authorize_spend
is the FIRST call in provision()'s body — AST-asserted by
tests/test_orchestration_skeletons.py::test_orchestration_modules_call_authorize_spend_first.

Dry-run mode: when VULTR_API_KEY is unset, provision() still authorizes spend
(so the operator sees the ledger row) and returns a ProvisionResult with
pod_id="dry-run". This lets Plan 03-01 close A4 (Vultr API surface) without
burning $.

Sentinel guard: _DEFAULT_IMAGE_ROCM is a loud-fail sentinel string until the
operator runs scripts/build_pod_image_rocm.sh --push and pastes the resolved
@sha256 digest below. Mirrors the Phase 2 Plan 02-06 _DEFAULT_IMAGE pattern
that prevented the $1.05 zkqbit98s0uulf incident from recurring.

Open Q 3 (Vultr MI300X plan-id): `vcg-MI300X` is a placeholder. Operator
confirms the real plan-id from `GET /v2/plans?type=gpu` at Task 5. If
self-serve MI300X provisioning is not available, Day-1 falls back to
ledger-only dry-run mode (Plan 03-02 chatterbox kill-switch runs against
dry-run-only and the result is documented).
"""

from __future__ import annotations

import base64
import datetime
import logging
import os
from dataclasses import dataclass

import httpx

from cost.ledger import Authorization, authorize_spend

logger = logging.getLogger(__name__)

# D-32 + Pitfall 10: separate rbox-pod-rocm image with baked ENTRYPOINT.
# Sentinel string fails loudly before any network call until operator pastes
# the resolved digest from scripts/build_pod_image_rocm.sh --push output.
_DEFAULT_IMAGE_ROCM = "rbox/pod-rocm:UNSET-run-scripts-build_pod_image_rocm.sh-and-pin-digest"
# Open Q 3 (03-RESEARCH.md): Vultr plan-id placeholder; operator confirms at
# Task 5 via GET /v2/plans?type=gpu. If MI300X requires sales contact (i.e.,
# not self-serve), Plan 03-02 runs in dry-run-only mode until sales unblocks.
_DEFAULT_GPU = "vcg-MI300X"
_VULTR_API_BASE = "https://api.vultr.com/v2"


class VultrProvisionError(Exception):
    """Raised when Vultr API provisioning fails AFTER ledger authorization.

    Authorization is committed before this error is raised, so the caller knows
    the spend row exists in the ledger and may need to record/refund. Also
    raised pre-network when _DEFAULT_IMAGE_ROCM still carries the UNSET sentinel.
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
    ssh_pubkey: str | None = None,
    operator_host: str | None = None,
    image_ref: str = _DEFAULT_IMAGE_ROCM,
    gpu_type: str = _DEFAULT_GPU,
) -> ProvisionResult:
    """Authorize spend, then provision a Vultr MI300X instance (D-31).

    Hard Constraint #1: first executable statement MUST be authorize_spend.
    AST-asserted by tests/test_orchestration_skeletons.py.

    Raises:
        cost.ledger.BudgetExhausted: request would breach the cap.
        VultrProvisionError: image_ref still carries UNSET sentinel, or HTTP
            failure AFTER authorization (caller may need refund/record).
    """
    auth = authorize_spend(provider="vultr", gate=gate, projected_cost=projected_cost)

    # Loud-fail on unpinned image (Pitfall 10 mirror of runpod_h100 _DEFAULT_IMAGE).
    # MUST come after authorize_spend (Hard Constraint #1) but BEFORE any network call.
    if "UNSET" in image_ref:
        raise VultrProvisionError(
            f"_DEFAULT_IMAGE_ROCM is the UNSET sentinel ({image_ref!r}). "
            "Run scripts/build_pod_image_rocm.sh --push and pin the resolved "
            "@sha256 digest in orchestration/vultr_mi300x.py + bench/images.lock.yaml "
            "before any real provisioning. See dockerfiles/rocm/README.md."
        )

    api_key = os.environ.get("VULTR_API_KEY")
    started = datetime.datetime.utcnow().isoformat()
    if not api_key:
        logger.warning(
            f"[vultr] DRY RUN — VULTR_API_KEY not set. WOULD create instance "
            f"gate={gate} image={image_ref} gpu={gpu_type} max_minutes={max_minutes}"
        )
        return ProvisionResult(
            authorization=auth,
            pod_id="dry-run",
            pod_url=None,
            image_ref=image_ref,
            gpu_type=gpu_type,
            started_utc=started,
        )

    env: dict[str, str] = {
        "GATE": gate,
        "MAX_MINUTES": str(max_minutes) if max_minutes else "30",
        "RUN_ID_PREFIX": gate,
        # DEV-1021: forward image_ref so substrate.rocm._lookup_image_digest stamps
        # the real digest on every result row. Without this, the lockfile fallback
        # returns "pending" until the operator pins it.
        "RBOX_IMAGE_DIGEST": image_ref,
        # Forward VULTR_API_KEY so on-pod cost-watch + self-stop can poll billing.
        "VULTR_API_KEY": api_key,
    }
    operator_user = os.environ.get("OPERATOR_USER")
    if operator_user:
        env["OPERATOR_USER"] = operator_user
    ssh_private_key = os.environ.get("SSH_PRIVATE_KEY")
    if ssh_private_key:
        # Match runpod_h100 pattern: base64 the key to avoid newline-in-string
        # issues with cloud-init user_data. pod_entrypoint.sh decodes back to PEM.
        env["SSH_PRIVATE_KEY_B64"] = base64.b64encode(ssh_private_key.encode("utf-8")).decode(
            "ascii"
        )
    if ssh_pubkey:
        env["SSH_PUBKEY"] = ssh_pubkey
    if operator_host:
        env["OPERATOR_HOST"] = operator_host

    region = os.environ.get("VULTR_REGION", "ord")
    body: dict = {
        "region": region,
        "plan": gpu_type,
        "image_id": image_ref,
        "label": f"rbox-{gate}-{int(datetime.datetime.utcnow().timestamp())}",
        "tag": "rbox-phase3",
        "user_data": _build_cloud_init(env),
    }
    if ssh_pubkey:
        # Vultr's /v2/instances accepts sshkey_id (account-level key by id) but
        # not a raw pubkey. The raw pubkey is forwarded through cloud-init env
        # for the pod to install into /root/.ssh/authorized_keys (matches Phase
        # 2 pod_entrypoint.sh _setup_ssh).
        pass

    try:
        r = httpx.post(
            f"{_VULTR_API_BASE}/instances",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json=body,
            timeout=30.0,
        )
        r.raise_for_status()
        instance = r.json().get("instance", {})
    except Exception as e:
        logger.error(f"[vultr] API provision failed AFTER authorization: {type(e).__name__}")
        raise VultrProvisionError(str(e)) from e

    pod_id = str(instance.get("id", "unknown"))
    main_ip = instance.get("main_ip")
    pod_url = f"http://{main_ip}:8000" if main_ip else None
    logger.info(
        f"[vultr] PROVISIONED instance={pod_id} gate={gate} image={image_ref} "
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


def _build_cloud_init(env: dict[str, str]) -> str:
    """Encode env dict as cloud-init user_data that exports values to /etc/environment.

    The pod_entrypoint.sh reads these via the standard /etc/environment path,
    matching the env-var contract on the CUDA rail (RunPod injects env directly;
    Vultr requires cloud-init).
    """
    lines = [
        "#cloud-config",
        "write_files:",
        "  - path: /etc/environment",
        "    append: true",
        "    content: |",
    ]
    for k, v in env.items():
        lines.append(f"      {k}={v}")
    return "\n".join(lines)


def terminate(pod_id: str) -> None:
    """Terminate a Vultr instance. Used by watchdog SIGTERM handler.

    Dry-runs when VULTR_API_KEY is unset or pod_id == 'dry-run'. Swallows HTTP
    failures (consistent with cost adapter pattern: terminate must not raise
    in the SIGTERM trap).
    """
    api_key = os.environ.get("VULTR_API_KEY")
    if not api_key or pod_id == "dry-run":
        logger.info(f"[vultr] DRY RUN terminate instance={pod_id}")
        return
    try:
        httpx.delete(
            f"{_VULTR_API_BASE}/instances/{pod_id}",
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=15.0,
        ).raise_for_status()
        logger.info(f"[vultr] TERMINATED instance={pod_id}")
    except Exception as e:
        logger.warning(f"[vultr] terminate {pod_id} failed: {type(e).__name__}")
