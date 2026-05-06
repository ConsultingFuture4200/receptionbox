# thUMBox Platform — Addendum: receptionBOX Discovery Gate

> **Target spec version:** v2.1
> **Addendum started:** 2026-04-22
> **Last updated:** 2026-04-22
> **Status:** DISCOVERY — PRE-BUILD GATE
> **Author:** Dustin (UMB Group)
> **For:** Board review (Eric, Kevin, Mike)
> **How to use:** This addendum is a **discovery-phase gate document**, not a build spec. It defines kill criteria, required validations, and legal/regulatory posture for a proposed voice-receptionist pack ("receptionBOX") in response to an inbound warm lead from a large law firm. No code, hardware selection, or pricing commitment should follow from this document until the five kill criteria in §KC are either passed or explicitly waived with board sign-off. If any kill criterion fails, the recommendation is to decline the opportunity or pivot scope to a non-voice intake product.

---

## Change Log

| Date | Section | Summary |
|------|---------|---------|
| 2026-04-22 | §1 (NEW) | Strategic framing — why this is a discovery gate, not a build |
| 2026-04-22 | §2 (NEW) | Proposed scope — receptionBOX as a voice receptionist pack |
| 2026-04-22 | §3 (NEW) | Architectural challenges — latency, telephony, concurrency |
| 2026-04-22 | §4 (NEW) | Regulatory posture — attorney-client privilege, state bar ethics, AI disclosure |
| 2026-04-22 | §KC (NEW) | Kill criteria — five gates that must pass before any build commitment |
| 2026-04-22 | §5 (NEW) | Discovery engagement structure (paid professional services) |
| 2026-04-22 | §6 (NEW) | Hardware tier analysis — T3 floor, T4/T5 under consideration |
| 2026-04-22 | §7 (NEW) | Positioning tension — data sovereignty claim vs. telephony reality |
| 2026-04-22 | §8 (NEW) | Open questions (NC markers) |
| 2026-04-22 | DR-20 (NEW) | Decision record: Treat receptionBOX as discovery engagement, not roadmap pack |
| 2026-04-22 | DR-21 (NEW) | Decision record: T3 Mac mini M4 as minimum viable platform (T2 Jetson insufficient) |
| 2026-04-22 | DR-22 (NEW) | Decision record: Telephony transport exception to "data never leaves the box" pillar |

---

## §1. Strategic Framing

A large law firm, introduced via the board network, has expressed interest in a "receptionist box" — scoped by Dustin's initial conversation as **a full voice receptionist that answers inbound calls**.

This is a meaningfully different product than any pack currently on the thUMBox roadmap (MailBOX One, SocialBOX, financeBOX, salesBOX, schedulerBOX, researchBOX, calendarBOX). The differences are not cosmetic:

- **Modality.** Every shipped and planned pack operates on asynchronous text-based inputs (email, documents, CRM records, social posts). Voice adds real-time speech-to-text, text-to-speech, and sub-second latency budgets.
- **Transport.** Every shipped and planned pack operates over customer-controlled or customer-authorized APIs (IMAP, OAuth, platform APIs). Voice receptionist requires PSTN connectivity, which means a third-party telephony carrier.
- **Buyer.** The current GTM wedge (DR-16, DR-17) is SMB owners and founder-led outbound for the first ~50 units. A large law firm is not an SMB and does not procure like one.
- **Regulatory surface.** Email triage touches CAN-SPAM, GDPR, and retention rules. Voice reception at a law firm touches attorney-client privilege, state bar ethics rules on AI use, two-party consent recording laws, and ABA Model Rule 5.3 (supervision of non-lawyer assistance — which now includes AI under multiple state bar advisory opinions).

The warm intro is valuable. The use case is legitimate. But shipping a voice receptionist pack to a large law firm on the current roadmap would **skip every one of the discipline gates that make financeBOX a measured build**: no hardware validation, no T2 benchmark, no legal review, no pricing model, no phase plan.

**The recommendation of this addendum is therefore:**

1. Accept the introduction and take the meeting.
2. Frame the engagement as a **paid discovery sprint** (UMB Group professional services, DR-16 wedge), not as a product sale or pack commitment.
3. Run the five kill criteria in §KC in sequence. If any fails, the engagement terminates cleanly with UMB Group having been paid for discovery work and the law firm having received a defensible technical assessment.
4. Only on full kill-criterion passage does a receptionBOX pack addendum (v0.2, build-phase) get authored.

**See DR-20.**

---

## §2. Proposed Scope

For the purpose of evaluating feasibility, the following scope is treated as the target product the law firm is asking about. This scope is **hypothetical** and subject to pivot during discovery.

### §2.1 In-Scope (if all kill criteria pass)

| ID | Capability |
|----|------------|
| R-01 | Inbound call answering with natural-sounding synthetic voice |
| R-02 | Caller intent classification (new matter inquiry, existing client, vendor, referral source, unsolicited sales) |
| R-03 | Conflict-check intake (caller name + adverse party name) routed to firm conflict-check system or held for attorney review |
| R-04 | Appointment scheduling against attorney calendars (integration with existing firm calendar system) |
| R-05 | Message taking with structured transcription and routing to the correct attorney or practice group |
| R-06 | After-hours and overflow handling (primary human receptionist offline or on another call) |
| R-07 | Local transcript storage — full call audio and transcript retained on the appliance, accessible via Optimus Brain dashboard |
| R-08 | Attorney-facing daily digest: calls taken, messages routed, appointments booked, escalations |

### §2.2 Out of Scope (explicit)

| ID | Exclusion | Rationale |
|----|-----------|-----------|
| R-X1 | Outbound calling | Regulatory complexity (TCPA) and lower value than inbound |
| R-X2 | Legal advice or case analysis during call | UPL (unauthorized practice of law) risk is categorical |
| R-X3 | Intake of privileged case facts beyond caller/adverse party names | Privilege attaches immediately; limit collection surface |
| R-X4 | Billing / AR collection calls | Different regulatory regime (FDCPA) |
| R-X5 | Interpretation between languages in real time | Liability surface too high for v1 |
| R-X6 | Replacing human receptionist entirely | Position as overflow + after-hours, not primary |

### §2.3 Positioning (Tentative)

If a pack ships, it should be positioned as **overflow and after-hours coverage that sounds human and never leaks client data** — not as a receptionist replacement. This reduces legal exposure (the firm retains a human receptionist as primary line of accountability) and matches the "graduated autonomy" frame already established in the platform (NC-0, buyer reassurance posture).

---

## §3. Architectural Challenges

Voice is the hardest modality thUMBox has been asked to support. Three issues dominate feasibility.

### §3.1 End-to-End Latency

A natural-sounding phone conversation requires response latency under roughly 800 milliseconds from the caller's last word to the appliance's first spoken word. Above that, the caller perceives the system as broken. Above 1.5 seconds, they hang up.

The pipeline is:

```
Caller audio → Carrier → Appliance STT → LLM inference → TTS → Carrier → Caller
                         └──────────── must complete in ~800ms ────────────┘
```

On T2 (Jetson Orin Nano 8GB), running Qwen3-4B already consumes most of the available memory and compute during MailBOX operation. Adding concurrent Whisper STT and a local TTS model (Piper, Coqui, or similar) to the same 8GB device while maintaining sub-800ms latency is **almost certainly infeasible** and has not been benchmarked.

T3 (Mac mini M4, 24GB) is the realistic minimum. Apple Silicon's unified memory architecture and neural engine give it a meaningful advantage for concurrent audio + LLM workloads. Even on T3, latency is unvalidated.

**See DR-21 and KC-1.**

### §3.2 Telephony Transport

PSTN connectivity requires one of:

| Option | Provider examples | Data path |
|--------|-------------------|-----------|
| Hosted SIP trunk | Twilio, Telnyx, Signalwire | Audio traverses provider's network |
| Bring-your-own carrier with SIP trunk to on-prem | Firm's existing carrier | Audio traverses carrier network only, terminates on appliance |
| VoIP integration with existing firm PBX | RingCentral, 8x8, firm's existing system | Audio traverses firm PBX + VoIP provider |

In all three cases, raw call audio crosses a third party's network before reaching the appliance. The "data never leaves the box" pillar must be caveated: **the appliance retains the transcript, the audio recording (if enabled), the call metadata, and all derived data locally; the transport layer is handled by a carrier and is out of UMB Group's control.**

This is not a fatal issue — it's analogous to how email traverses ISPs before reaching the IMAP server — but it needs to be explicitly stated in the pack positioning and in customer agreements. **See DR-22 and §7.**

### §3.3 Concurrency

A large law firm will have concurrent inbound calls during peak hours. Even a small firm averaging 50 calls/day will see bursts of 3–5 simultaneous calls during lunch hour and end-of-day.

Each concurrent call requires its own STT stream, LLM context, and TTS output. T3 Mac mini M4 can likely handle 2–3 concurrent calls. A large firm will need more. Options:

1. **One appliance per N concurrent lines** (scales with firm size; complicates the "one box" narrative)
2. **T4/T5 tier with more parallelism** (not yet specified, adds hardware SKU complexity)
3. **Queue overflow calls to human receptionist** (simplest; makes the product genuinely "overflow coverage" per §2.3)

Option 3 is the recommendation for any v1. **See KC-4.**

---

## §4. Regulatory Posture

Law firms are a regulated environment. A voice receptionist pack cannot be shipped into a law firm without specific legal review. This section is a **non-exhaustive** pre-read for that review.

### §4.1 Attorney-Client Privilege

Privilege attaches when a person consults a lawyer with the intent of obtaining legal services, regardless of whether the lawyer has formally agreed to representation. A caller describing their legal situation to the receptionist — even before an attorney picks up — may be communicating privileged information.

**Implications:**
- Call audio and transcripts are privileged material. Storage, access control, retention, and deletion must meet the same standard as the firm's existing document management.
- Any third party with access to audio or transcripts (including UMB Group) risks privilege waiver. This argues strongly for: (a) no remote access by UMB Group to call content, (b) no telemetry or diagnostic data that includes call content, (c) a data processing agreement that explicitly establishes the firm as the data controller and UMB Group (if involved at all in call content handling) as a processor under strict terms.
- OTA model updates and diagnostic pulls must be carefully scoped to exclude any call content.

### §4.2 State Bar Ethics Rules on AI Use

As of 2026, multiple state bars have issued advisory opinions on AI use in law practice. The pattern across CA, FL, NY, TX, and ABA Formal Opinion 512 is:

- Lawyers must supervise AI tools (ABA Model Rule 5.3 extended to AI).
- Lawyers must maintain competence regarding AI limitations (Rule 1.1 comment 8).
- Lawyers must preserve client confidentiality when using AI (Rule 1.6).
- Some states require client disclosure of AI use in the representation.

**Implications for receptionBOX:**
- The firm (not UMB Group) bears the ethical obligation, but the product must not make compliance impossible.
- Caller disclosure ("Calls may be answered by an automated assistant") is likely required in many jurisdictions.
- Logs must be sufficient for the firm to demonstrate supervision if challenged.

### §4.3 Call Recording Consent

US states split into one-party and two-party consent jurisdictions for call recording. Eleven states (CA, CT, DE, FL, IL, MD, MA, MT, NV, NH, PA, WA — note list is illustrative and requires legal confirmation before shipping) require all parties to consent.

**Implications:**
- If the product records audio (as opposed to transcribing in real time and discarding audio), the firm must play a consent disclosure before engaging the caller.
- The product should default to transcript-only (no audio retention) with audio retention as a firm-configurable option.
- Multi-state firms or firms serving out-of-state callers must use the strictest applicable standard.

### §4.4 Unauthorized Practice of Law (UPL)

The receptionist must not provide legal advice. This includes:
- Answering substantive legal questions ("Do I have a case?")
- Quoting fees or estimating case outcomes
- Identifying statutes of limitations or procedural deadlines

**Implications:**
- System prompts must explicitly scope the model to administrative tasks only.
- Clear fallback behavior when callers ask legal questions: "An attorney will need to answer that — I can take your information and have someone call you back."
- Logs of refusals should be retained for audit.

### §4.5 Required Legal Artifacts (Before Any Pilot)

| Artifact | Owner | Status |
|----------|-------|--------|
| Privilege-aware Data Processing Agreement | UMB Group counsel + firm counsel | Not started |
| Caller disclosure script (jurisdiction-appropriate) | Firm counsel | Not started |
| AI supervision policy template for firm | Firm counsel (UMB Group may provide reference) | Not started |
| Two-party consent recording module (if audio retention enabled) | UMB Group engineering + counsel review | Not started |
| UPL guardrail test suite (100+ legal-question probes) | UMB Group engineering | Not started |
| Privilege incident response runbook (what happens if audio leaks) | Joint | Not started |

---

## §KC. Kill Criteria

The following five criteria must all pass before UMB Group commits to building a receptionBOX pack. Each criterion is a go/no-go gate. Failure of any one is sufficient to decline the opportunity.

### KC-1: Latency Feasibility (Technical)

**Gate:** End-to-end latency (caller last word → appliance first spoken word) under 900ms at the 90th percentile across a 500-call synthetic test set, on the selected hardware tier.

**Validation method:** Benchmark on T3 Mac mini M4 with Whisper small/medium STT + Qwen3-4B inference + Piper or Coqui TTS, using a simulated SIP trunk. If T3 fails, re-benchmark on T4/T5 before killing the project.

**Fail disposition:** If no tier achieves the gate at acceptable COGS, decline.

**Owner:** UMB Group engineering.

**Estimated cost:** 40–60 hrs + one T3 unit (~$800 COGS).

---

### KC-2: Legal Review — UPL and Privilege (Regulatory)

**Gate:** Outside counsel opinion that (a) the product as specified does not constitute UPL when operated with the documented guardrails, and (b) privilege can be maintained with the proposed data handling architecture.

**Validation method:** Retain law firm specializing in legal ethics + technology. Provide them with system prompts, guardrail specification, data flow diagrams, and proposed DPA terms. Receive written opinion.

**Fail disposition:** If counsel opinion is negative, or if required mitigations would materially degrade the product, decline.

**Owner:** UMB Group (legal counsel retainer).

**Estimated cost:** $8,000–$15,000.

---

### KC-3: Client Firm Commitment (Commercial)

**Gate:** The law firm signs a paid discovery engagement (fixed fee, $25,000–$50,000 range) before any build work begins. Discovery engagement deliverables are: feasibility assessment, proposed architecture, pilot scope, pricing model, and a go/no-go recommendation. The engagement is designed to be valuable to the firm **even if UMB Group recommends they do not proceed.**

**Validation method:** Signed SOW, deposit received.

**Fail disposition:** If the firm is not willing to pay for discovery, they are not a serious buyer for a custom build. Offer to refer them to hosted alternatives (Ruby, Smith.ai, Posh) and close gracefully.

**Owner:** Dustin.

**Estimated cost:** Opportunity cost only.

---

### KC-4: Concurrency Budget (Technical + Commercial)

**Gate:** Firm's peak concurrent call volume is documentable and can be served by a single appliance at the selected tier, OR the firm accepts "overflow coverage" positioning (primary human receptionist remains in place; appliance handles overflow and after-hours only).

**Validation method:** Call volume data pull from firm's existing phone system for the last 90 days (peak concurrent calls by hour). Compare to benchmark concurrency on the selected hardware tier.

**Fail disposition:** If peak concurrency exceeds what one appliance can serve AND the firm rejects overflow positioning, decline or propose a multi-appliance architecture (which adds GTM and support complexity the roadmap is not ready for).

**Owner:** UMB Group engineering (benchmark) + Dustin (firm data request).

**Estimated cost:** Included in KC-1.

---

### KC-5: Positioning Coherence (Strategic)

**Gate:** A marketing-ready positioning statement for receptionBOX can be written that (a) does not undermine the dual ownership pillar (data sovereignty + cost predictability, DR-19), (b) is truthful about telephony transport, and (c) is defensible to the board without special pleading.

**Validation method:** Draft positioning passes Dustin's internal review and one board member's review.

**Fail disposition:** If the only way to sell the pack is to overclaim data sovereignty or contradict the pillar, the reputational cost of shipping it exceeds the revenue from one law firm deal.

**Owner:** Dustin.

**Estimated cost:** Bounded; this is a writing exercise.

---

### Kill Criteria Summary

| KC | Most likely to fail | Recommended order |
|----|---------------------|-------------------|
| KC-3 Firm commitment | Medium — tests seriousness of the buyer | Run **first** — cheapest to fail |
| KC-2 Legal review | Medium — depends on counsel's risk appetite | Run **second** — gate all build work |
| KC-1 Latency | High — this is the hardest technical bet | Run **third** — do not spend engineering time until KC-3 and KC-2 pass |
| KC-4 Concurrency | Low — overflow positioning is a clean fallback | Run alongside KC-1 |
| KC-5 Positioning | Low — solvable if KC-1 through KC-4 pass | Run last |

**If KC-3 fails, stop. Do not proceed to KC-1 or KC-2.**

---

## §5. Discovery Engagement Structure

If the firm signs the discovery SOW (KC-3 passes), the engagement runs 4–6 weeks with the following structure:

### §5.1 Week 1 — Requirements & Call Volume Audit
- Stakeholder interviews at firm (managing partner, office manager, existing receptionist, IT)
- Call volume data pull (prior 90 days, all lines)
- Existing phone system architecture documentation
- Existing calendar / matter management integration points

### §5.2 Week 2 — Legal Review
- Retain outside counsel (UPL + privilege specialist)
- Draft system prompts and guardrail specifications for counsel review
- Joint session with firm's ethics counsel (if they have one)

### §5.3 Weeks 3–4 — Technical Benchmark
- Procure T3 Mac mini M4 (if not already in inventory)
- Build receptionBOX feasibility prototype: Whisper STT + Qwen3-4B + Piper TTS + simulated SIP ingress
- Run KC-1 latency benchmark (500-call synthetic corpus)
- Run KC-4 concurrency benchmark

### §5.4 Week 5 — Synthesis
- Feasibility report (technical + legal + commercial)
- Proposed pilot architecture (if all KCs pass)
- Pricing model proposal
- Go/no-go recommendation

### §5.5 Week 6 — Board & Firm Review
- Present findings to firm leadership
- Present findings to UMB Group board
- If go: author receptionBOX build-phase addendum (v0.2)
- If no-go: deliver graceful exit plus referral to hosted alternatives

### §5.6 Discovery Deliverables (Regardless of Go/No-Go)

The firm receives value from the engagement even if UMB Group recommends not building:

1. Call volume analytics report
2. Independent legal opinion on AI receptionist use at a law firm (theirs to keep)
3. Comparative vendor analysis (Ruby, Smith.ai, Posh, PATLive, Answering Service Care)
4. Technical feasibility report they can use to evaluate any future AI receptionist vendor
5. Proposed AI supervision policy template (firm-counsel-reviewed)

---

## §6. Hardware Tier Analysis

| Tier | Platform | Memory | Est. Concurrent Calls | Fit for receptionBOX |
|------|----------|--------|-----------------------|----------------------|
| T0 | Raspberry Pi 5 | 8GB | 0 | Infeasible — no GPU for STT/TTS at required latency |
| T1 | Mini PC x86 (e.g., Beelink) | 16GB | 0–1 | Infeasible — insufficient inference throughput |
| T2 | Jetson Orin Nano 8GB | 8GB | 0–1 | **Unlikely feasible** — benchmark required; memory-bound with concurrent STT + LLM |
| T3 | Mac mini M4 | 24GB | 2–3 (estimated) | **Minimum viable** — assumed platform for discovery benchmark |
| T4 | Mac mini M4 Pro | 48GB | 4–6 (estimated) | Likely platform for large firms |
| T5 | Mac Studio M4 Max | 64GB+ | 6–10+ (estimated) | Enterprise / multi-line deployments |

**See DR-21.**

COGS implications: a T3/T4/T5 pack is a categorically different price point than T2 MailBOX. Pricing model must reflect this — receptionBOX will not fit the same subscription structure as MailBOX. (This is a KC-5 concern.)

---

## §7. Positioning Tension — Data Sovereignty vs. Telephony Reality

The dual ownership pillar (DR-19) claims data sovereignty: "your data never leaves the box." For text-based packs, this is literally true — IMAP and SMTP are configured from the firm's mail server directly to the appliance, and inference is local.

For voice, **the telephony carrier handles call transport.** This is an unavoidable architectural fact of PSTN connectivity.

**Three positioning options:**

| Option | Claim | Trade-off |
|--------|-------|-----------|
| A. Maintain strict pillar | "Data never leaves the box" | Requires carrying false claim; fails KC-5 |
| B. Caveated pillar (recommended) | "Transcripts, records, and all derived data stay on your appliance; call transport handled by your carrier of choice" | Honest, but longer to explain |
| C. Separate pillar for voice | "Your call content is retained only on your appliance" | Cleaner but fragments the pillar narrative |

**Recommendation: Option B.** The caveat is defensible and matches how email already works — SMTP traverses provider networks but the mailbox is customer-controlled. This is a **pillar refinement, not a pillar compromise.** See DR-22.

---

## §8. Open Questions

| ID | Question | Affects | Owner |
|----|----------|---------|-------|
| NC-R1 | Firm size: how many attorneys, how many incoming lines, how many concurrent peak calls? | KC-4, tier selection, pricing | Dustin to ask firm |
| NC-R2 | Does the firm have an existing PBX (RingCentral / 8x8 / on-prem) or does receptionBOX need to be the primary phone system? | Architecture, integration scope | Dustin to ask firm |
| NC-R3 | Practice areas of the firm? (Personal injury, corporate, family, criminal defense have different intake profiles and different UPL exposure) | KC-2, system prompts, guardrails | Dustin to ask firm |
| NC-R4 | Does the firm record calls today, and under what consent regime? | KC-2, §4.3, default audio-retention behavior | Dustin to ask firm |
| NC-R5 | What is the firm's willingness to pay for discovery (KC-3)? | Go/no-go trigger | Dustin to ask firm |
| NC-R6 | Which outside counsel does UMB Group retain for KC-2? | KC-2 execution | Dustin + board |
| NC-R7 | Voice synthesis: ElevenLabs (cloud, matches SocialBOX pattern) or local (Piper/Coqui, matches pillar)? Cloud TTS means caller voice prompts are generated on a third-party service even if caller audio never goes there. | KC-1 architecture, §7 positioning | Engineering |
| NC-R8 | Does the firm accept "overflow coverage" positioning or do they want to replace their receptionist? (If the latter, KC-4 concurrency budget becomes much harder.) | KC-4, §2.3 | Dustin to ask firm |
| NC-R9 | Pricing target: is this a premium pack (>$500/mo) or does the firm expect SMB pricing? | KC-5, commercial model | Dustin to ask firm |
| NC-R10 | Does the firm already have an IT/procurement process that will require a vendor security review (SOC 2, ISO 27001, penetration test)? | §4, sales cycle length | Dustin to ask firm |

---

## §9. Decision Records

### DR-20: receptionBOX is a Discovery Engagement, Not a Roadmap Pack

**Context:** Warm lead from a large law firm for a "receptionist box" — significantly out of scope for current roadmap (no voice packs exist, SMB wedge does not match buyer, regulatory layer is heavier than financeBOX).

**Decision:** Do not add receptionBOX to the product roadmap. Instead, accept the lead as a **paid discovery engagement** under UMB Group professional services (DR-16 wedge). Run five kill criteria (§KC) before any build commitment.

**Consequences:**
- No engineering time spent before KC-3 (firm commitment) passes.
- The engagement is revenue-positive even if the product is never built (discovery SOW is paid).
- If all KCs pass, author a build-phase addendum (v0.2) and add receptionBOX to the roadmap at that point.
- If any KC fails, decline the product engagement gracefully and retain the firm as a potential customer for other UMB Group services.

**Status:** Accepted.

---

### DR-21: T3 Mac mini M4 is the Minimum Viable Platform for Voice

**Context:** T2 Jetson Orin Nano 8GB is the current launch platform for MailBOX. Voice workloads (concurrent STT + LLM + TTS with sub-900ms latency) are highly unlikely to fit the T2 memory and compute envelope.

**Decision:** Any receptionBOX feasibility benchmark runs on T3 (Mac mini M4 24GB) as the minimum viable platform. T2 will not be benchmarked for voice unless T3 succeeds and a cost-reduction effort becomes warranted.

**Consequences:**
- COGS for receptionBOX is meaningfully higher than MailBOX. Pricing model must reflect this.
- The pack does not fit the existing T2-first GTM narrative; it's a premium pack by construction.
- T4/T5 may be required for large-firm concurrency. A tier-selection matrix will be produced in discovery.

**Status:** Accepted.

---

### DR-22: Telephony Transport is a Caveated Exception to the Data Sovereignty Pillar

**Context:** The dual ownership pillar (DR-19) claims "data never leaves the box." PSTN connectivity unavoidably routes call audio through a third-party carrier.

**Decision:** Refine the pillar for voice packs to read: "Transcripts, recordings, and all derived data remain on your appliance. Call transport is handled by your carrier of choice, under your existing carrier relationship." The pillar is not compromised — it is made precise for a new modality.

**Consequences:**
- Marketing language for receptionBOX must use the caveated form.
- Customer agreements must clearly identify the carrier as a separate data processor for transport.
- The same caveat does not apply to text-based packs (MailBOX, SocialBOX, financeBOX), which retain the stricter claim.
- This decision should be reviewed before any pack that introduces further modality complexity (e.g., video).

**Status:** Accepted.

---

## §10. Success Metrics (Discovery Phase)

| ID | Metric | Target |
|----|--------|--------|
| SM-R1 | Discovery SOW signed | Yes/No (KC-3 trigger) |
| SM-R2 | Outside counsel opinion received | Yes/No (KC-2 trigger) |
| SM-R3 | Latency benchmark 90th percentile | < 900ms on T3 or T4 (KC-1 trigger) |
| SM-R4 | Firm's peak concurrent calls documented | Number + fit determination (KC-4 trigger) |
| SM-R5 | Discovery engagement delivered on-time and on-budget | Within 6 weeks, within agreed fee |
| SM-R6 | Firm satisfaction with discovery (even if no-go) | Would recommend UMB Group to another firm: Yes |

---

## §11. Recommended Next Actions

1. **Dustin:** Take the intro meeting. Frame as "let's scope a discovery engagement."
2. **Dustin:** Ask NC-R1, NC-R2, NC-R3, NC-R4, NC-R5, NC-R8, NC-R9, NC-R10 during the first call.
3. **Dustin:** If firm signals discovery commitment, draft SOW (KC-3) before next touchpoint.
4. **Board:** Review this addendum at next meeting. Confirm or amend KC thresholds.
5. **UMB Group:** Identify outside counsel candidates for KC-2 before SOW is signed.
6. **Engineering (parked until KC-3):** Do not spec, design, or prototype receptionBOX until discovery SOW is signed.

---

**END OF ADDENDUM v0.1**
