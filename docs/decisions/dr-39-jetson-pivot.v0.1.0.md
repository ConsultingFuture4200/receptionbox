# DR-39: Product target pivot — Strix Halo → NVIDIA Jetson AGX Thor

**File version:** v0.3.0
**Status:** **APPROVED 2026-05-11** — parent thUMBox + UMB Group ratified; **target SKU = NVIDIA Jetson AGX Orin 64GB** (not Thor as originally drafted; see §10); **methodology refined 2026-05-11: cloud-measurement-and-derate, NOT dev-kit-direct-measurement (see §11)**
**Proposed by:** Claude drafted at operator (Dustin) request, 2026-05-11
**Ratified by:** Operator (Dustin) confirming parent thUMBox + UMB Group sign-off, 2026-05-11
**Supersedes (partial):** DR-24 (Strix Halo pivot, `docs/addendum-hardware-pivot-strix-halo-v0_1-2026-04-23.md`)
**Affects:** thUMBox technical PRD v2.1, receptionBOX technical PRD v0.2, feasibility memo v0.3, hardware-pivot addendum v0.1, discovery addendum v0.2, virtual benchmark plan v0.1, `.planning/PROJECT.md`, `.planning/REQUIREMENTS.md`, `.planning/ROADMAP.md`, Phase 3 plans 03-01..03-06, CLAUDE.md §§1.2/2.1/4.1/4.2/5/6/7
**Triggering event:** RunPod MI300X stock dry on 2026-05-11; TensorWave sales unblock pending ≥7 days; Vultr's only MI300X SKU is 8-GPU bare-metal preemptible at $14.80/hr (breaks budget 4×).

---

## §1 Decision (ratified)

Pivot the receptionBOX appliance target hardware from **AMD Ryzen AI Max+ 395 "Strix Halo" (gfx1151)** to **NVIDIA Jetson AGX Orin 64GB** (see §10 — original proposal named Thor; parent team substituted Orin 64GB on BOM grounds).

This is a parent-thUMBox-platform decision, not a Phase 0 internal decision. Phase 0 inherits whatever the target is — but the choice of target materially changes Phase 0 scope, risk profile, and timeline.

---

## §2 Rationale (3 reasons, declining order of importance)

### §2.1 Software-stack risk collapse

The dominant Phase 0 risk per the existing PRD risk register is **"does the model loader stack actually run on AMD's ROCm path."** Specifically:

- Chatterbox-Turbo ROCm install — devnen GitHub issues #92, #192, #445 open and unresolved as of 2026-05-11
- vLLM ROCm AITER kernel coverage for Qwen3-4B AWQ-Int4
- ONNX Runtime ROCm decoder path for distil-whisper INT8
- faster-whisper CTranslate2 ROCm build correctness
- `hipBLASLt` / rocBLAS / MIOpen op coverage on gfx1151 specifically (per PyTorch issues #171687, #6034 — gfx1151 has documented bf16 bugs + missing native kernels in current ROCm)

Switching the target to Jetson AGX Thor replaces ROCm with **CUDA + JetPack**, which is the most mature inference stack on the planet. Phase 2 already validated this stack end-to-end on H100 (smoke verdict pass, 02-07 T7, run `2f6b…`). The receptionBOX harness uses faster-whisper, vLLM, Chatterbox, Kokoro, LiveKit Agents — all four have known-good CUDA paths and are routinely deployed on Jetson Orin in production.

### §2.2 Cloud-derate-substrate matches abundant cloud supply

The current product target (Strix Halo, gfx1151) has no commercially-available exact-match cloud silicon. The methodology was to measure on MI300X (gfx942) and derate to gfx1151 — but MI300X is scarce: Vultr's only SKU is wrong-size + wrong-pricing, TensorWave is sales-gated, RunPod stock is intermittent and only available in EU-RO-1.

Jetson AGX Thor's closest cloud proxy is **NVIDIA H100 or H200** — both abundant on RunPod (9 DCs for H200; 5 DCs for H100 NVL including operator's existing volume DCs US-CA-2 + US-KS-2). Derate chain becomes: **H100 (Phase 2 already measured) → Jetson AGX Thor (one short hop using NVIDIA's published Thor inference benchmarks) → end**. One conversion, same vendor, well-documented hardware on both ends.

### §2.3 Production-stack parity strengthens the firm conversation

Phase 4's synthesis report has to survive adversarial review by the firm's technical advisors. The current methodology has a structural weakness: "we measured on AMD's flagship and projected to AMD's small chip" — but Strix Halo's RDNA3.5 ROCm support is publicly described as rough by NVIDIA's competitors and by AMD's own developer forums. The adversarial reviewer asks: "how do you know your benchmark Whisper INT8 latency on MI300X reflects what Whisper INT8 will do on Strix Halo's mostly-unsupported gfx1151 kernels?"

With Jetson AGX Thor as target: "we measured on NVIDIA H100, derated to NVIDIA Jetson AGX Thor using NVIDIA's published Jetson Thor inference benchmarks (NIM containers, TensorRT-LLM optimized models)." The adversarial reviewer's question becomes: "did you account for Thor's INT8 vs H100's FP8 quantization shift?" — a smaller, more tractable question.

---

## §3 What changes if this is ratified

### §3.1 Phase 0 (Phase 3 specifically)

**Effectively shelved:** Phase 3 ROCm-specific plans become moot.
- `03-01-PLAN.md` (HARNESS-03 substrate/rocm.py) — already SHIPPED; code stays in repo as optional ROCm path for future, not on critical path
- `03-02-PLAN.md` (GATE-CHATTERBOX-D1) — moot; Chatterbox on CUDA already validated in Phase 2
- `03-03-PLAN.md` (GATE-G1/G2/G3/G5 on MI300X) — RE-TARGETED to "Cross-substrate gates on H100/H200, then derate to Jetson AGX Thor"
- `03-04-PLAN.md` (GATE-G7 TTS A/B) — RE-TARGETED to H100/H200
- `03-05-PLAN.md` (AUDIT-01 co-residency, AUDIT-03 engine-swap) — RE-TARGETED to H100/H200 (still valid integration audits, just on CUDA)
- `03-06-PLAN.md` (AUDIT-02 gfx1151 op coverage) — **OBSOLETE**, no AMD silicon to profile

**Net effect:** Phase 3 collapses from ~$54 + ~2 weeks of ROCm risk validation to ~$30 + ~3 days of cross-substrate CUDA validation. Phase 4 synthesis follows immediately.

### §3.2 Parent thUMBox PRDs

Documents requiring update if ratified:
- `docs/thumbox-technical-prd-v2_1-2026-04-16.md` — T3 hardware section: Strix Halo → Jetson AGX Thor
- `docs/thumbox-business-prd-v2_1-2026-04-16.md` — BOM/cost section + vendor relationships
- `docs/addendum-hardware-pivot-strix-halo-v0_1-2026-04-23.md` — Either supersede entirely or extend with a "DR-39 reversal" addendum
- `docs/receptionbox-technical-prd-v0_2-2026-05-06.md` — Architecture diagrams + §4.x references to Strix Halo
- `docs/receptionbox-technical-feasibility-memo-v0_3-2026-04-23.md` — Predictions section
- `docs/addendum-receptionbox-discovery-v0_2-2026-04-22.md` — Sales-side talk track to firm
- `docs/receptionbox-virtual-benchmark-plan-v0_1-2026-05-03.md` — Benchmark substrate references
- `.planning/PROJECT.md` — T3 hardware references
- `CLAUDE.md` §1.2 (MI300X providers), §2.1 (ROCm container), §4.1/§4.2 (STT engine choice — Jetson uses TensorRT-LLM not ROCm), §5 (TTS engine ROCm forks → JetPack/TensorRT), §6 (turn detector unaffected), §7 (derating methodology — replace Strix Halo bandwidth/compute baseline with Jetson AGX Thor's)

### §3.3 Sales / firm conversation

- The discovery addendum (`docs/addendum-receptionbox-discovery-v0_2-2026-04-22.md`) currently positions an "AMD-based local appliance." If this has been read by the firm, the substrate pivot must be disclosed and re-positioned.
- The firm may or may not care about the SoC. Likely they care about: latency, privacy/on-prem, total cost, and warranty/support. NVIDIA Jetson is a stronger story on every dimension except possibly total BOM cost (Thor at ~$3.5–4k per unit vs Strix Halo at ~$2k).
- "On-prem appliance" story is unchanged. Jetson AGX Thor is shippable as an appliance.

### §3.4 BOM economics

| | Strix Halo (current) | Jetson AGX Thor |
|---|---|---|
| Module unit cost | ~$1.4k (Strix Halo SoC alone, in mini-PC chassis) | ~$3.5–4k (Thor module incl. carrier, OEM volume) |
| Full appliance BOM | ~$2k (Framework Desktop end-user MSRP) | ~$4–5k (custom chassis + cooling + NIC + storage) |
| NRE | Already partially expensed | Higher — JetPack tuning, TensorRT optimization, Jetson-specific OEM relationships |
| Volume pricing leverage | Unknown — Strix Halo via Framework | NVIDIA enterprise channel (likely better at >100 units) |
| Power | ~120 W | 40–130 W configurable |
| Software support timeline | ROCm gfx1151 still maturing | JetPack 7+ shipping, mature |

**Net BOM impact: +$2–3k per unit.** At the law-firm tier this is likely absorbable; at small-firm volumes it would not be. The discovery SOW conversation needs to confirm the firm's price sensitivity before this is final.

### §3.5 Vendor relationships

- Any existing AMD partnership / co-marketing / developer credits in flight at parent thUMBox level becomes less relevant. **This is the politically-heaviest item and the one I do not have visibility into.** Operator must surface to UMB Group + parent thUMBox stakeholders.
- NVIDIA channel: thUMBox doesn't currently appear to have an NVIDIA enterprise relationship; one would need to be established.

---

## §4 Risks of pivoting

| Risk | Mitigation |
|---|---|
| Parent thUMBox has AMD strategic commitments invisible to receptionBOX | Operator must surface this to UMB/thUMBox stakeholders before ratifying; this DR is a *proposal* |
| Firm conversation has been positioned around AMD | Operator must check the discovery thread; if positioned, plan a re-positioning conversation |
| Jetson AGX Thor BOM is +$2-3k per unit | Confirm firm price tolerance during discovery conversation; alternative is Jetson AGX Orin 64GB at near-Strix-Halo BOM but with lower compute headroom |
| Sunk-cost in Phase 3 ROCm work (~3 days of substrate + Dockerfile.rocm + Vultr orchestration) | Code stays in repo as optional ROCm path; not deleted; usable if vendor strategy ever flips back |
| NVIDIA channel relationship not yet established at thUMBox parent level | Operator to evaluate; likely tractable since thUMBox already uses CUDA for cloud development |

---

## §5 Risks of NOT pivoting

| Risk | Severity |
|---|---|
| Phase 0 stalls indefinitely on MI300X cloud supply | High — already 7+ days of waiting; no SLA on TensorWave sales response |
| Chatterbox-ROCm install path fails on Day 1, scope-shrinks GATE-G7 | Medium-High (PRD risk register existing assessment) |
| gfx1151 op coverage audit surfaces blocking gaps that force a product pivot anyway, after Phase 0 has already burned the $150 budget | Medium |
| Gate decision package ships with "we don't know if Chatterbox loads on the target hardware" caveat | Medium-High — weakens firm conversation |

---

## §6 Open questions for parent thUMBox + UMB Group review

1. Are there strategic AMD commitments at the parent thUMBox level that this pivot would conflict with?
2. Has the firm conversation positioned around AMD-specific value (data residency on AMD silicon, etc.) or around generic "on-prem appliance"?
3. Is the BOM cost increase (+$2–3k per unit) absorbable for the law-firm market segment receptionBOX targets?
4. Does an NVIDIA enterprise relationship exist or need establishing?
5. Is Jetson AGX Thor's 40–130 W power envelope (vs Strix Halo's ~120 W) acceptable for the "reception-desk appliance" form factor and acoustic budget?
6. Should we consider **Jetson AGX Orin 64GB** as an intermediate option? Same software stack, ~$2k BOM (matches Strix Halo), lower compute headroom (~275 TOPS INT8 vs Thor's ~2 PFLOPS FP4). May be the sweet spot for receptionBOX's actual workload (Qwen3-4B + Whisper + TTS at concurrency 1-4).

---

## §7 Effective date if ratified

| Ratification by | Action |
|---|---|
| End of operator decision (today) | This DR moves from PROPOSED to APPROVED; STATE.md updates pivot status; downstream doc-update plan executes |
| Day 0 of ratification | Stop all MI300X-related cloud work; Phase 3 plans 03-02..03-06 marked OBSOLETE in ROADMAP; new Phase 3 scope drafted ("Cross-substrate CUDA validation + Jetson AGX Thor derate") |
| Day +1 | Parent thUMBox PRDs updated; discovery addendum re-positioned for the firm |
| Day +2 | Buy 1× Jetson AGX Thor dev kit if direct measurement is part of the new methodology (~$3.5k, ~1 week shipping) |
| Day +3 onward | New Phase 3 executes; Phase 0 ships in ~5–7 calendar days from Day 0 |

---

## §8 Approval

- Operator (Dustin Powers): **APPROVED 2026-05-11**
- UMB Group / parent thUMBox stakeholder: **APPROVED 2026-05-11** (operator confirming on behalf of stakeholders)
- Date ratified: **2026-05-11**
- Target SKU: **NVIDIA Jetson AGX Orin 64GB** (Thor substituted out — see §10)

---

## §10 Thor → Orin 64GB substitution (added at ratification, 2026-05-11)

DR-39 v0.1.0 named **Jetson AGX Thor** as the target. The parent thUMBox + UMB Group review substituted **Jetson AGX Orin 64GB** at ratification on BOM-economics grounds. Rationale captured here for downstream coherence.

### §10.1 What stays the same

Every §2 rationale (software-stack risk collapse, cloud-derate-substrate match, production-stack parity) applies identically to Orin 64GB. Both are CUDA + JetPack; both have abundant H100/H200 cloud proxies; both eliminate the ROCm risk surface. The §3 doc-update scope is unchanged.

### §10.2 What changes vs the Thor draft

| Field | Thor (DR-39 v0.1.0 draft) | Orin 64GB (RATIFIED) |
|---|---|---|
| Unit cost (module + carrier, OEM volume) | ~$3.5–4k | **~$2k** (matches Strix Halo BOM) |
| BOM impact vs Strix Halo | +$2-3k per unit | **~$0** (cost-neutral) |
| Compute headroom | ~2 PFLOPS FP4 sparse marketing number; ~275 dense TOPS INT8 real | ~275 TOPS INT8 (Orin) |
| Memory | 128 GB unified LPDDR5X | 64 GB unified LPDDR5 |
| Memory bandwidth | ~273 GB/s | 204 GB/s |
| Power envelope | 40–130 W configurable | 15–60 W configurable |
| Software stack | JetPack 7+ / CUDA 13+ | **JetPack 6+ / CUDA 12.x — mature, deployed in production at scale** |
| Workload fit (Qwen3-4B Q4 + Whisper INT8 + Chatterbox + Kokoro at concurrency 1–4) | Massive headroom (probably 8–10x what receptionBOX needs) | **Comfortable fit (estimated 2–3x headroom)** |

### §10.3 Why Orin 64GB is the right call for receptionBOX specifically

1. **BOM cost neutral with Strix Halo.** No discovery-SOW price renegotiation needed. The firm conversation does not have to absorb a "appliance got $2k more expensive" line.
2. **Mature software.** JetPack 6 has been in production deployment for ~18 months as of ratification; thousands of robotics/edge AI products ship on Orin. CUDA 12.x is the same stack as RunPod H100 (Phase 2 substrate). Risk of dependency surprises near zero.
3. **Workload fit.** receptionBOX maxes out at concurrency-4 per the PRD. Qwen3-4B Q4 weights are ~2.4 GB; Whisper INT8 ~150 MB; Chatterbox ~700 MB; Kokoro ~80 MB; KV cache for 4 concurrent calls ~3-4 GB. Total VRAM working set ~10 GB. Orin 64GB unified memory is comfortable. Thor's 128 GB was overkill.
4. **Power.** 15–60 W is reception-desk friendly (passive or low-RPM fan; near-silent). Thor's 40–130 W needs active cooling.
5. **Future optionality.** If volume scales and the workload grows, Thor upgrade path is the same socket family — re-platform later if/when justified by data.

### §10.4 Where Thor would have won

- Multi-pack future (DR-25 v2 — currently out of scope per PROJECT.md)
- Higher-concurrency law firm tier (>4 simultaneous callers) — not the inbound lead's profile
- FP4/sparse model variants from 2026+ that genuinely need Thor's transformer engine

These are real but not relevant to receptionBOX v1.

### §10.5 Implications for the Phase 3 redirect

Same direction as the original Thor proposal, with slightly tighter Jetson-side derate confidence:
- Phase 3 collapses to "CUDA validation on H100/H200 (already partial from Phase 2) + direct measurement on Orin 64GB dev kit"
- Buy 1 Jetson AGX Orin 64GB Developer Kit (~$2k, ~1 week shipping from NVIDIA / arrow.com / amazon)
- Run the receptionBOX harness directly on Orin; compare to H100 measurements
- Derate methodology becomes: H100 numbers (upper bound, Phase 2) → Orin Direct (measured, Phase 3) → "the appliance"
- No derate distance at all between Orin Direct and shipped appliance — they're the same SoC

Phase 0 timeline from this ratification: ~5–7 calendar days assuming Orin dev kit ships in ~3 days.

## §11 Methodology refinement — cloud-derate (not direct-measure)

Added 2026-05-11 after operator instruction "we will use runpod and derate." The §10 Thor→Orin substitution kept the original §3.4 / §7 plan to **buy 1× Orin 64GB Developer Kit** for direct measurement. This §11 supersedes that sub-decision: **no dev kit purchase; measure on RunPod NVIDIA H100/H200 and derate to Orin 64GB using NVIDIA's published Jetson Orin inference benchmarks as the derate basis.**

### §11.1 Why this is the right call

The Orin 64GB direct-measure path needed CapEx (~$2k) + shipping delay (~3-7 days) + workstation setup + JetPack flash + harness port to Tegra. All real work, all on the critical path. Cloud-derate eliminates all of that:

- **Same vendor and stack** as the measurement: NVIDIA → NVIDIA, CUDA → CUDA. The derate distance shrinks dramatically vs the original AMD→AMD cross-architecture (gfx942 → gfx1151) chain.
- **Cross-reference data already published**: NVIDIA publishes Jetson Orin inference benchmarks for the exact workloads we care about (Whisper INT8 STT, transformer LLM decode, TTS). The derate basis is grounded in NVIDIA's own measurements + community reproductions on NIM containers + Jetson Orin Performance Benchmark releases.
- **No critical-path blockers**: cloud is provisioning now. Phase 3 can run this week.
- **The bench code is already written**: `substrate/cuda.py` from Phase 2 already runs the harness on RunPod NVIDIA. No Tegra-specific substrate needed for measurement (would need it for direct measurement, but we're not direct-measuring).

### §11.2 The new Phase 3 shape

1. **Measurement substrate**: RunPod NVIDIA Secure Cloud. Card selection is engineering judgment — H100 NVL ($3.07/GPU-hr, plentiful, already validated in Phase 2 smoke `2f6b…`) is the most likely pick; H200 ($3.99/GPU-hr, slightly closer bandwidth profile to Orin's published memory subsystem) is an option if the operator wants a tighter derate.
2. **Phase 3 plans**: rewrite 03-03 (G1+G2+G3+G5), 03-04 (G7), 03-05 (AUDIT-01+03) to target RunPod NVIDIA instead of cloud MI300X. The substrate-agnostic gate runners under `gates/g{1,2,3,5,7}/runner.py` carry over unchanged.
3. **Derate chain**: cloud H100 measurement (Phase 2 + Phase 3) → published Jetson Orin 64GB inference benchmark numbers → Phase 4 synthesis report's appliance predictions. The chain is one hop within the same vendor.
4. **Derate basis citation**: Phase 4 synthesis report cites NVIDIA's official Jetson Orin Performance Benchmarks (developer.nvidia.com/embedded/jetson-orin-benchmarks) + community NIM Orin reproductions (where applicable) + any model-specific Orin benchmarks the model authors publish.
5. **What Phase 4's "What we did not measure" section says**: "We did not directly measure on a Jetson AGX Orin 64GB developer kit. We measured on RunPod H100 and derated to Orin using NVIDIA's published Orin inference benchmarks for [Whisper INT8 | Qwen3-4B AWQ-Int4 | Chatterbox | Kokoro]. Derate distance estimate: [bandwidth ratio for decode] / [compute ratio for prefill]. Confidence interval on Orin predictions: ±[N]%."
6. **AUDIT-01 (co-residency)** + **AUDIT-03 (engine-swap)**: trivialized further — they happen on the same RunPod NVIDIA pod that runs G1-G7, as part of the existing 03-05-PLAN scope (rewritten to NVIDIA instead of MI300X).

### §11.3 What the operator does NOT need to do anymore

- ~~Order Jetson AGX Orin 64GB Developer Kit~~ (saved: ~$2k CapEx, ~3-7 days shipping)
- ~~Set up the dev kit at the workstation~~ (saved: ~half-day of setup)
- ~~Flash JetPack 6 + port harness to Tegra~~ (saved: ~1-2 days of engineering)
- ~~Run direct measurement on Orin~~ (saved: ~1 day of run-and-collect)

Approximate total saved: 5-10 days of program time + $2k CapEx.

### §11.4 Trade-off accepted

The cost: Phase 4 synthesis report's predictions for the Orin appliance carry a derate-error term that direct-measurement would have eliminated. For Phase 0's gate decision purpose ("go / no-go on the discovery SOW"), this is acceptable — derate confidence intervals are bounded and the same-vendor-same-stack derate chain is tractable to defend in adversarial review. If the firm signs the discovery SOW, Phase 1 work can include direct-measure validation on an Orin dev kit (and the dev kit purchase becomes Phase-1 capex, not Phase-0).

### §11.5 What this means for §3 + §10

- §3.1 Phase 0 (Phase 3) impact stays mostly the same — 03-02 / 03-06 still obsolete, 03-03 / 03-04 / 03-05 still need rewriting (just retargeted at RunPod NVIDIA instead of cloud MI300X).
- §10.5 Phase 3 redirect implications: the line "Run the receptionBOX harness directly on Orin; compare to H100 measurements" is amended to: **measure on RunPod H100/H200; derate to Orin using NVIDIA's published Orin benchmarks; no direct measurement on Orin in Phase 0.**

## §9 Notes

- This DR was drafted at operator request after Phase 0 MI300X cloud-supply blockers materialized. The technical case for Jetson AGX Thor is strong; the political/strategic case requires parent-team input that the drafting AI does not have visibility into.
- The "smallest correct change" alternative is to stay on Strix Halo + wait for MI300X stock (RunPod poller has been deployed; first 24-72 hr will tell). This DR represents the larger pivot if the wait turns out to be unbounded.
- If ratified, several Phase 3 artifacts (03-01-PLAN.md substrate + 03-01-AMENDMENTS.md + Dockerfile.rocm + orchestration/vultr_mi300x.py + substrate/rocm.py) **stay in the repo** as a parked ROCm path. They're tested code. Deleting them would lose optionality if AMD strategy ever reverses.
