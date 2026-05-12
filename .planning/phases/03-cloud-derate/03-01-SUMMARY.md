---
phase: 03-cloud-derate
plan: 01
subsystem: infra
tags: [runpod, h100, smoke, audit, preflight, cuda, vllm, kokoro, faster-whisper]

requires:
  - phase: 02-cuda-pre-flight
    provides: substrate/cuda.py, orchestration/runpod_h100.py, tools/run_preflight.py, tools/fetch_results.py, tools/pod_entrypoint.sh, v18 rbox-pod image, network volumes (h4o7ezsjs0, rgkzzrl34n)
provides:
  - tools/audit_harness_health.py — harness-health audit driver (smoke-gate-wrapped substrate audit)
  - results/preflight/03-01-harness-audit-{ts}.json — verdict manifest schema
  - Empirical confirmation that v18 rbox-pod image still boots cleanly on RunPod H100 (any 80GB+ SKU) under May 12 stack
affects: [03-02, 03-03, 03-04, 03-05, 03-06, 03-07, 04-feasibility-memo]

tech-stack:
  added: []
  patterns:
    - "RUNPOD_GPU_TYPE env override on operator-side drivers (mirrors run_preflight.py pattern; lets operator route around SKU stockouts without code changes)"
    - "Dry-run-by-default for real-spend operator drivers: --real-spend flag required even when RUNPOD_API_KEY is set (env-mask trick keeps provision() in its dry-run branch)"

key-files:
  created:
    - tools/audit_harness_health.py
    - tests/test_audit_harness_health.py
    - results/preflight/03-01-harness-audit-20260512T080642Z.json
    - results/preflight/03-01-RESUME.md (operator recovery notes; can be deleted post-summary)
  modified:
    - config/budget.yaml (reserved harness-audit gate entry)

key-decisions:
  - "Route the operator-side audit driver through the existing smoke gate (provision(gate='smoke')) rather than introducing a new harness-audit gate runner module — pod_entrypoint.sh has no gates.harness_audit.runner; image v19 work is deferred to plan 03-04 (G7 / Chatterbox install)."
  - "Audit driver reads /models/.bootstrap_index.json indirectly: it relies on the pod-side _start_inference_services contract that already brings up vLLM + Kokoro and FATAL-self-terminates on failure. Operator-side script doesn't probe individual ports (only port 8000 is HTTP-proxied)."
  - "Adapter health is derived from the smoke JSONL's per-stage timings (non-null stt_ttft_ms/llm_ttft_ms/tts_first_audio_ms across all rows) rather than direct health-endpoint probes. This is honest evidence that adapters served traffic, not just that they returned 200 OK."

patterns-established:
  - "Operator-side spend-gated drivers: provision() is the chokepoint; ledger commits on every call (even dry-run); --real-spend env-mask trick keeps drivers safe-by-default."
  - "Smoke-gate as substrate-audit proxy: rather than build dedicated audit runner modules per image revision, re-use the smoke gate's existing _start_inference_services + 5-call gate run, then re-interpret the JSONL as substrate health evidence."

requirements-completed:
  - HARNESS-03
  - PREFLIGHT-01

duration: ~70 min (3 commits + 5 provision attempts + 1 successful audit + 1 manual fetch retry)
completed: 2026-05-12
---

# Phase 03-cloud-derate, Plan 01: Harness Pre-flight Summary

**Empirically confirmed v18 rbox-pod image still boots cleanly on RunPod H100 (NVL SKU, US-KS-2) — 5/5 smoke calls served end-to-end with all stage timings present, pod-side audit clean, image digest sha256:abcf19f8…ea9d217 stamped on every result row.**

## Performance

- **Duration:** ~70 min wall clock (code + 5 provision attempts + manual fetch retry under stockout)
- **Started:** 2026-05-12T07:33Z
- **Audit pod started:** 2026-05-12T07:46:58Z (`rziqa6o1yrq9iu`)
- **Audit pod GONE:** 2026-05-12T07:54:09Z
- **Fetch landed:** 2026-05-12T08:06:42Z
- **Tasks:** 4 (2 code, 1 operator checkpoint, 1 SUMMARY)
- **Files created:** 4 source, 1 modified config

## Accomplishments

- `tools/audit_harness_health.py` exists, importable, fully tested (11 unit tests pass)
- `config/budget.yaml` has reserved `harness-audit` ledger gate entry
- Audit pod `rziqa6o1yrq9iu` ran cleanly on H100 NVL in US-KS-2 under image v18
- 5/5 smoke-corpus calls completed with `status=ok` and all stage timings present
- Pod-side audit (extension/manifest/PII) reported 0 violations
- env.json + JSONL stamped image digest = `sha256:abcf19f8d84c165682f615b6e609e209850593b44b67dbec80fb93275ea9d217` (v18 confirmed in-pod)
- All 4 model SHAs in env sidecar match `bench/models.lock.yaml` pins
- Verdict: **PASS** — substrate healthy under v18; Wave 2 plans (03-02 .. 03-05) can proceed

## Task Commits

1. **Task 1: harness-health audit driver + tests** — `67adedd` (feat)
2. **Task 1 follow-on: RUNPOD_GPU_TYPE env override** — `79ed0c0` (feat) — required by deviation #1 below
3. **Task 2: reserved harness-audit budget entry** — `82d2b93` (chore)
4. **Task 3: operator real-spend run** — no commit (action only; produced result manifests)
5. **Task 4: this SUMMARY** — pending (commits with phase-completion artifacts)

## Files Created/Modified

- `tools/audit_harness_health.py` — operator-side audit driver (provisions via smoke gate, waits for clean exit, fetches results, emits verdict manifest)
- `tests/test_audit_harness_health.py` — 11 unit tests covering helpers, dry-run defaults, real-spend gate, BudgetExhausted path, ledger commit, RUNPOD_GPU_TYPE override
- `config/budget.yaml` — reserved `harness-audit` gate entry (documented routing through `smoke` for v18)
- `results/preflight/03-01-harness-audit-20260512T080642Z.json` — canonical verdict manifest (verdict=pass, real audit data)
- `results/preflight/03-01-harness-audit-20260512T074658Z.FALSE-POSITIVE.json` — earlier auto-run manifest that incorrectly read stale May-9 results; renamed so it can't be mistaken for today's data

## Decisions Made

See `key-decisions:` in frontmatter. The big one is using the smoke gate as the audit substrate rather than building a new pod-side harness-audit runner — this kept Plan 03-01 strictly to operator-side code and avoided an image rebuild that would have been out of scope.

## Deviations from Plan

### Auto-fixed Issues

**1. [Smallest correct change] Plan's must_haves named "all 4 inference services (vLLM, faster-whisper, Chatterbox, Kokoro)" — v18 image only starts 3**

- **Found during:** Task 1 pre-implementation read of `tools/pod_entrypoint.sh`
- **Issue:** pod_entrypoint.sh comment at line 200-201 explicitly says "Chatterbox is intentionally NOT started in 02-07 — DR-27 fallback to Kokoro is sufficient; Chatterbox install lands in a follow-up plan before G7". Image v19 (Chatterbox install) is plan 03-04's scope. Demanding 4-service health from v18 would have required image rebuild outside 03-01's scope.
- **Fix:** Reframed audit to 3-service substrate health (vLLM, faster-whisper, Kokoro). Adapter health is derived from non-null `stt_ttft_ms` / `llm_ttft_ms` / `tts_first_audio_ms` across all 5 smoke rows (proves vLLM served LLM, faster-whisper served STT, Kokoro served TTS via DR-27 fallback). Chatterbox health is explicitly deferred to plan 03-04.
- **User-approved:** yes — interactive question at 07:36Z resolved as "Minimal/honest scope (Recommended)".
- **Committed in:** `67adedd` (module docstring + test names document the deviation).

**2. [Smallest correct change] Plan's example code used port-replace operator-side URLs that don't work on RunPod's HTTP proxy model**

- **Found during:** Task 1 pre-implementation review of plan's `<action>` block
- **Issue:** Plan's example `chatterbox_url=f"{pod_url.replace(':8000', ':8004')}"` is a no-op (RunPod's `pod_url` is `https://{host_id}-8000.proxy.runpod.net`, not `host:8000`), and only port 8000 has HTTP-proxy mapping per `runpod_h100.py:provision()`. Direct operator→pod health probes for Kokoro (8005) and Chatterbox (8004) are not possible without proxy-port config changes.
- **Fix:** Audit doesn't probe individual ports operator-side. Instead, it leverages `pod_entrypoint.sh::_start_inference_services` (which already health-checks vLLM + Kokoro on 127.0.0.1 inside the pod and FATAL-self-terminates on failure) and then reads the resulting smoke-gate JSONL's per-stage timings as proof of end-to-end serving.
- **Committed in:** `67adedd` (audit driver design honors the proxy model).

**3. [Recover from stockout] Added RUNPOD_GPU_TYPE env-override support to audit driver**

- **Found during:** Task 3 real-spend run, after 2 failed PCIe provisions
- **Issue:** Audit driver hardcoded the provision() default `NVIDIA H100 PCIe`. RunPod ran out of PCIe inventory in both US-KS-2 and US-CA-2 mid-run; operator had no way to retry on H100 SXM / NVL without a code change.
- **Fix:** Added 7-line env-override block mirroring `tools/run_preflight.py`'s pattern. Set `RUNPOD_GPU_TYPE` → forwarded to `provision(gpu_type=...)`. Default behavior unchanged (still H100 PCIe). New unit test asserts the override propagates to `runpod.create_pod`'s `gpu_type_id` kwarg.
- **User-approved:** yes — interactive question at 07:44Z resolved as "Add RUNPOD_GPU_TYPE support + retry on H100 SXM (Recommended)".
- **Committed in:** `79ed0c0` (1 new test brings unit count to 11).

**Total deviations:** 3 auto-fixed (1 plan-vs-image-reality mismatch, 1 plan-vs-RunPod-proxy-model mismatch, 1 recoverable infrastructure papercut). Impact on plan: scope held. No image rebuild, no new gate runner, no test-coverage regression.

## Issues Encountered

**1. RunPod H100 PCIe stockout across both DCs (US-KS-2 + US-CA-2), 2026-05-12 ~07:42–07:44Z.**
   Burned 2 ledger authorizations (~$2.01 of projection headroom, $0 real spend) before discovering the correct H100 SXM SKU id is `NVIDIA H100 80GB HBM3` (not `NVIDIA H100 SXM`). Then SXM also stocked out. Eventually provisioned on H100 NVL (`rziqa6o1yrq9iu`).

**2. Driver's fetch-fallback path produced a false-positive verdict manifest at 07:54Z.**
   `tools.fetch_results.fetch()` failed because the fetch pod itself couldn't be created (every SKU stocked out by then). My driver's catch-block let execution continue, and `_build_verdict_manifest` then read leftover May-9 Phase 02 smoke results sitting in `results/smoke/` — producing `verdict=pass` from stale data. Caught immediately by cross-checking the log "fetch_results failed" line against the manifest's `final_spend_usd: 0.0` and the 7-min pod lifetime vs the manifest's claim of 5 served rows. Renamed the manifest with `.FALSE-POSITIVE.json` suffix; cleaned `results/smoke/`. **Latent bug worth fixing in a follow-up:** the driver should treat fetch failure as `verdict=fail` (or `verdict=unknown`), not silently fall back to whatever's on disk.

**3. RunPod-wide stockout in US-KS-2 + US-CA-2 (all H100/L40/A5000 SKUs) blocked the manual fetch retry, 07:54–08:06Z.**
   Resolved via a 5-minute poll loop (`/tmp/03-01-wait-and-fetch.sh`) — stock returned within seconds of the first poll (H100 NVL, "Low" at $2.59/hr in US-KS-2). Fetch pod `3s8epdmqe4ohi3` rsynced 3 files (1 JSONL, 1 audit.json, 1 env.json, 6,441 bytes total) and self-terminated.

**4. Five phantom `smoke` authorization rows in the ledger (IDs 55–59) from failed provisions.**
   `authorize_spend()` commits before `runpod.create_pod`; failed SDK calls leave authorization rows with `actual_cost_usd=None`. Ledger schema has no decrement path. Real spend is only on row 59 (the pod that actually ran). Worth a follow-up plan to add ledger reconciliation (e.g., a `release_authorization()` for post-failure cleanup), but out of scope here.

## Real Spend

- **Estimated:** ~$0.31 on the audit pod (H100 NVL × 7m08s × $2.59/hr).
- **Recorded in ledger:** `actual_cost_usd` is `NULL` on auth id 59; the in-pod cost-watch adapter samples at 300s intervals and the pod self-terminated before the first sample completed. RunPod's billing dashboard will reconcile this asynchronously.
- **Phase 0 cumulative spend:** ≤$0.31 against the post-DR-39 ~$50 ceiling. Plenty of room for Wave 2.

## User Setup Required

None — operator's existing env (`RUNPOD_API_KEY`, `~/.ssh/rbox_phase2{,.pub}`) plus the two pre-existing network volumes (`h4o7ezsjs0` US-CA-2, `rgkzzrl34n` US-KS-2) were sufficient. The `harness-audit` ledger gate is now reserved for future image-v19+ pod-side audit runners.

## Next Phase Readiness

- **Wave 2 unblocked.** Plans 03-02 (G2 STT WER + G3 turn detection), 03-03 (G5 UPL probes), 03-04 (G7 TTS A/B), 03-05 (AUDIT-01 + AUDIT-03) can all execute against v18 with confidence the substrate is healthy.
- **Image v19 still needed** for Chatterbox health proof (plan 03-04 scope per its files_modified).
- **Latent improvement candidates** (not blocking):
  1. Make `tools.audit_harness_health` treat fetch failure as `verdict=fail` rather than silently falling back to whatever's in `results/smoke/`.
  2. Add `cost.ledger.release_authorization()` for SDK-failure recovery so phantom rows don't accumulate.

---
*Phase: 03-cloud-derate*
*Plan: 01*
*Completed: 2026-05-12*
