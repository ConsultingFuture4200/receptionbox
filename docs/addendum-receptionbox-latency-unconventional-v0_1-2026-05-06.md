# Addendum — receptionBOX Latency Reduction (Unconventional Lens)

## v0.1

> **Created:** 2026-05-06
> **Author:** Dustin (UMB Group), with Claude (unconventional-thinking lens)
> **Status:** Exploratory — input to v1.5/v2 latency roadmap (PRD §4.5, §6 latency table)
> **Parent:** `receptionbox-technical-prd-v0_1-2026-05-03.md`
> **Companion:** `receptionbox-virtual-benchmark-plan-v0_1-2026-05-03.md`
> **Scope:** Latency optimizations for the on-prem voice pipeline beyond the v1 conventional set already in PRD §4.5. Targets v1.5 and v2 roadmap slots. Does **not** revisit DR-24 (Strix Halo hardware pivot) or DR-26 (overflow positioning).
>
> **Changelog:**
> - v0.1 — Initial pass through the unconventional-thinking process. Names the v1 default, runs four inversions, presents three structurally-grounded unconventional paths (forked speculative S2S, predictive prefetch ASR, exemplar-cache-as-default) plus a watershed-routing pattern for the SIP edge. Each path includes a minimum viable experiment with kill criteria. Proposes DR-27, DR-28, DR-29 as candidate decision records and SM-79..SM-83 as candidate metrics. **All numbers in this document are exploratory and require Phase 0 / v1.5 spike validation before promotion.**

---

## §1. Problem Statement

receptionBOX must hit **NFR-R1: p90 end-to-end < 900ms, p99 < 1200ms**, on Strix Halo (T3), for 4 concurrent calls (NFR-R2), with no audio leaving the appliance (FR-R10, FR-R33).

The v1 latency budget in the parent PRD (§4.5, §6 latency table) gets to ≤ 900ms p90 through five conventional optimizations: KV cache persistence, speculative greeting playback, grammar-constrained generation, filler-word masking, and (deferred to Phase 2) streaming partial-hypothesis STT. That set is sound. It's also the same set every commercial voice-AI vendor is converging on — see the cited 2026 reference budgets from Smallest.ai, Deepgram, Retell, ElevenLabs Flash.

The unconventional question: **what's the latency floor that a local-only, single-firm, low-call-volume appliance can reach that a multi-tenant cloud agent structurally cannot?**

That asymmetry is what this addendum tries to exploit.

---

## §2. The Default — Named

Before exploring alternatives, the v1 default path:

> **Default:** Cascaded ASR → LLM → TTS pipeline, all stages streaming, with parallel optimizations (KV cache, grammar constraints, filler-word masking, pre-rendered greeting). Each stage is independent, swappable, and observable. Triggered by VAD endpointing at 800ms silence. Total budget ≤ 900ms p90 measured from caller's last syllable to assistant's first syllable.

**Strengths:** Proven, debuggable, swappable components, every commercial voice agent uses some variant of this, conforms to the existing thUMBox three-tier router pattern (DR-3).

**Latency floor under this architecture:** Realistically ~600–700ms p90 with all v1 optimizations active and a competitive STT/LLM/TTS stack. Below that, the cascade itself becomes the bottleneck — you can't cut what's already serial.

---

## §3. The Inversions

Four assumptions buried in the default. The 1–2 most productive are pursued in §4.

### Inversion 1: "We have to wait for the user to finish speaking."

The default assumes turn detection (VAD + semantic endpointing at 800ms silence) is the trigger for response generation. But the appliance is single-tenant and serves one firm — it can profile the call patterns. Most legal-intake calls follow predictable openings: *"Hi, I'm calling because…"*, *"I need to speak with someone about…"*, *"Yes, my name is…"*. The appliance has access to call history, time-of-day, ANI (caller phone number), and a 90-day corpus of intake calls per firm.

**The inversion:** what if the assistant starts generating a likely response *before* the caller finishes speaking — and either commits or discards based on what they actually said? This is **predictive prefetch ASR**, an Amazon-published technique (Personalized Predictive ASR for Latency Reduction in Voice Assistants, arXiv 2305.13794), and the structural foundation of the more recent **RelayS2S** dual-path speculative architecture (arXiv 2603.23346).

This inversion is the one with the most measured headroom — it's where the 200–400ms per turn lives.

### Inversion 2: "TTS first-audio latency is something we minimize."

The default treats TTS first-audio as a latency cost to be reduced (FR-R17: < 180ms p90). But for a single firm, with a known persona, the set of likely first phrases is small. Greetings, acknowledgments, common intake openers, common closures, common UPL refusals, common transfer announcements. Maybe 50–200 phrases account for 60%+ of all assistant turn-openings.

**The inversion:** what if first-audio latency is approximately zero, achieved by playing pre-rendered phrases from disk while the LLM continues generating the *continuation* in the background? This generalizes the v1 speculative-greeting trick (PRD §4.5.2) into a **per-firm phrase cache** that grows with use. This is what the ant-colony pattern (biomimetic-patterns.md §Optimization) actually models — pheromone-reinforced paths get faster every time they're traversed.

### Inversion 3: "Each stage is independent and swappable."

The default's modularity (FR-R18 pluggable TTS, FR-R11 pluggable STT) is good engineering, but every interface boundary is also a serialization point. The agent-worker process passes a finalized transcript to the LLM router, then a finalized text response to TTS. Each handoff adds latency.

**The inversion:** what if we collapse the boundary between LLM and TTS at the *token* level? As the LLM emits a token, it goes directly to TTS phoneme synthesis — no waiting for sentence boundaries, no waiting for a complete clause. This is what Pipecat and LiveKit Agents already partially do via streaming, but most deployments still buffer to clause boundaries because TTS quality degrades with sub-clause input. Worth interrogating; lower headroom than Inversion 1.

### Inversion 4: "The 800ms VAD silence threshold is fixed."

The default uses a fixed 800ms silence threshold for end-of-turn (FR-R12). But silence-after-utterance is highly speaker-dependent and context-dependent. Lawyers on intake calls have measurably different speech patterns than fast-talking sales callers.

**The inversion:** train a per-firm semantic turn detector that fires earlier on confident-end-of-thought utterances and waits longer on hesitation patterns. This is real but narrow — saves 100–200ms on a subset of turns, doesn't change the architecture. Capturable as an SM target without an architectural decision record.

**Pursued in §4:** Inversions 1 and 2. They have the largest headroom and the cleanest structural grounding.

---

## §4. Three Unconventional Paths

Each path is presented with: source analogy, structural mechanism, implementation sketch, kill criteria, and reversibility/leverage rating.

---

### Path A — Forked Speculative S2S Drafting (Inversion 1)

**Source:** RelayS2S (arXiv 2603.23346, "A Dual-Path Speculative Generation for Real-Time Dialogue") and the LTS-VoiceAgent listen-think-speak framework (arXiv 2601.19952). Both 2026, both cascaded-architecture-friendly.

**Structural principle:** Run two paths in parallel the moment a turn is detected. The **fast path** is a small duplex S2S model that drafts a short response prefix (≈5 words / ~2 seconds of speech) and ships it directly to TTS. The **slow path** is the existing cascaded ASR → Qwen3-4B → guardrails → response pipeline, which generates the high-quality continuation conditioned on the committed prefix. A lightweight verifier decides at the prefix boundary whether to commit or roll back to slow-path-only.

The **forked** part is critical: the fast-path model also continues monitoring the caller's audio for barge-in. Its main attention stream tracks the live audio; a speculative stream drafts the prefix at maximum speed.

**Why this fits the on-prem case better than the cloud case:**

The fast-path draft model is small (a 0.5–1B duplex audio model). On a multi-tenant cloud, running a separate small model alongside the main model for every call is GPU-wasteful — the economics push toward sharing one larger model across many calls. **On an appliance with 4 concurrent calls and dedicated 128GB unified memory** (Strix Halo Framework Desktop spec), running a dedicated draft model per call is essentially free — the VRAM is already provisioned.

This is the structural asymmetry. Cloud voice AI optimizes for utilization across many tenants; on-prem voice AI optimizes for latency for *one* tenant whose hardware is already paid for. The forked-speculative approach turns idle silicon into latency reduction.

**Implementation sketch:**

1. Add a fourth service to §4.2 topology: `draft-s2s` — small duplex S2S model (candidate: Moshi-7B distilled, or Kyutai's released duplex S2S checkpoint, or a custom Qwen2.5-Audio-0.5B fine-tune)
2. On turn-start signal from VAD, the draft-s2s emits a prefix to TTS within ~150ms while ASR is still finalizing
3. Cascaded slow path runs in parallel as today (PRD §4.3 step 7)
4. Verifier (a 50ms grammar-check + semantic-similarity cosine against firm corpus) gates the commit
5. On commit: TTS continues from the slow-path response; on rollback: TTS plays a brief recovery phrase ("Let me think for a moment…") while slow path completes

**Predicted impact:** 250–400ms p90 reduction. Brings the 900ms target down to 500–650ms range. Crosses the 600ms "feels human" threshold cited across 2026 voice-AI literature.

**Risks:**
- **Rollback artifacts.** When the verifier rejects a prefix, the recovery phrase is audible. If rollback rate exceeds ~5%, the experience degrades below the v1 baseline.
- **Model size constraint.** Draft model must fit in the remaining VRAM after Qwen3-4B + Whisper + Chatterbox-Turbo. Strix Halo's 128GB unified memory makes this likely workable but unconfirmed.
- **Interaction with UPL guardrails.** The fast path draft happens *before* guardrails run on the slow path. A drafted prefix that begins with "Sure, I can tell you about—" must be cancellable at the verifier even if the rest of the slow-path response correctly refuses. This is solvable but requires careful design.
- **Increased complexity.** Adds a model, a verifier, and a rollback path. Not a v1 candidate.

**Reversibility:** High. The draft-s2s service is a new component; disabling it falls back to v1 cascaded behavior with a single config flag. Behind a feature flag for the entire pilot is appropriate.

**Leverage:** High. 250–400ms is meaningful — this is the thing that makes receptionBOX feel measurably faster than the equivalent cloud-deployed Twilio + OpenAI Realtime stack from a caller's perspective. **It also becomes a defensible product moat:** the cloud incumbents can't easily replicate it because their economics push toward shared draft models, not per-call draft models.

**Maturity:** Early-adopter. RelayS2S is a 2026 paper with code-not-yet-released; LTS-VoiceAgent is similar. Reference implementations exist for the forked-attention pattern in the Pipecat / LiveKit Agents communities but not yet packaged. **Budget:** 2 weeks for spike, 4–6 weeks for production-grade if spike succeeds. Candidate for v1.5 timeline (PRD §6.1).

**Minimum viable experiment:**
- **Hypothesis:** Forked draft-s2s reduces p90 end-to-end latency by ≥ 200ms with verifier rollback rate ≤ 5% on the 500-call legal-intake corpus.
- **Timeframe:** 2-week spike, post-Phase-0.
- **Kill criteria:** Rollback rate > 10%, OR p90 reduction < 100ms, OR draft model OOMs on Strix Halo with 4 concurrent calls.
- **Success criteria:** p90 reduction ≥ 200ms AND rollback < 5% AND VRAM headroom ≥ 10GB.
- **Blast radius:** Spike is on cloud MI300X (per virtual benchmark plan), no firm exposure.
- **Escape hatch:** Feature flag, default OFF until Phase 2 soak completes (FR-R54).

---

### Path B — Exemplar-Cache-as-Default (Ant Colony Pattern, Inversion 2)

**Source:** Ant colony optimization (biomimetic-patterns.md §Ant Colony) and pheromone-reinforced path selection. Also: HTTP edge caching patterns (the ESI/Varnish school of "cache the assembled response, not the components").

**Structural principle:** Individual ants explore randomly, depositing pheromone on paths they take. Shorter, more-traveled paths accumulate more pheromone, attracting more ants. Pheromone evaporates over time, preventing lock-in to suboptimal paths. The collective optimum emerges from local feedback, not central planning.

**Mapped to receptionBOX:** Every assistant turn is a "path" through the LLM-output space. For a single firm, certain turn-paths are traversed thousands of times — greetings, acknowledgments, intake openers, common UPL refusals, transfer announcements, hours/location/parking deterministic responses. The v1 design pre-renders *one* phrase (the greeting, PRD §4.5.2). The unconventional version: **every traversed path leaves a pheromone trail in the form of cached PCM audio**, and the cache grows with use.

**The mechanism:**

1. After every turn, the agent-worker logs `(input_classification, response_template_id, generated_text, generated_audio_pcm)` to a local **exemplar cache** in Postgres + filesystem
2. On the next turn, before invoking the LLM, the classifier checks: does this input match a cached path with high similarity (cosine similarity > 0.92 on the embedding of the input + classification + persona context)?
3. If yes → ship the cached PCM directly to LiveKit, no LLM invocation, no TTS invocation. **Latency: ~30ms.** This is the pheromone trail being followed.
4. If no → run the slow path as v1, log the result, and the cache grows.
5. Cache entries have a TTL and a "pheromone score" — entries that get hit reinforce; entries that go unused for 30 days evaporate. Forces continued exploration, prevents stale-cache lock-in.
6. Critically: a small percentage of "should match" turns (≈10%) get diverted to the slow path *anyway* and the result is compared. If divergence is detected, the cache entry is invalidated. This is the "pheromone evaporation" — prevents lock-in to a stale answer when the firm's persona or process changes.

**Why this works on-prem and not in cloud:**

In multi-tenant cloud voice AI, you can't safely cache responses across tenants (privacy + persona divergence). Per-tenant caching is possible but the cache cold-starts every time a new tenant onboards, and the storage cost scales with tenant count. **On a single-firm appliance, the cache is one cache, owned by the firm, growing with the firm's actual call patterns.** A 90-day corpus of 50 calls/day = 4,500 call worth of cached turns — very likely producing 60%+ cache hit rate on common turn types.

This is also the strongest manifestation of the platform's "you own the economics and the data" pillar at the *latency* level. The longer the firm uses the appliance, the faster it gets — because the appliance has been listening.

**Implementation sketch:**

1. Add `receptionbox.exemplar_cache` Postgres table: `(input_embedding vector(768), classification, persona_context_hash, response_text, response_audio_path, hit_count, last_hit_at, divergence_check_due_at)`
2. Use existing Qdrant deployment (from parent §4.2) for similarity search — already in the stack
3. Embed input via local sentence-transformer (already in §5.1 RAG pipeline)
4. Audio files stored on local disk under `/var/lib/receptionbox/exemplar-audio/{firm_id}/`, encrypted at rest per FR-R33
5. Cache check happens *between* classifier and skill router (PRD §4.3 step 7d)
6. Divergence-check sampling job runs nightly via n8n workflow

**Predicted impact:** 60%+ of turns hit cache → **near-zero latency on those turns**. p90 across all turns drops because the high-frequency tail compresses dramatically. Quantitative prediction: if 60% of turns are cache hits at 30ms and 40% are LLM-generated at 700ms, the **p90 is dominated by the 40%** — so p90 itself doesn't change much, but **median** and **p50** drop into the sub-100ms range. The conversational *feel* improves disproportionately because the most common interactions become instant.

**The real win is qualitative, not numerical:** receptionBOX stops feeling like it's "thinking" on common turns. It becomes the first voice AI that gets *faster the more you use it*.

**Risks:**
- **Voice clone drift.** If the firm re-records the voice clone (FR-R22), all cached audio becomes stale. Need to invalidate the entire audio cache on persona update — mechanically straightforward, must be handled.
- **Persona update invalidation.** Same issue, broader scope. If the firm updates persona, system prompt, or guardrails, cache entries against the prior persona must be invalidated. Persona-context-hash in the cache key handles this if hashed correctly.
- **Privacy boundary.** Cached audio is generated audio (not caller audio), so no privilege issue. Caller-utterance embeddings in the cache key are *embeddings*, not raw text — but a determined attacker with appliance access could potentially reconstruct rough utterance content from embeddings. This is no worse than the existing transcript storage (FR-R34) and is covered by the existing encryption-at-rest requirement.
- **Stale-cache UPL risk.** A cached refusal from 6 months ago might be subtly wrong if the firm's UPL guidelines have evolved. Divergence sampling + persona-context-hash invalidation handles this, but it's the highest-risk failure mode and warrants explicit ethics-counsel review.
- **Cache poisoning / adversarial inputs.** A caller who deliberately produces a near-match input could potentially trigger an inappropriate cached response. Mitigation: divergence sampling rate raised on low-confidence-classification inputs.

**Reversibility:** High. Disable via config flag → behaves as v1. Cache deletion is a single SQL truncate.

**Leverage:** Very high. Median latency improvement is large (700ms → ~30ms on cached turns), and the marketing/positioning narrative is genuinely differentiated ("the receptionist that gets faster the more it works"). Compounds with Path A — they're complementary, not competing.

**Maturity:** Medium. The pattern (semantic response cache) is well-established in non-voice contexts (LangChain's cache, Helicone, LMCache). Voice-specific exemplar caching with audio-level caching is less common in the public literature. **Reference implementations exist** in commercial voice products (some hospitality bots cache common responses) but not as a published architectural pattern. **Budget:** 1 week for spike, 3 weeks for production-grade.

**Minimum viable experiment:**
- **Hypothesis:** Exemplar cache achieves ≥ 50% hit rate on a 500-call legal-intake replay corpus, with divergence-detection rate ≤ 2% (i.e., when the slow path is consulted as a sanity check, the cached response matches the freshly-generated response ≥ 98% of the time).
- **Timeframe:** 1-week spike, can run in parallel with Path A spike.
- **Kill criteria:** Hit rate < 30%, OR divergence rate > 5%, OR cache invalidation on persona update is not mechanically clean.
- **Success criteria:** Hit rate ≥ 50% AND divergence ≤ 2% AND median latency drops by ≥ 300ms.
- **Blast radius:** Behind feature flag; cache invalidation is destructive but bounded.
- **Escape hatch:** Feature flag, default OFF until ethics review approves UPL-stale-cache risk handling.

---

### Path C — Watershed Routing at the SIP Edge (Inversion 4, Generalized)

**Source:** Watershed dynamics (biomimetic-patterns.md §Watershed Dynamics) and the principle of overflow handling built into topology, not bolted on.

**Structural principle:** Water follows gravity along the path of least resistance. Channels that carry more flow get reinforced. Flood plains absorb overflow. The system never "fails to route water" — it just spreads the load.

**Mapped to receptionBOX latency:** The four-concurrent-call constraint (NFR-R2) is a hard cliff. Call #5 doesn't degrade gracefully — it's bounced to the firm's existing staff (DR-26, the overflow positioning). But that bounce decision happens *after* the SIP INVITE is accepted and the agent-worker tries to spawn. Better: **decide concurrency before audio enters the box**.

**The mechanism:** The carrier-facing edge (Caddy → LiveKit SIP bridge) maintains a **load gauge** — current concurrent calls, current average end-to-turn-latency p90 over the last 5 minutes, current LLM queue depth. When a new SIP INVITE arrives:

- **Gauge low (< 3 concurrent, p90 < 700ms):** Accept, route to fast path (Path A draft-s2s + Path B exemplar cache enabled)
- **Gauge medium (3 concurrent, p90 700–1000ms):** Accept, route to *conservative* path (exemplar cache enabled, draft-s2s disabled to free VRAM)
- **Gauge high (4 concurrent OR p90 > 1000ms):** Decline politely with SIP 486 (Busy Here) — the carrier hunt-group rolls to the firm's human staff per DR-26
- **Gauge critical (any inference service unhealthy):** Same as high; alarm fires to firm and to UMB Group on-call

This generalizes the v1 fixed-concurrency cap into a **load-adaptive admission control** that protects latency for accepted calls instead of accepting all calls and degrading all of them.

**This isn't really a latency *reduction* — it's a latency *protection* mechanism.** It ensures the p99 budget (NFR-R1: 1200ms) actually holds under load instead of degrading silently. It's the watershed flood-plain: the system has a defined overflow path, and the overflow path is graceful.

**Implementation sketch:**

1. Add a `gauge` service (or extend agent-worker) that tracks rolling-window metrics: concurrent calls, recent latency p50/p90/p99, inference health
2. SIP INVITE handler in `livekit-sfu` consults the gauge before allocating a room
3. Decision is in code, not config — measured response, not arbitrary thresholds
4. Gauge state exposed to Optimus Brain dashboard (per FR-R46 plugin slot)
5. n8n workflow alerts firm and UMB Group when gauge enters "high" for > 60 seconds — signals that capacity planning may be needed

**Predicted impact:** Doesn't move the median or the p90 of accepted calls. **Fixes the p99 tail and protects the firm from "bad calls" caused by load spikes.** Also: gives the firm visibility into when receptionBOX is at capacity, which is operationally important — they want to know if they need to hire a part-time human receptionist or upgrade to a T4 appliance.

**Risks:**
- **Polite decline experience.** If the gauge declines a call and the carrier hunt-group rolls to a busy human line, the caller waits. This is no worse than the existing DR-26 overflow design but exposed more visibly.
- **Threshold tuning.** The gauge thresholds need to be tuned per-firm based on actual call volume patterns. Discovery phase data informs this.
- **Coupling between paths.** If Path A and Path B aren't yet implemented, the gauge has nothing to fall back to except outright decline. This path is most valuable *after* Path A and B are in place.

**Reversibility:** Very high. It's an admission control policy at the edge — disable returns to v1 behavior.

**Leverage:** Medium for latency directly, high for **operational confidence**. Without this, the firm has no visibility into "is receptionBOX about to embarrass me?" Adding it makes the appliance behave like infrastructure, not like a demo.

**Maturity:** High. Load-adaptive admission control is standard in CDN / API gateway design (Cloudflare, AWS API Gateway, NGINX rate-limiting). The novelty is applying it at the SIP layer with voice-specific thresholds.

**Minimum viable experiment:** Defer to v2 — only meaningful after Paths A and B are in production and measured baselines exist.

---

### Path E — LLM-Native Audio Tokens (Graduated to Platform Layer)

**Status:** Graduated to its own platform-layer project as of 2026-05-07.

**Source:** thUMBox Audio Layer technical PRD — `audiolayer-technical-prd-v0_*.md` in the `thumbox-audio-layer` repo. Linear project `thUMBox Audio Layer` (M0–M4 milestones). Inception: receptionBOX latency-unconventional addendum framing (this document).

**The bet:** Replace the lossy ASR → text → LLM cascade with an LLM consuming neural audio tokens directly. Adds the codec layer as a parallel pipeline alongside ASR (which continues for guardrails + audit), then progressively specializes the codec per-firm.

**Three sub-phases:**

- **Phase 0 (2 weeks)** — Mimi feasibility spike on Strix Halo. Binary go/no-go.
- **Phase 1 (6-10 weeks)** — Predictive-delta ASR. Predictor + delta processor inside the existing cascade. Composable with Path A (forked speculative S2S drafting) and Path B (exemplar cache) — they're complementary.
- **Phase 2 (3-4 months)** — Mimi codec integration as parallel pipeline; LLM consumes audio tokens via fine-tuned adapter. Research-grade; gated on board appetite + Mimi licensing.
- **Phase 3 (6+ months)** — Per-firm codec fine-tuning on the firm's call corpus, on-appliance. The differentiator: "appliance gets faster the more your firm uses it."

**Composes with this addendum's paths:**

- Stacks on top of Path A (forked speculative): the audio-token input layer is upstream of speculative draft generation; either path's win compounds with the other.
- Stacks on top of Path B (exemplar cache): audio-similarity exemplar matching becomes possible at the token level (currently only text-level cache hits in this addendum).
- Independent of Path C (watershed routing): admission control operates at SIP edge, before either text-cascade or token-cascade has run.

**Reason for graduation out of receptionBOX:** Audio Layer is platform infrastructure consumed by voice packs (receptionBOX first, future voice packs later), not a path internal to receptionBOX. Per DR-AL-1 in the Audio Layer PRD: customers don't buy "audio infrastructure"; they buy receptionBOX. Treating the codec layer as a graduated platform project means the latency wins extend to all future voice packs without re-implementation per pack.

**Latency win estimate:**

- Phase 1 (predictive-delta ASR): 80-150ms p90 reduction
- Phase 2 (audio codec input): +150-300ms p90 reduction (research-grade estimate)
- Phase 3 (per-firm codec): marginal raw latency, but median experience drops below human perception threshold consistently

Combined with this addendum's Paths A + B, the realistic p90 floor falls to ~300-450ms.

**Where to track Path E from receptionBOX-side:** Cross-reference to thUMBox Audio Layer PRD only; do not duplicate scope here.

---

## §5. Tradeoff Analysis Across Paths

| Path | Headroom (p90) | Headroom (median) | Complexity | v1.5 candidate? | v2 candidate? |
|------|----------------|-------------------|------------|-----------------|---------------|
| A — Forked Speculative S2S | 250–400ms | ~150ms | High | Yes (post-Phase-0) | — |
| B — Exemplar Cache | ~50ms | 300–500ms | Medium | Yes (post-Phase-0) | — |
| C — Watershed Edge | ~0ms (median), large p99 win | 0ms | Low | No — needs A/B baseline first | Yes |

**Combinatorial behavior:**
- A and B compose well: A reduces TTFA on novel turns; B eliminates LLM cost on familiar turns. They optimize different parts of the distribution.
- C only matters once A and B are in place — its job is to protect the gains.

**The serious recommendation:**

If Phase 0 cloud benchmark passes the v1 default budget (≤ 900ms p90 on MI300X derated to Strix Halo prediction), proceed to Phase 1 discovery on the v1 baseline. **Do not block Phase 1 on these paths.**

Then, in v1.5 (post-Phase-2 production stability soak, NFR-R3 validated):
1. Spike Path B (exemplar cache) first — lower complexity, higher median impact, sets up the cache infrastructure
2. Spike Path A (forked speculative) second — higher complexity, requires draft model integration, depends on B being stable for A/B comparison

In v2:
3. Add Path C (watershed admission control) once A and B baseline metrics exist

---

## §6. Candidate Decision Records and Metrics

These are *candidate* records. They are not adopted by this addendum — adoption requires PRD revision and board signoff. They are listed here so the merge target into the PRD is unambiguous.

### Candidate Decision Records

**DR-27 (candidate): Adopt forked speculative S2S drafting for v1.5**
- Status: Candidate — gated on v1.5 spike per §4 Path A success criteria
- Merge target: receptionBOX PRD §4.5 (streaming optimization, new item 6) and §6 (latency target table, v1.5 row)

**DR-28 (candidate): Adopt per-firm exemplar audio cache for v1.5**
- Status: Candidate — gated on v1.5 spike per §4 Path B success criteria + ethics-counsel review of stale-cache UPL risk
- Merge target: receptionBOX PRD §4.5 (streaming optimization, new item 7), §1.7 (recording/consent — clarify exemplar cache audio is generated, not caller audio), §6 (latency target table, v1.5 row)

**DR-29 (candidate): Adopt watershed admission control at SIP edge for v2**
- Status: Candidate — gated on DR-27 and DR-28 being in production for ≥ 60 days
- Merge target: receptionBOX PRD §4.2 (service topology, livekit-sfu enhancement), §6 (latency target table, v2 row)

### Candidate Success Metrics

| ID | Metric | Target | Source |
|----|--------|--------|--------|
| SM-79 (cand.) | Verifier rollback rate (Path A) | ≤ 5% | Production telemetry, v1.5 |
| SM-80 (cand.) | Exemplar cache hit rate (Path B) | ≥ 50% | Production telemetry, v1.5 |
| SM-81 (cand.) | Cache divergence rate (Path B) | ≤ 2% | Nightly divergence-check sampling |
| SM-82 (cand.) | Median end-to-end latency on cache-hit turns | ≤ 100ms | Production telemetry |
| SM-83 (cand.) | p99 latency under high-gauge load (Path C) | ≤ NFR-R1 (1200ms) | Synthetic load test |

### Open Questions (NC-)

| ID | Question | Blocks |
|----|----------|--------|
| NC-R12 (cand.) | Does Strix Halo unified memory accommodate Qwen3-4B + distil-whisper + Chatterbox-Turbo + Moshi-distilled draft model + 4 concurrent call working sets? | Path A go/no-go |
| NC-R13 (cand.) | What is the legal-counsel position on exemplar-cached UPL refusals and cached responses in privilege-adjacent contexts? | Path B go/no-go |
| NC-R14 (cand.) | Does Pipecat / LiveKit Agents have native support for forked-attention patterns, or does this require custom agent-worker code? | Path A scoping |

---

## §7. Where I Am Honestly Uncertain

The unconventional-thinking skill requires honest risk assessment. Surfaces of uncertainty:

1. **The 250–400ms predicted impact for Path A is borrowed from RelayS2S paper benchmarks.** Those benchmarks are on cloud GPU with English customer-service intents. Strix Halo + legal-intake intents may yield different numbers. The Phase 0 virtual benchmark plan should add a "fork-speculative spike" scenario.

2. **Path B's 50% hit rate is a guess based on pattern frequency in the legal-intake space.** It could be 30%; it could be 70%. The 500-call corpus replay is the right way to find out, and the spike runs that experiment.

3. **All three paths add complexity to a v1 architecture that is already complex.** The PRD's strength is its discipline (§4.5 has only five conventional optimizations). Adding three more is a maintainability cost, not just an engineering cost. Worth discussing with Eric and Kevin before v1.5 commitment.

4. **Forked speculative is genuinely bleeding-edge.** RelayS2S is 2026. Code may not be released. We may be implementing from the paper, which is a real project-management risk for a small team.

5. **Exemplar cache is the thing I'd build first if I were Dustin.** It compounds with everything (works equally well with v1 or v1.5+v1.5), it's the most legible "you own the data" story at the latency level, and it's the lowest-risk of the three. If only one of these gets built, this is the one.

---

**END OF ADDENDUM v0.1**
