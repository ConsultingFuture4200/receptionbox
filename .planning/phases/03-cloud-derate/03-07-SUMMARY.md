---
phase: 03-cloud-derate
plan: 07
subsystem: synthesis
tags: [derate, orin, bootstrap, scipy, pandas, h100, jetson]

requires:
  - phase: 03-cloud-derate
    provides: gate JSONL rows (g1/g2/g3/g5/g7/audit_01/audit_03) — populated by 03-02..06
provides:
  - Per-stage Orin derate model (FP16/INT8/bandwidth ratios per CLAUDE.md §7)
  - Synthesis ingest pipeline (gate JSONLs → pandas DataFrame, REPRO-03 verified)
  - Bootstrap-CI derate table (scipy.stats.bootstrap, n=10000, 95% percentile)
  - NVIDIA published-benchmark cross-check runner (template-aware, >50% divergence flags)
  - Phase-4-ready derate methodology renderer
affects: [04-feasibility-memo, 04-gate-decision]

tech-stack:
  added: [scipy.stats.bootstrap (already in env), pandas evidence pipeline]
  patterns:
    - "Stage→derate-function dispatch via STAGE_DERATE_FUNCS dict (extensible without touching the pipeline core)"
    - "Graceful-degrade renderers: cross-check + methodology emit useful output when upstream inputs are absent (template / awaiting status)"
    - "OrinSpec dataclass parallel to (not extending) the existing op_classes.HardwareSpec — keeps Strix-era frozen schema untouched"

key-files:
  created:
    - derating/orin_model.py
    - synthesis/ingest_gate_jsonls.py
    - synthesis/derate_pipeline.py
    - synthesis/cross_check_nvidia.py
    - synthesis/render_methodology.py
    - tests/test_orin_derate.py
    - tests/test_derate_pipeline.py
    - tests/test_synthesis_scaffold.py
    - tests/fixtures/synthetic_gate_results.py
    - data/nvidia_orin_published_benchmarks.json
    - results/synthesis/measurements.csv
    - results/synthesis/orin_derate_table.csv
    - results/synthesis/nvidia_crosscheck.json
    - results/synthesis/derate_methodology.md
  modified: []

key-decisions:
  - "Composition over inheritance for OrinSpec — leaves derating.op_classes.HardwareSpec untouched so strix_model.py keeps working as the archived reference"
  - "Ingest writes measurements.csv (not parquet) per existing scaffold — operator decision Q3=A promotes SQLite as the canonical output in the 03-07b sub-plan"
  - "Cross-check ships with NVIDIA template (all value_* fields null); status=awaiting_operator_curation until operator curates from developer.nvidia.com/embedded/jetson-orin-benchmarks"
  - "Methodology renderer degrades gracefully when derate_table/crosscheck absent so it can be regenerated cheaply after each Wave 2/3 measurement landing"

patterns-established:
  - "Synthesis pipeline as 4-stage chain (ingest → derate → crosscheck → render) where each stage reads from results/synthesis/ and writes to results/synthesis/; zero coupling beyond the file-system contract"
  - "Bootstrap CI module-level constants (BOOTSTRAP_N_RESAMPLES=10000, BOOTSTRAP_CONFIDENCE=0.95) — tests assert these directly so a config drift cannot silently change CI semantics"

requirements-completed: [DERATE-02, DERATE-05]

duration: ~30 min
completed: 2026-05-13
---

# Phase 03 Plan 07: Synthesis Derate Pipeline Summary

**Local Python synthesis pipeline that ingests all Phase 3 gate JSONLs, derates H100 measurements to Jetson AGX Orin 64GB per CLAUDE.md §7 with bootstrap 95% CIs, cross-checks against NVIDIA-published benchmarks, and renders Phase-4-ready methodology prose — all zero cloud spend.**

## Performance

- **Duration:** ~30 min (this session) on top of ~prior scaffold commit `3e67851`
- **Started:** 2026-05-13T00:39Z (Wave 4 dispatch)
- **Completed:** 2026-05-13T00:55Z
- **Tasks:** 3 (Task 1 already shipped via scaffold; Task 2 + Task 3 finished this session)
- **Files modified:** 14 (5 source modules, 3 test modules + 1 fixture, 1 template, 4 generated artifacts, plus this summary)

## Accomplishments

- **Task 1 — orin_model.py + tests**: H100_PCIE + ORIN_AGX_64GB OrinSpec constants; three derate primitives (`derate_compute_bound_fp16`, `derate_compute_bound_int8`, `derate_bandwidth_bound`) per CLAUDE.md §7.1; `derate_pipeline()` applies Ollama-overhead to LLM stages only + universal ARM-penalty. 6 unit tests in `tests/test_orin_derate.py` (5 plan-named + 1 unknown-stage edge case) all pass.
- **Task 2 — ingest + derate_pipeline + nvidia template + tests**: `synthesis/ingest_gate_jsonls.py:load_all()` walks `results/*/*.jsonl`, skips preflight/smoke/_pulled/synthesis dirs, REPRO-03 columns validated, returns DataFrame; `synthesis/derate_pipeline.py:run()` buckets by (gate, stage, concurrency), emits per-bucket H100 p50 + derated Orin point + bootstrap CI low/high. 6 tests in `tests/test_derate_pipeline.py` covering all 4 plan behaviors + 7 tests in `tests/test_synthesis_scaffold.py` covering breadth (180-row fixture exercise).
- **Task 3 — cross_check_nvidia + render_methodology**: NVIDIA published-benchmark cross-check runner with template-aware status (awaiting_operator_curation / ok / flags_present) and >50% divergence flags; methodology renderer emits `derate_methodology.md` Phase-4-ready prose with per-stage ratios, overheads, bootstrap config, cross-check status, and the post-Phase-0 dev-kit validation plan from CLAUDE.md §7.3.

End-to-end execution against current `results/` (80 prior-phase smoke rows): 4 derate buckets emitted, cross-check correctly reports `awaiting_operator_curation`, methodology renders cleanly. 19/19 tests pass; ruff clean.

## Task Commits

Each task was committed atomically:

1. **Task 1: orin_model.py + tests (scaffold)** — `3e67851` (feat — pre-this-session scaffold commit)
2. **Task 2: ingest + derate_pipeline (scaffold) + named tests + NVIDIA template** — `3e67851` (scaffold) + `d1dfaae` (test/data)
3. **Task 3: cross_check_nvidia + render_methodology** — `adda993` (feat)
4. **Evidence artifacts** — `268832f` (chore)

**Plan metadata** (this SUMMARY + STATE/ROADMAP updates): pending sequential update in subsequent commit.

## Files Created/Modified

| File | Purpose |
|------|---------|
| `derating/orin_model.py` | OrinSpec dataclass; H100_PCIE + ORIN_AGX_64GB constants; 3 derate primitives + STAGE_DERATE_FUNCS dispatch + derate_pipeline() |
| `synthesis/__init__.py` | Empty package marker |
| `synthesis/ingest_gate_jsonls.py` | Walks results/ JSONL files into a pandas DataFrame; REPRO-03 verified; emits measurements.csv |
| `synthesis/derate_pipeline.py` | _measure_ollama_overhead() from audit_03; _bootstrap_ci() with scipy.stats.bootstrap n=10000 conf=0.95 percentile; run() buckets by (gate, stage, concurrency) |
| `synthesis/cross_check_nvidia.py` | Compares derated predictions vs NVIDIA-published benchmarks; emits nvidia_crosscheck.json with status + flag entries |
| `synthesis/render_methodology.py` | Renders Phase-4-ready derate_methodology.md from derate_table + crosscheck artifacts |
| `tests/test_orin_derate.py` | 6 tests covering all 5 plan-named Task 1 behaviors + 1 unknown-stage edge case |
| `tests/test_derate_pipeline.py` | 6 tests covering Plan Task 2 behaviors 3 (audit_03 ollama overhead) + 4 (scipy.stats.bootstrap config) + reconfirmation of 1+2 |
| `tests/test_synthesis_scaffold.py` | 7 tests exercising ingest + derate end-to-end against synthetic 180-row fixture |
| `tests/fixtures/synthetic_gate_results.py` | Realistic-shape gate row generator |
| `data/nvidia_orin_published_benchmarks.json` | Operator-curatable template (all value_* fields null) for NVIDIA Jetson Orin published benchmarks |
| `results/synthesis/measurements.csv` | 80 rows ingested from prior-phase smoke + early-gate JSONLs |
| `results/synthesis/orin_derate_table.csv` | 4 derate buckets with bootstrap 95% CIs |
| `results/synthesis/nvidia_crosscheck.json` | status=awaiting_operator_curation pending NVIDIA template population |
| `results/synthesis/derate_methodology.md` | Phase-4-ready derate methodology prose |

## Decisions Made

- **OrinSpec via composition, not subclass of HardwareSpec**: existing `derating/op_classes.HardwareSpec` is frozen, in use by `strix_model.py` (archived but kept), and carries `prompt_processing_factor` rather than FP16/INT8 splits. New `OrinSpec` dataclass keeps the two derate models independent — Strix Halo reference stays untouched, Orin model carries the §7.1 spec sheet directly.
- **Ingest writes CSV at `measurements.csv`** (existing scaffold) rather than the parquet target the plan named: operator promoted SQLite (Q3=A) in the 03-07b sub-plan, which is the next plan in Wave 4. Parquet would have been intermediate dead weight.
- **`scipy.stats.bootstrap` parameters frozen as module constants** so tests assert them directly: protects against silent config drift changing CI semantics across plans.
- **Cross-check ships with template that has no curated values** so the pipeline runs end-to-end immediately while the operator-curation step (~30 min to extract numbers from developer.nvidia.com/embedded/jetson-orin-benchmarks) remains a clearly-flagged followup.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 4 deferred — operator alignment, not architectural] Ingest writes CSV not parquet**
- **Found during:** Task 2 baseline check (scaffold commit `3e67851` already wrote CSV)
- **Issue:** Plan named `measurements.parquet` as canonical output; scaffold writes `measurements.csv`
- **Fix:** Left as-is — operator decision Q3=A in 03-07b sub-plan promotes SQLite as the canonical output going forward. Parquet would be intermediate dead weight. The derate_pipeline reader will gain a SQLite-fallback in 03-07b.
- **Files modified:** none (deferred to 03-07b)
- **Verification:** end-to-end pipeline runs clean against CSV
- **Committed in:** N/A (no-change deviation; documented here)

**2. [Rule 2 - Missing Critical] Added `_LLM_STAGES` constant + `_has_curated_data()` helper for cross-check**
- **Found during:** Task 3 (cross_check_nvidia drafting)
- **Issue:** Plan's prose described template-detection inline; extracting it to a helper made the main() function readable and the awaiting-curation branch testable.
- **Fix:** `_has_curated_data()` + `_published_value()` helpers; `_STAGE_TO_WORKLOAD_PREFIX` dispatch table for finding NVIDIA-published analogs.
- **Files modified:** `synthesis/cross_check_nvidia.py`
- **Verification:** End-to-end run emits the correct `status=awaiting_operator_curation` against the template; ruff clean.
- **Committed in:** `adda993` (Task 3 commit)

**3. [Rule 2 - Missing Critical] Methodology renderer degrades gracefully when inputs absent**
- **Found during:** Task 3 (render_methodology drafting)
- **Issue:** Plan called for the renderer to consume derate_table + crosscheck artifacts; in current state (no Wave 2/3 measurements yet) those are sparse. A renderer that hard-fails on missing inputs would block re-rendering after each measurement landing.
- **Fix:** `_load_derate_table()` returns None when missing/empty; `_load_crosscheck()` returns a stub dict. Output document includes an "AWAITING" note when derate_table is absent.
- **Files modified:** `synthesis/render_methodology.py`
- **Verification:** Renderer runs cleanly against the current sparse data; output document is valid Markdown.
- **Committed in:** `adda993` (Task 3 commit)

**4. [Rule 1 - Bug — pre-commit auto-format reformatting]**
- **Found during:** Task 3 commit
- **Issue:** Initial line-length E501 violations in the markdown table inside `render_methodology.py`'s f-string. Pre-commit `ruff format` also wanted to reflow the `awaiting_derate` ternary expression.
- **Fix:** Shortened table row labels ("STT encoder" not "STT encoder (compute-bound INT8)") so the f-string lines fit under the 100-char limit; pre-commit's reformat of `awaiting_derate` was accepted.
- **Files modified:** `synthesis/render_methodology.py`
- **Verification:** `uv run ruff check synthesis/ tests/test_derate_pipeline.py` clean.
- **Committed in:** `adda993` (rolled into Task 3 commit)

---

**Total deviations:** 4 auto-handled (1 deferred per operator decision, 2 missing-critical helpers, 1 pre-commit reformat).
**Impact on plan:** Plan executed substantively as written. The CSV-vs-parquet deferral is the only material divergence and it's already accounted for in 03-07b. No scope creep.

## Issues Encountered

- **80 ingested rows come from prior-phase smoke/Phase 2 data, not Phase 3 gate measurements.** Wave 2 (G2/G3, G5, G7) + Wave 3 (G1) have not yet run real-spend pod sessions; this plan exercises the pipeline shape against whatever rows are already on disk. The numerical derate table emitted here is **not** the Phase 0 evidence pack — it's a smoke confirmation that the pipeline runs. The pipeline must be re-run after operator-supervised real-spend measurements land in `results/g1..g7/`.
- **NVIDIA published-benchmark cross-check requires operator curation.** All `value_*` fields in `data/nvidia_orin_published_benchmarks.json` are null. Operator follow-up: populate from `developer.nvidia.com/embedded/jetson-orin-benchmarks` (Whisper-large-v3-INT8 encoder latency; Qwen2-7B-Q4 decode tokens/sec and TTFT@seq=200 are the three pre-stubbed slots).

## User Setup Required

None — this plan is zero cloud spend, all Python-local. Operator follow-up (populate NVIDIA template) is a manual ~30-min curation step that can happen any time before Phase 4 synthesis.

## Next Phase Readiness

- **Wave 4 next:** 03-07b (SQLite ingest) — surgical addition of SQLite emission to `synthesis/ingest_gate_jsonls.py:main()` per operator Q3=A. Depends on 03-07 (complete).
- **Phase 4 unblocked:** has the 4-stage synthesis pipeline + the Phase-4-ready methodology document template. Once real Wave 2/3 measurements land, Phase 4 author re-runs the 4 pipeline stages and writes the feasibility memo on top of `derate_methodology.md`.
- **Operator follow-up:** populate `data/nvidia_orin_published_benchmarks.json` before Phase 4 cross-check is meaningful.

---
*Phase: 03-cloud-derate*
*Completed: 2026-05-13*
