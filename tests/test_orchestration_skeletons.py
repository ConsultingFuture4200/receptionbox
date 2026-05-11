"""Orchestration skeletons must gate provisioning through cost.ledger."""

from __future__ import annotations

import ast
import pathlib

import pytest

from cost import ledger
from cost.ledger import BudgetExhausted

ROOT = pathlib.Path(__file__).resolve().parents[1]


@pytest.fixture
def init_runpod_ledger(monkeypatch, tmp_path):
    """Initialize a ledger row with $75 cap pointed at a tmp DB.

    Patches the bound default of `authorize_spend.db_path` so orchestration
    modules (which call `authorize_spend(...)` without `db_path=`) land on
    the tmp DB. Python binds defaults at definition time — we have to
    rewrite `__defaults__` to redirect them.
    """
    db = tmp_path / "ledger.sqlite"
    monkeypatch.setattr(ledger, "DEFAULT_DB", db)
    # Rebind authorize_spend defaults: signature is
    # (provider, gate, projected_cost, safety_factor=1.5, db_path=DEFAULT_DB)
    # so the last default is db_path.
    orig_defaults = ledger.authorize_spend.__defaults__
    new_defaults = (*orig_defaults[:-1], db)
    monkeypatch.setattr(ledger.authorize_spend, "__defaults__", new_defaults)
    ledger.initialize_provider("runpod", 75.0, db_path=db)
    ledger.initialize_provider("tensorwave", 75.0, db_path=db)
    ledger.initialize_provider("vultr", 75.0, db_path=db)
    return db


def test_runpod_provision_authorizes_within_budget(init_runpod_ledger) -> None:
    from orchestration import runpod_h100

    # Phase 2 changed the return type to ProvisionResult; the cost-ledger
    # Authorization is now reachable via .authorization. The AST ordering
    # contract (authorize_spend FIRST in provision()) is preserved — see
    # test_orchestration_modules_call_authorize_spend_first below.
    result = runpod_h100.provision(gate="smoke", projected_cost=10.0)
    auth = result.authorization
    assert auth.provider == "runpod"
    assert auth.gate == "smoke"


def test_runpod_provision_refused_over_budget(init_runpod_ledger) -> None:
    from orchestration import runpod_h100

    with pytest.raises(BudgetExhausted):
        runpod_h100.provision(gate="g1", projected_cost=60.0)  # 60 * 1.5 = 90 > 75


def test_tensorwave_provision_authorizes(init_runpod_ledger) -> None:
    from orchestration import tensorwave_mi300x

    auth = tensorwave_mi300x.provision(gate="g1", projected_cost=10.0)
    assert auth.provider == "tensorwave"


def test_vultr_provision_authorizes(init_runpod_ledger, monkeypatch) -> None:
    """Plan 03-01 Task 3: vultr_mi300x.provision() now returns ProvisionResult
    (same shape as runpod_h100). Authorization is reachable via .authorization.

    Override _DEFAULT_IMAGE_ROCM with a real-looking digest so the sentinel
    guard doesn't fire; ensure VULTR_API_KEY is unset to take the dry-run path.
    """
    from orchestration import vultr_mi300x

    monkeypatch.delenv("VULTR_API_KEY", raising=False)
    digest = "ghcr.io/consultingfuture4200/rbox-pod-rocm@sha256:" + ("a" * 64)
    monkeypatch.setattr(vultr_mi300x, "_DEFAULT_IMAGE_ROCM", digest, raising=True)
    # Function defaults are bound at definition time; rebind provision()'s
    # default image_ref kwarg so the UNSET sentinel guard doesn't fire.
    kwdefs = dict(vultr_mi300x.provision.__kwdefaults__ or {})
    kwdefs["image_ref"] = digest
    monkeypatch.setattr(vultr_mi300x.provision, "__kwdefaults__", kwdefs)

    result = vultr_mi300x.provision(gate="g1", projected_cost=10.0)
    assert result.authorization.provider == "vultr"
    assert result.authorization.gate == "g1"
    assert result.pod_id == "dry-run"


def test_orchestration_modules_call_authorize_spend_first() -> None:
    """AST check: every provision() body's first AST stmt that names
    `authorize_spend` must come before any other side-effect-looking call."""
    for mod_name in ("runpod_h100", "tensorwave_mi300x", "vultr_mi300x"):
        path = ROOT / "orchestration" / f"{mod_name}.py"
        tree = ast.parse(path.read_text())
        provision_fn = next(
            (n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "provision"),
            None,
        )
        assert provision_fn is not None, f"{mod_name}: provision() not found"
        # First call in body must be authorize_spend(...)
        first_call: ast.Call | None = None
        for stmt in ast.walk(provision_fn):
            if isinstance(stmt, ast.Call):
                first_call = stmt
                break
        assert first_call is not None
        # The function called must be `authorize_spend` (Name) or attribute ending in it
        target_name = ""
        if isinstance(first_call.func, ast.Name):
            target_name = first_call.func.id
        elif isinstance(first_call.func, ast.Attribute):
            target_name = first_call.func.attr
        assert target_name == "authorize_spend", (
            f"{mod_name}: first call is {target_name!r}, expected authorize_spend"
        )
