# Roadmap: receptionBOX Phase 0 — Cloud Benchmark Validation

## Overview

Phase 0 is a one-week, $150-ceiling cloud benchmark harness that produces derated Strix Halo (gfx1151) predictions for receptionBOX latency, WER, turn-detection, UPL, and TTS, packaged as a feasibility memo v0.4 update plus a sales-safe gate decision package. The roadmap follows dependency order, not gate order: a no-GPU-spend foundation phase prevents six of eleven critical pitfalls, then CUDA pre-flight on RunPod H100 assembles the pipeline at known-working-substrate cost, then ROCm validation on TensorWave MI300X collects the load-bearing measurements with co-residency and gfx1151 kernel-coverage audits, then synthesis derates per-stage with 80% confidence bands and produces a gate decision survivable under adversarial review.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

- [ ] **Phase 1: Foundation** — Repo skeleton, asset curation, cost rails, NC-R14 resolution; zero GPU spend
- [ ] **Phase 2: CUDA Pre-flight** — RunPod H100 substrate proves pipeline with 5-call smoke + G1/G2/G3/G5 sanity
- [ ] **Phase 3: ROCm Validation** — TensorWave MI300X full G1–G7 measurement + co-residency + gfx1151 audit
- [ ] **Phase 4: Synthesis & Gate Decision** — Per-stage derating, sales-safe report, feasibility memo v0.4, go/no-go package

## Phase Details

### Phase 1: Foundation
**Goal**: All structural pre-conditions for cloud spend exist on disk — corpora, cost rails, substrate skeletons, derating module, decisions — such that Phase 2 can begin with zero blockers and zero rework risk.
**Depends on**: Nothing (first phase)
**Requirements**: INFRA-01, INFRA-02, INFRA-03, INFRA-04, INFRA-05, INFRA-06, ASSETS-01, ASSETS-02, ASSETS-03, ASSETS-04, ASSETS-05, ASSETS-06, ASSETS-07, ASSETS-08, HARNESS-01, HARNESS-04, CLOUD-01, CLOUD-02, CLOUD-03, DERATE-01, REPRO-01, REPRO-02, DECISION-NC-R14, DECISION-DOCS
**Success Criteria** (what must be TRUE):
  1. All 5 evaluation corpora (500-call, 200 G.711, hesitation, 200 UPL + 50 benign control, 30 TTS pair) are SHA-pinned in `assets/manifest.csv` with provenance line per asset, and gate runners refuse assets not listed
  2. Cost ledger refuses cloud provisioning when `budget_remaining - projected_cost*1.5 < 0`, verified by a dry-run unit test against synthetic budget data
  3. NC-R14 sharing-policy resolution is recorded in `docs/decisions/dr-31-sharing-policy.v0.1.0.md` and operator has dropped parent thUMBox PRDs (technical + business v2.1), discovery addendum v0.2, hardware-pivot addendum v0.1, feasibility memo v0.3, and virtual benchmark plan v0.1 into `docs/`
  4. Substrate ABC, result schema (pydantic + `schema_version`), Makefile single-command targets, uv lockfile, image/model lockfiles, and `derating/strix_model.py` skeleton all type-check and pass unit tests on synthetic data
  5. RunPod and TensorWave accounts are provisioned with provider-level $75 caps each, `cost-watch.py` daemon polls billing APIs every 5 minutes, and dual cost-cap rails are demonstrably wired
**Plans**: 5 plans
Plans:
- [x] 01-01-PLAN.md — Repo skeleton + uv project + Makefile + pre-commit + config-as-code (INFRA-01..05)
- [x] 01-02-PLAN.md — Substrate ABC + GateResult + cost ledger + derating skeleton + lockfiles (INFRA-06, HARNESS-01, HARNESS-04, DERATE-01, REPRO-01, REPRO-02)
- [x] 01-03-PLAN.md — Reference prompt + UPL probes + benign control + TTS A/B text pairs + G.711 transcoder (ASSETS-04..08)
- [x] 01-04-PLAN.md — Local Kokoro audio rendering: 500-call corpus + 200 G.711 stratified subset + hesitation set (ASSETS-01..03)
- [x] 01-05-PLAN.md — Cost-watch daemon + provider adapters + orchestration skeletons + DR-31 + companion docs (CLOUD-01..03, DECISION-NC-R14, DECISION-DOCS)

### Phase 2: CUDA Pre-flight
**Goal**: End-to-end pipeline (LiveKit Agents → vLLM → faster-whisper → Chatterbox/Kokoro) assembles and runs once on RunPod H100 CUDA substrate, with substrate + orchestration + cost ledger + result store all proven against real spend before any MI300X provisioning.
**Depends on**: Phase 1
**Requirements**: HARNESS-02, HARNESS-05, HARNESS-06, PREFLIGHT-01, PREFLIGHT-02, PREFLIGHT-03, CLOUD-04, CLOUD-05, CLOUD-06, REPRO-03
**Success Criteria** (what must be TRUE):
  1. 5-call G1 smoke test on H100 completes end-to-end in under 30 minutes for under $1 of spend, with results landing in `results/` via the substrate-agnostic gate runner and emitting an `env.json` sidecar
  2. Sanity runs of G1, G2, G3, G5 on H100 produce non-degenerate baseline numbers with substrate fingerprint = `cuda` recorded for downstream cross-substrate consistency check
  3. In-instance watchdog terminates the H100 pod after `max_minutes`, rsync result-pull fires on shutdown, and pre-teardown cloud-storage audit confirms no PII or real-audio files survived the session
  4. Persistent HF model cache on cloud volume eliminates re-downloads across pods, and every result row records `(image_digest, model_sha, asset_manifest_sha, git_commit, run_id, timestamp_utc)`
**Plans**: 4 plans
Plans:
- [x] 02-01-PLAN.md — substrate/cuda.py composing 4 backend adapters + LiveKit AgentSession pipeline rig (HARNESS-02)
- [x] 02-02-PLAN.md — Substrate-agnostic gate runners g1/g2/g3/g5 + GateRunner base + env.json sidecar (HARNESS-05, HARNESS-06, REPRO-03)
- [ ] 02-03-PLAN.md — Pod entrypoint + watchdog + HF cache bootstrap + pre-teardown audit + real RunPod provisioning (CLOUD-04, CLOUD-05, CLOUD-06)
- [ ] 02-04-PLAN.md — Stratification config + pre-flight driver + operator checklist + real-spend smoke/sanity checkpoint (PREFLIGHT-01, PREFLIGHT-02, PREFLIGHT-03)

### Phase 3: ROCm Validation
**Goal**: TensorWave MI300X produces measurement-grade data for G1, G2, G3, G5, G7 against pinned corpora at concurrencies N=1/2/4 with per-stage decomposition, plus the three load-bearing audits (Chatterbox Day-1 kill-switch, co-residency stack-load, gfx1151 op coverage) that prevent the dominant Phase 0 → Phase 2 false-pass paths.
**Depends on**: Phase 2
**Requirements**: HARNESS-03, GATE-CHATTERBOX-D1, GATE-G1, GATE-G2, GATE-G3, GATE-G5, GATE-G7, AUDIT-01, AUDIT-02, AUDIT-03
**Success Criteria** (what must be TRUE):
  1. GATE-CHATTERBOX-D1 ROCm load smoke runs on Day 1 of MI300X work and produces an explicit pass/fail decision; on fail, Kokoro becomes the primary G1/G7 measurement engine and Chatterbox is flagged as a feasibility risk per DR-27
  2. G1 latency on the 500-call corpus at N=1/2/4 reports p50/p90/p99 per-stage (STT TTFT, LLM TTFT, LLM decode, TTS first-audio) and aggregate; G2 WER measured on 200 G.711 clips with both faster-whisper INT8 and ONNX-RT ROCm parallel paths; G3 turn-detection threshold sweep 400–1500ms in 100ms steps; G5 evaluated against the receptionBOX-shaped reference prompt with grammar-constrained generation ON; G7 renders both warm-path and cold-path TTS first-audio across 30 stimulus pairs
  3. Co-residency stack-load test (Whisper + Qwen3-4B + Chatterbox/Kokoro all loaded simultaneously under sustained load ≥ 5 min) records memory headroom, kernel mismatches, and crash detection without aborting; engine-swap-under-load demo flips TTS from Chatterbox to Kokoro mid-session via config row with measured swap-time
  4. `audit/gfx1151_op_status.md` exists with a status table (present / fallback / unknown) for every critical op used by Whisper, Qwen3-4B, Chatterbox, and Kokoro against the planned appliance ROCm minor + PyTorch wheel cut
**Plans**: TBD

### Phase 4: Synthesis & Gate Decision
**Goal**: A defensible synthesis report with per-stage roofline-derated Strix Halo predictions, 80% confidence bands, sales-safe excerpt, feasibility memo v0.4 fragment, and a Phase 0 gate decision package that survives adversarial review and can ground a paid-discovery SOW conversation with the firm.
**Depends on**: Phase 3
**Requirements**: DERATE-02, DERATE-03, DERATE-04, DERATE-05, REPORT-01, REPORT-02, REPORT-03, REPORT-04, REPORT-05, REPORT-06, REPORT-07, REPRO-04, REPRO-05, DECISION-NC-R12
**Success Criteria** (what must be TRUE):
  1. `make report` regenerates `docs/phase-0-synthesis-v0.1.md` from the SQLite result store with per-stage tables (measured cloud | derated point | derated 80% band | PRD target | gate verdict using band upper bound) and a standalone Derating Methodology section that survives Liotta-style adversarial review
  2. Synthesis report contains an unstrippable sales-safe excerpt with explicit "predicted, not measured" language and two-tier (Measured cloud / Predicted appliance) presentation on every appliance number, plus a "What we did not measure" section listing every caveat including NC-R12 deferral
  3. `docs/feasibility-memo-v0.4-fragment.md` is generated and ready to merge into the v0.3 baseline, and `docs/phase-0-gate-decision.md` records pass / soft-pass-with-caveats / fail recommendation, evidence summary, and SOW-ready feasibility excerpt
  4. End-of-week canary re-run executes a single G1 5-call run within tolerance of the original measurement, and `docs/repro-manifest-v1.0.md` is sealed referencing all locks, audits, and canary status
  5. Cross-substrate consistency check (H100→MI300X projection within 25%) is computed and any failures are flagged in the synthesis as a methodology warning; Q4_K_M↔AWQ-Int4 substitution-error term and Ollama-overhead derate (~1.3–1.5×) are documented in the methodology section
**Plans**: TBD

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3 → 4

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Foundation | 0/5 | Not started | - |
| 2. CUDA Pre-flight | 0/4 | Not started | - |
| 3. ROCm Validation | 0/TBD | Not started | - |
| 4. Synthesis & Gate Decision | 0/TBD | Not started | - |
