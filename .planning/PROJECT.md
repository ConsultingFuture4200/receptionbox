# receptionBOX Phase 0 — Cloud Benchmark Validation

## What This Is

A pre-discovery cloud benchmark effort that validates whether receptionBOX (a voice AI personality pack for the thUMBox edge-AI appliance platform, targeting law firms) can hit its end-to-end latency and quality budgets on the planned T3 hardware (Framework Desktop / AMD Ryzen AI Max+ 395 "Strix Halo"). Phase 0 runs entirely on rented cloud GPUs (RunPod H100 for CUDA pre-flight, MI300X via Vultr or TensorWave for ROCm validation) and produces derated Strix Halo predictions plus an updated feasibility memo. **It is the gate that determines whether UMB Group offers a paid discovery SOW to the inbound large-law-firm lead.**

## Core Value

Produce trustworthy go/no-go evidence on receptionBOX feasibility — derated Strix Halo predictions for latency/WER/turn-detection/UPL/TTS — *before* any sales commitment is made to the firm. If Phase 0 says "no", we walk away cleanly with $150 spent instead of refunding a discovery engagement.

## Requirements

### Validated

(None yet — ship to validate)

### Active

- [ ] **G1 latency benchmark** — End-to-end p90 < 900ms / p99 < 1200ms target measured on MI300X with Whisper STT + Qwen3-4B + Chatterbox-Turbo over a 500-call corpus, derated to Strix Halo prediction
- [ ] **G2 STT WER on G.711** — distil-whisper-large-v3 INT8 WER < 12% neutral / < 18% stressed measured on 200 clips at G.711 μ-law codec
- [ ] **G3 turn-detection** — False-positive rate < 2% on hesitation-heavy adversarial set
- [ ] **G5 UPL guardrail probes** — 100% pass on 200-probe adversarial suite covering substantive legal questions, fee quotes, statute-of-limitations, deadline advice, case-outcome predictions, prompt-injection variants
- [ ] **G7 TTS A/B preference** — Chatterbox-Turbo vs Kokoro-82M blind preference test, 30 pairs, 5 listeners, ≥ 60% prefer cloned target
- [ ] **CUDA pre-flight (RunPod H100)** — End-to-end pipeline assembles and runs once on CUDA before ROCm validation begins
- [ ] **ROCm validation (MI300X)** — Chatterbox-Turbo + Whisper + Qwen3-4B all run on ROCm 6.x; engine swap to Kokoro fallback proven
- [ ] **Synthesis report** — Derated Strix Halo predictions per gate, with confidence ranges and methodology
- [ ] **Feasibility memo v0.4** — Update `receptionbox-technical-feasibility-memo` from v0.3 to v0.4 with measured numbers
- [ ] **Phase 0 gate decision package** — Pass/fail recommendation, evidence, and SOW-ready feasibility excerpt for sales conversation
- [ ] **Cloud account provisioning** — RunPod, Vultr (or TensorWave), and a billing/cost-cap plan; ~$150 spend ceiling
- [ ] **Evaluation asset curation** — 500-call corpus, 200 G.711 clips, hesitation adversarial set, 200 UPL probes, 30-pair TTS A/B set built from synthetic + open-licensed sources

### Out of Scope

- **Phase 1 discovery work** — Outside-counsel ethics opinion, requirements audit, kill-criteria scoring. Per DR-28, Phase 1 only starts after Phase 0 passes and the firm signs a SOW.
- **Phase 2 founding-partner pilot** — Appliance assembly, SIP integration, onboarding, shadow mode. Conditional on Phase 1 success.
- **Local Strix Halo benchmarks** — No Framework Desktop dev unit on hand. All Phase 0 work is cloud-only; local Strix validation is post-Phase-0.
- **Production code (LiveKit SFU, agent-worker, full pipeline)** — Phase 0 produces benchmark harnesses, not the v1 product runtime. Production receptionBOX code is Phase 2+.
- **Outbound calling / TCPA work** — Per DR-30, v1 is inbound-only. Out of scope at every phase.
- **Multi-pack co-residency** — Per DR-25, v1 is single-pack-per-appliance. Phase 0 has no need to model multi-pack interactions.
- **Cloud LLM fallback** — Per FR-R49, OFF by default. Phase 0 benchmarks the local-only path; cloud fallback is not measured.
- **Sales artifacts and pitch updates** — Pitch deck and partnership PDF live elsewhere and are subordinate to PRD updates per §0.5.
- **Parent thUMBox platform development** — Platform is treated as available substrate. Phase 0 doesn't modify parent platform services.

## Context

- **Inbound warm lead.** Large law firm (NDA pending). UMB Group is positioning a paid discovery engagement as the next step. Phase 0 is the technical pre-check that gates that conversation.
- **Authoritative documents in this repo:** `receptionbox-technical-prd-v0_2-2026-05-03 (1).md` (this PRD).
- **Authoritative documents NOT yet in this repo (operator will drop into `docs/`):**
  - `thumbox-technical-prd-v2_1-2026-04-16.md` (parent platform tech PRD)
  - `thumbox-business-prd-v2_1-2026-04-16.md` (parent platform business PRD)
  - `addendum-receptionbox-discovery-v0_2-2026-04-22.md` (discovery gate, kill criteria, regulatory posture)
  - `addendum-hardware-pivot-strix-halo-v0_1-2026-04-23.md` (DR-24, Strix Halo pivot)
  - `receptionbox-technical-feasibility-memo-v0_3-2026-04-23.md` (Eric-facing feasibility brief — to be updated to v0.4 as a Phase 0 deliverable)
  - `receptionbox-virtual-benchmark-plan-v0_1-2026-05-03.md` (Phase 0 execution plan; authoritative on procedures)
- **PRD authority hierarchy** (per §0.5): Parent platform PRDs > this receptionBOX PRD > addenda > feasibility memo / benchmark plan > sales artifacts. Any Phase 0 finding that contradicts a higher-authority doc requires updating that doc before sales material moves.
- **Three-layer architecture framing** (per §0.2): Hardware → Platform (thUMBox) → Product (receptionBOX pack). Phase 0 validates feasibility at the Hardware × Product intersection only.
- **Hard latency budget:** p90 < 900ms / p99 < 1200ms end-to-end voice. This is the load-bearing technical risk and the primary motivator for Phase 0.
- **Pluggable TTS architecture (DR-27)** is already a decided design choice — Phase 0 benchmarks two engines (Chatterbox-Turbo primary, Kokoro-82M fallback) but the abstraction is locked.
- **Operator and execution model:** Dustin (this operator) drives Phase 0 locally on Ubuntu 22.04 from `~/RBOX`. Eric is the original feasibility memo author; Phase 0 results feed his next memo revision.

## Constraints

- **Budget**: ~$150 cloud GPU spend ceiling for Phase 0 — exceeded only with explicit operator approval. Methodology must be reproducible at this cost.
- **Timeline**: ~30–40 engineering hours over ~1 calendar week ("this week" per PRD §14). Phase 0 cannot drag — sales velocity depends on it.
- **Hardware**: Cloud-only. RunPod H100 for CUDA pre-flight; MI300X via Vultr or TensorWave for ROCm validation. No local Strix Halo dev unit available.
- **Tech stack**: ROCm 6.x for AMD path; CUDA 12.x for NVIDIA pre-flight. Models are pinned: distil-whisper-large-v3 INT8 (STT), Qwen3-4B Q4_K_M (LLM), Chatterbox-Turbo (TTS primary), Kokoro-82M (TTS fallback). Phase 0 does not deviate.
- **Audio**: G.711 μ-law is the mandatory codec for STT WER measurement. Synthetic phone-path transcoding required (16 kHz capture → 8 kHz μ-law).
- **Regulatory / privilege**: Phase 0 uses only synthetic or open-licensed audio. No real client calls, no PII. UPL probe set is content-free of real legal facts.
- **Data residency posture**: Phase 0 is cloud-based by necessity (DR-19 sovereignty pillar applies to product, not benchmarks). Cloud benchmark results are non-sensitive — no privilege exposure risk.
- **Reproducibility**: Every benchmark must be re-runnable from `~/RBOX` against pinned model weights and pinned cloud images. Synthesis report must cite hash-pinned artifacts.
- **Gate semantics**: Per DR-28, Phase 0 is a hard pre-condition for SOW signing. A "soft pass with caveats" outcome is allowed; a fail blocks the discovery offer or downgrades it to a disclosed-risk offer.

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Phase 0 scope is cloud-only (no local Strix) | No Framework Desktop dev unit on hand; cloud is faster, cheaper, and per virtual benchmark plan v0.1 the established methodology | — Pending |
| Operator drives Phase 0 locally (vs Eric remote) | Operator has Ubuntu 22.04 workstation + GPU experience; faster iteration than coordinating with remote engineer; Eric remains report consumer | — Pending |
| Pull parent thUMBox PRDs and addenda into this repo (`docs/`) | Phase 0 agents need to read parent decisions (DR-19, DR-22, plugin tier, llm-router) without re-deriving them | — Pending (operator dropping files in) |
| Treat receptionBOX PRD v0.2 as authoritative input doc | Most current; consolidates discovery addendum + hardware pivot + feasibility memo into one canonical spec | — Pending |
| All evaluation assets curated in Phase 0 (no pre-existing corpora) | No legacy benchmark corpus exists; Phase 0 includes asset construction from synthetic + open sources | — Pending |
| Use only RunPod (H100) and Vultr/TensorWave (MI300X) | Per virtual benchmark plan v0.1; standard combination; no need to evaluate alternatives at Phase 0 | — Pending |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd-transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd-complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-05-04 after initialization*
