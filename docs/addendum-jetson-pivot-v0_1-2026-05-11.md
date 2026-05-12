# receptionBOX Hardware Platform Pivot v2 — Decision Addendum

**To:** Eric
**From:** Dustin
**Date:** 2026-05-11
**Version:** v0.1
**Status:** Ratified by parent thUMBox + UMB Group 2026-05-11 (formal sign-off in `docs/decisions/dr-39-jetson-pivot.v0.1.0.md` §8)
**Target:** Feasibility Memo v0.3 → v0.4 (supersedes DR-24 / `addendum-hardware-pivot-strix-halo-v0_1-2026-04-23.md`)

**TL;DR** — Eighteen days after we ratified Strix Halo as the v1 platform, the cloud-validation path we depend on for the gate decision has collapsed. MI300X — the only commercially-available cloud silicon close enough to gfx1151 (Strix Halo) to support credible derate — has chronic supply scarcity across every cloud we've checked, and the one provider with stock (Vultr) only sells it in an 8-GPU bare-metal preemptible node that breaks our $54 Phase 3 budget by 4×. I'm recommending a pivot to **NVIDIA Jetson AGX Orin 64GB** as the v1 platform. BOM cost is neutral with Strix Halo (~$2k). Software stack risk drops dramatically (CUDA/JetPack vs. ROCm/gfx1151). And the cloud-validation path opens up — RunPod has H100/H200 in abundance, in our existing data centers, with substrate code already validated in Phase 2.

---

## §1. Why This Can't Wait (Round 2)

The Strix Halo pivot (DR-24, April 23) was the right call given what we knew then. What we couldn't know in April:

- **MI300X cloud supply has structurally collapsed.** As of May 11, RunPod's MI300X SKU is listed in only one data center (EU-RO-1), and live `create_pod` calls return "no instances available" across all GPU counts (1/2/4/8). The `available=True` flag on the inventory query is misleading — it just means "we offer this SKU somewhere," not "stock exists."
- **TensorWave sales unblock is taking weeks.** $75 deposit on file since 2026-05-04; no programmatic API access yet; no SLA on response time.
- **Vultr's only MI300X SKU is unusable for our budget.** `vbm-256c-2048gb-8-mi300x-gpu` is an 8-GPU bare-metal preemptible node at $14.80/hr for the whole node (preemptible-only, no on-demand). One run of GATE-CHATTERBOX-D1's 2-hour Day-1 kill-switch would cost $29.60 — that's 7× the $4 spend cap we set for that gate alone.

The pattern: AMD's enterprise GPU supply is going to high-volume customers; small benchmark workloads like ours are being squeezed out. Hot Aisle and Crusoe (the two other AMD-first clouds) might unblock us in days; might unblock us in months. None of them have an SLA.

This isn't a temporary delay we can wait out. **The cloud substrate we need to derate from doesn't have a reliable supply path.** Phase 0 has already burned ~10 days of calendar time on this; the firm conversation is on hold until we ship a gate decision package.

---

## §2. The Platform I'm Recommending

**NVIDIA Jetson AGX Orin 64GB Developer Kit.**

Key specs:

- 12-core Arm Cortex-A78AE (Ampere generation; 64-bit ARMv8.2)
- 2048-core NVIDIA Ampere GPU with 64 Tensor Cores
- 64GB LPDDR5 unified memory, 204 GB/s bandwidth
- ~275 TOPS INT8 sparse / ~138 TOPS INT8 dense
- 15–60W configurable power envelope
- ~$2,000 (NVIDIA direct, Arrow, Amazon)
- 110×110×72 mm; small chassis with Volcano-style cooling
- Ships in 3–7 days from NVIDIA / Arrow; Prime-eligible from Amazon
- Software: JetPack 6+ / CUDA 12.x / TensorRT-LLM / cuDNN — most mature inference stack in production

**Why this platform specifically:**

| Dimension | Strix Halo (current) | Jetson AGX Orin 64GB |
|-----------|----------------------|----------------------|
| Unified memory | 128GB LPDDR5X | 64GB LPDDR5 |
| Memory bandwidth | 256 GB/s | 204 GB/s |
| Price (full appliance config) | ~$2,200 | ~$2,000 |
| Power envelope | 54W / 85W / 140W | 15W / 30W / 60W |
| OS | Linux (Ubuntu 24.04) | Linux for Tegra (Ubuntu 22.04 base) |
| Software stack maturity | ROCm 7.2.2 (gfx1151 newly supported) | CUDA 12.x / JetPack (production-deployed for 18+ months) |
| Cloud derate substrate availability | Sparse (MI300X scarce) | **Abundant (H100/H200 widely available)** |
| Vendor concentration risk | AMD-only, single-vendor APU | NVIDIA-only, multiple-SKU Jetson family |
| Forward upgrade path | Strix Halo successor TBD; rumored 2027 | Jetson AGX Thor (announced 2024, shipping 2025) — drop-in upgrade if needed |

Three meaningful advantages beyond cloud-availability:

**Software stack maturity.** JetPack 6 / CUDA 12.x is in production deployment in millions of devices (robotics, edge AI, autonomous systems). The exact model stack we need — Whisper INT8, Qwen3-4B Q4, Chatterbox-Turbo, Kokoro-82M — all have known-good Jetson paths with published benchmarks. Strix Halo gfx1151 ROCm support is improving but is fundamentally newer (gfx1151 was added to AMD's official ROCm support matrix in early 2026). The "what if Chatterbox-Turbo doesn't load on the appliance" risk that drove our entire Phase 3 ROCm-validation plan disappears with the Jetson stack.

**Memory bandwidth is in the same neighborhood.** 204 GB/s on Orin vs 256 GB/s on Strix Halo. Both are bandwidth-bound for transformer decode at batch=1. Our PRD calls for concurrency 1–4; Orin's 64GB unified memory holds Qwen3-4B (3GB) + Whisper (1.2GB) + Chatterbox (1.5GB) + 4-call KV cache (~3-4GB) + OS + buffers with room to spare. We do lose the headroom for a 30B-class LLM that Strix Halo's 128GB gave us; per the PRD that's out of scope for v1.

**Power and acoustics.** Jetson AGX Orin's 15W idle / 60W peak is materially quieter than Strix Halo's 54W / 140W envelope. For a reception-desk appliance this is a real win. The Volcano-style fan on the dev kit is audible under load but passive-mode operation is realistic at receptionBOX's concurrency profile.

**Brand alignment.** This one cuts both ways. Framework was the sovereignty-and-repairability angle. NVIDIA Jetson is the AI-everywhere angle. The law firm's talk-track shifts from "open-source AMD hardware" to "the same NVIDIA AI silicon shipping in autonomous vehicles and Walmart's robots." Both are defensible. The Jetson story is probably easier to sell to a firm partner who reads The Information; the Framework story is easier to sell to someone who reads Hacker News. The firm is law not tech — Jetson is probably the safer bet on talk-track.

---

## §3. What It Costs Us

I want to be honest about the downsides.

**Software porting: 20–30 engineering hours.** Same number as the Strix Halo pivot. Phase 2 of the benchmark harness already runs CUDA on H100 (Phase 2 smoke verdict passed 2026-05-09 on run `2f6b…`). The Jetson side reuses 95% of that code — only Tegra-specific JetPack quirks need handling. **Methodology note (DR-39 §11)**: we're skipping the dev-kit purchase + Tegra port entirely for Phase 0 and doing cloud-measure-and-derate instead. The 20–30 engineering hours becomes Phase 1 work (post-SOW signing), not Phase 0.

**Sunk cost on Strix Halo work.** ~3 engineering days of substrate code (`substrate/rocm.py`, `Dockerfile.rocm`, `orchestration/vultr_mi300x.py`, etc.) are now archival. The code stays in the repo as an optional ROCm path — if AMD's enterprise GPU supply ever recovers and we want to revisit, the runway is short. Not deleted. Not on the critical path either.

**Memory headroom shrinks from 128GB → 64GB.** The PRD's v1 use case (Qwen3-4B + Whisper + TTS at concurrency ≤4) comfortably fits in 64GB. The "what about a 30B model in v2" headroom Strix Halo gave us is gone. Per DR-25 (single-pack-per-appliance) and the PRD's "v1 is small models" framing, this is acceptable. If we need 30B-class workloads in v2, that's a Jetson AGX Thor upgrade ($3.5–4k BOM) — same socket family, drop-in.

**One more brand-narrative pivot.** The discovery addendum (`docs/addendum-receptionbox-discovery-v0_2-2026-04-22.md`) positions the appliance with implicit Framework/AMD framing. If the firm has already read it, we owe them a re-positioning email before the gate decision package lands. Open question: did anyone send v0.2 to the firm or is it internal-only? **This needs operator confirmation before the gate package ships.**

---

## §4. What Changes in the Broader Spec

If this addendum is ratified (it has been, per parent thUMBox + UMB Group sign-off in DR-39 §8), the propagation is:

**Technical Feasibility Memo v0.3 → v0.4:**
- §1 Service topology — T3 platform reference updated (Strix Halo → Jetson AGX Orin 64GB)
- §1 Hardware target paragraph — full rewrite
- §2 Latency budget — ROCm references replaced with CUDA/JetPack/TensorRT-LLM; budget numbers stay the same pending derated measurement
- §3 Failure mode 3.1 — hardware escalation path is now Jetson AGX Orin 64GB → Jetson AGX Thor 128GB rather than Strix Halo → larger Strix Halo systems
- §4 G1 benchmark measurement — substrate stays RunPod NVIDIA H100/H200 (same as Phase 2; this pivot makes Phase 2 → Phase 3 → Phase 4 a single coherent measurement story)
- §5 Technical asks — "Chatterbox ROCm install risk" question retired; new methodology note on cloud-derate vs direct-measure

**Discovery Addendum v0.2 → v0.3:**
- DR-24 (Strix Halo as v1 platform) — superseded
- DR-39 (new) — Jetson AGX Orin 64GB as v1 platform; cloud-derate methodology via RunPod NVIDIA
- §6 Hardware Tier Analysis — full rewrite with Jetson family as T3 anchor (Orin 64GB primary, Thor 128GB as upgrade path)
- NC-R9 pricing discussion — unchanged, BOM is similar

**Phase 3 plans:**
- `03-01` (substrate/rocm.py + Vultr provisioning) — parked-archival
- `03-01.5` (RunPod MI300X enabler) — obsolete
- `03-02` (Chatterbox ROCm kill-switch) — obsolete (CUDA path validated in Phase 2)
- `03-03 / 03-04 / 03-05` — to be rewritten retargeted at RunPod NVIDIA
- `03-06` (gfx1151 op-coverage audit) — obsolete (no AMD silicon in new target)

**CLAUDE.md sections to update** (deferred to coordinated rewrite, separate session):
- §1.2 MI300X providers → NVIDIA H100/H200 providers
- §2.1 ROCm container references → JetPack/TensorRT-LLM container references
- §4.1 / §4.2 STT engine → faster-whisper INT8 on CUDA (no ROCm dual-path)
- §5 TTS engine → Chatterbox CUDA / Kokoro CUDA (drop ROCm forks)
- §6 Turn detection → unchanged (already substrate-agnostic)
- §7 Derating methodology → replace gfx942→gfx1151 bandwidth/compute baseline with H100/H200→Jetson AGX Orin 64GB

**Phase 0 budget:**
- Phase 3 spend estimate drops from $54 (MI300X subtotal) → ~$31-46 (H100 NVL × 10-15 GPU-hr at $3.07/hr)
- Total Phase 0 budget against the $150 ceiling: ~$50 baseline + $25 contingency = comfortable

---

## §5. What I Need From You

This addendum is already ratified per the DR-39 sign-off block, but two items still need your explicit attention:

**A) Discovery addendum re-positioning for the firm.** Confirm whether `addendum-receptionbox-discovery-v0_2-2026-04-22.md` was sent to the firm in any form. If yes, I draft a short re-positioning email today; if no, I just write v0.3 directly. The firm conversation talk-track shifts from "Framework AMD appliance" to "NVIDIA Jetson AI appliance" — both are defensible, but I want to know which one was already said out loud.

**B) Phase 1 dev-kit purchase decision (deferred).** If the firm signs the discovery SOW after Phase 0 lands, Phase 1 will want a real Orin 64GB dev kit on hand for direct validation. ~$2k CapEx, ~3-7 day shipping. Not on the Phase 0 critical path — but worth pre-deciding before the gate decision so we can order the moment the SOW is countersigned. My recommendation: pre-approve the purchase, conditional on Phase 0 passing.

---

## §6. Methodology Note — Cloud Derate (Why No Dev Kit For Phase 0)

DR-39 §11 captures the full reasoning, condensed here:

The original Jetson pivot draft (DR-39 v0.1.0–v0.2.0) called for buying an Orin dev kit and running the harness on it directly. **That variant added ~$2k CapEx and 5–10 days of program time to Phase 0.** Replacing it with cloud-measure-and-derate (DR-39 v0.3.0):

- We already measure on RunPod NVIDIA H100/H200 (Phase 2 substrate, Phase 3 retargeted)
- We derate to Jetson AGX Orin 64GB using NVIDIA's published Jetson Orin Performance Benchmarks (developer.nvidia.com/embedded/jetson-orin-benchmarks) as the derate basis
- Same-vendor same-stack one-hop derate chain (NVIDIA cloud → NVIDIA edge, CUDA → CUDA)
- Phase 4 synthesis report's "what we did not measure" section is now bounded and citation-grounded, not open-ended

The trade-off: Phase 4 carries a derate-error confidence interval that direct-measurement would have eliminated. For Phase 0's gate decision purpose (go/no-go on the discovery SOW), the same-vendor same-stack derate chain is tractable to defend in adversarial review. The firm's technical advisor's question becomes "did you account for Orin's INT8 vs H100's FP8 quantization shift?" — a specific, answerable question, not the open-ended "how do you know your ROCm benchmark reflects gfx1151's mostly-unsupported kernels?" we faced under the Strix Halo plan.

If the firm signs the SOW, Phase 1 direct-measure validation on a real Orin dev kit closes the derate-error term entirely. We carry the uncertainty for ~5 days during Phase 0 → SOW → Phase 1, not forever.

---

## §7. My Recommendation

Already ratified. This addendum captures the rationale durably so it survives the gate-decision conversation, the firm conversation, and the inevitable "wait, didn't you pivot to Framework in April?" question from anyone scanning the doc history.

The specific SKU committed: **NVIDIA Jetson AGX Orin 64GB Developer Kit, JetPack 6.x / Ubuntu 22.04 for Tegra base.** Zero units required for Phase 0 (cloud-derate methodology). One unit conditionally pre-approved for Phase 1 if firm signs SOW.

---

**Phase 0 critical path from this ratification:** rewrite 03-03 / 03-04 / 03-05 plans for RunPod NVIDIA; execute on H100 NVL; Phase 4 synthesis with Orin-derate. ~3–5 working days. Firm conversation reopens with the gate decision package next week.
