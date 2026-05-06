# receptionBOX Hardware Platform Pivot — Decision Addendum

**To:** Eric
**From:** Dustin
**Date:** 2026-04-23
**Version:** v0.1
**Status:** Decision requested before memo v0.3 is finalized
**Target:** Feasibility Memo v0.2 → v0.3 (supersedes DR-21)

**TL;DR** — Apple's Mac mini supply chain is broken in a way that makes it unviable as our v1 platform. I'm recommending a pivot to Framework Desktop on AMD Ryzen AI Max+ 395 "Strix Halo" with 128GB unified memory. Need your sign-off before I rewrite the feasibility memo and update the discovery addendum.

---

## §1. Why This Can't Wait

The v0.2 memo committed to T3 Mac mini M4 24GB as the minimum viable platform (DR-21). As of this week, that decision is effectively unexecutable:

- Base Mac mini M4 (16GB/256GB) marked "Currently Unavailable" on Apple's US store as of April 22
- Mac mini M4 Pro with 48GB or 64GB RAM: "Currently Unavailable," no order path
- Shortest quoted shipping estimate for any Mac mini config: 6 weeks
- Longest quoted shipping estimate: 4–5 months
- Mac Studio configurations above 64GB: "Currently Unavailable"
- Root cause: global DRAM shortage driven by AI server buildout, compounded by likely M5 inventory clearance ahead of WWDC (June 8, 2026)

This isn't "our shipment got delayed by a week." This is "the platform we chose has no supply until July at the earliest, and whatever we buy then will be obsolete in six weeks." A product line that ships hardware cannot commit to a platform in that state.

The platform question has to be settled before Week 3–4 of discovery (the benchmark phase). Ideally before we sign a discovery SOW at all, because the SOW references a specific benchmark target.

---

## §2. The Platform I'm Recommending

**Framework Desktop — AMD Ryzen AI Max+ 395 "Strix Halo" with 128GB LPDDR5X unified memory.**

Key specs:
- 16 Zen 5 cores, boost to 5.1GHz
- 40 RDNA 3.5 GPU compute units
- 128GB LPDDR5X-8000 unified memory, 256 GB/s bandwidth
- Up to 96GB allocatable as GPU VRAM
- 4.5-litre chassis, Framework-designed with Cooler Master and Noctua
- ~$2,000–$2,500 depending on storage config
- Power draw: 54W quiet / 85W balanced / 140W performance
- Ships today. Multi-hundred-unit supply available through Framework direct, Bosgame, GMKtec alternatives.

**Why this platform specifically:**

| Dimension | Mac mini M4 Pro 48GB | Framework Desktop 128GB |
|-----------|---------------------|-------------------------|
| Unified memory | 48GB | 128GB |
| Memory bandwidth | 273 GB/s | 256 GB/s |
| Price (equivalent config) | ~$1,999 (if in stock) | ~$2,200 |
| Availability | 4–5 months | In stock |
| Headroom for Phase 2 (30B+ LLM) | Tight | Comfortable |
| NPU (for future inference offload) | 16 TOPS Neural Engine | 50+ TOPS XDNA 2 |
| OS | macOS | Linux (Ubuntu 24.04) |
| Supply chain risk | Severe (one vendor, constrained) | Low (multiple Strix Halo vendors: Framework, Bosgame, Corsair, GMKtec) |

Two meaningful advantages beyond availability:

**Memory headroom.** 128GB vs. 48GB is not a marginal difference. The v0.2 budget for receptionBOX on M4 Pro was tight — Qwen3-4B (3GB) + Whisper (1.2GB) + Chatterbox-Turbo (1.5GB) + Qdrant (512MB) + OS + concurrent call buffers — workable but with no room to grow into a 30B-class model, a larger TTS, or higher concurrency without another platform swap. 128GB gives us years of headroom.

**Linux native.** The v0.2 memo flagged "Docker Desktop on Apple Silicon has historically added latency for audio-adjacent workloads; we may need to drop Docker for the voice path specifically." On Linux with Strix Halo this problem disappears — Docker is native, audio latency is well-characterized, systemd process supervision is the standard path we already use for our dev/test server.

**Brand alignment.** Framework is the sovereignty-and-repairability hardware brand. A thUMBox running on Framework hardware tells the same story our marketing tells. A thUMBox running on a generic Mac mini with a sticker tells a weaker one.

---

## §3. What It Costs Us

I want to be honest about the downsides, because pivoting to a new platform three weeks before a pilot firm meeting is not free.

**Software porting: 20–30 engineering hours.** Our current stack assumes MPS (Apple) or CUDA (NVIDIA). Strix Halo uses ROCm. Ollama ROCm support is mature and well-tested; Qwen3-4B runs fine. Whisper ROCm is stable. Chatterbox-Turbo on ROCm is less polished than the MPS path and will need validation during the benchmark phase. Piper and Kokoro run on ROCm or CPU with minimal work.

**Benchmark validation of ROCm paths.** We don't have prior numbers for our specific model set on Strix Halo. The community data is encouraging (Strix Halo runs GPT-OSS 120B at ~21 tok/s, which is 15x a high-end desktop CPU) but we need our own numbers for Qwen3-4B Q4_K_M specifically with Chatterbox-Turbo running concurrently. This is work that was already scoped into the G1 benchmark — the cost is that we're benchmarking a less-familiar stack rather than the MPS one we'd have confidence in from day one.

**Fan noise.** Mac mini is silent; Strix Halo mini PCs are quiet-but-not-silent (around 35dB in quiet mode on the GMKtec EVO-X2; Framework Desktop likely comparable with its Noctua-designed cooling). In a law firm's front office this matters. Mitigation: the appliance lives in an IT closet, not on the reception desk. We specify this in the onboarding guide.

**One more software decision deferred.** The v0.2 memo raised "Docker vs. native" as a question you'd weigh in on. On Strix Halo with Linux this question becomes much easier — Docker is the default. Not a cost so much as the pivot removing a decision we were going to have to make anyway.

---

## §4. What Changes in the Broader Spec

If you ratify this pivot, the propagation is:

**Technical Feasibility Memo v0.2 → v0.3:**
- §1 Service topology — T3 platform reference updated
- §1 Hardware target paragraph — full rewrite
- §2 Latency budget — MPS references replaced with ROCm; budget numbers stay the same pending benchmark
- §3 Failure mode 3.1 — hardware escalation path is now Framework Desktop → higher-tier Strix Halo systems (Bosgame, Corsair) rather than Mac tier climb
- §4 G1 benchmark measurement — substrate swapped
- §5 Technical asks — "Docker vs. native" question retired, new ask about ROCm validation timing

**Discovery Addendum v0.2 → v0.3:**
- DR-21 (T3 Mac mini as minimum viable) — superseded
- DR-24 (new) — Framework Desktop Strix Halo as v1 platform
- §6 Hardware Tier Analysis — full rewrite with Strix Halo as T3 anchor
- NC-R9 pricing discussion — unchanged, COGS is similar

**Discovery SOW (unwritten) — can now reference a platform we can actually source.**

---

## §5. What I Need From You

One of three answers:

**A) Ratify the pivot.** I rewrite memo v0.3 with Framework Desktop as the v1 platform, supersede DR-21, and we move to a benchmark SOW that can actually be executed. Target: v0.3 memo in your inbox within 48 hours of ratification.

**B) Push back with a specific concern.** If you see a failure mode I'm missing — ROCm maturity, fan noise tolerance in a legal office, the "it's not a Mac" perception issue with the firm, supply chain risk on Framework specifically — tell me now. I'd rather revise before rewriting than write the wrong memo twice.

**C) Prefer to wait for M5 Mac mini.** Defensible position. The cost is ~60 days of timeline slip and the risk that M5 supply at launch looks like M4 supply today. If this is your preference, we pause the firm conversation until July. The warm intro holds for ~30 days of explanation; beyond that we risk losing it.

---

## §6. My Recommendation

Option A. The Mac mini path has a real chance of not opening up before we need it, and even if M5 lands clean in June, we've spent 60 days waiting on a platform when an equivalent or better one is on a truck today.

The specific SKU I'd commit to: **Framework Desktop, AMD Ryzen AI Max+ 395, 128GB LPDDR5X, 2TB NVMe, Ubuntu 24.04 LTS.** One unit for the benchmark, pre-order commitment for three more if G1 passes and the firm signs Phase 2.

---

**Ready to move on your answer.**
