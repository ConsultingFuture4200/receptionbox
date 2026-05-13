"""Tests for tools/run_03_03.py (Plan 03-03: G5 UPL probe driver)."""

from __future__ import annotations

import json
import pathlib
import sqlite3
import sys
import types
from typing import Any

import pytest

from tools import run_03_03


@pytest.fixture
def _repo_results_dir(monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path) -> pathlib.Path:
    cfg = tmp_path / "config"
    cfg.mkdir()
    repo = pathlib.Path(__file__).resolve().parents[1]
    (cfg / "budget.yaml").write_text((repo / "config" / "budget.yaml").read_text())
    monkeypatch.chdir(tmp_path)
    from cost.ledger import initialize_provider

    initialize_provider("runpod", 75.0)
    return tmp_path / "results"


def _install_fake_runpod(monkeypatch: pytest.MonkeyPatch, pod_id: str = "fake-g5") -> dict:
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
    files = sorted((results_dir / "preflight").glob("03-03-wave2-g5-*.json"))
    assert files, "no 03-03 manifest produced"
    return json.loads(files[-1].read_text())


def test_dry_run_default_writes_manifest_returns_zero(
    _repo_results_dir: pathlib.Path,
) -> None:
    rc = run_03_03.main(["--max-minutes=30"])
    assert rc == 0
    m = _latest_manifest(_repo_results_dir)
    assert m["verdict"] == "dry-run"
    assert m["pod_id"] == "dry-run"
    assert m["real_spend"] is False
    assert m["gate"] == "g5"
    assert m["image_digest"].startswith("sha256:")


def test_real_spend_flag_required_even_when_key_set(
    monkeypatch: pytest.MonkeyPatch, _repo_results_dir: pathlib.Path
) -> None:
    tracker = _install_fake_runpod(monkeypatch)
    monkeypatch.setenv("RUNPOD_API_KEY", "fake-but-set")

    rc = run_03_03.main(["--max-minutes=30"])
    assert rc == 0
    m = _latest_manifest(_repo_results_dir)
    assert m["real_spend"] is False
    assert m["verdict"] == "dry-run"
    assert tracker["create_calls"] == []


def test_budget_exhausted_returns_two(
    monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path
) -> None:
    cfg = tmp_path / "config"
    cfg.mkdir()
    repo = pathlib.Path(__file__).resolve().parents[1]
    (cfg / "budget.yaml").write_text((repo / "config" / "budget.yaml").read_text())
    monkeypatch.chdir(tmp_path)
    from cost.ledger import initialize_provider

    initialize_provider("runpod", 0.20)

    rc = run_03_03.main(["--max-minutes=30"])
    assert rc == 2
    files = sorted((tmp_path / "results" / "preflight").glob("03-03-wave2-g5-*.json"))
    m = json.loads(files[-1].read_text())
    assert m["verdict"] == "budget-exhausted"
    assert "BudgetExhausted" in m["error"]


def test_real_spend_pass_path_verifies_row_count_and_xgrammar(
    monkeypatch: pytest.MonkeyPatch, _repo_results_dir: pathlib.Path
) -> None:
    """Real-spend happy path: 250 rows, probe_category populated, xgrammar
    backend stamped in env.json, audit clean ⇒ verdict=pass."""
    tracker = _install_fake_runpod(monkeypatch, pod_id="fake-g5-pass")
    monkeypatch.setenv("RUNPOD_API_KEY", "fake-but-set")

    async def _exit_now(pod_id: str, *, timeout_s: int) -> str:
        return "EXITED"

    async def _spend() -> float:
        return 0.85

    monkeypatch.setattr(run_03_03, "_wait_for_pod_exit", _exit_now)
    monkeypatch.setattr(run_03_03, "_final_spend", _spend)

    g5_dir = _repo_results_dir / "g5"
    g5_dir.mkdir(parents=True)
    rows = [{"probe_category": "indirect_injection", "passed": True} for _ in range(200)] + [
        {"probe_category": "control_benign", "passed": True} for _ in range(50)
    ]
    (g5_dir / "g5.jsonl").write_text("\n".join(json.dumps(r) for r in rows) + "\n")
    (g5_dir / "g5.audit.json").write_text(json.dumps({"summary": {"violations": 0}}))
    (g5_dir / "env.json").write_text(json.dumps({"GUIDED_DECODING_BACKEND": "xgrammar"}))

    import tools.fetch_results as fr

    monkeypatch.setattr(fr, "fetch", lambda *a, **k: 0)
    monkeypatch.setenv("RUNPOD_NETWORK_VOLUME_ID", "vol-xyz")

    rc = run_03_03.main(["--real-spend", "--max-minutes=30"])
    assert rc == 0
    m = _latest_manifest(_repo_results_dir)
    assert m["verdict"] == "pass"
    assert m["real_spend"] is True
    assert m["rows_observed"] == 250
    assert m["row_count_ok"] is True
    assert m["probe_category_populated"] is True
    assert m["xgrammar_backend_confirmed"] is True
    assert m["audit_clean"] is True
    assert len(tracker["create_calls"]) == 1


def test_real_spend_fail_when_row_count_off(
    monkeypatch: pytest.MonkeyPatch, _repo_results_dir: pathlib.Path
) -> None:
    """249 rows (not 250) ⇒ verdict=fail."""
    _install_fake_runpod(monkeypatch, pod_id="fake-g5-shortrows")
    monkeypatch.setenv("RUNPOD_API_KEY", "fake-but-set")

    async def _exit_now(pod_id: str, *, timeout_s: int) -> str:
        return "EXITED"

    async def _spend() -> float:
        return 0.85

    monkeypatch.setattr(run_03_03, "_wait_for_pod_exit", _exit_now)
    monkeypatch.setattr(run_03_03, "_final_spend", _spend)

    g5_dir = _repo_results_dir / "g5"
    g5_dir.mkdir(parents=True)
    rows = [{"probe_category": "x", "passed": True} for _ in range(249)]
    (g5_dir / "g5.jsonl").write_text("\n".join(json.dumps(r) for r in rows) + "\n")
    (g5_dir / "g5.audit.json").write_text(json.dumps({"summary": {"violations": 0}}))
    (g5_dir / "env.json").write_text(json.dumps({"GUIDED_DECODING_BACKEND": "xgrammar"}))

    import tools.fetch_results as fr

    monkeypatch.setattr(fr, "fetch", lambda *a, **k: 0)
    monkeypatch.setenv("RUNPOD_NETWORK_VOLUME_ID", "vol-xyz")

    rc = run_03_03.main(["--real-spend", "--max-minutes=30"])
    assert rc == 1
    m = _latest_manifest(_repo_results_dir)
    assert m["verdict"] == "fail"
    assert m["row_count_ok"] is False
    assert m["rows_observed"] == 249


def test_dry_run_commits_ledger_row_for_g5(
    _repo_results_dir: pathlib.Path,
) -> None:
    rc = run_03_03.main(["--max-minutes=30"])
    assert rc == 0
    conn = sqlite3.connect(pathlib.Path.cwd() / "cost" / "ledger.sqlite")
    rows = conn.execute("SELECT gate FROM authorizations WHERE provider='runpod'").fetchall()
    conn.close()
    assert any(r[0] == "g5" for r in rows)
