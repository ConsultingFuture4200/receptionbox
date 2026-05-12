"""Tests for tools/audit_harness_health.py (Plan 03-01 driver).

All tests rely on the autouse ``_scrub_cloud_keys`` fixture in
``tests/conftest.py`` which unsets RUNPOD_API_KEY by default so provision()
takes its built-in dry-run path. Tests that exercise the real-spend code
path re-set RUNPOD_API_KEY at function scope and install a fake ``runpod``
SDK module so no real RunPod traffic occurs.
"""

from __future__ import annotations

import json
import pathlib
import sqlite3
import sys
import types
from typing import Any

import pytest

from tools import audit_harness_health


@pytest.fixture
def _repo_results_dir(monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path) -> pathlib.Path:
    """Hermetic temp CWD with budget.yaml + initialized $75 RunPod ledger."""
    cfg = tmp_path / "config"
    cfg.mkdir()
    repo = pathlib.Path(__file__).resolve().parents[1]
    (cfg / "budget.yaml").write_text((repo / "config" / "budget.yaml").read_text())
    monkeypatch.chdir(tmp_path)
    from cost.ledger import initialize_provider

    initialize_provider("runpod", 75.0)
    return tmp_path / "results"


def _install_fake_runpod(monkeypatch: pytest.MonkeyPatch, pod_id: str = "fake-pod-1") -> dict:
    fake = types.ModuleType("runpod")
    fake.api_key = None  # type: ignore[attr-defined]
    tracker: dict[str, Any] = {"create_calls": [], "terminate_calls": []}

    def _create(**kwargs: Any) -> dict[str, str]:
        tracker["create_calls"].append(kwargs)
        return {"id": pod_id, "podHostId": f"host-{pod_id}"}

    def _terminate(pid: str) -> None:
        tracker["terminate_calls"].append(pid)

    fake.create_pod = _create  # type: ignore[attr-defined]
    fake.terminate_pod = _terminate  # type: ignore[attr-defined]
    fake.get_pods = lambda: []  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "runpod", fake)
    return tracker


def _latest_manifest(results_dir: pathlib.Path) -> dict:
    files = sorted((results_dir / "preflight").glob("03-01-harness-audit-*.json"))
    assert files, "no harness-audit manifest produced"
    return json.loads(files[-1].read_text())


def test_project_cost_formula() -> None:
    assert audit_harness_health._project_cost(15) == round(15 / 60 * 2.69, 2)
    assert audit_harness_health._project_cost(60) == 2.69


def test_split_image_digest_strips_repo_prefix() -> None:
    ref = "ghcr.io/x/y@sha256:" + "a" * 64
    assert audit_harness_health._split_image_digest(ref) == "sha256:" + "a" * 64
    assert audit_harness_health._split_image_digest("no-at-sign") == "unknown"


def test_adapter_health_all_true_when_every_row_has_timings() -> None:
    rows = [{"stt_ttft_ms": 1, "llm_ttft_ms": 2, "tts_first_audio_ms": 3}] * 5
    assert audit_harness_health._adapter_health_from_jsonl(rows) == {
        "stt": True,
        "llm": True,
        "tts": True,
    }


def test_adapter_health_false_on_empty_rows() -> None:
    assert audit_harness_health._adapter_health_from_jsonl([]) == {
        "stt": False,
        "llm": False,
        "tts": False,
    }


def test_adapter_health_false_when_any_row_missing_a_stage() -> None:
    rows = [
        {"stt_ttft_ms": 1, "llm_ttft_ms": 2, "tts_first_audio_ms": 3},
        {"stt_ttft_ms": None, "llm_ttft_ms": 2, "tts_first_audio_ms": 3},
    ]
    h = audit_harness_health._adapter_health_from_jsonl(rows)
    assert h["stt"] is False and h["llm"] is True and h["tts"] is True


def test_dry_run_default_no_key_writes_manifest_returns_zero(
    _repo_results_dir: pathlib.Path,
) -> None:
    """Behavior 1: With RUNPOD_API_KEY unset (conftest scrubs it) and no
    --real-spend, provision() routes to dry-run and the driver short-circuits
    to a dry-run verdict manifest.
    """
    rc = audit_harness_health.main(["--max-minutes=15"])
    assert rc == 0
    m = _latest_manifest(_repo_results_dir)
    assert m["verdict"] == "dry-run"
    assert m["pod_id"] == "dry-run"
    assert m["real_spend"] is False
    assert m["projected_cost_usd"] == round(15 / 60 * 2.69, 2)
    assert m["image_digest"].startswith("sha256:")


def test_real_spend_flag_required_even_when_key_set(
    monkeypatch: pytest.MonkeyPatch, _repo_results_dir: pathlib.Path
) -> None:
    """Behavior 4: With RUNPOD_API_KEY set but --real-spend absent, stay
    in dry-run. No SDK pod must be created (operator must explicitly opt
    in to spend).
    """
    tracker = _install_fake_runpod(monkeypatch)
    monkeypatch.setenv("RUNPOD_API_KEY", "fake-but-set")

    rc = audit_harness_health.main(["--max-minutes=15"])
    assert rc == 0
    m = _latest_manifest(_repo_results_dir)
    assert m["real_spend"] is False
    assert m["verdict"] == "dry-run"
    assert m["pod_id"] == "dry-run"
    assert tracker["create_calls"] == [], "must NOT create a pod without --real-spend"


def test_real_spend_pass_path_writes_verdict_manifest(
    monkeypatch: pytest.MonkeyPatch, _repo_results_dir: pathlib.Path
) -> None:
    """Behavior 2: With --real-spend + RUNPOD_API_KEY + mocked-healthy smoke
    results, manifest verdict=pass and all 3 adapters healthy.
    """
    tracker = _install_fake_runpod(monkeypatch, pod_id="fake-pod-pass")
    monkeypatch.setenv("RUNPOD_API_KEY", "fake-but-set")

    # Stub out the wait + spend polls.
    async def _exit_now(pod_id: str, *, timeout_s: int) -> str:
        return "EXITED"

    async def _spend() -> float:
        return 0.55

    monkeypatch.setattr(audit_harness_health, "_wait_for_pod_exit", _exit_now)
    monkeypatch.setattr(audit_harness_health, "_final_spend", _spend)

    # Synthesize what the v14 fetch transport would have rsynced back.
    # The driver looks under results/smoke/ after fetch_results returns.
    smoke_dir = _repo_results_dir / "smoke"
    smoke_dir.mkdir(parents=True)
    rows = [
        {"stt_ttft_ms": 80, "llm_ttft_ms": 50, "tts_first_audio_ms": 470, "e2e_ms": 700},
    ] * 5
    (smoke_dir / "fake.jsonl").write_text("\n".join(json.dumps(r) for r in rows) + "\n")
    (smoke_dir / "fake.audit.json").write_text(json.dumps({"summary": {"violations": 0}}))

    # Stub fetch_results so it doesn't try to spin up a fetch pod — the
    # smoke_dir is already pre-populated above.
    import tools.fetch_results as fr

    monkeypatch.setattr(fr, "fetch", lambda *a, **k: 0)
    monkeypatch.setenv("RUNPOD_NETWORK_VOLUME_ID", "vol-xyz")

    rc = audit_harness_health.main(["--real-spend", "--max-minutes=15"])
    assert rc == 0
    m = _latest_manifest(_repo_results_dir)
    assert m["verdict"] == "pass"
    assert m["real_spend"] is True
    assert m["pod_id"] == "fake-pod-pass"
    assert m["adapter_health"] == {"stt": True, "llm": True, "tts": True}
    assert m["audit_clean"] is True
    assert m["rows_observed"] == 5
    assert m["final_spend_usd"] == 0.55
    assert m["image_digest"].startswith("sha256:")
    assert len(tracker["create_calls"]) == 1


def test_budget_exhausted_returns_two_writes_error_manifest(
    monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path
) -> None:
    """Behavior 3: When provision() raises BudgetExhausted (ledger refused),
    the driver returns 2 and writes an error manifest.
    """
    # Init ledger with a $0.50 cap so a 15-min projection (~$0.67) plus the
    # 1.5x safety factor blows the cap. Provision() raises BudgetExhausted
    # via its first-line authorize_spend(...) call.
    cfg = tmp_path / "config"
    cfg.mkdir()
    repo = pathlib.Path(__file__).resolve().parents[1]
    (cfg / "budget.yaml").write_text((repo / "config" / "budget.yaml").read_text())
    monkeypatch.chdir(tmp_path)
    from cost.ledger import initialize_provider

    initialize_provider("runpod", 0.50)

    rc = audit_harness_health.main(["--max-minutes=15"])
    assert rc == 2
    files = sorted((tmp_path / "results" / "preflight").glob("03-01-harness-audit-*.json"))
    assert files
    m = json.loads(files[-1].read_text())
    assert m["verdict"] == "fail"
    assert "BudgetExhausted" in m["error"]


def test_dry_run_commits_ledger_row_for_visibility(
    _repo_results_dir: pathlib.Path,
) -> None:
    """Dry-run path still commits the spend row in cost/ledger.sqlite so the
    operator sees the projection even without --real-spend. Matches
    orchestration.runpod_h100.provision()'s dry-run contract.
    """
    rc = audit_harness_health.main(["--max-minutes=15"])
    assert rc == 0

    conn = sqlite3.connect(pathlib.Path.cwd() / "cost" / "ledger.sqlite")
    rows = conn.execute(
        "SELECT gate, projected_cost_usd FROM authorizations WHERE provider='runpod'"
    ).fetchall()
    conn.close()
    assert rows, "no authorization row committed"
    assert rows[-1][0] == "smoke"  # routes through smoke gate (see module docstring)
