"""Plan 03-07b Task 1 tests: SQLite emission in synthesis.ingest_gate_jsonls.

Covers the 4 named behaviors from the sub-plan:
  1. main() writes results/synthesis/measurements.sqlite with N=row-count rows
  2. Schema includes the REPRO-03 / per-row identity columns
  3. Idempotent re-ingest: running main() twice -> stable row count via UNIQUE index
  4. Parity: rows present in CSV are present in SQLite with matching scalar columns
"""

from __future__ import annotations

import pathlib
import sqlite3

import pandas as pd
import pytest

from synthesis.ingest_gate_jsonls import _SQLITE_TABLE, write_sqlite
from tests.fixtures.synthetic_gate_results import seed_results_dir


@pytest.fixture
def fixture_results(tmp_path: pathlib.Path) -> pathlib.Path:
    seed_results_dir(
        tmp_path,
        gates=("g1", "g2"),
        concurrencies=(1, 2),
        rows_per_run=5,
        seed=7,
    )
    return tmp_path


def _ingest_df(results_root: pathlib.Path) -> pd.DataFrame:
    from synthesis.ingest_gate_jsonls import load_all

    return load_all(results_root)


# ---------------------------------------------------------------------------
# Behavior 1: row count matches DataFrame on disk
# ---------------------------------------------------------------------------
def test_sqlite_row_count_matches_ingested_df(
    tmp_path: pathlib.Path, fixture_results: pathlib.Path
) -> None:
    df = _ingest_df(fixture_results)
    out = tmp_path / "measurements.sqlite"
    write_sqlite(df, out)
    with sqlite3.connect(out) as con:
        count = con.execute(f"SELECT COUNT(*) FROM {_SQLITE_TABLE}").fetchone()[0]
    # 2 gates * 2 concurrencies * 5 rows = 20
    assert count == 20
    assert count == len(df)


# ---------------------------------------------------------------------------
# Behavior 2: schema includes REPRO-03 + identity columns
# ---------------------------------------------------------------------------
def test_sqlite_schema_includes_repro03_columns(
    tmp_path: pathlib.Path, fixture_results: pathlib.Path
) -> None:
    df = _ingest_df(fixture_results)
    out = tmp_path / "measurements.sqlite"
    write_sqlite(df, out)
    with sqlite3.connect(out) as con:
        cols = {row[1] for row in con.execute(f"PRAGMA table_info({_SQLITE_TABLE})").fetchall()}
    required = {
        "gate",
        "run_id",
        "asset_id",
        "substrate",
        "image_digest",
        "git_commit",
        "concurrency",
    }
    assert required.issubset(cols), f"Missing REPRO-03 columns: {required - cols}"


# ---------------------------------------------------------------------------
# Behavior 3: idempotent re-ingest via UNIQUE index
# ---------------------------------------------------------------------------
def test_sqlite_unique_index_on_natural_key(
    tmp_path: pathlib.Path, fixture_results: pathlib.Path
) -> None:
    df = _ingest_df(fixture_results)
    out = tmp_path / "measurements.sqlite"
    write_sqlite(df, out)
    with sqlite3.connect(out) as con:
        indices = con.execute(
            f"SELECT name, sql FROM sqlite_master "
            f"WHERE type='index' AND tbl_name='{_SQLITE_TABLE}' AND sql IS NOT NULL"
        ).fetchall()
    # We expect at least one UNIQUE index named idx_measurements_key with
    # at minimum (gate, run_id, asset_id) participating.
    unique_idx = [(n, s) for n, s in indices if "UNIQUE" in (s or "") and "idx_measurements" in n]
    assert unique_idx, "Expected at least one UNIQUE index on the measurements table"
    idx_sql = unique_idx[0][1]
    for col in ("gate", "run_id", "asset_id"):
        assert col in idx_sql, f"UNIQUE index missing column {col}: {idx_sql}"


def test_sqlite_idempotent_rewrite(tmp_path: pathlib.Path, fixture_results: pathlib.Path) -> None:
    """Calling write_sqlite twice with the same df must yield the same row count."""
    df = _ingest_df(fixture_results)
    out = tmp_path / "measurements.sqlite"
    write_sqlite(df, out)
    with sqlite3.connect(out) as con:
        first_count = con.execute(f"SELECT COUNT(*) FROM {_SQLITE_TABLE}").fetchone()[0]
    # Second write: replaces table content. UNIQUE index re-created via IF NOT EXISTS.
    write_sqlite(df, out)
    with sqlite3.connect(out) as con:
        second_count = con.execute(f"SELECT COUNT(*) FROM {_SQLITE_TABLE}").fetchone()[0]
    assert first_count == second_count == 20


# ---------------------------------------------------------------------------
# Behavior 4: CSV/SQLite parity on scalar columns
# ---------------------------------------------------------------------------
def test_csv_and_sqlite_parity(tmp_path: pathlib.Path, fixture_results: pathlib.Path) -> None:
    df = _ingest_df(fixture_results)
    sqlite_out = tmp_path / "measurements.sqlite"
    write_sqlite(df, sqlite_out)
    with sqlite3.connect(sqlite_out) as con:
        sql_df = pd.read_sql(f"SELECT * FROM {_SQLITE_TABLE}", con)
    # Scalar identity columns must be byte-for-byte equal between csv-source
    # df and sqlite-read df after sorting on the natural key.
    keys = ["gate", "run_id", "asset_id"]
    df_sorted = df.sort_values(keys).reset_index(drop=True)
    sql_sorted = sql_df.sort_values(keys).reset_index(drop=True)
    for col in ("gate", "run_id", "asset_id", "substrate", "image_digest", "git_commit"):
        assert df_sorted[col].astype(str).tolist() == sql_sorted[col].astype(str).tolist(), (
            f"Parity mismatch on column {col}"
        )
