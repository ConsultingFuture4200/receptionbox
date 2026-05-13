---
phase: 03-cloud-derate
plan: 05
status: code-complete; awaiting operator pod run
requirements-completed:
  - AUDIT-01 (code path)
  - AUDIT-03 (code path)
requirements-blocked-on-operator:
  - AUDIT-01 (measurement)
  - AUDIT-03 (measurement)
budget_usd_spent: 0.00
budget_usd_remaining_envelope: 3.50
worktree: .claude/worktrees/plan-03-05-audits
branch: worktree-plan-03-05-audits
---

# Plan 03-05 Summary — AUDIT-01 + AUDIT-03 + Ollama Overhead

## Status

**Code-complete, awaiting operator real-spend pod run.** Tasks 1–3 done in the
worktree branch `worktree-plan-03-05-audits`. Task 4 (operator) is the only
remaining checkpoint and is blocking per the plan's `autonomous: false`.

## What landed in the worktree

| File | Change | LOC |
|------|--------|-----|
| `gates/audit_01/__init__.py` | new (empty package marker) | 0 |
| `gates/audit_01/runner.py` | new — `AUDIT01Runner` with nvidia-smi VRAM sampling + graceful fallback + per-sample row emission | ~165 |
| `gates/audit_03/__init__.py` | new | 0 |
| `gates/audit_03/runner.py` | new — `AUDIT03Runner` with engine-swap pass + Ollama-vs-vLLM tokens/sec pass + summary helper | ~330 |
| `tests/test_audit_01_runner.py` | new — 8 tests (parse, fallback, swap-time, model-resident check) | ~200 |
| `tests/test_audit_03_runner.py` | new — 9 tests (row counts, swap_ms placement, --verbose parse, overhead factor, not-installed, timeout) | ~290 |
| `harness/results.py` | extend `GateName` Literal: `+ "audit_01", "audit_03"` | +1 |
| `config/budget.yaml` | add `gates.audit_01` ($0.75) + `gates.audit_03` ($2.00) ledger entries | +9 |
| `tools/pod_entrypoint.sh` | install Ollama + `ollama serve` + `ollama pull qwen3:4b-q4_K_M` only when `GATE` starts with `audit_` | +25 |

## Test results

```
tests/test_audit_01_runner.py  8 passed
tests/test_audit_03_runner.py  9 passed
full local suite              285 passed, 2 skipped
ruff (audit_01 + audit_03)    All checks passed
```

## Deliberate deviations from the plan

1. **Underscored gate IDs (`audit_01` / `audit_03`) instead of hyphenated.**
   `python -m gates."$GATE".runner` is the dispatch path in
   `tools/pod_entrypoint.sh`; Python module names disallow hyphens. The
   `GateName` Literal and `config/budget.yaml` gates use the underscored
   form to stay consistent across substrate, results schema, and ledger.
2. **No edits to `tools/run_phase3_gate.py`.** That driver is a Plan 03-02
   deliverable still in flight on local `main` (origin/main does not yet
   have it). The audit runners dispatch through the existing
   `python -m gates.<gate>.runner` path, which works today via
   `pod_entrypoint.sh`. When 03-02 lands, add `audit_01` / `audit_03` to
   the new driver's `GATE_CORPUS` (None for both — they own their own
   asset loading).
3. **AUDIT-03 reaches through `substrate._chatterbox` / `._kokoro` directly.**
   The public `substrate.synthesize()` runs DR-27 fallback (Chatterbox if
   healthy, else Kokoro) — which would mask the exact swap we're trying
   to measure. The audit calls the adapters directly via `_tts_engine()`.
   The plan's pseudocode used a hypothetical `engine_hint=` parameter on
   `synthesize`; that parameter doesn't exist on the current Substrate
   ABC and adding it is out of scope for this audit.
4. **"All 4 models resident" check augments `substrate._loaded`.**
   `_loaded["tts"]` is OR'd (DR-27), so AUDIT-01's
   `_all_four_models_resident` also queries `_chatterbox.health()` AND
   `_kokoro.health()` separately to enforce strict simultaneous residency
   — the appliance-feasibility question the audit exists to answer.

## Worktree base + rebase note for operator

The worktree was created from `origin/main` (commit `0899690`) per the
default base-ref policy. Local `main` is 8 commits ahead (Plan 03-01
closures + Plan 03-02 in-flight work). The audit changes are purely
additive — three small edits to shared files (`harness/results.py`,
`config/budget.yaml`, `tools/pod_entrypoint.sh`) plus four new files —
so the rebase onto local `main` should fast-forward cleanly. Inspect
`tools/pod_entrypoint.sh` after rebase in case Plan 03-02 v19a digest
work touched the same region (it did not at last check).

## Operator handoff — Task 4 checkpoint

**Estimated wall-clock:** ~25–30 min on one v18 H100 PCIe pod.
**Estimated spend:** ≤ $3.50 against the $3 envelope.
**Pre-flight:** worktree merged to local `main` (or audit changes
cherry-picked); `RUNPOD_API_KEY` exported.

### Run command

```bash
cd ~/code/RBOX

# Provision a v18 pod and exec AUDIT-01 then AUDIT-03 sequentially.
# (Until Plan 03-02 lands the multi-gate `tools/run_phase3_gate.py`
# driver, each audit is its own GATE for the entrypoint dispatcher.)

# Session 1 — AUDIT-01 (~5 min sustained + ~10 min provisioning/health):
GATE=audit_01 OLLAMA_MODEL=qwen3:4b-q4_K_M \
  uv run python -m orchestration.runpod_h100 \
    --gate audit_01 --max-minutes 20 --real-spend

# Session 2 — AUDIT-03 (Ollama install + ~15 min swap + overhead):
GATE=audit_03 OLLAMA_MODEL=qwen3:4b-q4_K_M \
  uv run python -m orchestration.runpod_h100 \
    --gate audit_03 --max-minutes 30 --real-spend
```

If both audits should share one pod (cheaper, matches plan intent), the
recommended quick wrapper is to start the pod with `GATE=audit_01`,
let it complete, then exec `python -m gates.audit_03.runner --gate=audit_03`
inside the running pod before letting the watchdog terminate it. That
saves the ~$0.50 provisioning hit on the second pod.

### Acceptance criteria

| # | Criterion | Hard / Soft |
|---|-----------|-------------|
| 1 | `results/audit_01/*.jsonl` ≥ 30 rows (5 min / 10s sampling) | hard |
| 2 | `metrics.vram_mb` populated (numeric) on every audit_01 row | hard |
| 3 | `metrics.all_4_models_resident` True on the majority of rows | hard |
| 4 | Peak observed VRAM ≤ 64000 MB (Orin 64GB feasibility check) | hard |
| 5 | `results/audit_03/*.jsonl` ≥ 50 rows: 10 swap + 40 ollama-vs-vllm | hard |
| 6 | At least one audit_03 row has `metrics.engine_swap_ms` populated | hard |
| 7 | `ollama_overhead_factor` ∈ [1.1, 2.0] (predicted 1.3–1.5×) | soft — if Ollama install failed, retry as a follow-up |
| 8 | Total spend ≤ $3.50 | hard |
| 9 | Pod GONE after each session | hard |

### Resume signal

Operator types `approved` (criteria 1–6, 8, 9 hold; 7 may be deferred) or
`fail: {reason}`.

## Implication for Orin derate (Plan 03-07 input)

Both audits feed Plan 03-07's synthesis directly:

- **AUDIT-01 → DR-39 Orin 64GB feasibility.** Peak VRAM observed under
  sustained stack-load with all four models resident pins the upper
  bound for the appliance memory budget. If peak > 64000 MB on H100,
  the receptionBOX stack does not fit Orin 64GB without per-model
  quantization tightening, and the synthesis report must flag the
  shortfall as a hard blocker.
- **AUDIT-03 → grounds the CLAUDE.md §3.1 Ollama overhead factor.**
  Every LLM-stage Orin prediction in 03-07 is multiplied by this scalar.
  Today the scalar is `1.3–1.5×` extrapolated from community benchmarks;
  AUDIT-03 produces a pod-measured ratio at the same revision SHA and
  quantization the appliance will run.
