"""Tests for tools/run_preflight.py (Phase 2 pre-flight driver, dry-run only).

All tests run with RUNPOD_API_KEY UNSET so the driver routes through
orchestration.runpod_h100.provision()'s dry-run path. No real RunPod spend.
"""

from __future__ import annotations

import datetime
import json
import pathlib

import pytest

from tools import run_preflight


@pytest.fixture(autouse=True)
def _no_runpod_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """Force every test into dry-run mode; ledger row still commits."""
    monkeypatch.delenv("RUNPOD_API_KEY", raising=False)


@pytest.fixture
def _repo_results_dir(monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path) -> pathlib.Path:
    """Run the driver inside a temp dir but with the real budget.yaml + ledger.

    The driver reads config/budget.yaml from CWD; chdir to tmp + symlink the
    config file to keep tests hermetic.
    """
    cfg_dir = tmp_path / "config"
    cfg_dir.mkdir()
    repo = pathlib.Path(__file__).resolve().parents[1]
    (cfg_dir / "budget.yaml").write_text((repo / "config" / "budget.yaml").read_text())
    monkeypatch.chdir(tmp_path)
    return tmp_path / "results"


def test_project_cost_formula() -> None:
    assert run_preflight._project_cost(30) == round(30 / 60 * 2.69, 2)
    assert run_preflight._project_cost(60) == 2.69
    assert run_preflight._project_cost(15) == round(15 / 60 * 2.69, 2)


def test_run_preflight_smoke_dry_run_exits_zero(_repo_results_dir: pathlib.Path) -> None:
    rc = run_preflight.main(["--mode", "smoke"])
    assert rc == 0
    sessions = sorted((_repo_results_dir / "preflight").glob("*.json"))
    assert sessions, "no preflight session manifest written"
    sess = json.loads(sessions[-1].read_text())
    assert sess["mode"] == "smoke"
    assert len(sess["gates"]) == 1
    assert sess["gates"][0]["status"] == "dry-run"
    assert sess["gates"][0]["gate"] == "smoke"


def test_run_preflight_sanity_dry_run_iterates_4_gates(_repo_results_dir: pathlib.Path) -> None:
    rc = run_preflight.main(["--mode", "sanity"])
    assert rc == 0
    sessions = sorted((_repo_results_dir / "preflight").glob("*.json"))
    sess = json.loads(sessions[-1].read_text())
    assert sess["mode"] == "sanity"
    gate_names = [g["gate"] for g in sess["gates"]]
    assert gate_names == ["g1", "g2", "g3", "g5"]
    assert all(g["status"] == "dry-run" for g in sess["gates"])


def test_run_preflight_bootstrap_dry_run_logs_and_returns_zero(
    _repo_results_dir: pathlib.Path, caplog: pytest.LogCaptureFixture
) -> None:
    import logging

    caplog.set_level(logging.INFO)
    rc = run_preflight.main(["--mode", "bootstrap"])
    assert rc == 0
    assert any("DRY RUN bootstrap" in r.message for r in caplog.records)


def test_validate_smoke_pass_path(tmp_path: pathlib.Path) -> None:
    """Synthesize 5 valid rows + env.json + clean audit.json -> verdict pass."""
    smoke_dir = tmp_path / "smoke"
    smoke_dir.mkdir()
    run_id = "test-run"
    jsonl = smoke_dir / f"{run_id}.jsonl"
    rows = []
    for i in range(5):
        rows.append(
            {
                "schema_version": "1.0",
                "run_id": run_id,
                "gate": "smoke",
                "asset_id": f"call-{i:04d}",
                "asset_manifest_sha": "x" * 64,
                "substrate": "cuda",
                "image_digest": "sha256:abc",
                "model_shas": {"qwen": "rev"},
                "git_commit": "deadbeef",
                "timestamp_utc": datetime.datetime.utcnow().isoformat(),
                "concurrency": 1,
                "status": "ok",
                "stt_ttft_ms": 100.0,
                "llm_ttft_ms": 80.0,
                "llm_decode_ms_per_tok": 20.0,
                "tts_first_audio_ms": 150.0,
                "e2e_ms": 800.0,
                "metrics": {},
                "extras": {},
            }
        )
    jsonl.write_text("\n".join(json.dumps(r) for r in rows) + "\n")
    env_path = smoke_dir / f"{run_id}.env.json"
    env_path.write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "run_id": run_id,
                "gate": "smoke",
                "git_commit": "deadbeef",
                "asset_manifest_sha": "x" * 64,
                "env": {
                    "substrate": "cuda",
                    "image_digest": "sha256:abc",
                    "model_shas": {"qwen": "rev"},
                    "gpu_sku": "H100",
                    "gpu_count": 1,
                    "rocm_version": None,
                    "cuda_version": "12.4",
                    "vllm_version": "0.10.0",
                    "pytorch_version": "2.5.1",
                    "timestamp_utc": datetime.datetime.utcnow().isoformat(),
                },
            }
        )
    )
    audit_path = smoke_dir / f"{run_id}.audit.json"
    audit_path.write_text(json.dumps({"summary": {"violations": 0}}))

    verdict = run_preflight._validate_smoke(
        results_dir=tmp_path, run_id_glob="*", wall_clock_s=900.0, final_spend=0.5
    )
    assert verdict["pass"] is True, verdict
    assert verdict["a_5_rows"] is True
    assert verdict["b_under_30min"] is True
    assert verdict["c_under_1usd"] is True
    assert verdict["d_per_stage_timings"] is True
    assert verdict["e_env_sidecar"] is True
    assert verdict["f_audit_clean"] is True


def test_validate_smoke_only_4_rows_fails_a(tmp_path: pathlib.Path) -> None:
    smoke_dir = tmp_path / "smoke"
    smoke_dir.mkdir()
    jsonl = smoke_dir / "run-x.jsonl"
    jsonl.write_text("\n".join(json.dumps({"x": i}) for i in range(4)) + "\n")
    verdict = run_preflight._validate_smoke(
        results_dir=tmp_path, run_id_glob="*", wall_clock_s=10.0, final_spend=0.1
    )
    assert verdict["a_5_rows"] is False
    assert verdict["pass"] is False


def test_validate_smoke_missing_per_stage_timings_fails_d(tmp_path: pathlib.Path) -> None:
    smoke_dir = tmp_path / "smoke"
    smoke_dir.mkdir()
    rows = [
        {"stt_ttft_ms": None, "llm_ttft_ms": 1, "tts_first_audio_ms": 1, "e2e_ms": 1}
        for _ in range(5)
    ]
    (smoke_dir / "r.jsonl").write_text("\n".join(json.dumps(r) for r in rows) + "\n")
    verdict = run_preflight._validate_smoke(
        results_dir=tmp_path, run_id_glob="*", wall_clock_s=10.0, final_spend=0.1
    )
    assert verdict["d_per_stage_timings"] is False
    assert verdict["pass"] is False


def test_validate_smoke_audit_violation_fails_f(tmp_path: pathlib.Path) -> None:
    smoke_dir = tmp_path / "smoke"
    smoke_dir.mkdir()
    rows = [
        {
            "stt_ttft_ms": 1,
            "llm_ttft_ms": 1,
            "tts_first_audio_ms": 1,
            "e2e_ms": 1,
        }
        for _ in range(5)
    ]
    (smoke_dir / "r.jsonl").write_text("\n".join(json.dumps(r) for r in rows) + "\n")
    (smoke_dir / "r.env.json").write_text(
        json.dumps(
            {
                "env": {
                    "substrate": "cuda",
                    "image_digest": "x",
                    "model_shas": {},
                    "gpu_sku": "H100",
                    "gpu_count": 1,
                    "rocm_version": None,
                    "cuda_version": "12.4",
                    "vllm_version": "0.10",
                    "pytorch_version": "2.5",
                    "timestamp_utc": datetime.datetime.utcnow().isoformat(),
                }
            }
        )
    )
    (smoke_dir / "r.audit.json").write_text(json.dumps({"summary": {"violations": 2}}))
    verdict = run_preflight._validate_smoke(
        results_dir=tmp_path, run_id_glob="*", wall_clock_s=10.0, final_spend=0.1
    )
    assert verdict["f_audit_clean"] is False
    assert verdict["pass"] is False


def test_run_preflight_session_manifest_written(_repo_results_dir: pathlib.Path) -> None:
    rc = run_preflight.main(["--mode", "smoke"])
    assert rc == 0
    sessions = sorted((_repo_results_dir / "preflight").glob("*.json"))
    sess = json.loads(sessions[-1].read_text())
    for k in ("session_id", "mode", "gates"):
        assert k in sess


def test_run_preflight_help_lists_modes() -> None:
    with pytest.raises(SystemExit) as excinfo:
        run_preflight.main(["--help"])
    assert excinfo.value.code == 0
