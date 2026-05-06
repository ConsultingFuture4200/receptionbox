"""Tests for orchestration/runpod_h100.py (Phase 2 real provisioning).

Replaces the Phase 1 stub. Hard Constraint #1: authorize_spend MUST be the
FIRST AST Call in provision() (test_orchestration_skeletons.py enforces it
at the AST level — the test below is behavior-level proof that the runtime
ordering matches the AST ordering).

Mock-only: no real RunPod spend in this test module.
"""

from __future__ import annotations

import sys
import types
from typing import Any

import pytest

from cost import ledger
from cost.ledger import BudgetExhausted


@pytest.fixture
def init_runpod_ledger(monkeypatch, tmp_path):
    """Initialize a $75 cap ledger pointed at tmp DB.

    Mirrors the fixture in tests/test_orchestration_skeletons.py so the new
    real-provisioning code lands on the same ledger contract.
    """
    db = tmp_path / "ledger.sqlite"
    monkeypatch.setattr(ledger, "DEFAULT_DB", db)
    orig_defaults = ledger.authorize_spend.__defaults__
    new_defaults = (*orig_defaults[:-1], db)
    monkeypatch.setattr(ledger.authorize_spend, "__defaults__", new_defaults)
    ledger.initialize_provider("runpod", 75.0, db_path=db)
    return db


def _install_fake_runpod(monkeypatch, *, create_pod_returns=None, create_pod_raises=None):
    """Install a fake `runpod` SDK module so import-inside-function lands on it."""
    fake = types.ModuleType("runpod")
    fake.api_key = None
    calls: dict[str, list] = {"create_pod": [], "terminate_pod": []}

    def _create(**kwargs: Any) -> dict:
        calls["create_pod"].append(kwargs)
        if create_pod_raises is not None:
            raise create_pod_raises
        if create_pod_returns is not None:
            return create_pod_returns
        return {"id": "pod_default", "podHostId": "host_default"}

    def _terminate(pod_id: str) -> None:
        calls["terminate_pod"].append(pod_id)

    fake.create_pod = _create
    fake.terminate_pod = _terminate
    monkeypatch.setitem(sys.modules, "runpod", fake)
    return calls


def test_provision_dry_run_when_no_api_key(init_runpod_ledger, monkeypatch):
    monkeypatch.delenv("RUNPOD_API_KEY", raising=False)
    from orchestration import runpod_h100

    result = runpod_h100.provision(gate="smoke", projected_cost=1.0)
    assert isinstance(result, runpod_h100.ProvisionResult)
    assert result.pod_id == "dry-run"
    # Ledger row was committed despite dry run (auth.id from sqlite)
    assert result.authorization.provider == "runpod"
    assert result.authorization.gate == "smoke"


def test_provision_calls_authorize_spend_first(init_runpod_ledger, monkeypatch):
    """If authorize_spend raises, runpod.create_pod must NEVER be called."""
    calls = _install_fake_runpod(monkeypatch)
    monkeypatch.setenv("RUNPOD_API_KEY", "fake-key")
    from orchestration import runpod_h100

    # Project too large -> BudgetExhausted (75 / 1.5 = 50; 60*1.5=90 > 75)
    with pytest.raises(BudgetExhausted):
        runpod_h100.provision(gate="g1", projected_cost=60.0)
    assert calls["create_pod"] == [], "create_pod called despite budget refusal"


def test_provision_with_api_key_calls_create_pod(init_runpod_ledger, monkeypatch):
    calls = _install_fake_runpod(
        monkeypatch,
        create_pod_returns={"id": "pod_xyz", "podHostId": "abc"},
    )
    monkeypatch.setenv("RUNPOD_API_KEY", "fake-key")
    from orchestration import runpod_h100

    res = runpod_h100.provision(gate="g1", projected_cost=2.0)
    assert res.pod_id == "pod_xyz"
    assert res.pod_url is not None and "abc" in res.pod_url
    assert len(calls["create_pod"]) == 1


def test_provision_passes_volume_mount_when_volume_id_given(init_runpod_ledger, monkeypatch):
    calls = _install_fake_runpod(monkeypatch)
    monkeypatch.setenv("RUNPOD_API_KEY", "fake-key")
    from orchestration import runpod_h100

    runpod_h100.provision(
        gate="smoke",
        projected_cost=1.0,
        network_volume_id="vol_abc",
    )
    kw = calls["create_pod"][0]
    assert kw.get("network_volume_id") == "vol_abc"
    assert kw.get("volume_mount_path") == "/models"


def test_provision_injects_env_vars(init_runpod_ledger, monkeypatch):
    calls = _install_fake_runpod(monkeypatch)
    monkeypatch.setenv("RUNPOD_API_KEY", "fake-key")
    from orchestration import runpod_h100

    runpod_h100.provision(
        gate="g1",
        projected_cost=2.0,
        max_minutes=30,
        ssh_pubkey="ssh-ed25519 AAAA fake",
        operator_host="ops.example.com",
    )
    kw = calls["create_pod"][0]
    env = kw["env"]
    assert env["GATE"] == "g1"
    assert env["MAX_MINUTES"] == "30"
    assert env["SSH_PUBKEY"] == "ssh-ed25519 AAAA fake"
    assert env["OPERATOR_HOST"] == "ops.example.com"


def test_provision_raises_RunPodProvisionError_when_sdk_fails(init_runpod_ledger, monkeypatch):
    """SDK failure AFTER authorization wraps into RunPodProvisionError so callers
    know the spend was committed and may need to record/refund."""
    _install_fake_runpod(monkeypatch, create_pod_raises=RuntimeError("rate limited"))
    monkeypatch.setenv("RUNPOD_API_KEY", "fake-key")
    from orchestration import runpod_h100

    with pytest.raises(runpod_h100.RunPodProvisionError):
        runpod_h100.provision(gate="g1", projected_cost=2.0)
    # Verify: an authorization row was committed before the SDK failure
    import sqlite3

    db = init_runpod_ledger
    rows = (
        sqlite3.connect(db)
        .execute("SELECT count(*) FROM authorizations WHERE gate='g1'")
        .fetchone()
    )
    assert rows[0] >= 1


def test_terminate_dry_run_when_no_api_key(monkeypatch):
    monkeypatch.delenv("RUNPOD_API_KEY", raising=False)
    from orchestration import runpod_h100

    # Should NOT raise
    runpod_h100.terminate("any-pod-id")


def test_terminate_swallows_sdk_failure(monkeypatch):
    monkeypatch.setenv("RUNPOD_API_KEY", "fake-key")

    fake = types.ModuleType("runpod")
    fake.api_key = None

    def _boom(pod_id):
        raise RuntimeError("SDK exploded")

    fake.terminate_pod = _boom
    monkeypatch.setitem(sys.modules, "runpod", fake)

    from orchestration import runpod_h100

    # Must not propagate
    runpod_h100.terminate("pod_xyz")
