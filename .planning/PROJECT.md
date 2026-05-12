# receptionBOX Phase 0 — Cloud Benchmark Validation

## What This Is

A pre-discovery benchmark effort that validates whether receptionBOX (a voice AI personality pack for the thUMBox edge-AI appliance platform, targeting law firms) can hit its end-to-end latency and quality budgets on the planned T3 hardware. **DR-39 RATIFIED 2026-05-11: T3 hardware retargeted from AMD Strix Halo (Framework Desktop) → NVIDIA Jetson AGX Orin 64GB (cost-neutral BOM at ~$2k, mature CUDA software stack, eliminates ROCm risk surface).** Phase 0 runs on **RunPod H100 only** (no MI300X / no ROCm) and derates to Orin 64GB via same-vendor CUDA spec-sheet math; the Orin Developer Kit (~$2k) is purchased post-Phase-0 to validate the derate prediction. **Phase 0 is the gate that determines whether UMB Group offers a paid discovery SOW to the inbound large-law-firm lead.**

## Core Value

Produce trustworthy go/no-go evidence on receptionBOX feasibility — H100-measured numbers derated to the Jetson AGX Orin 64GB appliance SoC, across latency / WER / turn-detection / UPL / TTS — *before* any sales commitment is made to the firm. If Phase 0 says "no", we walk away cleanly with <$50 spent (post-DR-39 reduced budget) instead of refunding a discovery engagement.

## Requirements

### Validated

(None yet — ship to validate)

### Active

- [ ] **G1 latency benchmark** — End-to-end p90 < 900ms / p99 < 1200ms target measured on RunPod H100 with Whisper STT + Qwen3-4B + Chatterbox-Turbo over a 500-call corpus, derated to Jetson AGX Orin 64GB prediction
- [ ] **G2 STT WER on G.711** — distil-whisper-large-v3 INT8 WER < 12% neutral / < 18% stressed measured on 200 clips at G.711 μ-law codec (H100 measurement)
- [ ] **G3 turn-detection** — False-positive rate < 2% on hesitation-heavy adversarial set (H100 measurement)
- [ ] **G5 UPL guardrail probes** — 100% pass on 200-probe adversarial suite covering substantive legal questions, fee quotes, statute-of-limitations, deadline advice, case-outcome predictions, prompt-injection variants (H100 measurement)
- [ ] **G7 TTS A/B preference** — Chatterbox-Turbo vs Kokoro-82M blind preference test, 30 pairs, 5 listeners, ≥ 60% prefer cloned target (H100 render)
- [ ] **RunPod H100 measurement substrate** — End-to-end pipeline assembles and runs the full gate set on a single substrate. Phase 02 CUDA pre-flight is now the *primary* measurement rail, not a throwaway.
- [ ] **Spec-sheet derate methodology** — H100 (Hopper, measured) → Jetson AGX Orin 64GB (spec-sheet) per CLAUDE.md §7. Per-stage logic: bandwidth-bound for decode, FP16/INT8 compute ratio for prefill, Ollama overhead factor, ARM CPU integration penalty.
- [ ] **Synthesis report** — Derated Orin 64GB predictions per gate, with confidence ranges and methodology. Names every spec-sheet ratio used and the substitution-risk caveats (vLLM vs production Ollama, AWQ-Int4 vs Q4_K_M).
- [ ] **Feasibility memo v0.4** — Update `receptionbox-technical-feasibility-memo` from v0.3 to v0.4 with measured H100 numbers + Orin derate predictions
- [ ] **Phase 0 gate decision package** — Pass/fail recommendation, evidence, and SOW-ready feasibility excerpt for sales conversation
- [ ] **Evaluation asset curation** — 500-call corpus, 200 G.711 clips, hesitation adversarial set, 200 UPL probes, 30-pair TTS A/B set built from synthetic + open-licensed sources
- [ ] **Post-Phase-0 dev-kit validation plan** — After gate passes, buy 1× Jetson AGX Orin 64GB Developer Kit (~$2k, ~1 week ship), run the same harness, confirm the predicted ratios within ±20%, re-issue the synthesis report as v0.2 before SOW execution.

### Out of Scope

- **AMD ROCm / MI300X / TensorWave / Vultr** — Killed by DR-39. The entire AMD rail is gone. Archived at git tag `pivot/strix-halo-end-state` (`4c0bb57`) and protected branch `archive/amd-rocm-substrate` if ever reactivated. Phase 03 directory moved to `.planning/phases/03-rocm-validation-archived/` with README-pivot.md.
- **Local Strix Halo / Framework Desktop benchmarks** — Target SoC pivoted to Jetson AGX Orin 64GB. Strix Halo derate math + gfx1151 op-coverage audit are obsolete.
- **Chatterbox / Kokoro ROCm forks (devnen, moritzchow)** — Killed by DR-39. Use mainline CUDA paths (Resemble AI Chatterbox upstream + remsky/Kokoro-FastAPI upstream).
- **Jetson AGX Orin Developer Kit purchase in Phase 0 critical path** — Deferred to post-Phase-0 verification (~$2k, ~1 week ship). Phase 0 ships on H100 cloud + spec-sheet derate.
- **Phase 1 discovery work** — Outside-counsel ethics opinion, requirements audit, kill-criteria scoring. Per DR-28, Phase 1 only starts after Phase 0 passes and the firm signs a SOW.
- **Phase 2 founding-partner pilot** — Appliance assembly, SIP integration, onboarding, shadow mode. Conditional on Phase 1 success.
- **Production code (LiveKit SFU, agent-worker, full pipeline)** — Phase 0 produces benchmark harnesses, not the v1 product runtime. Production receptionBOX code is Phase 2+.
- **Outbound calling / TCPA work** — Per DR-30, v1 is inbound-only. Out of scope at every phase.
- **Multi-pack co-residency** — Per DR-25, v1 is single-pack-per-appliance. Phase 0 has no need to model multi-pack interactions.
- **Cloud LLM fallback** — Per FR-R49, OFF by default. Phase 0 benchmarks the local-only path; cloud fallback is not measured.
- **Sales artifacts and pitch updates** — Pitch deck and partnership PDF live elsewhere and are subordinate to PRD updates per §0.5.
- **Parent thUMBox platform development** — Platform is treated as available substrate. Phase 0 doesn't modify parent platform services.

## Context

- **Inbound warm lead.** Large law firm (NDA pending). UMB Group is positioning a paid discovery engagement as the next step. Phase 0 is the technical pre-check that gates that conversation.
- **Authoritative documents in this repo:** `docs/receptionbox-technical-prd-v0_2-2026-05-06.md` (PRD), `docs/decisions/dr-39-jetson-pivot.v0.1.0.md` (DR-39, ratified — the substrate pivot of record).
- **Authoritative documents pending operator update post-DR-39:**
  - `docs/thumbox-technical-prd-v2_1-2026-04-16.md` (parent platform tech PRD — T3 hardware section needs rewrite)
  - `docs/thumbox-business-prd-v2_1-2026-04-16.md` (parent platform business PRD — BOM / vendor sections)
  - `docs/addendum-receptionbox-discovery-v0_2-2026-04-22.md` (discovery gate — sales-side re-positioning for NVIDIA story)
  - `docs/addendum-hardware-pivot-strix-halo-v0_1-2026-04-23.md` (DR-24, Strix Halo pivot — to be superseded or extended with DR-39 reversal addendum)
  - `docs/receptionbox-technical-feasibility-memo-v0_3-2026-04-23.md` (Eric-facing feasibility brief — to be updated to v0.4 as a Phase 0 deliverable with new Orin-derate predictions)
  - `docs/receptionbox-virtual-benchmark-plan-v0_1-2026-05-03.md` (Phase 0 execution plan — substrate references)
- **PRD authority hierarchy** (per §0.5): Parent platform PRDs > this receptionBOX PRD > addenda > feasibility memo / benchmark plan > sales artifacts. Any Phase 0 finding that contradicts a higher-authority doc requires updating that doc before sales material moves.
- **Three-layer architecture framing** (per §0.2): Hardware → Platform (thUMBox) → Product (receptionBOX pack). Phase 0 validates feasibility at the Hardware × Product intersection only.
- **Hard latency budget:** p90 < 900ms / p99 < 1200ms end-to-end voice. This is the load-bearing technical risk and the primary motivator for Phase 0.
- **Pluggable TTS architecture (DR-27)** is decided. ROCm-specific risk under DR-27 is moot post-DR-39 (CUDA Chatterbox path is mainline); the abstraction remains useful for Phase 1 substitution flexibility.
- **Operator and execution model:** Dustin (this operator) drives Phase 0 locally on Ubuntu 22.04 from `~/RBOX`. Eric is the original feasibility memo author; Phase 0 results feed his next memo revision.

## Constraints

- **Budget**: **~$50** cloud GPU spend ceiling for Phase 0 (post-DR-39 reduction from ~$150 — the entire MI300X rail was eliminated). Exceeded only with explicit operator approval. Methodology must be reproducible at this cost.
- **Timeline**: Compressed materially under DR-39 — no cross-stack ROCm risk surface, no hardware procurement gate. Target: ~5–7 calendar days from ratification to gate decision package.
- **Hardware**: Cloud-only for measurement. **RunPod H100 only** (Phase 02 substrate, already wired up with API key + tooling + datacenter probe + network-volume strategy). Spec-sheet derate to Jetson AGX Orin 64GB; no Orin dev kit in Phase 0 critical path.
- **Tech stack**: CUDA 12.x throughout. Models pinned: distil-whisper-large-v3 INT8 (STT), Qwen3-4B (LLM — AWQ-Int4 on H100 measurement, Q4_K_M on Orin production via Ollama), Chatterbox-Turbo (TTS primary), Kokoro-82M (TTS fallback). All have first-class CUDA paths.
- **Audio**: G.711 μ-law is the mandatory codec for STT WER measurement. Synthetic phone-path transcoding required (16 kHz capture → 8 kHz μ-law).
- **Regulatory / privilege**: Phase 0 uses only synthetic or open-licensed audio. No real client calls, no PII. UPL probe set is content-free of real legal facts.
- **Data residency posture**: Phase 0 is cloud-based by necessity (DR-19 sovereignty pillar applies to product, not benchmarks). Cloud benchmark results are non-sensitive — no privilege exposure risk.
- **Reproducibility**: Every benchmark must be re-runnable from `~/RBOX` against pinned model weights and pinned cloud images. Synthesis report must cite hash-pinned artifacts.
- **Gate semantics**: Per DR-28, Phase 0 is a hard pre-condition for SOW signing. A "soft pass with caveats" outcome is allowed; a fail blocks the discovery offer or downgrades it to a disclosed-risk offer.

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| **DR-39 (2026-05-11) — T3 target Strix Halo → Jetson AGX Orin 64GB** | Cost-neutral BOM (~$2k), mature CUDA + JetPack 6 stack, eliminates ROCm risk surface, ~2-3× workload headroom for receptionBOX concurrency-4 envelope | **RATIFIED** (Operator on behalf of UMB Group / parent thUMBox; see `docs/decisions/dr-39-jetson-pivot.v0.1.0.md` §10 Thor→Orin substitution) |
| Phase 0 substrate = RunPod H100 only | Single-vendor single-substrate post-DR-39; existing Phase 02 tooling; ~$50 budget vs $150 for the old MI300X+H100 dual-rail plan | RATIFIED (DR-39 follow-on) |
| Spec-sheet derate H100 → Orin 64GB; buy dev kit post-Phase-0 | Same-vendor CUDA derate is tight without hardware in hand; gate decision doesn't need physical Orin first; dev-kit validation ($2k, ~1 week ship) happens after gate passes to confirm prediction within ±20% before SOW execution | RATIFIED (DR-39 follow-on) |
| Repo strategy = tag + archived branch (not fork) | Single repo, archived AMD path preserved at tag `pivot/strix-halo-end-state` and protected branch `archive/amd-rocm-substrate`; cheaper than fork maintenance for code we're parking | RATIFIED |
| Operator drives Phase 0 locally (vs Eric remote) | Operator has Ubuntu 22.04 workstation + GPU experience; faster iteration than coordinating with remote engineer; Eric remains report consumer | RATIFIED |
| Pull parent thUMBox PRDs and addenda into this repo (`docs/`) | Phase 0 agents need to read parent decisions (DR-19, DR-22, plugin tier, llm-router) without re-deriving them | RATIFIED (operator dropping files in) |
| Treat receptionBOX PRD v0.2 as authoritative input doc | Most current; consolidates discovery addendum + hardware pivot + feasibility memo into one canonical spec | RATIFIED |
| All evaluation assets curated in Phase 0 (no pre-existing corpora) | No legacy benchmark corpus exists; Phase 0 includes asset construction from synthetic + open sources | RATIFIED |
| Use RunPod (H100) as the only cloud provider | Per DR-39; Vultr/TensorWave deposited but unused post-pivot (Vultr backup-only with sentinel guard; TensorWave secondary-fallback never built out) | RATIFIED |

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
*Last updated: 2026-05-11 after DR-39 ratification (Jetson AGX Orin 64GB pivot). See `docs/decisions/dr-39-jetson-pivot.v0.1.0.md` and Linear DEV-1117.*
