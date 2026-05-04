"""TensorWave adapter (CLOUD-03 — Pitfall C closure).

TensorWave's public billing API is undocumented as of May 2026. This
adapter logs a WARNING per poll and returns (0.0, 0.0). Operator
manual dashboard check is the second rail. Phase 4 reproducibility
manifest documents this gap explicitly.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import httpx

logger = logging.getLogger(__name__)


async def poll(client: httpx.AsyncClient) -> tuple[float, float]:
    logger.warning(
        "[tensorwave] adapter cannot poll spend programmatically (Pitfall C); "
        "check dashboard. Cap enforcement = $75 prepaid + manual."
    )
    return (0.0, 0.0)
