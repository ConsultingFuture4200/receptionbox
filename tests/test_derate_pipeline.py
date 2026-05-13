"""Plan 03-07 Task 2 named tests for synthesis.derate_pipeline.

Covers the four explicit behaviors from the plan:
  1. ingest -> DataFrame with REPRO-03 + per-stage columns + run_id
  2. derate.run() -> per-(gate,stage,concurrency) bucket table with bootstrap CI columns
  3. Ollama overhead is derived from results/audit_03/*.jsonl (or default 1.4 when absent)
  4. scipy.stats.bootstrap is invoked with n_resamples=10000, conf=0.95, method='percentile'

Behaviors 1/2 are already covered breadth-first by tests/test_synthesis_scaffold.py.
This module concentrates on the AUDIT-03 ingestion path (behavior 3) and the bootstrap
configuration assertion (behavior 4) per the plan's explicit Task 2 checklist.
"""

from __future__ import annotations

import json
import pathlib
from unittest import mock

import numpy as np
import pandas as pd
import pytest

from synthesis.derate_pipeline import (
    BOOTSTRAP_CONFIDENCE,
    BOOTSTRAP_N_RESAMPLES,
    _bootstrap_ci,
    _measure_ollama_overhead,
    run,
)


# ---------------------------------------------------------------------------
# Behavior 3: AUDIT-03 ollama-overhead loading
# ---------------------------------------------------------------------------
def _write_audit03_fixture(
    root: pathlib.Path,
    vllm_tps: list[float],
    ollama_tps: list[float],
) -> pathlib.Path:
    """Seed `root/audit_03/sample.jsonl` with engine-discriminated rows."""
    audit_dir = root / "audit_03"
    audit_dir.mkdir(parents=True, exist_ok=True)
    rows: list[dict] = []
    for tps in vllm_tps:
        rows.append({"metrics": {"engine_kind": "vllm", "tokens_per_sec": tps}})
    for tps in ollama_tps:
        rows.append({"metrics": {"engine_kind": "ollama", "tokens_per_sec": tps}})
    (audit_dir / "sample.jsonl").write_text("\n".join(json.dumps(r) for r in rows) + "\n")
    return audit_dir


def test_ollama_overhead_from_audit03_uses_median_ratio(tmp_path: pathlib.Path) -> None:
    audit_dir = _write_audit03_fixture(
        tmp_path,
        vllm_tps=[100.0, 110.0, 120.0],  # median 110
        ollama_tps=[70.0, 80.0, 90.0],  # median 80
    )
    factor = _measure_ollama_overhead(audit_dir)
    assert factor == pytest.approx(110.0 / 80.0, rel=1e-9)


def test_ollama_overhead_missing_audit03_dir_returns_none(tmp_path: pathlib.Path) -> None:
    assert _measure_ollama_overhead(tmp_path / "nonexistent") is None


def test_ollama_overhead_missing_one_engine_returns_none(tmp_path: pathlib.Path) -> None:
    audit_dir = _write_audit03_fixture(tmp_path, vllm_tps=[100.0], ollama_tps=[])
    assert _measure_ollama_overhead(audit_dir) is None


# ---------------------------------------------------------------------------
# Behavior 4: scipy.stats.bootstrap configured per CLAUDE.md §10
# ---------------------------------------------------------------------------
def test_bootstrap_uses_required_parameters() -> None:
    """The bootstrap helper must call scipy.stats.bootstrap with n=10000, conf=0.95, percentile."""
    assert BOOTSTRAP_N_RESAMPLES == 10_000
    assert BOOTSTRAP_CONFIDENCE == 0.95

    samples = np.array([10.0, 11.0, 12.0, 13.0, 14.0, 15.0])
    with mock.patch("synthesis.derate_pipeline.stats.bootstrap") as mocked:
        # Need a return whose `.confidence_interval.low/.high` is numeric
        ci = mock.Mock()
        ci.confidence_interval.low = 10.5
        ci.confidence_interval.high = 14.5
        mocked.return_value = ci
        _bootstrap_ci(samples)
        assert mocked.call_count == 1
        kwargs = mocked.call_args.kwargs
        assert kwargs["n_resamples"] == BOOTSTRAP_N_RESAMPLES
        assert kwargs["confidence_level"] == BOOTSTRAP_CONFIDENCE
        assert kwargs["method"] == "percentile"


def test_bootstrap_singleton_falls_back_without_calling_scipy() -> None:
    """n<2 falls back to (val, val, val); scipy is not invoked."""
    with mock.patch("synthesis.derate_pipeline.stats.bootstrap") as mocked:
        point, lo, hi = _bootstrap_ci(np.array([42.0]))
        assert point == lo == hi == 42.0
        mocked.assert_not_called()


# ---------------------------------------------------------------------------
# Behavior 1/2 lightweight reconfirmation (column shape on minimal frame)
# ---------------------------------------------------------------------------
def test_run_minimal_frame_emits_expected_columns() -> None:
    df = pd.DataFrame(
        {
            "gate": ["g1"] * 4,
            "concurrency": [1] * 4,
            "stt_ttft_ms": [100.0, 110.0, 105.0, 108.0],
            "llm_ttft_ms": [80.0, 85.0, 82.0, 84.0],
            "llm_decode_ms_per_tok": [8.0, 9.0, 7.5, 8.5],
            "tts_first_audio_ms": [50.0, 55.0, 52.0, 53.0],
        }
    )
    out = run(df)
    assert set(out["stage"]) == {"stt_ttft", "llm_ttft", "llm_decode", "tts_first_audio"}
    for col in (
        "measured_h100_p50_ms",
        "derated_orin_point_ms",
        "derated_orin_ci_lo_ms",
        "derated_orin_ci_hi_ms",
    ):
        assert col in out.columns
    # CI monotone
    assert (out["derated_orin_ci_lo_ms"] <= out["derated_orin_point_ms"]).all()
    assert (out["derated_orin_point_ms"] <= out["derated_orin_ci_hi_ms"]).all()
