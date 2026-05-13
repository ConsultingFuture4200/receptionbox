---
phase: 03-cloud-derate
plan: 07b
subsystem: synthesis
tags: [sqlite, ingest, idempotent, evidence-pack]

requires:
  - phase: 03-cloud-derate
    provides: synthesis ingest + derate pipeline (03-07)
provides:
  - SQLite emission in synthesis.ingest_gate_jsonls (canonical post-Q3=A)
  - UNIQUE-index-based idempotent re-ingest
  - SQLite-first read path in synthesis.derate_pipeline (CSV fallback retained)
  - Stock-tool queryable evidence pack (sqlite3 / DBeaver / Datasette)
affects: [04-feasibility-memo]

tech-stack:
  added: [stdlib sqlite3 (already in env)]
  patterns:
    - "Write SQLite via pandas.to_sql(if_exists='replace') + manual UNIQUE index for idempotent re-ingest semantics"
    - "Reader prefers SQLite -> CSV -> live ingest, in that order, so the pipeline degrades gracefully across the rollout"

key-files:
  created:
    - tests/test_ingest_sqlite.py
    - results/synthesis/measurements.sqlite
  modified:
    - synthesis/ingest_gate_jsonls.py
    - synthesis/derate_pipeline.py

key-decisions:
  - "Preserve measurements.csv alongside SQLite for one transition cycle: keeps the existing 03-07 evidence path working while operators/downstream tools migrate to the SQLite canonical artifact"
  - "UNIQUE index over the natural-key subset that is actually present (typically gate+run_id+asset_id for raw ingest, gate+run_id+asset_id+stage for post-derate). The flexible-index approach lets the same write_sqlite() helper serve both ingest and derate tables without schema duplication"
  - "Nested dict/list cells JSON-stringified rather than normalized into child tables — keeps the schema flat, queryable from CLI, and avoids over-engineering for a Phase-0 evidence pack"

patterns-established:
  - "write_sqlite(df, path) helper: drop-in for any pandas DataFrame with a natural key — single function, single index strategy, idempotent re-write"

requirements-completed: [DERATE-05]

duration: ~15 min
completed: 2026-05-13
---

# Phase 03 Plan 07b: SQLite Ingest Layer Summary

**SQLite emission added to synthesis.ingest_gate_jsonls:main() with UNIQUE-index-based idempotent re-ingest; derate_pipeline reads SQLite-first with CSV fallback. Canonical evidence pack now queryable from stock sqlite3 CLI / DBeaver / Datasette without a Python kernel.**

## Performance

- **Duration:** ~15 min
- **Started:** 2026-05-13T00:55Z (after 03-07 completion)
- **Completed:** 2026-05-13T01:05Z
- **Tasks:** 2
- **Files modified:** 4 (2 source modules, 1 test module, 1 evidence artifact)

## Accomplishments

- **Task 1 — SQLite emission**: New `write_sqlite()` helper in `synthesis/ingest_gate_jsonls.py` serializes dict/list cells to JSON, writes the DataFrame to a `measurements` table, and creates `CREATE UNIQUE INDEX idx_measurements_key ON measurements(gate, run_id, asset_id)` (flexibly using whatever subset of `(gate, run_id, asset_id, stage)` columns are present). `main()` writes both `measurements.csv` (compat) and `measurements.sqlite` (canonical). 5 tests in `tests/test_ingest_sqlite.py` all pass.
- **Task 2 — derate_pipeline SQLite-first reader**: `synthesis/derate_pipeline.py:main()` now prefers `measurements.sqlite` → `measurements.csv` → live ingest, in that order. End-to-end exercised: delete CSV, derate emits the same 4 buckets from SQLite-only path.

End-to-end re-run produced: 80 rows in `measurements.sqlite` with REPRO-03 columns intact + UNIQUE index. 24/24 tests pass; ruff clean.

## Task Commits

1. **Task 1: SQLite emission + tests** — `191910b` (feat)
2. **Task 2: derate_pipeline SQLite-first reader** — `54aba29` (feat)
3. **Evidence artifact**: `bf505de` (chore)

## Files Created/Modified

| File | Purpose |
|------|---------|
| `synthesis/ingest_gate_jsonls.py` | Added `write_sqlite()` helper + SQLite emission in `main()`; `_SQLITE_TABLE` / `_SQLITE_UNIQUE_KEY` constants exported for tests |
| `synthesis/derate_pipeline.py` | New `_load_measurements()` helper: SQLite-first, CSV fallback, live ingest as last resort |
| `tests/test_ingest_sqlite.py` | 5 tests covering all 4 plan-named behaviors (row count, schema, UNIQUE index + idempotent re-write, CSV/SQLite parity) |
| `results/synthesis/measurements.sqlite` | Canonical evidence artifact: 80 rows with UNIQUE index on (gate, run_id, asset_id) |

## Decisions Made

- **Preserve `measurements.csv` alongside SQLite** for one transition cycle — protects any existing downstream consumer that pre-dates 03-07b. Will retire CSV after Phase 4 confirms it has no live readers.
- **JSON-stringify nested cells rather than normalize into child tables** — Phase 0 evidence pack is queried as a flat table; schema normalization is post-Phase-0 work if at all.
- **Index over the natural-key subset that exists** — keeps `write_sqlite()` reusable for both the raw-ingest table (gate, run_id, asset_id) and any future derate table that adds (..., stage) without schema branching.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] Empty-DataFrame guard in main()**
- **Found during:** Task 1 end-to-end run
- **Issue:** Plan didn't specify behavior when `load_all()` returns an empty DataFrame; calling `write_sqlite(empty_df, ...)` would emit an empty SQLite file with no columns, breaking the schema-check tests.
- **Fix:** `main()` skips the SQLite write when the DataFrame is empty (CSV still written). Avoids creating a degenerate SQLite that downstream readers would fail to inspect cleanly.
- **Files modified:** `synthesis/ingest_gate_jsonls.py`
- **Verification:** end-to-end runs produce a populated SQLite; tests cover the populated path. Empty-input behavior is exercised by the existing scaffold tests (CSV-only).
- **Committed in:** `191910b` (Task 1 commit)

**2. [Rule 1 - Bug] Pre-commit ruff-format auto-reflowed test assertions**
- **Found during:** First commit attempt of Task 1
- **Issue:** Long parity-check assertion in `tests/test_ingest_sqlite.py` exceeded line-length on the implicit-string-concat path; ruff format wanted to reflow to a parenthesized message.
- **Fix:** Accepted ruff's reformat (no semantic change).
- **Files modified:** `tests/test_ingest_sqlite.py`
- **Verification:** ruff clean after the format pass.
- **Committed in:** `191910b` (rolled into Task 1 commit)

---

**Total deviations:** 2 auto-fixed (1 missing-critical guard, 1 pre-commit reformat).
**Impact on plan:** Plan executed substantively as written. Empty-input guard is a correctness improvement, not scope creep.

## Issues Encountered

None — Plan executed cleanly. The CSV-vs-SQLite-vs-parquet evolution that prompted Q3=A is documented in the 03-07 SUMMARY's Decisions section.

## User Setup Required

None — local Python only.

## Next Phase Readiness

- **Phase 3 Wave 4 complete.** Two remaining waves (2/3) deferred to operator-supervised real-spend session; see end-of-run report for full deferral rationale.
- **Phase 4 unblocked on the synthesis substrate.** Once real Wave 2/3 measurements land in `results/{g1,g2,g3,g5,g7,audit_01,audit_03}/`, Phase 4 author re-runs the 4-stage pipeline (`ingest → derate → cross_check → render`) and the canonical evidence pack lives at `results/synthesis/measurements.sqlite`.
- **Operator follow-up:** populate `data/nvidia_orin_published_benchmarks.json` before Phase 4 cross-check is meaningful (~30-min curation step).

---
*Phase: 03-cloud-derate*
*Completed: 2026-05-13*
