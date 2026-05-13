"""Tests for tools/run_03_05.py (Plan 03-05: AUDIT-01 + AUDIT-03 driver)."""

from __future__ import annotations

import json
import pathlib
import sqlite3
import sys
import types
from typing import Any

import pytest

from tools import run_03_05


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


def _install_fake_runpod(monkeypatch: pytest.MonkeyPatch) -> dict:
    fake = types.ModuleType("runpod")
    fake.api_key = None  # type: ignore[attr-defined]
    tracker: dict[str, Any] = {"create_calls": [], "terminate_calls": []}
    counter = {"n": 0}

    def _create(**kwargs: Any) -> dict[str, str]:
        counter["n"] += 1
        pid = f"fake-audit-{counter['n']}"
        tracker["create_calls"].append(kwargs)
        return {"id": pid, "podHostId": f"host-{pid}"}

    def _terminate(pid: str) -> None:
        tracker["terminate_calls"].append(pid)

    fake.create_pod = _create  # type: ignore[attr-defined]
    fake.terminate_pod = _terminate  # type: ignore[attr-defined]
    fake.get_pods = lambda: []  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "runpod", fake)
    return tracker


def _latest_manifest(results_dir: pathlib.Path) -> dict:
    files = sorted((results_dir / "preflight").glob("03-05-wave2-audits-*.json"))
    assert files, "no 03-05 manifest produced"
    return json.loads(files[-1].read_text())


def test_dry_run_default_no_key_runs_both_audits_returns_zero(
    _repo_results_dir: pathlib.Path,
) -> None:
    rc = run_03_05.main(["--max-minutes-per-audit=30"])
    assert rc == 0
    m = _latest_manifest(_repo_results_dir)
    assert m["verdict"] == "pass"
    assert m["real_spend"] is False
    assert [e["audit"] for e in m["audits"]] == ["audit_01", "audit_03"]
    for entry in m["audits"]:
        assert entry["verdict"] == "dry-run"
        assert entry["pod_id"] == "dry-run"
        assert entry["image_digest"].startswith("sha256:")


def test_real_spend_flag_required_even_when_key_set(
    monkeypatch: pytest.MonkeyPatch, _repo_results_dir: pathlib.Path
) -> None:
    tracker = _install_fake_runpod(monkeypatch)
    monkeypatch.setenv("RUNPOD_API_KEY", "fake-but-set")

    rc = run_03_05.main(["--max-minutes-per-audit=30"])
    assert rc == 0
    m = _latest_manifest(_repo_results_dir)
    assert m["real_spend"] is False
    for entry in m["audits"]:
        assert entry["verdict"] == "dry-run"
    assert tracker["create_calls"] == []


def test_single_audit_arg_runs_only_one(
    _repo_results_dir: pathlib.Path,
) -> None:
    rc = run_03_05.main(["--gate=audit_03", "--max-minutes-per-audit=30"])
    assert rc == 0
    m = _latest_manifest(_repo_results_dir)
    assert [e["audit"] for e in m["audits"]] == ["audit_03"]


def test_budget_exhausted_short_circuits_returns_two(
    monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path
) -> None:
    cfg = tmp_path / "config"
    cfg.mkdir()
    repo = pathlib.Path(__file__).resolve().parents[1]
    (cfg / "budget.yaml").write_text((repo / "config" / "budget.yaml").read_text())
    monkeypatch.chdir(tmp_path)
    from cost.ledger import initialize_provider

    initialize_provider("runpod", 0.20)

    rc = run_03_05.main(["--max-minutes-per-audit=30"])
    assert rc == 2
    m = _latest_manifest(tmp_path / "results")
    assert m["verdict"] == "budget-exhausted"
    # First audit short-circuits; second never attempted.
    assert len(m["audits"]) == 1
    assert m["audits"][0]["audit"] == "audit_01"


def test_dry_run_commits_ledger_rows_for_both_audits(
    _repo_results_dir: pathlib.Path,
) -> None:
    rc = run_03_05.main(["--max-minutes-per-audit=30"])
    assert rc == 0
    conn = sqlite3.connect(pathlib.Path.cwd() / "cost" / "ledger.sqlite")
    rows = conn.execute(
        "SELECT gate FROM authorizations WHERE provider='runpod' ORDER BY id"
    ).fetchall()
    conn.close()
    gates = [r[0] for r in rows]
    assert "audit_01" in gates and "audit_03" in gates


def test_real_spend_multi_audit_commits_ledger_for_both_even_if_second_fails(
    monkeypatch: pytest.MonkeyPatch, _repo_results_dir: pathlib.Path
) -> None:
    """Both audits' authorize_spend rows commit even when audit_03's fetch
    yields no rows (verdict=fail)."""
    tracker = _install_fake_runpod(monkeypatch)
    monkeypatch.setenv("RUNPOD_API_KEY", "fake-but-set")

    async def _exit_now(pod_id: str, *, timeout_s: int) -> str:
        return "EXITED"

    async def _spend() -> float:
        return 0.65

    monkeypatch.setattr(run_03_05, "_wait_for_pod_exit", _exit_now)
    monkeypatch.setattr(run_03_05, "_final_spend", _spend)

    a01 = _repo_results_dir / "audit_01"
    a01.mkdir(parents=True)
    (a01 / "a01.jsonl").write_text(json.dumps({"id": 1}) + "\n")
    (a01 / "a01.audit.json").write_text(json.dumps({"summary": {"violations": 0}}))

    import tools.fetch_results as fr

    monkeypatch.setattr(fr, "fetch", lambda *a, **k: 0)
    monkeypatch.setenv("RUNPOD_NETWORK_VOLUME_ID", "vol-xyz")

    rc = run_03_05.main(["--real-spend", "--max-minutes-per-audit=30"])
    assert rc == 1  # audit_03 fail
    m = _latest_manifest(_repo_results_dir)
    assert [e["audit"] for e in m["audits"]] == ["audit_01", "audit_03"]
    assert len(tracker["create_calls"]) == 2

    conn = sqlite3.connect(pathlib.Path.cwd() / "cost" / "ledger.sqlite")
    gates = [
        r[0]
        for r in conn.execute("SELECT gate FROM authorizations WHERE provider='runpod'").fetchall()
    ]
    conn.close()
    assert gates.count("audit_01") >= 1 and gates.count("audit_03") >= 1
