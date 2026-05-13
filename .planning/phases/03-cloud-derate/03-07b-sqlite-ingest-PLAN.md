---
phase: 03-cloud-derate
plan: 07b
type: execute
wave: 4
depends_on: ["03-07"]
files_modified:
  - synthesis/ingest_gate_jsonls.py
  - tests/test_ingest_sqlite.py
autonomous: true
budget_usd: 0.0
requirements:
  - DERATE-05
user_setup: []
must_haves:
  truths:
    - "synthesis/ingest_gate_jsonls.py:main() writes measurements to results/synthesis/measurements.sqlite (SQLite) in addition to (or in place of) the existing parquet output, with one row per measurement and a stable schema queryable via standard sqlite3 CLI"
    - "Downstream consumers (synthesis/derate_pipeline.py) continue to function — either reading from parquet as before OR transparently from SQLite via a thin pd.read_sql wrapper if parquet is absent"
    - "SQLite schema includes a UNIQUE index on (gate, run_id, asset_id, stage) to make re-runs idempotent (INSERT OR REPLACE semantics) — running ingest twice on the same JSONLs does NOT duplicate rows"
    - "ZERO cloud spend; local Python only"
  artifacts:
    - path: "synthesis/ingest_gate_jsonls.py"
      provides: "main() now writes to results/synthesis/measurements.sqlite via pandas.to_sql with if_exists='replace' OR via explicit sqlite3 with UNIQUE index + INSERT OR REPLACE; parquet emission preserved for backwards compatibility unless explicitly disabled"
      min_lines: 130
    - path: "results/synthesis/measurements.sqlite"
      provides: "SQLite DB with `measurements` table; queryable with `sqlite3 results/synthesis/measurements.sqlite 'SELECT COUNT(*) FROM measurements'`"
      contains: "measurements"
    - path: "tests/test_ingest_sqlite.py"
      provides: "Unit tests verifying SQLite emission, schema, idempotent re-ingest, and parquet/sqlite parity"
      min_lines: 60
  key_links:
    - from: "synthesis/ingest_gate_jsonls.py"
      to: "results/synthesis/measurements.sqlite"
      via: "stdlib sqlite3 or pandas.DataFrame.to_sql"
      pattern: "measurements.sqlite"
    - from: "synthesis/derate_pipeline.py"
      to: "results/synthesis/measurements.sqlite (fallback when parquet missing)"
      via: "pd.read_sql('SELECT * FROM measurements', sqlite3.connect(...))"
      pattern: "read_sql"
---

<objective>
Promote operator decision Q3=A: write the synthesis ingest layer's canonical output as SQLite (`measurements.sqlite`) instead of (or in addition to) CSV/parquet. Surgical change to `synthesis/ingest_gate_jsonls.py:main()` only; no schema redesign, no derate-pipeline rewrite. Preserves backwards compatibility with the existing 03-07 PLAN.

Rationale (per operator Q3=A): SQLite makes the synthesis evidence pack interrogable via stock CLI tools (`sqlite3`, DataGrip, DBeaver, Datasette) without a Python kernel, and gives idempotent re-ingest semantics via a UNIQUE index — both are wins for the Phase 4 author and for any re-run after a partial gate failure.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/phases/03-cloud-derate/03-CONTEXT.md
@.planning/phases/03-cloud-derate/03-07-PLAN.md
@./CLAUDE.md
@synthesis/ingest_gate_jsonls.py

<interfaces>
From the existing 03-07 PLAN (Task 2), `synthesis/ingest_gate_jsonls.py:main()` already:
- Walks `results/**/*.jsonl`
- Loads into a single pandas DataFrame
- Writes to `results/synthesis/measurements.parquet`

This plan adds — in the same `main()` — a SQLite write step. Either output is acceptable to downstream `synthesis/derate_pipeline.py`; preference is SQLite as the canonical artifact, parquet as an optional compatibility shim during transition.

Stable SQLite schema for the `measurements` table:
- TEXT: gate, run_id, asset_id, stage, substrate, image_digest, git_commit, asset_manifest_sha
- INTEGER: concurrency
- REAL: stt_ttft_ms, llm_ttft_ms, llm_decode_ms_per_tok, tts_first_audio_ms, e2e_ms (and any future stage columns — emit whatever the DataFrame has)
- UNIQUE INDEX on (gate, run_id, asset_id, stage)

Idempotency contract: `python -m synthesis.ingest_gate_jsonls` run N times against the same on-disk JSONLs yields the same row count (no duplicates).
</interfaces>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Add SQLite emission to ingest_gate_jsonls.main() + idempotent re-ingest</name>
  <files>synthesis/ingest_gate_jsonls.py, tests/test_ingest_sqlite.py</files>
  <read_first>
    - synthesis/ingest_gate_jsonls.py (existing main() from 03-07 Task 2)
    - harness/results.py (GateResult schema — confirm field names)
  </read_first>
  <behavior>
    - Test 1: After `main()` runs against a fixture results dir with N JSONL rows, `results/synthesis/measurements.sqlite` exists and `SELECT COUNT(*) FROM measurements` returns N.
    - Test 2: Schema check — `PRAGMA table_info(measurements)` includes at minimum: gate, run_id, asset_id, stage, substrate, image_digest, git_commit, concurrency.
    - Test 3: Idempotency — running `main()` twice on the same fixture yields the same row count (UNIQUE index on (gate, run_id, asset_id, stage) + INSERT OR REPLACE semantics).
    - Test 4: Parity — for any row present in the parquet output, the same row (matching on (gate, run_id, asset_id, stage)) exists in the SQLite output with identical scalar columns.
  </behavior>
  <action>
    Modify `synthesis/ingest_gate_jsonls.py` to add a `_write_sqlite(df, out_path)` helper and call it from `main()` immediately after the existing parquet write. Keep parquet write to avoid breaking any in-flight 03-07 Task 2 invocation; the SQLite file becomes the canonical artifact going forward.

    Approximate diff shape:

    ```python
    import sqlite3

    def _write_sqlite(df: pd.DataFrame, out_path: pathlib.Path) -> None:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        # Drop columns that contain nested dicts/lists — SQLite can't store them natively
        scalar_df = df.copy()
        for col in scalar_df.columns:
            if scalar_df[col].apply(lambda v: isinstance(v, (dict, list))).any():
                scalar_df[col] = scalar_df[col].apply(
                    lambda v: json.dumps(v) if isinstance(v, (dict, list)) else v
                )
        con = sqlite3.connect(out_path)
        try:
            # Write fresh, then add UNIQUE index for idempotency on re-runs
            scalar_df.to_sql("measurements", con, if_exists="replace", index=False)
            # Best-effort UNIQUE index — only if all 4 columns exist
            cols = set(scalar_df.columns)
            need = {"gate", "run_id", "asset_id", "stage"}
            if need.issubset(cols):
                con.execute(
                    "CREATE UNIQUE INDEX IF NOT EXISTS idx_measurements_key "
                    "ON measurements(gate, run_id, asset_id, stage)"
                )
            con.commit()
        finally:
            con.close()

    def main() -> int:
        df = load_all()
        out_dir = pathlib.Path("results/synthesis")
        out_dir.mkdir(parents=True, exist_ok=True)
        df.to_parquet(out_dir / "measurements.parquet")  # preserved
        _write_sqlite(df, out_dir / "measurements.sqlite")
        print(f"[ingest] {len(df)} rows -> {out_dir/'measurements.sqlite'} (+ parquet)")
        return 0
    ```

    Write `tests/test_ingest_sqlite.py` covering Tests 1-4. Use a tmp_path fixture and a synthetic 3-row JSONL written into a fake `results/g1/run.jsonl`; monkeypatch the cwd or pass a results_root argument if needed (refactor `load_all` to accept the root; tests should not hit real results/).

    Acceptance: `uv run pytest tests/test_ingest_sqlite.py -x -q` clean; `uv run ruff check synthesis/ingest_gate_jsonls.py` clean.
  </action>
  <verify>
    <automated>uv run pytest tests/test_ingest_sqlite.py -x -q &amp;&amp; uv run ruff check synthesis/ingest_gate_jsonls.py</automated>
  </verify>
  <done>
    `synthesis/ingest_gate_jsonls.py:main()` writes `results/synthesis/measurements.sqlite` with the documented schema; 4 unit tests pass; idempotent re-ingest verified; parquet emission preserved.
  </done>
</task>

<task type="auto">
  <name>Task 2: derate_pipeline SQLite fallback (read measurements.sqlite when parquet absent)</name>
  <files>synthesis/derate_pipeline.py</files>
  <read_first>
    - synthesis/derate_pipeline.py:main() (existing reader of measurements.parquet from 03-07)
  </read_first>
  <action>
    Modify `synthesis/derate_pipeline.py:main()` to prefer `measurements.parquet` if present, else fall back to `measurements.sqlite` via `pd.read_sql("SELECT * FROM measurements", sqlite3.connect(...))`. This makes the SQLite output a first-class consumer surface without breaking the parquet-first path the rest of 03-07 Task 2 expects.

    Approximate diff:

    ```python
    def main() -> int:
        parquet = pathlib.Path("results/synthesis/measurements.parquet")
        sqlite_path = pathlib.Path("results/synthesis/measurements.sqlite")
        if parquet.exists():
            df = pd.read_parquet(parquet)
        elif sqlite_path.exists():
            import sqlite3
            with sqlite3.connect(sqlite_path) as con:
                df = pd.read_sql("SELECT * FROM measurements", con)
        else:
            raise FileNotFoundError(
                "Neither measurements.parquet nor measurements.sqlite found. "
                "Run `python -m synthesis.ingest_gate_jsonls` first."
            )
        out = run(df)
        ...
    ```

    Acceptance: `uv run ruff check synthesis/derate_pipeline.py` clean; end-to-end `python -m synthesis.ingest_gate_jsonls && rm results/synthesis/measurements.parquet && python -m synthesis.derate_pipeline` succeeds (sqlite-only path exercised).
  </action>
  <verify>
    <automated>uv run ruff check synthesis/derate_pipeline.py</automated>
  </verify>
  <done>
    Derate pipeline reads SQLite when parquet is absent; no regression to the parquet-first path.
  </done>
</task>

</tasks>

<verification>
- `results/synthesis/measurements.sqlite` exists after ingest; queryable via stock sqlite3 CLI.
- Re-running ingest is idempotent (row count stable; UNIQUE index enforces (gate, run_id, asset_id, stage)).
- `synthesis/derate_pipeline.py` can read from SQLite when parquet is absent.
- 4 unit tests pass in `tests/test_ingest_sqlite.py`.
- ZERO cloud spend.
</verification>

<success_criteria>
Phase 4 author (and any future Phase 3 re-run) has a queryable SQLite evidence pack at `results/synthesis/measurements.sqlite` and can interrogate it with `sqlite3` / DBeaver / Datasette without a Python kernel. The 03-07 derate pipeline continues to function unchanged. This plan adds; it does not break.
</success_criteria>

<output>
After completion, append a short note to `.planning/phases/03-cloud-derate/03-07-SUMMARY.md` (created by 03-07 main plan) documenting the SQLite output path, row count, idempotency check result, and the fact that derate_pipeline now supports SQLite-fallback reads.
</output>
