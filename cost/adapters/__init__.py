"""Per-provider billing adapters for cost-watch (CLOUD-03).

Each adapter exports `async def poll(client: httpx.AsyncClient) -> tuple[float, float]`
returning (cumulative_spend_usd, projected_daily_spend_usd). Adapters MUST
NOT raise — they log WARNING on failure and return (0.0, 0.0) so the
5-minute poll loop continues regardless.

Provider asymmetry per RESEARCH.md Pitfalls B/C:
- Vultr: documented /v2/billing/pending-charges endpoint
- RunPod: no programmatic cap; SDK get_pods() + costPerHr; "fund only $75" is the cap
- TensorWave: undocumented billing API; stub with WARNING per poll
"""

from . import runpod as runpod
from . import tensorwave as tensorwave
from . import vultr as vultr

__all__ = ["runpod", "tensorwave", "vultr"]
