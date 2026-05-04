"""Vultr MI300X orchestration skeleton (CLOUD-02 backup).

Phase 1 ships the cost-ledger gate + a stub that logs the intended action.
Phase 3 replaces the stub with the real Vultr provisioning call.
"""

from __future__ import annotations

import logging

from cost.ledger import Authorization, authorize_spend

logger = logging.getLogger(__name__)


def provision(*, gate: str, projected_cost: float) -> Authorization:
    """Authorize spend, then provision a Vultr MI300X pod.

    Raises:
        cost.ledger.BudgetExhausted: if the request would breach the cap.
    """
    auth = authorize_spend(provider="vultr", gate=gate, projected_cost=projected_cost)
    logger.info(
        f"[vultr] AUTHORIZED gate={gate} projected=${projected_cost:.2f} "
        f"auth_id={auth.id}; Phase 1 stub — no pod created"
    )
    return auth
