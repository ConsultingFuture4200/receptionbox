"""End-to-end mock test for the bootstrap -> smoke chain (Plan 02-05 Task 3).

Defense in depth: closes 02-VERIFICATION GAP-3 secondary by proving the full
pre-flight orchestration chain wires correctly without real spend. This is
what the operator's actual run will exercise; we dry-run it locally first
against mocked RunPod SDK + SSH + rsync.

The test installs a fake `runpod` SDK module so `import runpod` inside
`orchestration.runpod_h100.provision()` lands on the fake; monkeypatches
`_wait_for_pod_exit` and `_final_spend`; synthesizes the smoke pod's
would-be-rsynced result files; and asserts the driver's D-25 verdict
against them.
"""

from __future__ import annotations

import datetime
import json
import pathlib
import sys
import types
from typing import Any

import pytest


def _install_fake_runpod(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    """Install a fake `runpod` module; return a tracker dict."""
    fake = types.ModuleType("runpod")
    fake.api_key = None  # type: ignore[attr-defined]
    tracker: dict[str, Any] = {
        "create_calls": [],
        "terminate_calls": [],
        "next_pod_id": iter(["fake-bootstrap-1", "fake-smoke-1", "fake-extra-1"]),
    }

    def _create(**kwargs: Any) -> dict[str, str]:
        tracker["create_calls"].append(kwargs)
        pid = next(tracker["next_pod_id"])
        return {"id": pid, "podHostId": f"host-{pid}"}

    def _terminate(pod_id: str) -> None:
        tracker["terminate_calls"].append(pod_id)

    def _get_pods() -> list[dict[str, Any]]:
        return []

    fake.create_pod = _create  # type: ignore[attr-defined]
    fake.terminate_pod = _terminate  # type: ignore[attr-defined]
    fake.get_pods = _get_pods  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "runpod", fake)
    return tracker


def _bootstrap_ledger(tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> pathlib.Path:
    """Initialize a $75 RunPod ledger in tmp_path; rebind authorize_spend default."""
    from cost import ledger

    db = tmp_path / "ledger.sqlite"
    monkeypatch.setattr(ledger, "DEFAULT_DB", db)
    orig = ledger.authorize_spend.__defaults__
    assert orig is not None
    new = (*orig[:-1], db)
    monkeypatch.setattr(ledger.authorize_spend, "__defaults__", new)
    ledger.initialize_provider("runpod", 75.0, db_path=db)
    return db


def _copy_budget(tmp_path: pathlib.Path) -> None:
    cfg_dir = tmp_path / "config"
    cfg_dir.mkdir()
    repo = pathlib.Path(__file__).resolve().parents[1]
    (cfg_dir / "budget.yaml").write_text((repo / "config" / "budget.yaml").read_text())


def _synthesize_smoke_results(results_dir: pathlib.Path, run_id: str = "test-smoke-001") -> None:
    smoke_dir = results_dir / "smoke"
    smoke_dir.mkdir(parents=True, exist_ok=True)
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
    (smoke_dir / f"{run_id}.jsonl").write_text("\n".join(json.dumps(r) for r in rows) + "\n")
    (smoke_dir / f"{run_id}.env.json").write_text(
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
    (smoke_dir / f"{run_id}.audit.json").write_text(json.dumps({"summary": {"violations": 0}}))


@pytest.fixture
def e2e_env(tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("RUNPOD_API_KEY", "fake-but-set")
    _copy_budget(tmp_path)
    _bootstrap_ledger(tmp_path, monkeypatch)
    tracker = _install_fake_runpod(monkeypatch)

    # Patch wait_for_pod_exit + final_spend on tools.run_preflight.
    from tools import run_preflight as rp

    async def _exit_now(pod_id: str, *, timeout_s: int) -> str:
        return "EXITED"

    spend_seq = iter([0.40, 0.85, 0.20, 0.20, 0.20])

    async def _spend() -> float:
        try:
            return next(spend_seq)
        except StopIteration:
            return 0.0

    monkeypatch.setattr(rp, "_wait_for_pod_exit", _exit_now)
    monkeypatch.setattr(rp, "_final_spend", _spend)
    return {"tmp": tmp_path, "tracker": tracker}


def test_e2e_bootstrap_then_smoke_passes(e2e_env: dict[str, Any]) -> None:
    """Pass-path: bootstrap pod EXITED, smoke pod EXITED with synthetic
    rsynced results, every D-25 sub-criterion True, smoke_verdict.pass True.
    """
    from tools import run_preflight as rp

    # Step 1: bootstrap.
    rc1 = rp.main(["--mode", "bootstrap"])
    assert rc1 == 0, "bootstrap should pass with mocked SDK"
    boot_calls = e2e_env["tracker"]["create_calls"]
    assert len(boot_calls) == 1
    assert boot_calls[0]["env"].get("BOOTSTRAP_MODE") == "1"
    assert boot_calls[0]["env"]["GATE"] == "bootstrap"

    # Step 2: synthesize what the smoke pod would have rsynced.
    results_dir = e2e_env["tmp"] / "results"
    _synthesize_smoke_results(results_dir)

    # Step 3: smoke.
    rc2 = rp.main(["--mode", "smoke"])
    assert rc2 == 0, "smoke should pass with synthetic results + mocked SDK"
    all_calls = e2e_env["tracker"]["create_calls"]
    assert len(all_calls) == 2, "smoke should have created a second pod"
    assert all_calls[1]["env"]["GATE"] == "smoke"
    assert all_calls[1]["env"].get("BOOTSTRAP_MODE") is None, (
        "smoke pod must NOT inherit BOOTSTRAP_MODE"
    )

    # Verify session manifests. The two runs may collide on session_id (same
    # UTC second granularity), so just assert >=1 manifest exists and the
    # most recent one matches the mode of the most recent run (smoke).
    sessions = sorted((results_dir / "preflight").glob("*.json"))
    assert len(sessions) >= 1
    smoke_sess = json.loads(sessions[-1].read_text())
    assert smoke_sess["mode"] == "smoke"
    v = smoke_sess["gates"][0]["smoke_verdict"]
    assert v["pass"] is True, v
    for k in (
        "a_5_rows",
        "b_under_30min",
        "c_under_1usd",
        "d_per_stage_timings",
        "e_env_sidecar",
        "f_audit_clean",
    ):
        assert v[k] is True, f"D-25 criterion {k} False: {v}"


def test_e2e_smoke_fails_loud_when_results_missing(e2e_env: dict[str, Any]) -> None:
    """Fail-path: bootstrap + smoke without synthesizing results -> verdict
    fails-loud (no JSONL found / a_5_rows False).
    """
    from tools import run_preflight as rp

    rc1 = rp.main(["--mode", "bootstrap"])
    assert rc1 == 0
    rp.main(["--mode", "smoke"])
    results_dir = e2e_env["tmp"] / "results"
    sessions = sorted((results_dir / "preflight").glob("*.json"))
    smoke_sess = json.loads(sessions[-1].read_text())
    v = smoke_sess["gates"][0].get("smoke_verdict", {})
    assert v.get("pass") is False
    # Either the validator reports the missing JSONL explicitly, or it falls
    # through with a_5_rows False.
    assert v.get("error") == "no JSONL found" or v.get("a_5_rows") is False


def test_e2e_bootstrap_does_not_create_results_dirs(e2e_env: dict[str, Any]) -> None:
    """Bootstrap-only run: no gate result dirs are created (the bootstrap pod
    produces no result rows; only the session manifest dir exists).
    """
    from tools import run_preflight as rp

    rc = rp.main(["--mode", "bootstrap"])
    assert rc == 0
    results_dir = e2e_env["tmp"] / "results"
    existing = sorted(p.name for p in results_dir.iterdir())
    assert existing == ["preflight"], f"bootstrap should not create gate dirs; got {existing}"
