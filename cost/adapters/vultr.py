"""Vultr adapter (CLOUD-03 — RESEARCH §Pattern 4 verified endpoint)."""

from __future__ import annotations

import logging
import os
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import httpx

logger = logging.getLogger(__name__)

PENDING_CHARGES_URL = "https://api.vultr.com/v2/billing/pending-charges"


async def poll(client: httpx.AsyncClient) -> tuple[float, float]:
    api_key = os.environ.get("VULTR_API_KEY")
    if not api_key:
        logger.warning("[vultr] VULTR_API_KEY env var not set; skipping poll.")
        return (0.0, 0.0)
    headers = {"Authorization": f"Bearer {api_key}"}
    try:
        resp = await client.get(PENDING_CHARGES_URL, headers=headers, timeout=15.0)
    except Exception as e:
        logger.warning(f"[vultr] poll request failed: {e}")
        return (0.0, 0.0)
    if resp.status_code != 200:
        logger.warning(f"[vultr] poll status={resp.status_code}: {resp.text[:200]}")
        return (0.0, 0.0)
    try:
        data = resp.json()
    except Exception as e:
        logger.warning(f"[vultr] response JSON parse failed: {e}")
        return (0.0, 0.0)
    pending = data.get("pending_charges", [])
    cumulative = sum(float(c.get("amount", 0.0)) for c in pending)
    # Projected daily is unavailable from this endpoint; Phase 2 may add a
    # second call or use a heuristic. Phase 1 reports 0 for projected.
    logger.info(f"[vultr] cumulative=${cumulative:.2f} (projected_daily not available)")
    return (cumulative, 0.0)
