# Roadmap: receptionBOX Phase 0 — Cloud Benchmark Validation

## Overview

Phase 0 is a one-week, $150-ceiling cloud benchmark harness that produces derated Strix Halo (gfx1151) predictions for receptionBOX latency, WER, turn-detection, UPL, and TTS, packaged as a feasibility memo v0.4 update plus a sales-safe gate decision package. The roadmap follows dependency order, not gate order: a no-GPU-spend foundation phase prevents six of eleven critical pitfalls, then CUDA pre-flight on RunPod H100 assembles the pipeline at known-working-substrate cost, then ROCm validation on RunPod MI300X (per D-31-A4.1 amendment — single substrate for both rails) collects the load-bearing measurements with co-residency and gfx1151 kernel-coverage audits, then synthesis derates per-stage with 80% confidence bands and produces a gate decision survivable under adversarial review.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

- [x] **Phase 1: Foundation** — Repo skeleton, asset curation, cost rails, NC-R14 resolution; zero GPU spend
- [x] **Phase 2: CUDA Pre-flight** — RunPod H100 substrate proves pipeline with 5-call smoke (verdict pass) + G1/G2/G3/G5 sanity (DEV-1019 Delivered with operator-accepted 20-row-per-gate partial coverage)
- [ ] **Phase 3: Jetson Orin Validation [REDIRECTED per DR-39 RATIFIED 2026-05-11]** — Direct measurement on Jetson AGX Orin 64GB Developer Kit (target SoC of the appliance). No further derate — Orin IS the appliance. Old "ROCm Validation on MI300X" scope is parked-archival.
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
**Plans**: 8 plans (3 gap-closure plans across 02-05 / 02-07 / 02-08)
Plans:
- [x] 02-01-PLAN.md — substrate/cuda.py composing 4 backend adapters + LiveKit AgentSession pipeline rig (HARNESS-02)
- [x] 02-02-PLAN.md — Substrate-agnostic gate runners g1/g2/g3/g5 + GateRunner base + env.json sidecar (HARNESS-05, HARNESS-06, REPRO-03 schema)
- [x] 02-03-PLAN.md — Pod entrypoint + watchdog + HF cache bootstrap + pre-teardown audit + real RunPod provisioning (CLOUD-04, CLOUD-05, CLOUD-06)
- [x] 02-04-PLAN.md — Stratification config + pre-flight driver + operator checklist + real-spend smoke (PREFLIGHT-01) [smoke portion closed via 02-07 T7; sanity portion = DEV-1019, separate]
- [x] 02-05-PLAN.md — GAP CLOSURE: resolve lockfile pending revisions + auto-provision bootstrap pod + E2E mock test (REPRO-02 data, unblocks PREFLIGHT-01)
- [x] 02-06-PLAN.md — Custom rbox-pod image (FROM vllm/vllm-openai:v0.10.0) with pod_entrypoint baked as ENTRYPOINT, digest-pinned in _DEFAULT_IMAGE (DEV-1035)
- [x] 02-07-PLAN.md — GAP CLOSURE: multi-service pod startup (vLLM+Kokoro) + corpus_500 in image + fetch_results transport pivot; image v8→v18 iteration; smoke verdict pass (closes 02-04 T4 / PREFLIGHT-01)
- [x] 02-08-PLAN.md — RETROACTIVE GAP CLOSURE: image_digest + git_commit lineage on result rows (DEV-1021); REPRO-03 data verified on G2 diag pod

### Phase 3: Jetson Orin Validation [REDIRECTED per DR-39 RATIFIED 2026-05-11]
**Goal**: Direct measurement of the receptionBOX harness on the target appliance SoC — NVIDIA Jetson AGX Orin 64GB Developer Kit. Produces G1, G2, G3, G5, G7 numbers measured on the exact silicon the v1 appliance ships with, eliminating the cloud-derate confidence gap entirely. Derate methodology collapses: H100 (Phase 2 measured) → Orin Direct (Phase 3 measured) → no further derate (Orin IS the appliance). Phase 4 synthesis builds the gate decision directly from Phase 3's measured-on-target numbers.
**Depends on**: Phase 2 + 1× Jetson AGX Orin 64GB Developer Kit on operator workstation (~$2k, ~1 week shipping from NVIDIA / Arrow / Amazon)
**Requirements**: HARNESS-03 (REDIRECTED — was ROCm, now JetPack/CUDA on Orin), GATE-G1, GATE-G2, GATE-G3, GATE-G5, GATE-G7. **OBSOLETE under DR-39**: GATE-CHATTERBOX-D1 (Chatterbox-CUDA already validated in Phase 2; no ROCm risk to kill-switch), AUDIT-02 (gfx1151 op coverage — no AMD silicon in the new product target). AUDIT-01 (co-residency) + AUDIT-03 (engine-swap) remain valid but trivialized — both run directly on the operator's Orin dev kit alongside the gate measurements.
**Success Criteria** (what must be TRUE — REWRITTEN per DR-39):
  1. receptionBOX harness builds and runs on Jetson AGX Orin 64GB with JetPack 6+ / CUDA 12.x; vLLM, faster-whisper, Chatterbox, Kokoro, LiveKit Agents all load successfully
  2. G1 latency on the 500-call corpus at N=1/2/4 reports p50/p90/p99 per-stage (STT TTFT, LLM TTFT, LLM decode, TTS first-audio) and aggregate, measured directly on Orin
  3. G2 WER measured on 200 G.711 clips with faster-whisper INT8 on Orin (ONNX-RT ROCm dual-path obsolete under DR-39)
  4. G3 turn-detection threshold sweep 400–1500ms in 100ms steps on Orin
  5. G5 UPL probes against the receptionBOX-shaped reference prompt with grammar-constrained generation ON, on Orin
  6. G7 TTS A/B renders both warm-path and cold-path first-audio across 30 stimulus pairs on Orin
  7. Co-residency stack-load (AUDIT-01): all 4 models loaded simultaneously on Orin under sustained ≥ 5-min load; memory headroom + crash detection recorded
**Plans**: TBD — new Phase 3 plan set drafts after Orin dev kit arrives. Old ROCm-targeted plans 03-01..03-06 + 03-01.5 are **parked-archival** (committed code stays in repo as optional ROCm path for future, off the critical path).
Old plans (parked-archival per DR-39):
- [archive] 03-01-PLAN.md — substrate/rocm.py + Dockerfile.rocm + Vultr provisioning + phase3 config (parked: code shipped, off critical path)
- [obsolete] 03-01.5-PLAN.md — RunPod MI300X stock-poll + orchestration (obsolete under DR-39 redirect to direct Orin measurement)
- [obsolete] 03-02-PLAN.md — Day-1 Chatterbox ROCm kill-switch (no ROCm risk to validate)
- [redirect] 03-03-PLAN.md — G1+G2+G3+G5 (will be rewritten for Orin direct measurement)
- [redirect] 03-04-PLAN.md — G7 TTS A/B (will be rewritten for Orin direct measurement)
- [redirect] 03-05-PLAN.md — AUDIT-01 co-residency + AUDIT-03 engine-swap (will be rewritten for Orin direct measurement)
- [obsolete] 03-06-PLAN.md — AUDIT-02 gfx1151 op-coverage (no AMD silicon in the new product target)

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
| 1. Foundation | 5/5 | Complete | 2026-05-04 |
| 2. CUDA Pre-flight | 8/8 plans; PREFLIGHT-01/02/03 all closed | Complete (smoke verdict pass + sanity 20-row-per-gate partial coverage operator-accepted via DEV-1019) | 2026-05-11 |
| 3. ROCm Validation | 1/7 | Planned (7 plans on disk; 03-01 closed via amendments; 03-01.5 inserted as substrate-pivot enabler 2026-05-11; rewritten in place per D-31-A4.1 to retarget RunPod) | - |
| 4. Synthesis & Gate Decision | 0/TBD | Not started | - |
