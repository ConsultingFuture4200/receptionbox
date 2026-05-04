"""RunPod adapter (CLOUD-03 — Pitfall B closure).

RunPod has no programmatic cumulative-spending-cap API as of May 2026.
The "$75 provider cap" is achieved by the operator funding only $75 in
credits AND keeping auto-recharge OFF. This adapter polls active pods
via the runpod SDK and reports cumulative cost per hour x elapsed.

Hard-stop logic (Phase 2 wiring) calls runpod.terminate_pod(pod_id) when
projected cumulative > balance. Phase 1 ships visibility only.
"""

from __future__ import annotations

import logging
import os
import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import httpx

logger = logging.getLogger(__name__)


async def poll(client: httpx.AsyncClient) -> tuple[float, float]:
    """Returns (cumulative_spend_usd, projected_daily_spend_usd).

    Cumulative is computed across all live pods as costPerHr * elapsed
    since pod start. Projected daily extrapolates current rate * 24.
    Network/auth failures log WARNING and return (0.0, 0.0).
    """
    api_key = os.environ.get("RUNPOD_API_KEY")
    if not api_key:
        logger.warning(
            "[runpod] RUNPOD_API_KEY env var not set; skipping poll. "
            "Operator note: Pitfall B — cap is $75 credit deposit, "
            "NOT a programmatic API cap. Auto-recharge MUST be OFF."
        )
        return (0.0, 0.0)
    try:
        import runpod  # type: ignore[import-untyped]

        runpod.api_key = api_key
        pods = runpod.get_pods()
    except Exception as e:
        logger.warning(f"[runpod] poll failed: {e}")
        return (0.0, 0.0)
    cumulative = 0.0
    rate_per_hr = 0.0
    now = time.time()
    for pod in pods or []:
        cost_per_hr = float(pod.get("costPerHr", 0.0))
        # Pod 'createdAt' is an ISO-8601 string; treat as start time.
        created = pod.get("createdAt")
        elapsed_hr = 0.0
        if created:
            try:
                from datetime import datetime

                dt = datetime.fromisoformat(created.replace("Z", "+00:00"))
                elapsed_hr = (now - dt.timestamp()) / 3600.0
            except Exception:
                elapsed_hr = 0.0
        cumulative += cost_per_hr * max(elapsed_hr, 0.0)
        rate_per_hr += cost_per_hr
    projected_daily = rate_per_hr * 24.0
    logger.info(f"[runpod] cumulative=${cumulative:.2f} projected_daily=${projected_daily:.2f}")
    return (cumulative, projected_daily)
