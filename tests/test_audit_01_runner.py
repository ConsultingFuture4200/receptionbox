"""AUDIT-01 co-residency runner tests (plan 03-05 Task 1).

All tests drive AUDIT01Runner against `_StubSubstrate` — no GPU, no
HTTP, no real nvidia-smi binary. nvidia-smi is monkeypatched at the
`subprocess.run` call site to control parse behavior + fault injection.
"""

from __future__ import annotations

import pathlib
import subprocess

import pytest

from gates.audit_01.runner import AUDIT01Runner, _parse_nvidia_smi_csv
from substrate._stub import _StubSubstrate


@pytest.fixture()
def manifest_csv(tmp_path: pathlib.Path) -> pathlib.Path:
    p = tmp_path / "manifest.csv"
    p.write_text("asset_id,corpus,path\nfake-1,test,/dev/null\n")
    return p


def _stubbed_nvidia_smi_success(*_args, **_kwargs):
    """Replacement for subprocess.run returning a CompletedProcess clone."""

    class _R:
        returncode = 0
        stdout = "22000, 81920, 35"
        stderr = ""

    return _R()


async def _nosleep(*_a, **_kw):
    """Zero-duration sleep used to monkeypatch out the inter-sample wait."""
    return None


def _make_runner(tmp_path: pathlib.Path, manifest_csv: pathlib.Path) -> AUDIT01Runner:
    return AUDIT01Runner(
        substrate=_StubSubstrate(),
        asset_manifest_path=manifest_csv,
        results_dir=tmp_path,
    )


# ---------------------------------------------------------------------------
# Test 1: 60s / 10s = 6 samples; metrics.vram_mb populated.
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_run_all_emits_one_row_per_sample_with_vram_populated(
    tmp_path: pathlib.Path,
    manifest_csv: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("gates.audit_01.runner._subprocess_run", _stubbed_nvidia_smi_success)
    # Avoid the inter-sample sleep dominating the test runtime.
    monkeypatch.setattr("gates.audit_01.runner.asyncio.sleep", _nosleep)

    runner = _make_runner(tmp_path, manifest_csv)
    await runner.start()
    results = await runner.run_all([{"duration_s": 60, "sample_interval_s": 10}])

    assert len(results) == 6
    for r in results:
        assert r.metrics["vram_mb"] == 22000
        assert r.metrics["vram_total_mb"] == 81920
        assert r.metrics["gpu_util_pct"] == 35
        assert r.metrics["error"] is None


# ---------------------------------------------------------------------------
# Test 2: all_4_models_resident True iff stt + llm + tts all loaded.
# _StubSubstrate has only the 3-key _loaded; after load_*() all three True.
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_all_4_models_resident_true_when_substrate_fully_loaded(
    tmp_path: pathlib.Path,
    manifest_csv: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("gates.audit_01.runner._subprocess_run", _stubbed_nvidia_smi_success)
    monkeypatch.setattr("gates.audit_01.runner.asyncio.sleep", _nosleep)

    runner = _make_runner(tmp_path, manifest_csv)
    await runner.start()
    results = await runner.run_all([{"duration_s": 10, "sample_interval_s": 10}])

    assert len(results) == 1
    assert results[0].metrics["all_4_models_resident"] is True


@pytest.mark.asyncio
async def test_all_4_models_resident_false_when_llm_unloaded(
    tmp_path: pathlib.Path,
    manifest_csv: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("gates.audit_01.runner._subprocess_run", _stubbed_nvidia_smi_success)
    monkeypatch.setattr("gates.audit_01.runner.asyncio.sleep", _nosleep)

    sub = _StubSubstrate()
    runner = AUDIT01Runner(
        substrate=sub,
        asset_manifest_path=manifest_csv,
        results_dir=tmp_path,
    )
    await runner.start()
    # Simulate a degraded substrate — LLM dropped offline mid-run.
    sub._loaded["llm"] = False
    results = await runner.run_all([{"duration_s": 10, "sample_interval_s": 10}])

    assert results[0].metrics["all_4_models_resident"] is False


# ---------------------------------------------------------------------------
# Test 3: nvidia-smi CSV parse — "22000, 81920, 35" → integers.
# ---------------------------------------------------------------------------
def test_parse_nvidia_smi_csv_extracts_three_integers() -> None:
    parsed = _parse_nvidia_smi_csv("22000, 81920, 35")
    assert parsed == {"vram_mb": 22000, "vram_total_mb": 81920, "gpu_util_pct": 35}


def test_parse_nvidia_smi_csv_raises_on_malformed_input() -> None:
    with pytest.raises(ValueError):
        _parse_nvidia_smi_csv("garbage")


# ---------------------------------------------------------------------------
# Test 4: nvidia-smi unavailable → graceful degradation, no crash.
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_nvidia_smi_unavailable_emits_null_vram_with_error_message(
    tmp_path: pathlib.Path,
    manifest_csv: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _boom(*_args, **_kwargs):
        raise FileNotFoundError("[Errno 2] No such file or directory: 'nvidia-smi'")

    monkeypatch.setattr("gates.audit_01.runner._subprocess_run", _boom)
    monkeypatch.setattr("gates.audit_01.runner.asyncio.sleep", _nosleep)

    runner = _make_runner(tmp_path, manifest_csv)
    await runner.start()
    results = await runner.run_all([{"duration_s": 10, "sample_interval_s": 10}])

    assert len(results) == 1
    m = results[0].metrics
    assert m["vram_mb"] is None
    assert m["vram_total_mb"] is None
    assert m["gpu_util_pct"] is None
    assert m["error"] is not None
    assert "FileNotFoundError" in m["error"]
    # Crucially: status is still "ok" — the run completed, we just have null VRAM.
    assert results[0].status == "ok"


@pytest.mark.asyncio
async def test_nvidia_smi_called_process_error_does_not_abort_run(
    tmp_path: pathlib.Path,
    manifest_csv: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _calledprocess(*_args, **_kwargs):
        raise subprocess.CalledProcessError(returncode=9, cmd=["nvidia-smi"])

    monkeypatch.setattr("gates.audit_01.runner._subprocess_run", _calledprocess)
    monkeypatch.setattr("gates.audit_01.runner.asyncio.sleep", _nosleep)

    runner = _make_runner(tmp_path, manifest_csv)
    await runner.start()
    results = await runner.run_all([{"duration_s": 30, "sample_interval_s": 10}])

    assert len(results) == 3
    for r in results:
        assert r.status == "ok"
        assert r.metrics["vram_mb"] is None
        assert "CalledProcessError" in r.metrics["error"]


# ---------------------------------------------------------------------------
# Bonus: interval validation guards against div-by-zero.
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_run_all_raises_on_zero_interval(
    tmp_path: pathlib.Path, manifest_csv: pathlib.Path
) -> None:
    runner = _make_runner(tmp_path, manifest_csv)
    await runner.start()
    with pytest.raises(ValueError):
        await runner.run_all([{"duration_s": 60, "sample_interval_s": 0}])
