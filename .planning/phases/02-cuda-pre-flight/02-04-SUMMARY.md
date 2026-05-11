---
phase: 02-cuda-pre-flight
plan: 04
subsystem: preflight driver / stratification
gap_closure: false
closed_by:
  - "Plan 02-05 (lockfile pending-revisions + bootstrap SDK path)"
  - "Plan 02-07 (multi-service pod startup + corpus_500 in image + operator transport)"
  - "Plan 02-08 (image_digest + git_commit lineage capture, DEV-1021)"
requires:
  - "Plan 02-01 (substrate/cuda.py)"
  - "Plan 02-02 (gate runners g1/g2/g3/g5)"
  - "Plan 02-03 (pod_entrypoint.sh, RunPod provisioning, audit)"
  - "Plan 02-05 (lockfile data + bootstrap SDK provisioning)"
  - "Plan 02-07 (multi-service startup + transport via fetch_results)"
provides:
  - "tools/run_preflight.py (bootstrap | smoke | sanity driver)"
  - "config/sanity_strata.yaml + tools/build_strata.py (sanity gate count source)"
  - "docs/OPERATOR-CHECKLIST-PHASE-02.md (operator runbook)"
  - "PREFLIGHT-01 closed: 5-call G1 smoke on H100 completes end-to-end (verdict pass)"
tags: [preflight, smoke, sanity, h100, dev-1018, gap-closed]
---

# Phase 02 Plan 04 — Summary

## Outcome

PREFLIGHT-01 closed. Per-stage timings, audit, env-sidecar, and substrate-fingerprint all proven on real H100 spend via session `20260509T231720Z`.

PREFLIGHT-02 (G1/G2/G3/G5 sanity baselines) and PREFLIGHT-03 (substrate fingerprint=cuda on sanity results) remain pending operator-driven sanity execution — out of scope for this plan, tracked as DEV-1019 with the same driver code path.

## Path-to-close

Plan 02-04 shipped Tasks 1–3 (build_strata, run_preflight driver, operator checklist) at commits `1c7e70d`, `8cc35e3`, `097f95e`, `ba2c1a4`, `bd5e6eb` on 2026-05-06 and was paused before Task 4 (real-spend smoke + sanity) when an operator dry-run surfaced GAP-3 (lockfile pending revisions; manual `runpodctl` bootstrap step). Operator selected path C: defer real spend, route to follow-up gap-closure planning. $0 was spent on this plan's Task 4.

Gap closure landed across three follow-up plans:

| Plan | Closed |
|---|---|
| 02-05 (gap closure) | lockfile pending-revisions + `--mode bootstrap` SDK provisioning + E2E mock chain |
| 02-06 | custom `rbox-pod` image (`FROM vllm/vllm-openai:v0.10.0`) with `pod_entrypoint.sh` baked as `ENTRYPOINT`, digest-pinned in `_DEFAULT_IMAGE` |
| 02-07 (gap closure) | multi-service pod startup (vLLM + Kokoro), `corpus_500` in image, operator-side fetch pod transport (`tools/fetch_results.py`), v8→v16→v18 image iteration |
| 02-08 (retroactive) | `image_digest` + `git_commit` populated in every result row (DEV-1021); REPRO-03 data verified |

Plan 02-04 Task 4 (smoke real-spend) executed inside 02-07's T7, recorded under `results/preflight/20260509T231720Z.json`.

## Smoke verdict (D-25 evidence)

Session `20260509T231720Z` — pod `d6ii16l245t41m`, GPU H100 NVL, image v9 (DEV-1021 not yet baked at run time):

```json
"smoke_verdict": {
  "a_5_rows": true,
  "b_under_30min": true,
  "c_under_1usd": true,
  "d_per_stage_timings": true,
  "e_env_sidecar": true,
  "f_audit_clean": true,
  "pass": true
}
```

- Run id: `2f6b0aa20acb4ebda0302d51b98c6334` (5 rows in `results/smoke/`).
- Wall-clock: 185.66 s (well under the 30-min ceiling).
- Final ledger spend: $0.00 reported (pod terminated before RunPod's billing API refreshed; estimated true spend ~$0.14 at $2.69/hr × ~3 min). Within D-25(c) ceiling either way.
- Audit: 0 violations across extension_check, manifest_check (500 of 755 expected — corpus_500 only in smoke image, g711/hesitation excluded by `.dockerignore`), pii_check.
- Pod terminal state: `GONE` (self-termination via `runpod.terminate_pod()` in pod_entrypoint v13+).

### Per-stage timing observations (smoke)

Smoke is correctness, not measurement — but the row content is real:

| Call | STT TTFT (ms) | LLM TTFT (ms) | LLM decode (ms/tok) | TTS first-audio (ms) | E2E (ms) |
|---|---|---|---|---|---|
| 0001 (cold) | 12768.92 | 130.96 | 5.61 | 465.36 | 14077.59 |
| 0002 | 193.89 | 162.65 | 5.61 | 382.75 | 1446.48 |
| 0003 | 121.95 | 162.25 | 5.56 | 377.51 | 1367.30 |
| 0004 | 102.46 | 168.71 | 5.65 | 410.94 | 1414.66 |
| 0005 | 110.07 | 138.94 | 5.54 | 421.84 | 1408.43 |

Cold-load STT dominates call 0001 (12.7 s — faster-whisper INT8 first decode loads the encoder); warm-path STT settles at 100–200 ms. LLM TTFT 130–170 ms, decode ~5.6 ms/token. Kokoro CPU first-audio 380–470 ms (within the §5.3 reference range). E2E warm-path ~1.4 s.

These are not gate measurements — they are smoke evidence. The G1 gate (DEV-1018 sanity) will produce N=500 distribution numbers under load with the same pipeline.

## REPRO-03 lineage

On the smoke result rows (`2f6b…jsonl`):

| Field | Value | Verified by |
|---|---|---|
| `schema_version` | `1.0` | row |
| `substrate` | `cuda` | row |
| `asset_manifest_sha` | `751423c77…f03d73` | row |
| `model_shas.*` | populated (4 entries) | row |
| `image_digest` | `pending` | row (pre-DEV-1021) |
| `git_commit` | `unknown` | row (pre-DEV-1021) |
| `run_id`, `timestamp_utc` | populated | row |

`image_digest` and `git_commit` were the two known REPRO-03 gaps on smoke. **Closed by Plan 02-08 (DEV-1021)** with independent verification on a G2 diag pod (`jow8x9kugpkgxm`, image v18, session `20260510T132812Z-dev1021-verify`) producing rows with `image_digest=sha256:abcf19f8…ea9d217` and `git_commit=f049bb87…`. The fix is harness-side (read `RBOX_IMAGE_DIGEST` env var) plus image-side (`/workspace/.git_commit` baked at build time) and is now wired into `provision()` and `_DEFAULT_IMAGE`.

A fresh smoke run is not required to ship the closure; PREFLIGHT-01 is correctness-of-pipeline and was satisfied by `2f6b`. The lineage data path is satisfied by the G2 diag run and the fix is in HEAD. Future smoke / sanity / phase-3 runs will carry both proofs on the same row.

## Final state

- `[x]` PREFLIGHT-01 (this plan, via 02-07 T7)
- `[ ]` PREFLIGHT-02 (DEV-1019 sanity baselines — operator-driven)
- `[ ]` PREFLIGHT-03 (substrate fingerprint=cuda on sanity results — DEV-1019)

## Operator's next action

1. `/gsd-verify-work 2` to refresh `02-VERIFICATION.md` against current state.
2. Choose:
   - Run DEV-1019 sanity to close PREFLIGHT-02/03 inside Phase 2, OR
   - Archive Phase 2 with sanity carved out as an explicit Phase-3-precondition.
3. `/gsd-discuss-phase 3` once Phase 2 verification status is acceptable.
