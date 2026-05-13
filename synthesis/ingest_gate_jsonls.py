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


def main() -> int:
    df = load_all()
    out_dir = pathlib.Path("results/synthesis")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "measurements.csv"
    df.to_csv(out_path, index=False)
    print(f"[ingest] {len(df)} rows -> {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
