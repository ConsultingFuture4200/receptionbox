"""Repo-wide pytest fixtures.

Plan 02-09 (gap closure, 2026-05-12): clear cloud-provider API keys from
the env for every test by default. Operator env routinely carries
RUNPOD_API_KEY (from secrets/rboxkey.md via .claude/settings.local.json);
without this autouse fixture, any test that calls
orchestration.runpod_h100.provision() without mocking the SDK will hit
the real RunPod GraphQL endpoint and either fail-flaky on stock or burn
real cents. Tests that want a "key is set" code path use
monkeypatch.setenv(...) at function scope, which supersedes this.
"""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _scrub_cloud_keys(monkeypatch: pytest.MonkeyPatch) -> None:
    """Unset cloud-provider API keys for every test by default.

    Function-scope (matches pytest's built-in `monkeypatch` scope) so
    individual tests can still call monkeypatch.setenv("RUNPOD_API_KEY",
    "fake-but-set") to flip into the SDK-path branch (with their own SDK
    mocks in place). The autouse delenv only fires BEFORE the test body
    runs; any setenv inside the test or its other fixtures takes
    precedence. Function-scope also gets us automatic teardown via
    monkeypatch's undo() — no manual save/restore needed.
    """
    for key in ("RUNPOD_API_KEY", "TENSORWAVE_API_KEY", "VULTR_API_KEY"):
        monkeypatch.delenv(key, raising=False)
