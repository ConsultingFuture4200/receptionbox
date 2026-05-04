"""Cost ledger dry-run tests (ROADMAP Phase 1 success criterion #2).

Each test uses tmp_path so no real cost/ledger.sqlite is touched.
"""

from __future__ import annotations

import pathlib
import sqlite3

import pytest

from cost import ledger


def test_initialize_provider_creates_row(tmp_path: pathlib.Path) -> None:
    db = tmp_path / "ledger.sqlite"
    ledger.initialize_provider("runpod", 75.0, db_path=db)
    conn = sqlite3.connect(db)
    try:
        row = conn.execute(
            "SELECT cap_usd, spent_usd FROM budget WHERE provider='runpod'"
        ).fetchone()
    finally:
        conn.close()
    assert row == (75.0, 0.0)


def test_initialize_provider_is_idempotent_preserves_spent(tmp_path: pathlib.Path) -> None:
    db = tmp_path / "ledger.sqlite"
    ledger.initialize_provider("runpod", 75.0, db_path=db)
    # Simulate prior spend
    conn = sqlite3.connect(db)
    conn.execute("UPDATE budget SET spent_usd=10.0 WHERE provider='runpod'")
    conn.commit()
    conn.close()
    # Re-initialize with new cap; spent should be preserved
    ledger.initialize_provider("runpod", 100.0, db_path=db)
    conn = sqlite3.connect(db)
    row = conn.execute("SELECT cap_usd, spent_usd FROM budget WHERE provider='runpod'").fetchone()
    conn.close()
    assert row == (100.0, 10.0)


def test_authorizes_below_threshold(tmp_path: pathlib.Path) -> None:
    db = tmp_path / "ledger.sqlite"
    ledger.initialize_provider("runpod", 75.0, db_path=db)
    auth = ledger.authorize_spend("runpod", "smoke", 10.0, db_path=db)
    assert auth.provider == "runpod"
    assert auth.gate == "smoke"
    assert auth.projected_cost == 10.0


def test_refuses_when_safety_breach(tmp_path: pathlib.Path) -> None:
    db = tmp_path / "ledger.sqlite"
    ledger.initialize_provider("runpod", 75.0, db_path=db)
    # 50.01 * 1.5 = 75.015 > 75 -> headroom < 0
    with pytest.raises(ledger.BudgetExhausted) as exc:
        ledger.authorize_spend("runpod", "g1", 50.01, db_path=db)
    assert "headroom=" in str(exc.value)


def test_refuses_unknown_provider(tmp_path: pathlib.Path) -> None:
    db = tmp_path / "ledger.sqlite"
    with pytest.raises(ledger.BudgetExhausted):
        ledger.authorize_spend("acme_cloud", "g1", 1.0, db_path=db)


def test_authorization_commits_before_return(tmp_path: pathlib.Path) -> None:
    """Reopen the DB in a separate connection; row must already exist."""
    db = tmp_path / "ledger.sqlite"
    ledger.initialize_provider("vultr", 75.0, db_path=db)
    auth = ledger.authorize_spend("vultr", "smoke", 5.0, db_path=db)
    # Fresh connection — must see the row already committed
    conn = sqlite3.connect(db)
    try:
        row = conn.execute(
            "SELECT provider, gate, projected_cost_usd, status FROM authorizations WHERE id=?",
            (auth.id,),
        ).fetchone()
    finally:
        conn.close()
    assert row == ("vultr", "smoke", 5.0, "authorized")


def test_custom_safety_factor(tmp_path: pathlib.Path) -> None:
    db = tmp_path / "ledger.sqlite"
    ledger.initialize_provider("runpod", 75.0, db_path=db)
    # 50 * 2.0 = 100 > 75 -> refuse with safety_factor=2.0
    with pytest.raises(ledger.BudgetExhausted):
        ledger.authorize_spend("runpod", "g1", 50.0, safety_factor=2.0, db_path=db)
    # But 30 * 2.0 = 60 < 75 -> succeed
    auth = ledger.authorize_spend("runpod", "g1", 30.0, safety_factor=2.0, db_path=db)
    assert auth.id > 0
