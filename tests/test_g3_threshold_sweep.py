"""G3 threshold sweep tests (Plan 03-02 Task 1).

Verifies that G3Runner emits one result row per (asset, threshold_ms) pair
when configured with a `threshold_ms_list`. Mirrors the test_gate_runners.py
fixture conventions so this file can run alongside the existing suite
without conflicts.
"""

from __future__ import annotations

import pathlib
import wave

import pytest

from gates.g3.runner import DEFAULT_THRESHOLDS_MS, G3Runner
from substrate._stub import _StubSubstrate


@pytest.fixture()
def manifest_csv(tmp_path: pathlib.Path) -> pathlib.Path:
    p = tmp_path / "manifest.csv"
    p.write_text("asset_id,corpus,path\nfake-1,test,/dev/null\n")
    return p


@pytest.fixture()
def silence_wav(tmp_path: pathlib.Path) -> pathlib.Path:
    out = tmp_path / "silence_1s.wav"
    with wave.open(str(out), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(16000)
        w.writeframes(b"\x00\x00" * 16000)
    return out


@pytest.mark.asyncio
async def test_threshold_sweep_emits_one_row_per_threshold(
    tmp_path: pathlib.Path, manifest_csv: pathlib.Path, silence_wav: pathlib.Path
) -> None:
    """Behavior 1: 3-threshold list x 1 asset → 3 rows. FP follows
    `threshold_ms < gt_endpoint_ms` semantics."""
    runner = G3Runner(
        substrate=_StubSubstrate(),
        threshold_ms_list=[400, 800, 1500],
        asset_manifest_path=manifest_csv,
        results_dir=tmp_path,
    )
    await runner.start()
    asset = {
        "asset_id": "hes-sweep",
        "path": str(silence_wav),
        "gt_endpoint_ms": "1200",
        "hesitation_pattern": "filler_words",
    }
    rows = await runner.run_all([asset])
    assert len(rows) == 3
    by_threshold = {r.metrics["threshold_ms"]: r for r in rows}
    assert set(by_threshold) == {400, 800, 1500}
    # gt=1200; threshold-aware FP: threshold < gt.
    assert by_threshold[400].metrics["false_positive"] is True  # 400 < 1200
    assert by_threshold[800].metrics["false_positive"] is True  # 800 < 1200
    assert by_threshold[1500].metrics["false_positive"] is False  # 1500 >= 1200
    # All rows carry the substrate's detected endpoint (stub yields end_ms=1000).
    for r in rows:
        assert r.metrics["detected_endpoint_ms"] == 1000.0
        assert r.metrics["gt_endpoint_ms"] == 1200.0
        assert r.metrics["hesitation_pattern"] == "filler_words"
    # asset_id is suffixed with _t{threshold} to keep JSONL rows distinguishable.
    assert {r.asset_id for r in rows} == {"hes-sweep_t400", "hes-sweep_t800", "hes-sweep_t1500"}


@pytest.mark.asyncio
async def test_default_threshold_list_is_12_step_100ms_sweep(
    tmp_path: pathlib.Path, manifest_csv: pathlib.Path, silence_wav: pathlib.Path
) -> None:
    """Behavior 2: Default `threshold_ms_list` is the SM-69 12-threshold
    sweep (400..1500 step 100). One asset → 12 rows."""
    assert DEFAULT_THRESHOLDS_MS == (
        400,
        500,
        600,
        700,
        800,
        900,
        1000,
        1100,
        1200,
        1300,
        1400,
        1500,
    )
    runner = G3Runner(
        substrate=_StubSubstrate(),
        asset_manifest_path=manifest_csv,
        results_dir=tmp_path,
    )
    await runner.start()
    asset = {
        "asset_id": "hes-default",
        "path": str(silence_wav),
        "gt_endpoint_ms": "1000",
        "hesitation_pattern": "trailing_off",
    }
    rows = await runner.run_all([asset])
    assert len(rows) == 12
    seen_thresholds = {r.metrics["threshold_ms"] for r in rows}
    assert seen_thresholds == set(DEFAULT_THRESHOLDS_MS)


@pytest.mark.asyncio
async def test_single_threshold_value_is_backward_compatible(
    tmp_path: pathlib.Path, manifest_csv: pathlib.Path, silence_wav: pathlib.Path
) -> None:
    """Behavior 3: `threshold_ms_list=[800]` → 1 row per asset, matching the
    pre-sweep G3Runner shape that test_gate_runners.py was written against."""
    runner = G3Runner(
        substrate=_StubSubstrate(),
        threshold_ms_list=[800],
        asset_manifest_path=manifest_csv,
        results_dir=tmp_path,
    )
    await runner.start()
    asset = {
        "asset_id": "hes-single",
        "path": str(silence_wav),
        "gt_endpoint_ms": "500",
        "hesitation_pattern": "filler_words",
    }
    [r] = await runner.run_all([asset])
    assert r.status == "ok"
    assert r.metrics["threshold_ms"] == 800
    # gt=500, threshold=800: 800 < 500 is False → not a FP.
    assert r.metrics["false_positive"] is False


@pytest.mark.asyncio
async def test_threshold_sweep_rows_carry_full_repro_tuple(
    tmp_path: pathlib.Path, manifest_csv: pathlib.Path, silence_wav: pathlib.Path
) -> None:
    """Behavior 4: Every emitted row carries the full REPRO-03 tuple
    (run_id, image_digest, model_shas, git_commit, asset_manifest_sha,
    timestamp_utc, substrate) via build_result()."""
    runner = G3Runner(
        substrate=_StubSubstrate(),
        threshold_ms_list=[400, 1500],
        asset_manifest_path=manifest_csv,
        results_dir=tmp_path,
    )
    await runner.start()
    asset = {
        "asset_id": "hes-repro",
        "path": str(silence_wav),
        "gt_endpoint_ms": "1000",
        "hesitation_pattern": "trailing_off",
    }
    rows = await runner.run_all([asset])
    assert len(rows) == 2
    for r in rows:
        assert r.run_id == runner.run_id
        assert r.image_digest  # set by build_result via _env_fp
        assert r.model_shas
        assert r.git_commit
        assert r.asset_manifest_sha
        assert r.timestamp_utc is not None
        assert r.substrate == "cuda"


@pytest.mark.asyncio
async def test_threshold_sweep_runs_substrate_once_per_asset(
    tmp_path: pathlib.Path, manifest_csv: pathlib.Path, silence_wav: pathlib.Path
) -> None:
    """Efficiency invariant: the substrate.transcribe call must run exactly
    once per asset regardless of len(threshold_ms_list). Each threshold row
    is a re-tag of the same substrate-derived detected_endpoint_ms.
    Guards against accidentally re-transcribing per threshold (would 12x
    the cloud spend on a real H100 run)."""

    class _CountingSubstrate(_StubSubstrate):
        transcribe_calls = 0

        async def transcribe(self, audio, *, sample_rate):
            type(self).transcribe_calls += 1
            async for chunk in super().transcribe(audio, sample_rate=sample_rate):
                yield chunk

    _CountingSubstrate.transcribe_calls = 0
    runner = G3Runner(
        substrate=_CountingSubstrate(),
        threshold_ms_list=list(DEFAULT_THRESHOLDS_MS),  # 12 thresholds
        asset_manifest_path=manifest_csv,
        results_dir=tmp_path,
    )
    await runner.start()
    asset = {
        "asset_id": "hes-once",
        "path": str(silence_wav),
        "gt_endpoint_ms": "900",
        "hesitation_pattern": "trailing_off",
    }
    rows = await runner.run_all([asset])
    assert len(rows) == 12
    assert _CountingSubstrate.transcribe_calls == 1


@pytest.mark.asyncio
async def test_empty_threshold_list_raises(
    tmp_path: pathlib.Path, manifest_csv: pathlib.Path
) -> None:
    """Defensive: empty list is a config error, not silently ignored."""
    with pytest.raises(ValueError, match="threshold_ms_list"):
        G3Runner(
            substrate=_StubSubstrate(),
            threshold_ms_list=[],
            asset_manifest_path=manifest_csv,
            results_dir=tmp_path,
        )


@pytest.mark.asyncio
async def test_missing_gt_endpoint_ms_treated_as_zero(
    tmp_path: pathlib.Path, manifest_csv: pathlib.Path, silence_wav: pathlib.Path
) -> None:
    """Edge case: asset without gt_endpoint_ms still produces N rows
    (gt_endpoint_ms=0.0; FP=False for any threshold since threshold > 0)."""
    runner = G3Runner(
        substrate=_StubSubstrate(),
        threshold_ms_list=[400, 1500],
        asset_manifest_path=manifest_csv,
        results_dir=tmp_path,
    )
    await runner.start()
    asset = {
        "asset_id": "hes-missing-gt",
        "path": str(silence_wav),
        "hesitation_pattern": "trailing_off",
    }
    rows = await runner.run_all([asset])
    assert len(rows) == 2
    for r in rows:
        assert r.metrics["gt_endpoint_ms"] == 0.0
        assert r.metrics["false_positive"] is False


@pytest.mark.asyncio
async def test_transcribe_failure_emits_single_error_row(
    tmp_path: pathlib.Path, manifest_csv: pathlib.Path, silence_wav: pathlib.Path
) -> None:
    """If substrate.transcribe raises, emit ONE error row per asset (not
    N copies — threshold sweep is meaningless without a detected endpoint)."""

    class _BoomSubstrate(_StubSubstrate):
        async def transcribe(self, audio, *, sample_rate):
            raise RuntimeError("substrate exploded")
            if False:  # unreachable; needed so this is an async generator
                yield

    runner = G3Runner(
        substrate=_BoomSubstrate(),
        threshold_ms_list=[400, 800, 1500],
        asset_manifest_path=manifest_csv,
        results_dir=tmp_path,
    )
    await runner.start()
    asset = {
        "asset_id": "hes-boom",
        "path": str(silence_wav),
        "gt_endpoint_ms": "1000",
    }
    rows = await runner.run_all([asset])
    assert len(rows) == 1
    assert rows[0].status == "error"
    assert rows[0].error_kind == "RuntimeError"
