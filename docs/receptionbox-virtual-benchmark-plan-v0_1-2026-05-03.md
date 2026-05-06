# receptionBOX Virtual Benchmark Plan

**To:** Eric (FYI), engineering bench
**From:** Dustin
**Date:** 2026-05-03
**Version:** v0.1
**Status:** Active execution plan
**Companion to:** Hardware Pivot Addendum v0.1, Feasibility Memo v0.3

**Purpose:** De-risk the receptionBOX latency budget and ROCm software stack in cloud before the Framework Desktop ships and before we sign a discovery SOW with the firm. This document is the executable plan — what to spin up, what to run, what to measure, and how to translate cloud numbers into honest Strix Halo predictions.

---

## §1. Why Virtual, and Why Now

The original plan (memo v0.3) called for benchmarking on actual Framework Desktop hardware in Week 3 of the discovery engagement. Two facts make that timing wrong:

1. **Hardware availability is not a given.** Beelink GTR9 Pro (the closest-equivalent prosumer Strix Halo box) is currently listed at $3,399 on Amazon Prime with a 2.4-star rating across 10 reviews — a meaningful price increase from the $1,999 ServeTheHome reported in October 2025, plus quality concerns that didn't exist six months ago. Framework Desktop ship times are 4–6 weeks. Either path means the benchmark slips into June or beyond.

2. **The single biggest risk in the project is ROCm software maturity for our specific stack** (Whisper streaming + Chatterbox-Turbo + Qwen3-4B concurrent). That risk can be retired on cloud MI300X this week for under $200 in compute. We do not need physical Strix Halo to retire it. We need *any* ROCm-capable AMD silicon.

Cloud benchmarking is therefore the right move not as a substitute for Strix Halo benchmarking, but as a **sequenced de-risking step** that runs before we commit to either a hardware purchase or a discovery SOW.

---

## §2. What We Can and Cannot Learn From Cloud

This is the calibration honesty section. Eric will ask exactly this question; pre-empting it.

### §2.1 What cloud MI300X validates with high confidence

- **Software stack assembly.** Does Ollama-with-Qwen3-4B-Q4_K_M run on ROCm without crashing? Does Whisper streaming work? Does Chatterbox-Turbo's ROCm build actually exist and produce intelligible audio? Does LiveKit Agents tie them together?
- **Pipeline correctness.** End-to-end: caller speaks → STT transcribes → LLM responds → TTS synthesizes → caller hears reply. The architecture either works or it doesn't, and that result is platform-independent.
- **Concurrency design.** Can the agent worker handle multiple parallel call contexts without deadlocks, memory corruption, or cross-talk? Same answer on MI300X as on Strix Halo.
- **Model quality at our chosen quantization.** Does Qwen3-4B Q4_K_M actually produce acceptable intake conversations? Does Chatterbox-Turbo's clone of a reference voice meet the bar? These are model-level questions, not hardware-level.
- **Guardrail robustness (G5).** UPL refusal, prompt injection resistance, conflict-check intake correctness. Hardware-independent.

### §2.2 What cloud MI300X tells us only by extrapolation

- **Absolute latency numbers.** MI300X has 192GB HBM3 at 5,300 GB/s memory bandwidth. Strix Halo has 128GB LPDDR5X at 256 GB/s. For our model sizes (Qwen3-4B is 3GB resident, Whisper is 1.2GB, Chatterbox is 1.5GB) we are **not memory-bandwidth bound** in the way 70B-class models would be. We are compute-and-coordination bound. The MI300X-to-Strix-Halo derating ratio for our specific workload is unknown but bounded — community benchmarks suggest somewhere between 1.5x and 4x slower on Strix Halo depending on the kernel.
- **Concurrency ceiling.** MI300X will trivially handle more concurrent calls than Strix Halo. We can determine our software-side concurrency limits but not the hardware-side ceiling.

### §2.3 What cloud MI300X cannot tell us

- **Power, thermals, fan noise.** Strix Halo at 140W performance mode in a small office is a real consideration; cloud MI300X tells us nothing about it.
- **OS/driver stability over a 30-day soak.** Cloud instances are reset between sessions; we will not see the kind of long-tail driver issues that would appear on a deployed appliance after weeks of uptime. This is a separate validation that needs a physical box.
- **Strix Halo–specific firmware quirks.** ServeTheHome's GTR9 Pro review flagged Intel NIC driver issues under load. We won't see Strix Halo platform issues until we have Strix Halo silicon.

### §2.4 The honest framing for Eric and the firm

> "We benchmarked the receptionBOX software stack on AMD MI300X via cloud, validating that the architecture, ROCm software path, and pipeline assembly all function. Latency on MI300X measured at X ms p90. Strix Halo on Framework Desktop is expected to land between X and 2.5X based on memory-bandwidth derating, with the upper bound staying within our 1200ms p99 ceiling. Physical hardware validation is scheduled for Week 1 of pilot deployment."

That framing is defensible to a sophisticated buyer. It is not "we ran it on the box you'll get" — but it is also not "we hope it works." It's a calibrated prediction with stated bounds.

---

## §3. Provider Selection

Three viable providers, listed in order of recommendation.

### §3.1 Recommended: TensorWave or Vultr (MI300X)

Current pricing: TensorWave and Vultr are running an MI300X price war below $2/hr per GPU as of April 2026. Vultr specifically lists MI300X single-GPU at $1.85/hr in their Chicago region. TensorWave is comparable.

**Why first choice:** Lowest cost for the actual ROCm path we'll ship. Single-GPU instances are sufficient for our workload (we don't need multi-GPU). Pay-as-you-go billing with no minimums.

**Why not first choice:** Less polished UX than RunPod; some configuration friction. Worth the $1/hr savings for what will likely be a 60-100 hour benchmark window.

### §3.2 Backup: RunPod (MI300X)

Pricing: RunPod MI300X is under $3/hr per GPU. Easier self-service experience than Vultr/TensorWave. Per-second billing, custom Docker containers supported.

**Why backup:** ~50% more expensive than the budget option. But the developer experience savings are real if our benchmark engineering hours are constrained.

### §3.3 Sanity-check option: NVIDIA H100 on RunPod or Lambda (CUDA)

Pricing: H100 80GB at $1.38–$2.50/hr on RunPod, Lambda, or Thunder Compute.

**Why include this at all:** As a *pre-flight check* before we touch ROCm. CUDA's tooling is significantly more mature; if our pipeline assembles cleanly on CUDA in 2 hours, we know the issues we hit on ROCm are ROCm-specific rather than logic bugs in our agent code. This is an hour or two of work, ~$10 in spend, and it strictly de-risks the ROCm session.

**Do not benchmark for production decisions on CUDA.** Numbers are not transferable to Strix Halo at all.

### §3.4 Provider selection — final

**Day 1:** RunPod H100 (~2 hours, ~$10) for pipeline pre-flight. Standard CUDA Docker, just confirm the architecture assembles.

**Days 2–5:** Vultr or TensorWave MI300X (~30–50 hours active, ~$60–$100) for the real benchmark. ROCm path validation, latency measurement, concurrency testing, guardrail probing.

**Total compute budget:** ~$150 worst case.

---

## §4. The Benchmark Itself

The benchmark mirrors the G1–G7 gates from feasibility memo v0.3 §4, adapted for cloud execution. Each gate gets a virtual-substrate caveat noted explicitly.

### §4.1 Gate-by-gate plan

| Gate | Target | Cloud-substrate notes |
|------|--------|----------------------|
| **G1: End-to-end latency** | p90 < 900ms, p99 < 1200ms | Measure on MI300X. Apply 1.5x–2.5x derating bound for Strix Halo prediction. **Pass condition modified:** MI300X p90 must be < 600ms to leave headroom for derating. |
| **G2: STT quality on phone audio** | WER < 12% on G.711 codec | Hardware-independent. Run on MI300X. Result transfers cleanly to Strix Halo. |
| **G3: Turn detection accuracy** | < 2% false-positive on mid-utterance pauses | Hardware-independent. LiveKit's semantic turn detector. Transfers cleanly. |
| **G4: Concurrency** | 4 concurrent calls at G1 latency | **Cannot fully validate on MI300X.** MI300X will handle far more than 4 concurrent. We can only validate that our agent-worker code handles 4 concurrent contexts correctly without deadlocks. Hardware ceiling determined later on Strix Halo. |
| **G5: Prompt-guardrail robustness** | Zero escapes on 200-probe UPL + injection suite | Hardware-independent. Run on MI300X. |
| **G6: PBX integration** | SIP trunk roundtrip end-to-end | **Skip in virtual phase.** SIP trunk testing requires a real Twilio number and a real PBX or test rig — not impossible to do in cloud, but not the highest-value test for $/$$$ this week. |
| **G7: TTS naturalness (cloned voice)** | Cloned Chatterbox-Turbo preferred over Kokoro in 60%+ blind A/B | Hardware-independent (model output identical given same weights). Run on MI300X. |

### §4.2 Schedule

**Day 1 (Tuesday May 5):**
- Spin up RunPod H100. Stand up the receptionBOX Docker stack — Ollama+Qwen3-4B, faster-whisper, Chatterbox-Turbo, LiveKit Agents, Postgres, Qdrant. Verify pipeline assembles end-to-end with one synthetic call.
- Spin down. **~2 hours, ~$10.**

**Day 2 (Wednesday):**
- Spin up Vultr or TensorWave MI300X. Re-deploy the same Docker stack with ROCm-enabled images. **First major risk gate:** does Chatterbox-Turbo's ROCm path actually run? If yes, proceed. If no, escalate — fall back to Kokoro-only for v1, write up the limitation, continue.
- Run G2 (STT WER) on a 200-clip synthetic G.711 corpus.
- Run G7 (TTS A/B) — record a reference voice, generate Chatterbox clone vs. Kokoro default reading 30 sample intake scripts. Send to 5 in-firm listeners for blind preference.

**Day 3 (Thursday):**
- Run G1 (end-to-end latency) on 500-call synthetic corpus. Measure p50/p90/p99.
- Run G3 (turn detection) on hesitation-heavy adversarial test set.

**Day 4 (Friday):**
- Run G5 (guardrail probes) on 200-probe UPL + injection suite.
- Run G4 (concurrency) — verify agent-worker handles 4 concurrent simulated call contexts.
- Spin down weekend; preserve volume snapshots.

**Day 5 (next Monday):**
- Synthesis. Write up results document for Eric and (later) the firm. Apply derating bounds for Strix Halo prediction. Identify any failure-mode discoveries that need to be flagged.

**Total active engineering: ~30–40 hours over 5 days. Total cloud spend: ~$150.**

### §4.3 Expected outcomes (honest predictions)

If the project is feasible, I predict:
- **G1:** MI300X p90 lands at 400–550ms. Derated Strix Halo prediction: 700–1100ms p90. Within budget but tight.
- **G2:** WER on G.711 with distil-whisper-large-v3 lands at 8–11%. Within budget.
- **G3:** Turn detection false-positive rate at 1.5–3% with default LiveKit threshold. Borderline; tunable.
- **G5:** First pass shows 5–15 escapes on a 200-probe suite. Iterative prompt hardening required; this is normal.
- **G7:** Clone vs. Kokoro is 50/50 with poorly-recorded reference, 70/30 with well-recorded reference. Confirms the recommendation to ship with onboarding-time voice recording guidance.

If any of these comes back materially worse, it's a discovery — not a failure of the plan but useful information about where to spend Phase 2 engineering.

---

## §5. What Gets Updated After

Once the cloud benchmark completes, three documents update:

**Feasibility Memo v0.3 → v0.4:**
- §2 Latency table gains "Measured on MI300X / Predicted on Strix Halo" columns
- §4 Gate table gains actual results
- §5 Technical Asks updated based on what we learned

**Hardware Pivot Addendum v0.1 → v0.2:**
- New §7: "Virtual benchmark validation — MI300X cloud test results"
- DR-25 added if results justify any architectural change

**Discovery Addendum v0.2 → v0.3:**
- KC-1 (latency feasibility) gets a "preliminary cloud validation" entry alongside the Strix Halo Phase 2 entry
- The discovery SOW we present to the firm now references *measured* preliminary numbers, not just predicted ones

---

## §6. The One Decision I Need From Eric

This plan is mostly self-funded engineering time plus ~$150 of cloud spend, so I am not asking for board sign-off. The one decision I want explicit:

**Should we share the virtual-benchmark numbers with the firm during the intro meeting, or hold them for the discovery engagement?**

- **Argument for sharing:** Demonstrates technical rigor before they sign anything. Differentiates us from Smith.ai by showing we benchmark before we sell. Builds trust.
- **Argument for holding:** The numbers will be calibrated predictions, not measurements on the actual platform. A sophisticated buyer might prefer the discovery engagement deliverable to be the first time they see real numbers. Sharing too much pre-sales devalues the discovery deliverable.

My instinct: **share at a high level** ("we ran a preliminary cloud-based feasibility test; the architecture works and projected latency on the production hardware is X–Y"), **deliver detail in the discovery deliverable** ("here are the 500-call traces, the WER measurements, the guardrail probe results, and the comparison against your specific PBX"). The discovery engagement becomes the rigor-deepening moment, not the "is this even possible" moment.

Eric's call.

---

## §7. Risk: What If Chatterbox-Turbo Doesn't Run on MI300X?

This is the single highest-risk discovery in the virtual benchmark. The Chatterbox-Turbo ROCm path is less documented than the MPS or CUDA paths. If it fails to run on MI300X, it will almost certainly fail to run on Strix Halo as well (same ROCm runtime, similar driver stack).

**Fallback hierarchy:**

1. **Try Chatterbox-Turbo with the standard ROCm 6.x runtime first.** If it works, no problem.
2. **If Chatterbox fails to run, try VoxCPM2 on ROCm.** Less polished but newer and may have better AMD coverage.
3. **If both fail, fall back to Kokoro-82M as the v1 default voice with no clone option.** Document this as a limitation; defer cloned voice to v2 (or a cloud-TTS bridge that breaks data sovereignty for outbound audio only — already noted in pluggable TTS architecture §1.5).

Any of these is recoverable. None of them kills the project. The pluggable TTS architecture (§1.5 of the feasibility memo) was built specifically to make this risk recoverable, and it does its job here.

---

## §8. Next Action

If you (Eric) have no objection: **starting RunPod H100 pre-flight Tuesday May 5.** I will send a results memo by Monday May 12. Discovery engagement timeline holds.

If you have a concern — provider choice, scope, sharing posture, or anything else — flag it before EOD Monday and I'll revise.

---

**END OF VIRTUAL BENCHMARK PLAN v0.1**
