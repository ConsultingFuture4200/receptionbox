"""SQLite-backed cost ledger (INFRA-06).

Single chokepoint for cloud provisioning. Every `runpodctl pod create`,
TensorWave provisioning call, or Vultr provisioning call (Phase 2/3 + Plan 05)
goes through `authorize_spend(provider, gate, projected_cost)` first.

Refusal rule (locked from REQUIREMENTS.md INFRA-06 + ROADMAP success #2):
    budget_remaining - projected_cost * safety_factor < 0  -> BudgetExhausted

Default safety_factor = 1.5 (D-12 in CONTEXT.md "Cost ledger projection
mechanism"; refined to dynamic in Phase 4).

Authorization commits to SQLite BEFORE returning, so a Python crash mid-flow
leaves the spend visible to the next process (Pitfall: race-then-crash).
"""

from __future__ import annotations

import datetime
import pathlib
import sqlite3
from dataclasses import dataclass

DEFAULT_DB = pathlib.Path("cost/ledger.sqlite")
DEFAULT_SAFETY_FACTOR = 1.5

CREATE_SQL = """
CREATE TABLE IF NOT EXISTS budget (
    provider TEXT PRIMARY KEY,
    cap_usd REAL NOT NULL,
    spent_usd REAL NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS authorizations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    provider TEXT NOT NULL,
    gate TEXT NOT NULL,
    projected_cost_usd REAL NOT NULL,
    safety_factor REAL NOT NULL,
    authorized_at TEXT NOT NULL,
    actual_cost_usd REAL,
    status TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_auth_provider ON authorizations(provider);
"""


class BudgetExhausted(Exception):
    """Raised when authorize_spend would breach the cap-with-safety-factor rule."""


@dataclass(frozen=True)
class Authorization:
    id: int
    provider: str
    gate: str
    projected_cost: float


def _ensure_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(CREATE_SQL)


def initialize_provider(
    provider: str,
    cap_usd: float,
    db_path: pathlib.Path = DEFAULT_DB,
) -> None:
    """Initialize a provider's row in the budget table. Idempotent."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    try:
        _ensure_schema(conn)
        conn.execute(
            "INSERT OR REPLACE INTO budget(provider, cap_usd, spent_usd) "
            "SELECT ?, ?, COALESCE("
            "  (SELECT spent_usd FROM budget WHERE provider=?), 0)",
            (provider, cap_usd, provider),
        )
        conn.commit()
    finally:
        conn.close()


def authorize_spend(
    provider: str,
    gate: str,
    projected_cost: float,
    safety_factor: float = DEFAULT_SAFETY_FACTOR,
    db_path: pathlib.Path = DEFAULT_DB,
) -> Authorization:
    """Authorize a cloud provisioning request.

    Refuses if `cap_usd - spent_usd - projected_cost * safety_factor < 0`.
    On success, inserts a row in `authorizations` and returns its id.
    """
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    try:
        _ensure_schema(conn)
        row = conn.execute(
            "SELECT cap_usd, spent_usd FROM budget WHERE provider=?",
            (provider,),
        ).fetchone()
        if row is None:
            raise BudgetExhausted(
                f"Provider {provider!r} not initialized in ledger; "
                f"call initialize_provider() first."
            )
        cap, spent = row
        remaining = cap - spent
        headroom = remaining - projected_cost * safety_factor
        if headroom < 0:
            raise BudgetExhausted(
                f"{provider}: remaining=${remaining:.2f}, "
                f"projected=${projected_cost:.2f}*{safety_factor}="
                f"${projected_cost * safety_factor:.2f}, "
                f"headroom=${headroom:.2f}"
            )
        cur = conn.execute(
            "INSERT INTO authorizations(provider, gate, projected_cost_usd, "
            "safety_factor, authorized_at, status) VALUES (?, ?, ?, ?, ?, 'authorized')",
            (
                provider,
                gate,
                projected_cost,
                safety_factor,
                datetime.datetime.utcnow().isoformat(),
            ),
        )
        auth_id = cur.lastrowid
        conn.commit()  # commit BEFORE returning — Pitfall race-then-crash mitigation
        assert auth_id is not None
        return Authorization(auth_id, provider, gate, projected_cost)
    finally:
        conn.close()
