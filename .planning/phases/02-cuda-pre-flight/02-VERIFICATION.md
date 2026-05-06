---
status: gaps_found
phase: 02-cuda-pre-flight
verified_utc: 2026-05-06T17:30:00Z
verifier: orchestrator (operator-driven path-C verification, not gsd-verifier subagent)
must_haves_total: 7
must_haves_passed: 4
must_haves_failed: 3
gaps_block_phase_complete: true
---

# Phase 02: cuda-pre-flight — Verification Report

## Summary

Plans 02-01, 02-02, 02-03 are complete and shipped (224 tests passing, lint clean). Plan 02-04 reached 3/4 tasks complete and was paused at Task 4 (real H100 spend) when an operator bootstrap dry-run surfaced an upstream blocker. The operator selected path C (defer real spend; route to gap-closure planning) so $0 was spent on RunPod this session.

**Phase cannot be marked complete** because the must-haves PREFLIGHT-01, PREFLIGHT-02, PREFLIGHT-03 require an actual H100 run, and the bootstrap step that precedes them is a no-op against the current lockfile state.

## Must-Haves Verified

| ID | Status | Evidence |
|----|--------|----------|
| HARNESS-02 | PASS | `substrate/cuda.py` + 4 adapters + `substrate/livekit_pipeline.py` shipped in 02-01 (137→164 tests). Adapters expose `health()` per [Phase 02-01] decision; CUDASubstrate composes per D-14; LiveKit AgentSession rig per D-15. |
| HARNESS-05 | PASS | `harness/env_sidecar.py` writes pydantic-validated `results/{gate}/{run_id}.env.json` once per run; verified by `tests/test_env_sidecar.py`. |
| HARNESS-06 | PASS | 4 substrate-agnostic gate runners under `gates/g{1,2,3,5}/runner.py`, all typed against `substrate.Substrate` ABC (grep-asserted). G7 explicitly deferred to Phase 3 in Makefile. |
| REPRO-03 | PASS | `GateRunner.build_result` injects all 6 reproducibility fields from `self`; pydantic `GateResult` validation rejects construction if any field is missing; verified by `tests/test_gate_runners.py`. |

## Must-Haves Failed (Gaps)

### GAP-1: PREFLIGHT-01 not executed (BLOCKING)

**Requirement:** 5-call G1 smoke test on RunPod H100 proves substrate + orchestration + cost ledger work end-to-end (~$1, <30 min).

**Status:** Code path complete (`tools/run_preflight.py --mode smoke` is wired and tested with mocks); no real H100 run performed.

**Root cause:** Blocked by GAP-3 (lockfile pending-revisions) — a smoke pod cannot legitimately run without first bootstrapping the model cache, and the cache bootstrap is currently a no-op.

**Evidence:** No `results/smoke/*.jsonl` in repo; cost ledger has no Phase 02 RunPod entries.

### GAP-2: PREFLIGHT-02 + PREFLIGHT-03 not executed (BLOCKING)

**Requirement:**
- PREFLIGHT-02: Sanity G1+G2+G3+G5 runs on H100 produce non-degenerate baseline numbers.
- PREFLIGHT-03: Every result row has `substrate_fingerprint == "cuda"` + full REPRO-03 tuple.

**Status:** Driver complete; no real run.

**Root cause:** Same as GAP-1 — blocked downstream of GAP-3.

**Evidence:** `results/g{1,2,3,5}/` empty for Phase 02.

### GAP-3: Lockfile pending-revisions + manual bootstrap step (ROOT CAUSE)

**Requirement:** REPRO-02 — `bench/models.lock.yaml` pins every HF model by `revision=<commit_sha>` (Whisper, Qwen3-4B, Chatterbox, Kokoro).

**Status:** PARTIAL. The lockfile structure exists and the schema is enforced, but **all 4 entries are at `revision: pending`** with `files: []` (Qwen/Chatterbox/Kokoro) or `sha256: pending` (Whisper). REPRO-02 was prematurely marked `[x]` in REQUIREMENTS.md after Phase 01 — the structural commitment is satisfied but the data is not.

**Discovered via:** Operator-run `uv run python -m tools.run_preflight --mode bootstrap` on 2026-05-06 returned `[preflight] bootstrap real-spend mode requires operator-side runpodctl invocation`. Investigation of `tools/cache_bootstrap.py` and `tools/fetch_models.py` revealed both skip `pending` entries with WARN-and-continue semantics, so even if the operator manually provisioned a bootstrap pod via `runpodctl`, no models would actually land on the network volume.

**Secondary gap:** `tools/run_preflight.py --mode bootstrap` does not auto-provision the bootstrap pod via the RunPod SDK — it defers to operator-side `runpodctl`. This is documented in `docs/OPERATOR-CHECKLIST-PHASE-02.md` §4 Step 1, but the checklist was written assuming the operator would invoke `runpodctl pod create` by hand. That breaks the "Reproducibility" constraint (CLAUDE.md §Constraints): every benchmark must be re-runnable from `~/RBOX`.

**Evidence:**
```yaml
# bench/models.lock.yaml — all 4 entries
- name: distil_whisper_large_v3_int8
  revision: pending
- name: qwen3_4b_awq_int4
  revision: pending
- name: chatterbox_turbo
  revision: pending
- name: kokoro_82m
  revision: pending
```

```python
# tools/cache_bootstrap.py:62-63
if rev == "pending":
    logger.warning(f"SKIP {name}: revision still 'pending'; resolve in lockfile first")
    continue
```

```python
# tools/run_preflight.py:247-251
logger.info(
    "[preflight] bootstrap real-spend mode requires operator-side runpodctl "
    "invocation; see docs/OPERATOR-CHECKLIST-PHASE-02.md"
)
```

## Recommended Gap-Closure Plan

A single follow-up plan (Plan 02.1-01) should close all three gaps in dependency order:

### Task 1 — Resolve HF revision SHAs (closes GAP-3 root)

- Pin commit SHAs for the 4 models. Choice criteria for SHA selection should be discussed before pinning — these become the fixed substrate for every Phase 02–4 measurement and any post-hoc re-run. Prefer the most-recent SHA on `main` at the time of Phase 02 execution unless there is a known regression.
- Models:
  - `Systran/faster-distil-whisper-large-v3` — populate `revision` + per-file SHA-256 for `model.bin`, `config.json`, `tokenizer.json`, `vocabulary.json`.
  - `Qwen/Qwen3-4B` — choose AWQ-Int4 quantized variant (per [Phase 02-02] context); populate `revision` + relevant `files`.
  - `ResembleAI/chatterbox` — `revision` + main weight file SHAs.
  - `hexgrad/Kokoro-82M` — `revision` + main weight file SHAs.
- Update `REQUIREMENTS.md`: REPRO-02 should remain `[x]` after this is resolved (it'll genuinely be true).
- AC: `tools/cache_bootstrap.py --target /tmp/cache --lockfile bench/models.lock.yaml` no longer logs any `SKIP` lines (run locally with limited disk; we don't need to hold full weights — just verify resolution succeeds).

### Task 2 — Auto-provision bootstrap pod via SDK (closes GAP-3 secondary)

- Replace the operator-action stub in `tools/run_preflight.py` `if mode == "bootstrap": ...real-spend...` branch with a real call to `orchestration.runpod_h100.provision()` (cost-ledger gated, just like smoke/sanity) configured for: small CPU-only or smallest-GPU pod, `/models` volume mounted, entrypoint `python -m tools.cache_bootstrap`, watchdog max ~15 min.
- Rev `config/budget.yaml` `phase2.cache_bootstrap_one_time_usd` if pod selection changes the cost.
- Update `docs/OPERATOR-CHECKLIST-PHASE-02.md` §4 Step 1 to document the now-automated path.
- AC: `RUNPOD_API_KEY=fake-but-set uv run python -m tools.run_preflight --mode bootstrap` calls `provision()` (mocked at SDK boundary), session manifest gets `gates[0].status: STOPPED` (or `EXITED`), pod starts and self-terminates after running cache_bootstrap. Tests at the mock-SDK level only — real spend lives in Task 4 below.

### Task 3 — End-to-end mock smoke test (defense in depth)

- Add an E2E test that mocks the RunPod SDK + SSH + rsync layer and proves the full `bootstrap → smoke` chain runs cleanly without real spend. This is what the operator's actual run will exercise; we should be able to dry-run it locally first.
- AC: `tests/test_run_preflight_e2e.py` simulates a successful bootstrap pod, then a successful smoke pod, asserts `smoke_verdict.pass: true` against synthetic results.

### Task 4 — Operator real-spend run (closes GAP-1, GAP-2, GAP-3)

- This is the original Plan 02-04 Task 4 unchanged: operator walks `docs/OPERATOR-CHECKLIST-PHASE-02.md`, runs bootstrap (now automated), runs smoke, runs sanity. Total ~$5–6, ceiling $14.
- AC: `results/smoke/*.jsonl` has 5 rows with `substrate == "cuda"` + full REPRO-03 tuple; `results/g{1,2,3,5}/*.jsonl` each have 10 rows; cumulative spend < $14; PREFLIGHT-01/02/03 marked `[x]` in REQUIREMENTS.md; Plan 02-04 SUMMARY written; Plan 02.1-01 SUMMARY written; Phase 02 marked complete.

## Pre-existing Issues Surfaced

- **REQUIREMENTS.md REPRO-02 marked `[x]` prematurely.** The Phase 01 closeout marked REPRO-02 complete on the basis of structural lockfile schema enforcement, but the data inside the lockfile is empty. This is a process gap to flag for whoever runs `/gsd-audit-uat` or `/gsd-audit-milestone` — requirement traceability should distinguish "schema enforced" from "data populated". Not blocking Phase 02 gap closure; mention it in Plan 02.1-01 deliverable so it gets corrected as a side effect.

## Pass-Through Gates (NOT BLOCKING)

These were not run as part of this verification; they should run after the gap-closure plan completes:

- Code review (`/gsd-code-review 02`) — advisory; runs after Phase 02 is actually complete.
- Regression gate (`pytest` against Phase 01 test files) — should be re-run after Plan 02.1-01 lands.
- Schema drift gate — N/A this phase (no DB schema changes).

## Routing

```
/gsd-plan-phase 02 --gaps    # writes Plan 02.1-01 (or similar numbering) closing GAP-1/2/3
```

After Plan 02.1-01 is planned and reviewed:
```
/gsd-execute-phase 02.1 --gaps-only
```

The execute path will hit Task 4's checkpoint exactly as 02-04 just did, but this time the bootstrap will actually do something.
