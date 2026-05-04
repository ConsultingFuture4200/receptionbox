"""RunPod H100 orchestration skeleton (CLOUD-01).

Phase 1 ships the cost-ledger gate + a stub that logs the intended action.
Phase 2 replaces the stub with the real `runpodctl pod create` (or
runpod SDK equivalent) call.
"""

from __future__ import annotations

import logging

from cost.ledger import Authorization, authorize_spend

logger = logging.getLogger(__name__)


def provision(*, gate: str, projected_cost: float) -> Authorization:
    """Authorize spend, then provision an H100 pod.

    Phase 1: returns the Authorization without spinning up a real pod.
    Phase 2: calls `runpod.create_pod(...)` after authorization succeeds.

    Raises:
        cost.ledger.BudgetExhausted: if the request would breach the cap.
    """
    auth = authorize_spend(provider="runpod", gate=gate, projected_cost=projected_cost)
    logger.info(
        f"[runpod] AUTHORIZED gate={gate} projected=${projected_cost:.2f} "
        f"auth_id={auth.id}; Phase 1 stub — no pod created"
    )
    return auth
