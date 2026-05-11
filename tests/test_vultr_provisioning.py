"""Tests for orchestration/vultr_mi300x.py (Phase 3 Plan 03-01 Task 3).

Mirrors tests/test_runpod_provisioning.py. Hard Constraint #1: authorize_spend
MUST be the FIRST AST Call in provision() (enforced at AST level by
tests/test_orchestration_skeletons.py and behavior-tested below).

Sentinel guard mirrors Phase 2 Plan 02-06 _DEFAULT_IMAGE pattern: when
_DEFAULT_IMAGE_ROCM still contains "UNSET", provision() raises
VultrProvisionError BEFORE any network call (operator must run
scripts/build_pod_image_rocm.sh --push and paste the @sha256 digest first).

Mock-only: no real Vultr spend in this test module.
"""

from __future__ import annotations

import importlib
from typing import Any

import httpx
import pytest

from cost import ledger
from cost.ledger import BudgetExhausted


@pytest.fixture
def init_vultr_ledger(monkeypatch, tmp_path):
    """Initialize a $75 cap ledger pointed at tmp DB. Mirrors the runpod
    fixture so the new real-provisioning code lands on the same contract."""
    db = tmp_path / "ledger.sqlite"
    monkeypatch.setattr(ledger, "DEFAULT_DB", db)
    orig_defaults = ledger.authorize_spend.__defaults__
    new_defaults = (*orig_defaults[:-1], db)
    monkeypatch.setattr(ledger.authorize_spend, "__defaults__", new_defaults)
    ledger.initialize_provider("vultr", 75.0, db_path=db)
    return db


@pytest.fixture
def pinned_image_ref(monkeypatch):
    """Override _DEFAULT_IMAGE_ROCM and rebind provision()'s default kwarg so
    tests calling provision() without an explicit image_ref skip the UNSET
    sentinel guard (sentinel exercised separately in
    test_provision_raises_when_image_ref_is_sentinel).

    Real digest format: ghcr.io/.../rbox-pod-rocm@sha256:<64hex>.

    Function defaults are bound at definition time — patching the module-level
    constant alone is insufficient. Rewrite provision.__defaults__ to redirect
    the default image_ref value (signature ends with image_ref=..., gpu_type=...).
    """
    digest = "ghcr.io/consultingfuture4200/rbox-pod-rocm@sha256:" + ("a" * 64)
    from orchestration import vultr_mi300x

    monkeypatch.setattr(vultr_mi300x, "_DEFAULT_IMAGE_ROCM", digest, raising=True)
    # provision() signature: (*, gate, projected_cost, max_minutes=None,
    # ssh_pubkey=None, operator_host=None, image_ref=_DEFAULT_IMAGE_ROCM,
    # gpu_type=_DEFAULT_GPU). Python's __defaults__ holds positional defaults;
    # keyword-only defaults live in __kwdefaults__.
    kwdefs = dict(vultr_mi300x.provision.__kwdefaults__ or {})
    kwdefs["image_ref"] = digest
    monkeypatch.setattr(vultr_mi300x.provision, "__kwdefaults__", kwdefs)
    return digest


def _install_fake_httpx(
    monkeypatch,
    *,
    post_response=None,
    post_raises=None,
    delete_response=None,
    delete_raises=None,
    calls=None,
):
    """Replace httpx.post and httpx.delete with thunks recording all calls."""
    if calls is None:
        calls = {"post": [], "delete": []}

    def fake_post(url, **kwargs):
        calls["post"].append({"url": url, "kwargs": kwargs})
        if post_raises is not None:
            raise post_raises
        if post_response is not None:
            return post_response
        # Default: 200 with a Vultr-shaped instance body.
        return _FakeResp(
            200,
            {"instance": {"id": "vinst_123", "main_ip": "203.0.113.10"}},
        )

    def fake_delete(url, **kwargs):
        calls["delete"].append({"url": url, "kwargs": kwargs})
        if delete_raises is not None:
            raise delete_raises
        if delete_response is not None:
            return delete_response
        return _FakeResp(204, None)

    monkeypatch.setattr(httpx, "post", fake_post)
    monkeypatch.setattr(httpx, "delete", fake_delete)
    return calls


class _FakeResp:
    def __init__(self, status_code: int, body: Any) -> None:
        self.status_code = status_code
        self._body = body

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError(
                f"HTTP {self.status_code}",
                request=httpx.Request("POST", "http://fake/"),
                response=self,  # type: ignore[arg-type]
            )

    def json(self):
        return self._body


# ---------------------------------------------------------------------------
# Test 1: dry-run when VULTR_API_KEY unset
# ---------------------------------------------------------------------------


def test_provision_dry_run_when_no_api_key(init_vultr_ledger, monkeypatch, pinned_image_ref):
    monkeypatch.delenv("VULTR_API_KEY", raising=False)
    from orchestration import vultr_mi300x

    result = vultr_mi300x.provision(gate="chatterbox_d1", projected_cost=4.0, max_minutes=120)
    assert isinstance(result, vultr_mi300x.ProvisionResult)
    assert result.pod_id == "dry-run"
    assert result.pod_url is None
    assert result.image_ref == pinned_image_ref
    # Ledger row was committed despite dry run (real authorization)
    assert result.authorization.provider == "vultr"
    assert result.authorization.gate == "chatterbox_d1"


# ---------------------------------------------------------------------------
# Test 2: BudgetExhausted prevents any httpx call
# ---------------------------------------------------------------------------


def test_provision_calls_authorize_spend_first(init_vultr_ledger, monkeypatch, pinned_image_ref):
    calls = _install_fake_httpx(monkeypatch)
    monkeypatch.setenv("VULTR_API_KEY", "fake-key")
    from orchestration import vultr_mi300x

    # 60 * 1.5 = 90 > 75 cap → BudgetExhausted
    with pytest.raises(BudgetExhausted):
        vultr_mi300x.provision(gate="g1", projected_cost=60.0)
    assert calls["post"] == [], "httpx.post called despite budget refusal"


# ---------------------------------------------------------------------------
# Test 3: real path POSTs to /v2/instances; response parsed; env injected
# ---------------------------------------------------------------------------


def test_provision_with_api_key_posts_instance(init_vultr_ledger, monkeypatch, pinned_image_ref):
    calls = _install_fake_httpx(monkeypatch)
    monkeypatch.setenv("VULTR_API_KEY", "fake-key")
    from orchestration import vultr_mi300x

    res = vultr_mi300x.provision(gate="g1", projected_cost=2.0, max_minutes=30)
    assert res.pod_id == "vinst_123"
    assert res.pod_url == "http://203.0.113.10:8000"
    assert len(calls["post"]) == 1
    call = calls["post"][0]
    # Confirms correct API endpoint
    assert "/v2/instances" in call["url"]
    # Auth header present
    headers = call["kwargs"]["headers"]
    assert headers["Authorization"] == "Bearer fake-key"
    # image_ref + RBOX_IMAGE_DIGEST round-trip — DEV-1021
    body = call["kwargs"]["json"]
    assert body["image_id"] == pinned_image_ref
    user_data = body["user_data"]
    assert f"RBOX_IMAGE_DIGEST={pinned_image_ref}" in user_data


# ---------------------------------------------------------------------------
# Test 4: sentinel guard — _DEFAULT_IMAGE_ROCM with UNSET raises BEFORE any
# network call (and AFTER authorize_spend per Hard Constraint #1).
# ---------------------------------------------------------------------------


def test_provision_raises_when_image_ref_is_sentinel(init_vultr_ledger, monkeypatch):
    calls = _install_fake_httpx(monkeypatch)
    monkeypatch.setenv("VULTR_API_KEY", "fake-key")
    # NOTE: NOT applying pinned_image_ref fixture — use the real UNSET sentinel.
    from orchestration import vultr_mi300x

    # Sanity: the module-level default carries the sentinel string.
    assert "UNSET" in vultr_mi300x._DEFAULT_IMAGE_ROCM

    with pytest.raises(vultr_mi300x.VultrProvisionError) as excinfo:
        vultr_mi300x.provision(gate="chatterbox_d1", projected_cost=4.0)
    assert "UNSET" in str(excinfo.value)
    assert calls["post"] == [], "httpx.post called despite UNSET sentinel"


# ---------------------------------------------------------------------------
# Test 5: BudgetExhausted does NOT call httpx.post (already covered by Test 2;
# this test verifies the AST ordering survives — module reload + re-import).
# ---------------------------------------------------------------------------


def test_provision_authorize_spend_before_httpx(init_vultr_ledger, monkeypatch, pinned_image_ref):
    """Reload the module after monkeypatching to confirm authorize_spend's
    side effect (BudgetExhausted) prevents httpx.post even on a fresh import."""
    calls = _install_fake_httpx(monkeypatch)
    monkeypatch.setenv("VULTR_API_KEY", "fake-key")
    from orchestration import vultr_mi300x

    importlib.reload(vultr_mi300x)
    # Re-apply the pinned image after reload (module-level default was reset).
    digest = pinned_image_ref
    monkeypatch.setattr(vultr_mi300x, "_DEFAULT_IMAGE_ROCM", digest, raising=True)

    with pytest.raises(BudgetExhausted):
        vultr_mi300x.provision(gate="g1", projected_cost=60.0)
    assert calls["post"] == []


# ---------------------------------------------------------------------------
# Test 6: HTTP 4xx/5xx after authorization wraps into VultrProvisionError
# ---------------------------------------------------------------------------


def test_provision_raises_VultrProvisionError_on_http_failure(
    init_vultr_ledger, monkeypatch, pinned_image_ref
):
    _install_fake_httpx(
        monkeypatch,
        post_response=_FakeResp(500, {"error": "server fail"}),
    )
    monkeypatch.setenv("VULTR_API_KEY", "fake-key")
    from orchestration import vultr_mi300x

    with pytest.raises(vultr_mi300x.VultrProvisionError):
        vultr_mi300x.provision(gate="g1", projected_cost=2.0)
    # Verify the authorization row was committed BEFORE the http failure
    import sqlite3

    db = init_vultr_ledger
    rows = (
        sqlite3.connect(db)
        .execute("SELECT count(*) FROM authorizations WHERE gate='g1' AND provider='vultr'")
        .fetchone()
    )
    assert rows[0] >= 1


# ---------------------------------------------------------------------------
# Test 7: terminate() swallows all exceptions
# ---------------------------------------------------------------------------


def test_terminate_dry_run_when_no_api_key(monkeypatch):
    monkeypatch.delenv("VULTR_API_KEY", raising=False)
    from orchestration import vultr_mi300x

    # Must not raise
    vultr_mi300x.terminate("any-pod-id")


def test_terminate_swallows_http_failure(monkeypatch):
    monkeypatch.setenv("VULTR_API_KEY", "fake-key")
    _install_fake_httpx(
        monkeypatch,
        delete_raises=httpx.ConnectError("boom", request=httpx.Request("DELETE", "/")),
    )
    from orchestration import vultr_mi300x

    # Must not raise
    vultr_mi300x.terminate("vinst_xyz")


def test_terminate_dry_run_for_dry_run_pod_id(monkeypatch):
    monkeypatch.setenv("VULTR_API_KEY", "fake-key")
    calls = _install_fake_httpx(monkeypatch)
    from orchestration import vultr_mi300x

    vultr_mi300x.terminate("dry-run")
    # Must not actually hit the API
    assert calls["delete"] == []


# ---------------------------------------------------------------------------
# Test 8: env vars injected via user_data — DEV-1021 + Phase 2 lineage
# ---------------------------------------------------------------------------


def test_provision_injects_all_env_vars(init_vultr_ledger, monkeypatch, pinned_image_ref):
    calls = _install_fake_httpx(monkeypatch)
    monkeypatch.setenv("VULTR_API_KEY", "fake-key")
    monkeypatch.setenv("OPERATOR_USER", "opsuser")
    monkeypatch.setenv(
        "SSH_PRIVATE_KEY",
        "-----BEGIN OPENSSH PRIVATE KEY-----\nfake\n-----END OPENSSH PRIVATE KEY-----",
    )
    from orchestration import vultr_mi300x

    vultr_mi300x.provision(
        gate="g1",
        projected_cost=2.0,
        max_minutes=30,
        ssh_pubkey="ssh-ed25519 AAAA fake",
        operator_host="ops.example.com",
    )
    user_data = calls["post"][0]["kwargs"]["json"]["user_data"]
    # All expected env vars appear in cloud-init user_data:
    for needle in (
        "GATE=g1",
        "MAX_MINUTES=30",
        "RUN_ID_PREFIX=g1",
        f"RBOX_IMAGE_DIGEST={pinned_image_ref}",
        "VULTR_API_KEY=fake-key",
        "OPERATOR_USER=opsuser",
        "SSH_PRIVATE_KEY_B64=",
        "SSH_PUBKEY=ssh-ed25519 AAAA fake",
        "OPERATOR_HOST=ops.example.com",
    ):
        assert needle in user_data, f"missing env: {needle}"
