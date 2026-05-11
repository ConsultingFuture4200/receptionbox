---
phase: 02-cuda-pre-flight
audit_kind: independent_gsd_verifier
audited_utc: 2026-05-10T18:55:00Z
auditor: gsd-verifier subagent (Claude Opus 4.7)
companion_file: 02-VERIFICATION.md (operator-side bookkeeping, preserved as-is)
verdict: phase_complete_with_carve_outs
status: human_needed
score: 8/10 must-haves verified; 2 explicitly carved out as DEV-1019
overrides_applied: 2
overrides:
  - must_have: "SC-1 sub-criterion: final_spend_usd < $1 on smoke verdict"
    reason: "Ledger reports final_spend_usd=0.0 because the RunPod billing API lags pod termination. Pod wall-clock was 185.66 s on H100 NVL at $2.69/hr ≈ $0.14 estimated true spend — well under $1 either way. Operator-documented behaviour in 02-07-SUMMARY 'Process notes' and acknowledged in 02-04-SUMMARY."
    accepted_by: "operator (Dustin Powers, Path-A decision 2026-05-10)"
    accepted_at: "2026-05-10T16:35:00Z"
  - must_have: "SC-4 sub-criterion: image_digest + git_commit populated on smoke run 2f6b… result rows"
    reason: "Smoke run 2f6b was executed on image v9 — pre-DEV-1021. Rows carry image_digest='pending' and git_commit='unknown' literally. The DEV-1021 lineage fix was verified independently on the G2 diag pod jow8x9kugpkgxm (image v18, post-fix): rows there show image_digest=sha256:abcf19f8…ea9d217 and git_commit=f049bb87…. Operator argument (split-proof): smoke verdict (D-25) is correctness-of-pipeline and does not include lineage as a sub-criterion; lineage is a separate REPRO-03 requirement satisfied by the diag-pod row plus the code fix in HEAD. _DEFAULT_IMAGE is repinned to v18 so all future runs inherit the fix automatically."
    accepted_by: "operator (Dustin Powers, Path-A decision 2026-05-10)"
    accepted_at: "2026-05-10T16:35:00Z"
carve_outs:
  - requirement: PREFLIGHT-02
    disposition: DEV-1019 (operator-driven sanity), explicit deferral
    reasoning: "Sanity baselines for G1/G2/G3/G5 on H100 are a separate ~$4.49 operator-driven session. Roadmap.md Phase 2 row already marked [~] with sanity carved out. Closure path remains intact via the same gates/g{1,2,3,5}/runner.py and tools/run_preflight.py --mode sanity codepath that smoke proved out."
  - requirement: PREFLIGHT-03
    disposition: DEV-1019 (operator-driven sanity), explicit deferral
    reasoning: "Substrate-fingerprint path (substrate='cuda') is proven on every smoke row and on the DEV-1021 verify row. The row-data side of PREFLIGHT-03 (sanity-gate rows carrying full lineage + substrate fingerprint) waits on DEV-1019 sanity execution."
human_verification:
  - test: "Decide carve-out vs in-phase closure for DEV-1019 sanity"
    expected: "Operator chooses either (a) run DEV-1019 sanity to close PREFLIGHT-02/03 inside Phase 2 (~$4.49) before /gsd-plan-phase 3, or (b) accept the carve-out and let sanity be a Phase 3 precondition. Either choice is roadmap-compatible; this is a budget/sequencing decision, not a verification gap."
    why_human: "DEV-1019 carve-out is a deliberate scope choice, not a programmatic failure. Cannot be resolved by code inspection."
  - test: "Commit-vs-gitignore review of ~22 untracked files"
    expected: "Operator triages results/_pulled/, results/g{1,2,3,5}/, results/smoke/, results/preflight/, secrets/, .planning/debug/, three RunPod probe scripts in tools/, and docs/receptionbox-technical-prd-v0_2-2026-05-06.md. Evidence files cited in SUMMARY artifacts (the smoke jsonl, env.json, audit.json, dev1021-verify env.json) MUST be committed so future audits can re-verify against a SHA-pinned tree. Secrets and pulled diag-pod artifacts may legitimately be gitignored."
    why_human: "Mix of legitimate evidence-to-commit and legitimate gitignore-candidates; a programmatic split would mis-classify. See AUDIT-FINDING-3 below."
audit_findings:
  - id: AUDIT-FINDING-1
    severity: info
    title: "Smoke run rows carry placeholder lineage; lineage proof split across two runs"
    detail: "results/smoke/2f6b…jsonl: image_digest='pending', git_commit='unknown' (literal strings, all 5 rows). Lineage is proven separately on results/_pulled/jow8x9kugpkgxm/g2/e9319ce2…jsonl with image_digest=sha256:abcf19f8d84c…ea9d217 and git_commit=f049bb8748678ca9…. The split-proof argument is sound — but is a process antipattern (a single proof would be cleaner). Future smoke / G1 / G2 cohorts will carry both proofs on the same row because _DEFAULT_IMAGE is now repinned to v18 and the fix is in HEAD; recommend regenerating smoke on the next paid pod-session for archival cleanliness, not as a verification blocker."
  - id: AUDIT-FINDING-2
    severity: info
    title: "final_spend_usd=0.0 reported on smoke is misleading without context"
    detail: "results/preflight/20260509T231720Z.json shows final_spend_usd=0.0 despite wall_clock_s=185.66 on H100 NVL. Operator note explicitly states the RunPod billing API lags pod termination, so the ledger reads $0 pre-settlement. The wall-clock×hourly-rate estimate (~$0.14) is the operative truth and is still under the $1 D-25(c) ceiling. Recommend: add an estimated_spend_usd field to the preflight JSON that derives spend from wall_clock × pod_hourly_rate so the verdict is auditable without external context. Tracked as future hardening, not a blocker."
  - id: AUDIT-FINDING-3
    severity: warning
    title: "Evidence files cited in SUMMARY artifacts are not git-tracked"
    detail: "git status shows results/_pulled/, results/g{1,2,3,5}/, results/smoke/, results/preflight/ as UNTRACKED. The audit cites: results/preflight/20260509T231720Z.json, results/smoke/2f6b0aa20acb4ebda0302d51b98c6334.{jsonl,env.json}, results/smoke/1778368799.audit.json, results/preflight/20260510T132812Z-dev1021-verify.json, results/_pulled/jow8x9kugpkgxm/g2/e9319ce2…{jsonl,env.json}. These files exist on disk RIGHT NOW and contain the claimed values — verification is currently sound. However, any future audit (Phase 4 repro-manifest seal especially) will fail to reproduce the citations from a fresh clone. RECOMMEND: commit the cited evidence to git, even if results/_pulled/ remains gitignored for diag-pod by-products."
  - id: AUDIT-FINDING-4
    severity: info
    title: "Pre-DEV-1021 sanity stub rows in results/g{1,2,3,5}/"
    detail: "Each of results/g{1,2,3,5}/ contains 2 jsonl files dated May 9 17:25-19:28 with 10 rows each and image_digest='pending', git_commit='unknown'. These look like early diag/test outputs from substrate validation, NOT full sanity baselines (the gates need 200-500 rows). Do not mistake these for PREFLIGHT-02 completion. The carve-out narrative remains correct: full sanity = DEV-1019."
  - id: AUDIT-FINDING-5
    severity: info
    title: "Plan 02-04 [x] dependency chain is sound"
    detail: "Plan 02-04 was paused before Task 4 (real-spend smoke) when GAP-3 surfaced. Task 4 was executed inside Plan 02-07 T7 on session 20260509T231720Z. The 02-04 frontmatter `closed_by` declares this dependency, and 02-07 frontmatter `closes_gaps` includes 'Plan 02-04 Task 4 deferral'. The [x] mark on 02-04 with a closed_by pointer is acceptable bookkeeping for a paused-then-closed-by-successor pattern. ROADMAP.md Phase 2 row reflects this correctly."
  - id: AUDIT-FINDING-6
    severity: info
    title: "Code-level DEV-1021 implementation verified end-to-end"
    detail: "All four code/build artifacts cited in 02-08-SUMMARY are present and correct: (1) orchestration/runpod_h100.py:108 forwards RBOX_IMAGE_DIGEST=image_ref; _DEFAULT_IMAGE at line 32-35 is sha256:abcf19f8…ea9d217. (2) substrate/cuda.py:152-181 reads RBOX_IMAGE_DIGEST env var first, lockfile fallback preserved, handles bare and full-qualified digest formats. (3) Dockerfile lines 138-139 declare ARG GIT_COMMIT=unknown and RUN echo $GIT_COMMIT > /workspace/.git_commit AFTER heavy COPY/pip layers (cache preservation intact). (4) scripts/build_pod_image.sh lines 55-56, 64, 85 resolve git rev-parse HEAD and pass as build-arg. (5) gates/_runner_base.py:42-71 implements the 3-step fallback chain (git rev-parse → /workspace/.git_commit → 'unknown'). Commit 34c3607 matches the claim."
---

# Phase 02: cuda-pre-flight — Independent Audit (gsd-verifier)

**Companion to** `02-VERIFICATION.md` (operator-side bookkeeping). This file is the independent audit explicitly requested by the operator at the bottom of that file (`/gsd-verify-work 2`). Both files are preserved.

## Verdict

**`phase_complete_with_carve_outs`** — Phase 2 has achieved its goal (end-to-end pipeline assembles and runs once on RunPod H100 CUDA substrate with substrate + orchestration + cost ledger + result store all proven against real spend) within the carve-outs the operator has explicitly accepted. PREFLIGHT-02/03 sanity baselines remain open as DEV-1019, which is a deliberate scope choice not a verification failure. There are no blocking issues; the human-verification items below are decisions, not gaps.

**Score:** 8/10 must-haves verified; 2 (PREFLIGHT-02, PREFLIGHT-03) carved out as DEV-1019.

## Goal-Backward Verification

**Phase Goal** (verbatim from ROADMAP.md): _End-to-end pipeline (LiveKit Agents → vLLM → faster-whisper → Chatterbox/Kokoro) assembles and runs once on RunPod H100 CUDA substrate, with substrate + orchestration + cost ledger + result store all proven against real spend before any MI300X provisioning._

### Observable Truths (derived from ROADMAP Success Criteria)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | 5-call G1 smoke test on H100 completes end-to-end in under 30 minutes for under $1, with results landing in `results/` via substrate-agnostic gate runner and emitting `env.json` sidecar | PASSED (override on final_spend_usd) | `results/preflight/20260509T231720Z.json` smoke_verdict.pass=true, wall_clock_s=185.66 (<<30 min), all 6 D-25 sub-criteria true. `results/smoke/2f6b…jsonl` has 5 rows with non-null per-stage timings. `results/smoke/2f6b…env.json` exists. final_spend_usd=0.0 override accepted (RunPod billing-API lag; ~$0.14 estimated true spend). |
| 2 | Sanity runs of G1, G2, G3, G5 on H100 produce non-degenerate baseline numbers with substrate fingerprint=cuda | CARVED OUT to DEV-1019 | Full sanity baselines (200-500 rows per gate) NOT executed. Substrate-fingerprint path proven on every smoke row and DEV-1021 verify row (`substrate:"cuda"`). The 10-row stub files in `results/g{1,2,3,5}/` are early diag outputs, NOT baselines. Operator explicitly defers to DEV-1019. |
| 3 | In-instance watchdog terminates the H100 pod after `max_minutes`, rsync result-pull fires on shutdown, pre-teardown audit confirms no PII or real-audio files | PASSED | `tools/pod_entrypoint.sh:183` defines `_start_watchdog` consuming `MAX_MINUTES`; line 306 calls `runpod.terminate_pod()`. Smoke verdict shows pod terminal state=GONE. Result transport pivoted from rsync-push to fetch_pod-pull via `tools/fetch_results.py` (architecture change documented in 02-07-SUMMARY); pulls verified by presence of `results/_pulled/` artifacts. `results/smoke/1778368799.audit.json` reports 0 violations across extension_check / manifest_check / pii_check. |
| 4 | Persistent HF model cache on cloud volume eliminates re-downloads; every result row records `(image_digest, model_sha, asset_manifest_sha, git_commit, run_id, timestamp_utc)` | PASSED (override on smoke-row lineage; verified separately on G2 diag) | HF cache on `/models` network volume per 02-06 (idempotency verified across 3 SKIP-on-rerun cycles, per 02-06-SUMMARY). All 6 lineage fields present on `results/_pulled/jow8x9kugpkgxm/g2/e9319ce2…jsonl` (post-DEV-1021): `image_digest=sha256:abcf19f8d84c…ea9d217`, `git_commit=f049bb87…`, `model_shas={4 entries}`, `asset_manifest_sha=751423c77…`, `run_id`, `timestamp_utc`. Smoke run 2f6b carries placeholder image_digest+git_commit (pre-fix) — override accepted; lineage proof split across two runs. |

**Score:** 4/4 ROADMAP Success Criteria satisfied (2 with operator-accepted overrides; 1 with explicit DEV-1019 carve-out on its sanity component).

### Per-Requirement Verification

| Req | Status | Evidence (independently re-verified on disk) |
|-----|--------|----------------------------------------------|
| HARNESS-02 | PASS | `substrate/cuda.py` (4-adapter composition), `substrate/livekit_pipeline.py` shipped 02-01. Env-fingerprint capture at line 130. DEV-1021 env-var read at 152-181. |
| HARNESS-05 | PASS | `harness/env_sidecar.py` exists; smoke + DEV-1021-verify both wrote pydantic-validated env.json files; checked schema_version=1.0 on `2f6b…env.json` and `e9319ce2…env.json`. |
| HARNESS-06 | PASS | `gates/g{1,2,3,5}/runner.py` all present and runnable; substrate-agnostic per `gates/_runner_base.py`. |
| CLOUD-04 | PASS | `tools/pod_entrypoint.sh` watchdog at line 183, terminate at line 306; baked as ENTRYPOINT per Dockerfile. |
| CLOUD-05 | PASS | HF cache on `/models` volume per 02-06; lockfile populated via 02-05; idempotent. |
| CLOUD-06 | PASS | `tools/audit_pod_state.py` exists; smoke audit `1778368799.audit.json` shows 0 violations across 3 checks. |
| REPRO-03 | PASS (split-proof override) | Schema enforced in 02-02 (`gates/_runner_base.py` populates all 6 fields). Data verified on G2 diag row `e9319ce2…` — all 6 fields non-placeholder. Smoke row `2f6b…` carries placeholder image_digest+git_commit (pre-fix). Operator-accepted override. |
| PREFLIGHT-01 | PASS | Session `20260509T231720Z`, pod `d6ii16l245t41m`, run `2f6b…`, all 6 D-25 sub-criteria true, pod state GONE. |
| PREFLIGHT-02 | CARVED OUT to DEV-1019 | Not executed; explicit operator deferral documented in ROADMAP, REQUIREMENTS, STATE, and 02-VERIFICATION. |
| PREFLIGHT-03 | CARVED OUT to DEV-1019 | Substrate-fingerprint path proven; sanity-row data verification deferred to DEV-1019. |

### Per-Plan Dependency-Chain Audit

| Plan | ROADMAP `[x]` | Independently Verified? | Note |
|------|---------------|--------------------------|------|
| 02-01 | yes | yes | substrate/cuda.py + adapters + LiveKit pipeline present |
| 02-02 | yes | yes | gates/g{1,2,3,5}/runner.py + _runner_base.py + env_sidecar.py present |
| 02-03 | yes | yes | pod_entrypoint.sh + audit_pod_state.py + provisioning present |
| 02-04 | yes (via 02-07 T7) | yes | AUDIT-FINDING-5: paused-then-closed-by-successor pattern is sound; 02-07 frontmatter explicitly closes 02-04 T4 deferral; ROADMAP row annotated |
| 02-05 | yes | yes (via earlier verification cycles) | Gap-closure lockfile data + bootstrap SDK; 4 models confirmed on volume `rgkzzrl34n` per 02-06-SUMMARY |
| 02-06 | yes | yes | Dockerfile + scripts/build_pod_image.sh present; `_DEFAULT_IMAGE` repinned multiple times culminating at v18 |
| 02-07 | yes | yes | 8 image iterations documented; smoke verdict pass on 2f6b confirmed end-to-end |
| 02-08 | yes | yes | DEV-1021 commit `34c3607` matches SUMMARY claims field-by-field (AUDIT-FINDING-6); G2 diag row carries real lineage |

## Independence Test — What the auditor verified directly (not just trusted from SUMMARY)

1. **Smoke verdict JSON** read directly: `results/preflight/20260509T231720Z.json` — all 6 sub-criteria true, pod state GONE.
2. **Smoke jsonl rows** read directly: 5 rows present, per-stage timings non-null, but `image_digest:"pending"` and `git_commit:"unknown"` confirmed literally.
3. **Smoke env.json sidecar** read directly: schema_version=1.0, substrate=cuda, GPU=H100 NVL, all 4 model SHAs present.
4. **Smoke audit.json** read directly: 0 violations across extension_check, manifest_check, pii_check.
5. **DEV-1021 verify G2 row** read directly from `results/_pulled/jow8x9kugpkgxm/g2/e9319ce2…jsonl` — image_digest=sha256:abcf19f8d84c… and git_commit=f049bb87… confirmed.
6. **Code claims** independently grepped: `_DEFAULT_IMAGE` value, `RBOX_IMAGE_DIGEST` env-var forwarding, `_lookup_image_digest` env-first read, `_git_commit` fallback chain, Dockerfile `ARG GIT_COMMIT` placement, build-script git rev-parse pass-through — all match SUMMARY claims.
7. **Pre-DEV-1021 sanity stubs** flagged: 10-row jsonl files in `results/g{1,2,3,5}/` carry placeholder lineage; correctly identified as diag outputs, not PREFLIGHT-02 evidence.
8. **Commit `34c3607`** inspected: matches DEV-1021 claim end-to-end.

## Decisions on contested points

| Claim | Auditor accepts? | Reasoning |
|-------|------------------|-----------|
| Smoke row carries placeholder lineage but PREFLIGHT-01 is still satisfied because lineage isn't a D-25 sub-criterion | YES (with caveat AUDIT-FINDING-1) | D-25 sub-criteria are: a_5_rows / b_under_30min / c_under_1usd / d_per_stage_timings / e_env_sidecar / f_audit_clean. None require lineage on the verdict row. REPRO-03 is a separate requirement satisfied by the G2 diag row + the code fix in HEAD. The split-proof is structurally valid; the cleanup recommendation is process hygiene, not a verification gap. |
| `final_spend_usd=0.0` is acceptable because RunPod billing API lags | YES (with caveat AUDIT-FINDING-2) | The wall_clock × hourly-rate estimate (~$0.14) is comfortably under $1, and the operator's documentation of the billing-lag is consistent with RunPod behavior. The c_under_1usd verdict is correct on operative-truth grounds. Recommend adding an `estimated_spend_usd` field for future audit reproducibility, but not blocking. |
| ~22 untracked files containing evidence cited in SUMMARY artifacts | YES (with WARNING AUDIT-FINDING-3) | Evidence is on-disk and verifiable RIGHT NOW. The verification holds at this moment. However, a Phase 4 repro-manifest seal from a fresh clone will fail to find the citations. Recommend committing the cited evidence (preflight/, smoke/, the DEV-1021-verify env.json + jsonl) before Phase 4. Not a Phase 2 blocker. |
| 02-04 marked `[x]` because 02-07 T7 closed Task 4 | YES | The closed_by chain is documented in both 02-04-SUMMARY and 02-07-SUMMARY frontmatter; the paused-then-closed-by-successor pattern is acceptable bookkeeping; ROADMAP row annotation makes the dependency visible. |

## Recommendations (non-blocking)

1. **Before Phase 4 repro-manifest seal**, commit the evidence files cited in this audit (per AUDIT-FINDING-3). At minimum: `results/preflight/20260509T231720Z.json`, `results/smoke/2f6b…{jsonl,env.json}`, `results/smoke/1778368799.audit.json`, `results/preflight/20260510T132812Z-dev1021-verify.json`, `results/_pulled/jow8x9kugpkgxm/g2/e9319ce2…{jsonl,env.json}`.
2. **Before DEV-1019 sanity execution**, add an `estimated_spend_usd` field to the preflight JSON derived from `wall_clock_s × pod_hourly_rate` so the c_under_1usd verdict is auditable without external context (per AUDIT-FINDING-2).
3. **On the next paid pod-session that produces smoke/sanity output**, the smoke row will naturally carry real lineage (because `_DEFAULT_IMAGE`=v18 and the harness fix is in HEAD). At that point, run a refresher smoke and supersede `2f6b…` as the canonical lineage-clean smoke artifact (per AUDIT-FINDING-1). This is hygiene, not a re-verification requirement.
4. **Pytest regression**: per the operator note in `02-VERIFICATION.md` "Pass-Through Gates", run `pytest` once before Phase 3 begins. Not run as part of this audit.

## Conclusion

The operator's narrative is supported by the evidence on disk. Both the smoke verdict and the DEV-1021 lineage fix are independently verifiable from the repository state. The two overrides (final_spend_usd=0.0 due to billing-API lag; smoke-row lineage placeholder closed by separate G2 diag pod) are structurally valid and well-documented. The two carve-outs (PREFLIGHT-02 + PREFLIGHT-03 → DEV-1019) are explicit scope decisions, not failures. Phase 2's roadmap goal is achieved within these accepted carve-outs.

Phase 3 (ROCm Validation) is unblocked from a Phase-2-verification standpoint. The operator's choice between (a) running DEV-1019 sanity inside Phase 2 first, or (b) carrying it as a Phase 3 precondition, is a sequencing/budget decision rather than a verification gap.

---

_Audited by gsd-verifier subagent on 2026-05-10T18:55:00Z._
_Companion to `02-VERIFICATION.md` (operator bookkeeping, preserved unchanged)._
