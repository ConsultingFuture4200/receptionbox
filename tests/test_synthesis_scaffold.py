"""End-to-end synthesis-pipeline scaffolding test against synthetic fixtures.

Generates a results root with realistic-shape gate JSONLs, runs ingest +
derate, and asserts the output table covers every (gate, stage, concurrency)
bucket with bootstrap CIs. Scaffolded ahead of Plan 03-07 Task 2 so the
shape is locked before W2/W3 measurements land.
"""

from __future__ import annotations

import pathlib

import pandas as pd
import pytest

from synthesis.derate_pipeline import run as derate_run
from synthesis.ingest_gate_jsonls import REPRO_03_COLUMNS, load_all
from tests.fixtures.synthetic_gate_results import seed_results_dir


@pytest.fixture
def fixture_results_root(tmp_path: pathlib.Path) -> pathlib.Path:
    seed_results_dir(
        tmp_path,
        gates=("g1", "g2", "g5"),
        concurrencies=(1, 2, 4),
        rows_per_run=20,
        seed=42,
    )
    return tmp_path


def test_ingest_loads_every_gate_row(fixture_results_root: pathlib.Path) -> None:
    df = load_all(fixture_results_root)
    # 3 gates * 3 concurrencies * 20 rows = 180 rows
    assert len(df) == 180
    for col in REPRO_03_COLUMNS:
        assert col in df.columns, f"REPRO-03 column missing: {col}"
    assert set(df["gate"].unique()) == {"g1", "g2", "g5"}
    assert set(df["concurrency"].unique()) == {1, 2, 4}


def test_ingest_empty_root_returns_empty_frame(tmp_path: pathlib.Path) -> None:
    df = load_all(tmp_path)
    assert df.empty


def test_ingest_skips_preflight_and_smoke_dirs(tmp_path: pathlib.Path) -> None:
    """Non-gate dirs under results/ must NOT pollute the ingest."""
    (tmp_path / "smoke").mkdir()
    (tmp_path / "smoke" / "decoy.jsonl").write_text('{"foo":"bar"}\n')
    (tmp_path / "preflight").mkdir()
    (tmp_path / "preflight" / "decoy.jsonl").write_text('{"foo":"bar"}\n')
    # Real gate dir with proper rows
    seed_results_dir(tmp_path, gates=("g1",), concurrencies=(1,), rows_per_run=3, seed=1)
    df = load_all(tmp_path)
    assert len(df) == 3
    assert "foo" not in df.columns  # decoy didn't land


def test_derate_produces_bucket_per_stage_concurrency(
    fixture_results_root: pathlib.Path,
) -> None:
    df = load_all(fixture_results_root)
    out = derate_run(df)
    # 3 gates * 4 stages * 3 concurrencies = 36 buckets
    assert len(out) == 36
    expected_cols = {
        "gate",
        "stage",
        "concurrency",
        "n_samples",
        "measured_h100_p50_ms",
        "derated_orin_point_ms",
        "derated_orin_ci_lo_ms",
        "derated_orin_ci_hi_ms",
        "ollama_overhead_applied",
        "arm_penalty_applied",
    }
    assert expected_cols.issubset(set(out.columns))


def test_derate_ci_bounds_monotone(fixture_results_root: pathlib.Path) -> None:
    """For every bucket, ci_lo <= point <= ci_hi must hold."""
    df = load_all(fixture_results_root)
    out = derate_run(df)
    lo = out["derated_orin_ci_lo_ms"]
    pt = out["derated_orin_point_ms"]
    hi = out["derated_orin_ci_hi_ms"]
    assert (lo <= pt).all()
    assert (pt <= hi).all()


def test_derate_llm_stages_carry_ollama_overhead(
    fixture_results_root: pathlib.Path,
) -> None:
    df = load_all(fixture_results_root)
    out = derate_run(df, ollama_overhead=1.42, arm_penalty=1.15)
    llm = out[out["stage"].isin(["llm_ttft", "llm_decode"])]
    other = out[~out["stage"].isin(["llm_ttft", "llm_decode"])]
    assert (llm["ollama_overhead_applied"] == 1.42).all()
    assert (other["ollama_overhead_applied"] == 1.0).all()


def test_derate_empty_df_returns_empty_with_full_schema() -> None:
    out = derate_run(pd.DataFrame())
    assert out.empty
    assert "derated_orin_point_ms" in out.columns
