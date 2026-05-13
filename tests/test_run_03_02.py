"""Tests for tools/run_03_02.py (Plan 03-02: Wave 2 G2 + G3 driver).

Mirrors tests/test_audit_harness_health.py. The autouse ``_scrub_cloud_keys``
fixture in tests/conftest.py unsets RUNPOD_API_KEY so provision() defaults
to its dry-run path; tests that exercise real-spend re-set it at function
scope and install a fake ``runpod`` SDK module.
"""

from __future__ import annotations

import json
import pathlib
import sqlite3
import sys
import types
from typing import Any

import pytest

from tools import run_03_02


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


def _install_fake_runpod(monkeypatch: pytest.MonkeyPatch) -> dict:
    fake = types.ModuleType("runpod")
    fake.api_key = None  # type: ignore[attr-defined]
    tracker: dict[str, Any] = {"create_calls": [], "terminate_calls": []}
    counter = {"n": 0}

    def _create(**kwargs: Any) -> dict[str, str]:
        counter["n"] += 1
        pid = f"fake-pod-{counter['n']}"
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
    files = sorted((results_dir / "preflight").glob("03-02-wave2-g2g3-*.json"))
    assert files, "no 03-02 manifest produced"
    return json.loads(files[-1].read_text())


def test_dry_run_default_no_key_runs_both_gates_returns_zero(
    _repo_results_dir: pathlib.Path,
) -> None:
    """Dry-run default: both gates land a dry-run entry; ledger rows commit."""
    rc = run_03_02.main(["--max-minutes-per-gate=20"])
    assert rc == 0
    m = _latest_manifest(_repo_results_dir)
    assert m["verdict"] == "pass"
    assert m["real_spend"] is False
    assert [g["gate"] for g in m["gates"]] == ["g2", "g3"]
    for entry in m["gates"]:
        assert entry["verdict"] == "dry-run"
        assert entry["pod_id"] == "dry-run"
        assert entry["real_spend"] is False
        assert entry["image_digest"].startswith("sha256:")


def test_real_spend_flag_required_even_when_key_set(
    monkeypatch: pytest.MonkeyPatch, _repo_results_dir: pathlib.Path
) -> None:
    """RUNPOD_API_KEY set but --real-spend absent stays in dry-run; no
    real pods created (operator must explicitly opt in)."""
    tracker = _install_fake_runpod(monkeypatch)
    monkeypatch.setenv("RUNPOD_API_KEY", "fake-but-set")

    rc = run_03_02.main(["--max-minutes-per-gate=20"])
    assert rc == 0
    m = _latest_manifest(_repo_results_dir)
    assert m["real_spend"] is False
    for entry in m["gates"]:
        assert entry["verdict"] == "dry-run"
    assert tracker["create_calls"] == []


def test_single_gate_arg_runs_only_one_gate(
    _repo_results_dir: pathlib.Path,
) -> None:
    """--gate=g3 runs only G3, not G2 (operator re-run path)."""
    rc = run_03_02.main(["--gate=g3", "--max-minutes-per-gate=20"])
    assert rc == 0
    m = _latest_manifest(_repo_results_dir)
    assert [g["gate"] for g in m["gates"]] == ["g3"]


def test_budget_exhausted_returns_two_writes_error_manifest(
    monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path
) -> None:
    """Ledger initialized at $0.20 cap so any 20-min projection (~$0.90)
    blows past the 1.5x safety factor; first gate's authorize_spend raises.
    Subsequent gates must NOT be attempted."""
    cfg = tmp_path / "config"
    cfg.mkdir()
    repo = pathlib.Path(__file__).resolve().parents[1]
    (cfg / "budget.yaml").write_text((repo / "config" / "budget.yaml").read_text())
    monkeypatch.chdir(tmp_path)
    from cost.ledger import initialize_provider

    initialize_provider("runpod", 0.20)

    rc = run_03_02.main(["--max-minutes-per-gate=20"])
    assert rc == 2
    files = sorted((tmp_path / "results" / "preflight").glob("03-02-wave2-g2g3-*.json"))
    assert files
    m = json.loads(files[-1].read_text())
    assert m["verdict"] == "budget-exhausted"
    # The first gate raises BudgetExhausted; the loop short-circuits so only
    # one entry is recorded.
    assert len(m["gates"]) == 1
    assert "BudgetExhausted" in m["gates"][0]["error"]


def test_dry_run_commits_ledger_rows_for_both_gates(
    _repo_results_dir: pathlib.Path,
) -> None:
    """Even on dry-run, both G2 and G3 commit ledger authorization rows so
    the operator sees the projected spend for the full wave."""
    rc = run_03_02.main(["--max-minutes-per-gate=20"])
    assert rc == 0

    conn = sqlite3.connect(pathlib.Path.cwd() / "cost" / "ledger.sqlite")
    rows = conn.execute(
        "SELECT gate FROM authorizations WHERE provider='runpod' ORDER BY id"
    ).fetchall()
    conn.close()
    gates = [r[0] for r in rows]
    assert "g2" in gates and "g3" in gates


def test_real_spend_multi_gate_commits_ledger_for_both_even_if_second_fails(
    monkeypatch: pytest.MonkeyPatch, _repo_results_dir: pathlib.Path
) -> None:
    """Both ledger rows commit even when the second pod fetch yields no data
    (i.e., the second gate's verdict is fail but its authorize_spend already
    executed)."""
    tracker = _install_fake_runpod(monkeypatch)
    monkeypatch.setenv("RUNPOD_API_KEY", "fake-but-set")

    async def _exit_now(pod_id: str, *, timeout_s: int) -> str:
        return "EXITED"

    async def _spend() -> float:
        return 0.45

    monkeypatch.setattr(run_03_02, "_wait_for_pod_exit", _exit_now)
    monkeypatch.setattr(run_03_02, "_final_spend", _spend)

    # Pre-populate ONLY g2 results; g3 dir empty so g3 verdict=fail.
    g2_dir = _repo_results_dir / "g2"
    g2_dir.mkdir(parents=True)
    (g2_dir / "fake.jsonl").write_text(json.dumps({"id": 1}) + "\n")
    (g2_dir / "fake.audit.json").write_text(json.dumps({"summary": {"violations": 0}}))

    import tools.fetch_results as fr

    monkeypatch.setattr(fr, "fetch", lambda *a, **k: 0)
    monkeypatch.setenv("RUNPOD_NETWORK_VOLUME_ID", "vol-xyz")

    rc = run_03_02.main(["--real-spend", "--max-minutes-per-gate=20"])
    # g3 has no rows -> verdict fail -> overall rc=1
    assert rc == 1
    m = _latest_manifest(_repo_results_dir)
    assert [g["gate"] for g in m["gates"]] == ["g2", "g3"]
    # BOTH pods provisioned (both ledger rows committed by virtue of
    # reaching provision()).
    assert len(tracker["create_calls"]) == 2

    conn = sqlite3.connect(pathlib.Path.cwd() / "cost" / "ledger.sqlite")
    gates = [
        r[0]
        for r in conn.execute(
            "SELECT gate FROM authorizations WHERE provider='runpod' ORDER BY id"
        ).fetchall()
    ]
    conn.close()
    assert gates.count("g2") >= 1 and gates.count("g3") >= 1
