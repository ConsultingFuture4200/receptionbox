---
phase: 01-foundation
plan: "02"
subsystem: harness-core
tags: [harness, substrate-abc, gate-result, cost-ledger, derating, reproducibility]
requires: ["01-01"]
provides:
  - "Substrate ABC (async streaming transcribe/generate/synthesize) — gate-runner contract"
  - "_StubSubstrate (deterministic in-memory; tests-only) for GPU-free Phase 1 unit tests"
  - "GateResult pydantic v2 schema with schema_version: Literal['1.0'] (Pitfall E enforcement)"
  - "append_result JSONL writer + rebuild_index idempotent SQLite (D-11)"
  - "harness.env_fingerprint.capture() helper for HARNESS-05 sidecar"
  - "cost.ledger.{initialize_provider, authorize_spend, BudgetExhausted, Authorization}"
  - "derating.{HardwareSpec, OpClass, StageMeasurement, derate_compute_bound, derate_bandwidth_bound, derate_stage, derate_pipeline}"
  - "Hardware specs: MI300X (4240 GB/s realized, 1.0×), H100_SXM (3350, 1.0×), STRIX_HALO (212, 12.5×)"
  - "tests/test_harness_isolation.py — AST scan that fails CI if any gates/ module imports torch/onnxruntime/vllm/transformers/ctranslate2/faster_whisper"
  - "bench/images.lock.yaml (REPRO-01 — 4 image entries, cuda+rocm rails)"
  - "bench/models.lock.yaml (REPRO-02 — 4 models, HF revision + per-file SHA-256 schema)"
  - "tools/fetch_models.py — huggingface_hub CLI wrapper for Phase 2 cloud-side fetch"
affects:
  - "Every Phase 2 (CUDA) and Phase 3 (ROCm) substrate impl will subclass Substrate"
  - "Every gate runner under gates/ will produce GateResult rows and write via append_result"
  - "All cloud provisioning (CLOUD-01..03 in Plan 05) routes through cost.ledger.authorize_spend"
  - "Phase 4 synthesis calls derate_pipeline(measurements, MI300X, STRIX_HALO)"
tech-stack:
  added: []  # all dependencies were already pinned in Plan 01
  patterns:
    - "Substrate ABC = async generators (matches LiveKit Agents 1.x AgentSession contract)"
    - "Pydantic v2 schema_version: Literal['1.0'] enables future discriminated-union upgrade without silent widening (Pitfall E)"
    - "JSONL primary store + idempotent SQLite index rebuild (D-11) + per-run env.json sidecar (D-12)"
    - "Cost ledger commits to SQLite BEFORE returning Authorization (race-then-crash mitigation)"
    - "Per-stage roofline derating with op_class dispatch — UNKNOWN propagates total_ms=None (Pitfall 2)"
    - "Lockfile-as-data with pydantic schema enforcement in tests (REPRO-01/02)"
key-files:
  created:
    - substrate/types.py
    - substrate/_stub.py
    - harness/results.py
    - harness/store.py
    - harness/env_fingerprint.py
    - cost/ledger.py
    - derating/op_classes.py
    - derating/strix_model.py
    - derating/tests/__init__.py
    - bench/images.lock.yaml
    - bench/models.lock.yaml
    - tools/fetch_models.py
    - tests/test_substrate_abc.py
    - tests/test_harness_isolation.py
    - tests/test_harness_results.py
    - tests/test_cost_ledger.py
    - tests/test_strix_model.py
    - tests/test_lockfiles.py
  modified:
    - substrate/__init__.py  # placeholder → ABC + exports
    - harness/__init__.py    # placeholder → schema/store exports
    - cost/__init__.py       # placeholder → ledger exports
    - derating/__init__.py   # placeholder → derating exports
decisions:
  - "Pydantic v2 BaseModel chosen over @dataclass for STT/LLMChunk so JSON sidecars (env.json per HARNESS-05/D-12) round-trip cleanly"
  - "_StubSubstrate ships under a private name (leading underscore) and is NOT exported from substrate/__init__.py — gate runners cannot import it accidentally"
  - "harness.env_fingerprint._git_commit uses subprocess (5-second timeout) rather than parsing .git/HEAD chain manually — simpler and correct under detached HEAD / packed refs"
  - "Lockfile pydantic schemas live in the test file (tests/test_lockfiles.py) rather than a runtime module — they're enforcement contracts on data, not application logic"
  - "Phase 1 lockfiles use revision='pending' / digest='pending' literals; Phase 2's first-pull task on RunPod resolves them — keeps Phase 1 entirely GPU-free"
metrics:
  duration: "~6 minutes"
  completed: "2026-05-04T21:48:09Z"
  tasks: 3
  files_created: 18
  files_modified: 4
  lines_total: 1408
  tests_added: 35  # 8 substrate+isolation + 15 results+ledger + 12 derating+lockfiles
---

# Phase 01 Plan 02: Harness Core Summary

**One-liner:** Substrate ABC (async streaming transcribe/generate/synthesize), GateResult v1.0 schema with Literal-discriminator pitfall guard, JSONL-primary + idempotent-SQLite-index store, SQLite-backed cost ledger with `headroom < 0` refusal rule, per-stage roofline derating skeleton (no `derate_e2e` shortcut — Pitfall 2 enforced by absence test), and reproducibility lockfiles for cloud images + HF model revisions — all GPU-free, 35 unit tests pass, `make check` green.

## What Was Built

### Task 1 — Substrate ABC + types + deterministic stub + HARNESS-01 isolation test

`substrate/__init__.py` defines the `Substrate(ABC)` with 7 abstract methods:
`load_stt`, `load_llm`, `load_tts`, `transcribe`, `generate`, `synthesize`, `env_fingerprint`. The three streaming methods are async generators that yield `STTChunk` / `LLMChunk` / raw `bytes`. `Grammar = str | dict[str, Any]` is a plain type alias because xgrammar accepts JSON Schema strings or dicts (RESEARCH Open Q #5).

`substrate/types.py` defines pydantic v2 models for the chunk types + `EnvFingerprint` so they round-trip through JSON for HARNESS-05 sidecars. `EnvFingerprint.model_dump_json() → model_validate_json` proven equality in test.

`substrate/_stub.py` provides `_StubSubstrate` — a real Substrate whose `load_*` are no-ops and whose streaming methods yield deterministic synthetic chunks. Lives under a private name; never exported in `__all__`. This is what every Phase 1 unit test consumes when they need a working Substrate without torch.

`tests/test_harness_isolation.py` AST-walks `gates/` and asserts no module imports `torch | onnxruntime | vllm | transformers | ctranslate2 | faster_whisper`. Phase 1's `gates/` only contains `__init__.py` so the test passes; the test exists so Phase 2/3 contributors who regress trip it immediately.

8 tests pass (7 in `test_substrate_abc.py` + 1 isolation test).

### Task 2 — GateResult schema + JSONL + SQLite + cost ledger

`harness/results.py` defines `GateResult` with `schema_version: Literal["1.0"] = "1.0"` plus all 21 fields per D-10 (identity, substrate fingerprint, run config, status, 5 per-stage timings, gate-specific `metrics` and `extras` dicts). All per-stage timings are `float | None` so a single schema serves smoke/canary/G1/G2/G3/G5/G7 plus error rows (Liotta-survivable per D-11). `append_result` writes JSONL to `results/{gate}/{run_id}.jsonl`. `read_jsonl` parses back through pydantic.

`harness/store.py` provides `rebuild_index(results_dir)` which drops `results/index.sqlite` and re-walks `results/**/*.jsonl`. Idempotent — proven by re-running and checking the same path is returned. SQLite schema indexes on `gate`, `substrate`, `status`.

`harness/env_fingerprint.py` provides `capture(...)` which builds an `EnvFingerprint` for the current process. `_git_commit` uses `subprocess.run(['git', 'rev-parse', 'HEAD'])` with a 5-second timeout and returns `'unknown'` if the call fails — handles detached HEAD, packed refs, missing git binary.

`cost/ledger.py` provides `initialize_provider(provider, cap_usd)` (idempotent — preserves spent_usd on re-init) and `authorize_spend(provider, gate, projected_cost, safety_factor=1.5)`. The refusal rule is literally:

```python
remaining = cap - spent
headroom = remaining - projected_cost * safety_factor
if headroom < 0:
    raise BudgetExhausted(...)
```

`authorize_spend` does `conn.commit()` BEFORE returning the `Authorization` so a Python crash mid-flow cannot produce a ghost authorization that the caller thinks succeeded. Proven by `test_authorization_commits_before_return`, which reopens the DB on a fresh connection and reads the row.

15 tests pass (8 in `test_harness_results.py` + 7 in `test_cost_ledger.py`). ROADMAP Phase 1 success criterion #2 (cost ledger dry-run unit test) satisfied.

### Task 3 — Per-stage derating skeleton + lockfiles

`derating/op_classes.py` defines `OpClass` enum (`COMPUTE_BOUND`, `BANDWIDTH_BOUND`, `UNKNOWN`), `HardwareSpec` (frozen dataclass with `bandwidth_gb_s` + `prompt_processing_factor`), `StageMeasurement` (frozen dataclass with stage name + op_class + measured_ms + n).

`derating/strix_model.py` defines the three hardware specs:

| Spec | bandwidth_gb_s | prompt_processing_factor |
|------|----------------|--------------------------|
| MI300X | 4240.0 (80% of 5.3 TB/s peak) | 1.0 (baseline) |
| H100_SXM | 3350.0 | 1.0 |
| STRIX_HALO | 212.0 (rocm_bandwidth_test realized) | 12.5 (10–15× midpoint per Phoronix Nov 2025) |

`derate_compute_bound` uses `dst.prompt_processing_factor / src.prompt_processing_factor`. `derate_bandwidth_bound` uses `src.bandwidth_gb_s / dst.bandwidth_gb_s`. `derate_stage` dispatches on `op_class` — UNKNOWN returns `None`. `derate_pipeline` sums per-stage derates and returns `{stage_name: float|None, ..., 'total_ms': float|None}`. If ANY stage is UNKNOWN, `total_ms` becomes `None` — Pitfall 2 enforcement: callers cannot accidentally produce an end-to-end number from incomplete classification.

`test_no_e2e_shortcut_exists` asserts `derate_e2e` is NOT a function on the module — the absence is the contract.

`bench/images.lock.yaml` has 4 entries: vllm/vllm-openai (cuda), nvcr.io/nvidia/pytorch (cuda), rocm/vllm (rocm), rocm/pytorch (rocm). All `digest`s are literal `pending`; Phase 2's first-pull resolves them.

`bench/models.lock.yaml` has 4 model entries: distil-whisper, Qwen3-4B, Chatterbox, Kokoro-82M. All `revision`s are `pending`; whisper has 4 file slots with per-file SHA-256 placeholders.

`tools/fetch_models.py` is a 44-line CLI wrapper around `huggingface_hub.hf_hub_download(..., revision=...)` that iterates the lockfile and skips any entry whose revision is still `pending`.

`tests/test_lockfiles.py` defines pydantic schemas for both lockfiles (in the test file, since they're enforcement contracts on data) and asserts the regex shape of every revision (40-char hex SHA or `pending`) and digest (`sha256:<64hex>` or `pending`).

12 tests pass (7 in `test_strix_model.py` + 5 in `test_lockfiles.py`).

## Commits

| Task | Hash | Subject |
|------|------|---------|
| 1 | `2e6f976` | substrate ABC + types + deterministic stub + isolation test |
| 2 | `4b15208` | GateResult schema + JSONL/SQLite store + cost ledger |
| 3 | `e8f3b5f` | per-stage derating skeleton + reproducibility lockfiles |

## Verification Results

All 6 commands from the verification block exit 0:

```
make check                     → lint + 46 tests + manifest enforcement all green
substrate import + _StubSubstrate → 'substrate OK'
harness import (GateResult, append_result, rebuild_index) → 'harness OK'
cost.ledger import (authorize_spend, BudgetExhausted) → 'cost OK'
derate_pipeline([COMPUTE_BOUND@100ms], MI300X, STRIX_HALO)['total_ms'] == 1250.0 → 'derating OK'
images.lock len>=4 + models.lock len==4 → 'lockfiles OK'
```

Test count: 35 new tests added in Plan 02 (8 substrate+isolation + 15 results+ledger + 12 derating+lockfiles) — exceeds the ≥22 target in the plan output spec.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 — Blocking] Ruff format-on-write rewrites required**
- **Found during:** Task 2 + Task 3 lint runs
- **Issue:** `ruff format --check` flagged 4 files for reformatting after Write: `harness/store.py`, `tests/test_cost_ledger.py`, `tests/test_lockfiles.py`, `tests/test_strix_model.py`. Causes were SQL string-literal collapsing (single-line wrapping ruff prefers) and assertion-message string normalization.
- **Fix:** Ran `uv run ruff format <files>` to apply the project's formatter. Re-ran tests — all passed identically.
- **Files modified:** 4 (formatter-only changes; no semantics)
- **Commits:** Folded into Task 2 (`4b15208`) and Task 3 (`e8f3b5f`)

**2. [Rule 3 — Blocking] `datetime.timezone.utc` flagged by UP017**
- **Found during:** Task 2 lint
- **Issue:** `tests/test_harness_results.py` imported `from datetime import datetime, timezone` and used `tz=timezone.utc`. Ruff UP017 wants the new `datetime.UTC` alias instead.
- **Fix:** `--fix` rewrote it to `from datetime import UTC, datetime` and `tz=UTC`. Both forms are semantically identical.
- **Files modified:** `tests/test_harness_results.py`
- **Commit:** Folded into Task 2 (`4b15208`)

**3. [Rule 3 — Blocking] `__all__` not isort-sorted (RUF022)**
- **Found during:** Task 1 lint
- **Issue:** Plan's `__all__` listing in `substrate/__init__.py` was not isort-sorted; ruff RUF022 flagged it.
- **Fix:** Reordered alphabetically: `[EnvFingerprint, Grammar, LLMChunk, STTChunk, Substrate, VoiceRef]`. Same for `harness/__init__.py` and `derating/__init__.py`.
- **Files modified:** 3 `__init__.py` files
- **Commits:** Folded into Tasks 1 / 2 / 3 commits

None of these are semantic deviations from the plan — they're style-rule alignments the plan's verbatim code skeletons hadn't been pre-run through ruff against.

### Architectural / Behavioral Deviations

None. Every locked contract (D-09 substrate ABC shape, D-10 GateResult fields, D-11 JSONL+SQLite store, D-12 env.json sidecar, INFRA-06 refusal rule, Pitfall 2 no-shortcut) implemented verbatim.

## Authentication Gates

None — Plan 02 is fully local; no cloud / API surface touched. `tools/fetch_models.py` does not run in Phase 1; Phase 2 invokes it on the RunPod pod after `huggingface-hub login` (Phase 2 plan handles the auth gate).

## Pitfall Closure Verification

| Pitfall | Status | Evidence |
|---------|--------|----------|
| **2** (single-multiplier shortcut) | CLOSED | `derating.strix_model` has no `derate_e2e` function; `test_no_e2e_shortcut_exists` enforces. UNKNOWN op propagates `total_ms=None` (`test_pipeline_total_none_if_any_unknown_pitfall_2`). |
| **E** (pydantic Literal vs Union) | CLOSED | `GateResult.schema_version: Literal["1.0"]` — `model_validate({"schema_version": "9.9", ...})` raises `ValidationError` (`test_unknown_schema_version_rejected_pitfall_e`). |
| **9** (HF revision pinning) | PARTIAL — schema in place | `bench/models.lock.yaml` schema enforces 40-char hex SHA or `pending`; per-file SHA-256 slots present. Phase 2 first-fetch task resolves the `pending`s via `tools/fetch_models.py` (which uses `hf_hub_download(revision=...)` ETag verification). |
| **HARNESS-01** (gates importing torch directly) | CLOSED | `tests/test_harness_isolation.py` AST-walks `gates/` and fails on any import of `torch | onnxruntime | vllm | transformers | ctranslate2 | faster_whisper`. Runs in `make test`. |

## Phase 2 Hand-off

`bench/images.lock.yaml` and `bench/models.lock.yaml` ship with `digest: pending` and `revision: pending` literals. Phase 2's first task on the RunPod H100 pod must:

1. `docker pull <image_ref>:<tag>` for each cuda-rail entry → record `sha256:...` digest and `captured_utc` ISO timestamp into the lockfile.
2. Run `tools/fetch_models.py` (after `huggingface-hub login`) → pull each model, then resolve `revision` (40-char SHA from HF) and per-file `sha256` (from the `.cache/huggingface/hub/.../blobs/<sha>` filenames). Commit the lockfile updates to git BEFORE running any benchmark.

`tests/test_lockfiles.py` validates the resolved values automatically — Phase 2 doesn't need to extend the schema.

## Plan 05 Hand-off

`cost.ledger.initialize_provider(provider, cap_usd)` is the API the cost-watch daemon (CLOUD-03) uses to seed the budget table from `config/budget.yaml`. Plan 05 will iterate `BudgetConfig.provider_caps` and call `initialize_provider` for each. The daemon's polling loop will read `SELECT cap_usd, spent_usd FROM budget` to compute remaining headroom.

## Self-Check: PASSED

- `substrate/__init__.py` — FOUND (contains `class Substrate(ABC):`)
- `substrate/types.py`, `substrate/_stub.py` — FOUND
- `harness/results.py` — FOUND (contains `schema_version: Literal["1.0"] = "1.0"`)
- `harness/store.py`, `harness/env_fingerprint.py` — FOUND
- `cost/ledger.py` — FOUND (contains `class BudgetExhausted` and `headroom = remaining - projected_cost * safety_factor`)
- `derating/strix_model.py` — FOUND (contains `MI300X`, `H100_SXM`, `STRIX_HALO`; does NOT contain `derate_e2e`)
- `derating/op_classes.py`, `derating/__init__.py`, `derating/tests/__init__.py` — FOUND
- `bench/images.lock.yaml` — FOUND (4 entries, both rails)
- `bench/models.lock.yaml` — FOUND (4 models)
- `tools/fetch_models.py` — FOUND (exposes `fetch_pinned`, `main`)
- All 6 test files added — FOUND
- Commit `2e6f976` (Task 1) — FOUND in `git log`
- Commit `4b15208` (Task 2) — FOUND in `git log`
- Commit `e8f3b5f` (Task 3) — FOUND in `git log`
- `make check` — exits 0 (46 tests pass total: 11 from Plan 01 + 35 new)
- All 6 verification-block commands — exit 0
