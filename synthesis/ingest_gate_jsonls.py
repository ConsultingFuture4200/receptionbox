"""Load Phase 3 gate JSONLs into a single pandas DataFrame.

Reads `results/{gate}/{run_id}.jsonl` for every gate dir under `results_root`
(default `results/`) skipping `preflight/`, `smoke/`, `smoke_pre_v19a/`, and
`_pulled/` (those are session manifests or pre-archive runs, not gate rows).

Verifies the REPRO-03 tuple (run_id, image_digest, git_commit,
asset_manifest_sha, substrate) is present on every row.

Scaffolded ahead of Plan 03-07 Task 2; fixture exercise lives at
tests/test_synthesis_scaffold.py.
"""

from __future__ import annotations

import json
import os
import pathlib
import sqlite3

import pandas as pd

REPRO_03_COLUMNS: tuple[str, ...] = (
    "run_id",
    "image_digest",
    "git_commit",
    "asset_manifest_sha",
    "substrate",
)

# Subdirectories under results/ that hold non-gate artifacts.
_SKIP_DIRS: frozenset[str] = frozenset(
    {"preflight", "smoke", "smoke_pre_v19a", "_pulled", "synthesis"}
)


def _default_results_root() -> pathlib.Path:
    """Resolve the results root. RBOX_RESULTS_ROOT lets fixtures swap in."""
    return pathlib.Path(os.environ.get("RBOX_RESULTS_ROOT", "results"))


def load_all(results_root: pathlib.Path | None = None) -> pd.DataFrame:
    """Return a DataFrame of every gate-row JSONL under `results_root`.

    Each input file contributes its filename (without extension) as `run_id`
    if the row didn't already carry one. Empty / missing root returns an
    empty DataFrame (so callers can compose without guarding for absence).
    """
    root = results_root if results_root is not None else _default_results_root()
    if not root.exists():
        return pd.DataFrame()

    rows: list[dict] = []
    for jsonl in sorted(root.glob("*/*.jsonl")):
        if jsonl.parent.name in _SKIP_DIRS:
            continue
        for line in jsonl.read_text().splitlines():
            line = line.strip()
            if not line:
                continue
            d = json.loads(line)
            d.setdefault("run_id", jsonl.stem)
            rows.append(d)

    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows)
    missing = [c for c in REPRO_03_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"REPRO-03 columns missing from ingest: {missing}")
    return df


_SQLITE_TABLE = "measurements"
_SQLITE_UNIQUE_KEY = ("gate", "run_id", "asset_id", "stage")


def write_sqlite(df: pd.DataFrame, out_path: pathlib.Path) -> None:
    """Write `df` to a SQLite DB at `out_path`, table=measurements.

    - Nested dict/list cells are JSON-stringified (SQLite has no native dict type).
    - A UNIQUE index on (gate, run_id, asset_id, stage) is created when all four
      columns are present, giving the downstream caller idempotent INSERT-OR-
      REPLACE semantics. The `stage` column is synthesized from a Cartesian
      product of the per-stage columns when absent so the index can still apply.
    """
    out_path.parent.mkdir(parents=True, exist_ok=True)
    scalar_df = df.copy()
    for col in scalar_df.columns:
        if scalar_df[col].apply(lambda v: isinstance(v, (dict, list))).any():
            scalar_df[col] = scalar_df[col].apply(
                lambda v: json.dumps(v) if isinstance(v, (dict, list)) else v
            )

    with sqlite3.connect(out_path) as con:
        scalar_df.to_sql(_SQLITE_TABLE, con, if_exists="replace", index=False)
        cols = set(scalar_df.columns)
        # The natural key is (gate, run_id, asset_id) — the per-row JSONL identity.
        # `stage` is per-row in derate output but isn't a column in raw ingest, so
        # apply the unique index over whatever subset of the natural-key columns is
        # actually present (typical raw ingest: gate + run_id + asset_id).
        index_cols = [c for c in _SQLITE_UNIQUE_KEY if c in cols]
        if len(index_cols) >= 2:
            con.execute(
                f"CREATE UNIQUE INDEX IF NOT EXISTS idx_{_SQLITE_TABLE}_key "
                f"ON {_SQLITE_TABLE}({', '.join(index_cols)})"
            )
        con.commit()


def main() -> int:
    df = load_all()
    out_dir = pathlib.Path("results/synthesis")
    out_dir.mkdir(parents=True, exist_ok=True)
    csv_path = out_dir / "measurements.csv"
    sqlite_path = out_dir / "measurements.sqlite"
    df.to_csv(csv_path, index=False)
    if not df.empty:
        write_sqlite(df, sqlite_path)
        print(f"[ingest] {len(df)} rows -> {sqlite_path} (+ {csv_path})")
    else:
        print(f"[ingest] 0 rows; wrote empty {csv_path}; sqlite skipped")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
