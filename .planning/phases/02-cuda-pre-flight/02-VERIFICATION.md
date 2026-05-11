---
status: smoke_pass_sanity_carved_out
phase: 02-cuda-pre-flight
verified_utc: 2026-05-10T16:35:00Z
verifier: orchestrator (operator-driven path-A verification, summary refresh — not gsd-verifier subagent)
prior_verification:
  - utc: "2026-05-06T17:30:00Z"
    status: gaps_found
    gaps_blocking_phase_complete: true
must_haves_total: 10
must_haves_passed: 8
must_haves_carved_out: 2
gaps_block_phase_complete: false
notes: Re-run /gsd-verify-work 2 with the gsd-verifier subagent for an independent audit; this refresh is operator-side bookkeeping after 02-04 / 02-07 / 02-08 SUMMARY artifacts landed.
---

# Phase 02: cuda-pre-flight — Verification Refresh

## Summary

The 2026-05-06 verification reported `gaps_found` with three BLOCKING gaps (PREFLIGHT-01/02/03 not executed; root cause lockfile pending-revisions). All three gaps closed in dependency order:

1. **Plan 02-05** (gap closure) resolved the lockfile data + auto-provisioned bootstrap SDK path → unblocked the model cache.
2. **Plan 02-06** baked the custom `rbox-pod` image and digest-pinned `_DEFAULT_IMAGE` → env vars are actually consumed by the pod entrypoint.
3. **Plan 02-07** (gap closure) closed three newly-surfaced pre-conditions for smoke (multi-service startup; corpus_500 in image; operator transport via fetch_pod pull) across eight image iterations (v8 → v18); smoke verdict `pass=True` recorded on session `20260509T231720Z`.
4. **Plan 02-08** (retroactive gap closure, DEV-1021) populated the `image_digest` + `git_commit` REPRO-03 fields on result rows; verified on a G2 diag pod row.

PREFLIGHT-01 closed. PREFLIGHT-02 + PREFLIGHT-03 carved out as DEV-1019 (operator-driven sanity) — explicit choice, not a gap.

## Must-Haves Verified

| ID | Status | Evidence |
|----|--------|----------|
| HARNESS-02 | PASS | `substrate/cuda.py` + 4 adapters + `substrate/livekit_pipeline.py` shipped in 02-01. Adapters expose `health()`; CUDASubstrate composes per D-14; LiveKit AgentSession rig per D-15. |
| HARNESS-05 | PASS | `harness/env_sidecar.py` writes pydantic-validated `results/{gate}/{run_id}.env.json` once per run; verified by `tests/test_env_sidecar.py` and on smoke run `2f6b…` (env sidecar present, values populated). |
| HARNESS-06 | PASS | 4 substrate-agnostic gate runners under `gates/g{1,2,3,5}/runner.py`, all typed against `substrate.Substrate` ABC. G7 deferred to Phase 3 per Makefile. |
| CLOUD-04 | PASS | `tools/pod_entrypoint.sh` orchestrates watchdog + audit + service startup + result transport; image v18 baked with sshd + pod_entrypoint as ENTRYPOINT (02-06) plus multi-service startup (02-07). |
| CLOUD-05 | PASS | HF model cache on `/models` network volume; bootstrap SDK-driven via `provision()`; lockfile populated (02-05); idempotency verified across 3 SKIP-on-rerun cycles (02-06 T6); operator confirmation that all 4 model directories landed on volume `rgkzzrl34n`. |
| CLOUD-06 | PASS | `tools/audit_pod_state.py` runs in shutdown chain; smoke audit `1778368799.audit.json` reports 0 violations across extension_check, manifest_check, pii_check. |
| REPRO-03 | PASS | Schema enforced in 02-02 (pydantic GateResult). Row-data populated for all six fields verified on Plan 02-08 / DEV-1021 (G2 diag pod `jow8x9kugpkgxm`, image v18, rows show real `sha256:abcf19f8…` digest + real commit `f049bb87…`). Smoke run `2f6b…` carries placeholders for `image_digest` and `git_commit` (pre-DEV-1021); future smoke / sanity / Phase-3 runs inherit the fix automatically. |
| PREFLIGHT-01 | PASS | Session `20260509T231720Z`, pod `d6ii16l245t41m`, run `2f6b0aa20acb4ebda0302d51b98c6334`. All six D-25 sub-criteria (a_5_rows, b_under_30min, c_under_1usd, d_per_stage_timings, e_env_sidecar, f_audit_clean) → True. Pod GONE; wall-clock 185.66 s; estimated true spend ~$0.14. |

## Must-Haves Carved Out

| ID | Status | Disposition |
|----|--------|-------------|
| PREFLIGHT-02 | DEFERRED to DEV-1019 (operator-driven sanity) | Sanity baselines for G1/G2/G3/G5 on H100 are a separate operator-driven run (~$4.49 per the operator checklist); not a gap, an explicit carve-out. Closes inside Phase 2 if run before Phase 3 starts, OR carries as a Phase 3 precondition. Operator decides. |
| PREFLIGHT-03 | DEFERRED to DEV-1019 | Substrate-fingerprint path is proven on every smoke row (`substrate="cuda"`). Row-data verification across all sanity gates is part of DEV-1019. |

## Resolution Log (vs. 2026-05-06 verification)

### GAP-1 (PREFLIGHT-01 not executed, BLOCKING) → RESOLVED

Smoke real-spend executed via 02-07 T7 on 2026-05-09 23:17; verdict pass. See `results/preflight/20260509T231720Z.json` and `results/smoke/2f6b0aa20acb4ebda0302d51b98c6334.jsonl`.

### GAP-2 (PREFLIGHT-02 + PREFLIGHT-03 not executed, BLOCKING) → REFRAMED

Not a verification gap; explicit carve-out as DEV-1019. Sanity is its own operator-driven session, decoupled from smoke verdict so Phase 3 planning can proceed in parallel.

### GAP-3 (Lockfile pending + manual bootstrap, ROOT CAUSE) → RESOLVED

Closed by Plan 02-05 (lockfile data + SDK-driven `--mode bootstrap`) and Plan 02-06 (custom image so env vars are actually consumed). Bootstrap re-run confirmed all 4 models on `/models`.

## New Gaps Surfaced During Closure

| Gap | Origin | Closed by |
|-----|--------|-----------|
| `pod_entrypoint.sh` smoke branch fired the runner with no inference services running → ConnectionRefused | 02-04 / 02-07 audit | 02-07 T3 (`_start_inference_services`) |
| `.dockerignore` excluded `corpus_500` → FileNotFoundError mid-smoke | 02-07 audit | 02-07 T4 (un-ignore corpus_500) |
| Operator-side rsync receiver setup friction (Tailscale-on-pod) | 02-07 execution | 02-07 architecture pivot: `tools/fetch_results.py` pull-based transport via diag pod |
| Image restart-loop before entrypoint log reachable | 02-07 v10 | tee entrypoint log to `/models/_boot` (image v10) |
| `image_digest = "pending"` + `git_commit = "unknown"` on smoke rows (REPRO-03 data) | 02-07 post-pass audit | 02-08 retroactive (DEV-1021); image v18 baked + verified on G2 diag |
| Wedged bootstrap pods burning the full 30-min ceiling silently | 02-07 v13 | `fix(preflight): terminate pod on TIMEOUT instead of leaking RUNNING` (commit `ab31d97`) |

## Pre-existing Issues Resolved / Carried Forward

- **REQUIREMENTS.md REPRO-02 schema-vs-data trap** (flagged 2026-05-06) → resolved by 02-05 with lockfile data populated; lesson generalized to REPRO-03 via 02-08. Audit heuristic to add: "every `[x]` REPRO requirement must have both schema enforcement and a sampled data row showing non-placeholder values."

## Pass-Through Gates (Not Run This Session)

- `/gsd-code-review 02` — advisory; recommend running before Phase 3 begins.
- `pytest` regression — last run was during 02-08 verification (commit `34c3607` notes); should re-run before Phase 3.

## Routing

```
/gsd-verify-work 2          # Independent audit by gsd-verifier subagent of this refresh
                            # (this file is operator bookkeeping, not the subagent's report)
# parallel/branch choice:
#   - run DEV-1019 sanity to close PREFLIGHT-02/03 inside Phase 2, OR
#   - /gsd-plan-phase 3 against .planning/phases/03-rocm-validation/03-CONTEXT.md
```
