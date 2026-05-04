# receptionBOX — Technical Build PRD

## v0.2

> **Created:** 2026-05-03
> **Last updated:** 2026-05-03
> **Author:** Dustin (UMB Group)
> **Status:** Draft — pre-discovery, awaiting cloud benchmark validation and firm signoff
> **Product type:** Voice AI personality pack for thUMBox platform
> **Target firm:** Inbound warm lead — large law firm (NDA pending)
> **Companion documents:**
> - `thumbox-technical-prd-v2_1-2026-04-16.md` — platform-level technical spec (parent)
> - `thumbox-business-prd-v2_1-2026-04-16.md` — platform-level business spec (parent)
> - `addendum-receptionbox-discovery-v0_2-2026-04-22.md` — discovery gate, kill criteria, regulatory posture
> - `addendum-hardware-pivot-strix-halo-v0_1-2026-04-23.md` — hardware platform pivot (DR-24)
> - `receptionbox-technical-feasibility-memo-v0_3-2026-04-23.md` — Eric-facing technical feasibility brief
> - `receptionbox-virtual-benchmark-plan-v0_1-2026-05-03.md` — Phase 0 cloud benchmark plan
> **Inheritance:** This PRD inherits the thUMBox platform's identifier conventions. DR/SM/NC numbers continue the platform sequence. FR identifiers use `FR-R##` prefix to distinguish receptionBOX-specific functional requirements from platform FRs. Where receptionBOX requirements override or extend platform requirements, the platform FR is cited and the override behavior is documented. The architectural relationship between this PRD and the parent platform PRD is formally defined in §0.
>
> **Changelog:**
> - v0.2 — Added §0 (Document Conventions and Parent Platform Relationship) defining the architectural layering between the platform PRD, this pack-level PRD, and downstream addenda. Establishes the canonical pattern for future pack PRDs (e.g., a hypothetical financeBOX PRD or a receptionBOX-medical vertical extension). No functional, non-functional, or decision-record changes from v0.1.
> - v0.1 — Initial PRD. Consolidates discovery addendum v0.2, hardware pivot addendum v0.1, feasibility memo v0.3, and virtual benchmark plan v0.1 into a single canonical product specification. Establishes Phase 0 (cloud benchmark) as the gate before any commitment to discovery SOW. Mirrors structure of platform technical PRD v2.1.

---

## §0. Document Conventions and Parent Platform Relationship

### §0.1 What "Parent Platform" Refers To

This PRD references "the parent platform" or "parent thUMBox" extensively. **The parent platform is thUMBox itself** — the underlying edge-AI appliance platform that all UMB Group products run on. thUMBox is not a product the customer buys directly. It is the architectural substrate that hosts specific products ("personality packs") such as MailBOX, financeBOX, SocialBOX, and now receptionBOX.

The two documents that constitute the authoritative platform specification are:

| Document | Scope |
|----------|-------|
| `thumbox-technical-prd-v2_1-2026-04-16.md` | Platform technical spec — runtime environment, service topology, RAG pipeline, relationship graph, persona system, pack architecture, dashboard plugin model, security architecture, hardware tiers, decision records DR-1 through DR-19, success metrics SM-1 through SM-65 |
| `thumbox-business-prd-v2_1-2026-04-16.md` | Platform business spec — customer profile, pricing model, go-to-market strategy, packaging, bundling, commercial milestones |

When this PRD says "parent §5.1 RAG Pipeline" it means §5.1 of the technical PRD above. When it cites "DR-19 (data sovereignty pillar)" it means a decision record formalized in the platform documents.

### §0.2 The Three-Layer Architecture

The relationship between this PRD and the parent platform is best understood as three layers:

```
┌─────────────────────────────────────────────────────────┐
│  PRODUCT LAYER (what customers buy)                     │
│                                                          │
│  MailBOX     financeBOX    SocialBOX    receptionBOX    │
│  (email)     (bookkeeping) (social)     (voice) ◄─ THIS │
│                                                          │
│  Each pack has its own pack-level PRD that inherits     │
│  from the platform PRD and specifies vertical-specific  │
│  behavior, services, plugins, and decisions.            │
└──────────────────────────┬──────────────────────────────┘
                           │
                           │ inherits from
                           ▼
┌─────────────────────────────────────────────────────────┐
│  PLATFORM LAYER (thUMBox — defined by parent PRDs)      │
│                                                          │
│  Optimus Brain dashboard │ Plugin system │ RAG pipeline │
│  Relationship graph │ Skill bus │ llm-router            │
│  Persona system │ Update mechanism │ Security model     │
│  Pack architecture contract │ Hardware tier definitions │
│  OpenClaw/NemoClaw integration layer                    │
│                                                          │
│  Cross-cutting concerns shared by all packs.            │
└──────────────────────────┬──────────────────────────────┘
                           │
                           │ runs on
                           ▼
┌─────────────────────────────────────────────────────────┐
│  HARDWARE LAYER (the physical appliance)                │
│                                                          │
│  Compute (Strix Halo / Jetson / Mac / DGX Spark)        │
│  Memory │ Storage │ TPM │ OS (Ubuntu) │ Docker          │
│                                                          │
│  Hardware tiers defined in parent platform §3.          │
└─────────────────────────────────────────────────────────┘
```

receptionBOX is one pack at the product layer. It defines voice-specific behavior, services, plugins, and decisions in this PRD. It inherits everything else from the platform layer below.

### §0.3 Three Modes of Inheritance

This PRD's relationship to the parent platform takes one of three forms in any given section:

**Mode 1 — Inherited unchanged.** The parent platform decision applies to receptionBOX without modification. Examples: encryption posture (parent §8.1), update mechanism (parent §5.6), dashboard plugin tier system (parent §7.8), cloud-API budget guard (parent §5.3). These are cited but not restated.

**Mode 2 — Inherited with extensions.** The parent platform provides the foundation; receptionBOX adds vertical-specific elements on top. Examples: model selection (parent §5.3) is inherited and extended with STT and TTS engines (this PRD §5.3); persona system (parent §5.4) is inherited and extended with voice persona elements (this PRD §5.4); service topology (parent §4.2) is inherited and extended with four new voice services (this PRD §4.2).

**Mode 3 — Inherited with overrides or refinements.** The parent platform decision required modification when applied to voice. Currently only one such case exists: parent **DR-19 (data sovereignty pillar — "your data never leaves the box")** is refined by **DR-22 (telephony transport is a caveated exception)** because PSTN audio unavoidably traverses a carrier network before reaching the appliance. This is the only platform-level decision the receptionBOX work has refined rather than inherited cleanly.

When a receptionBOX requirement, decision, or section is in Mode 3 (override or refinement), the parent decision is cited and the divergence is explicitly justified. Silent overrides are not permitted.

### §0.4 Identifier Convention

Identifiers across the platform, this PRD, and downstream addenda use a shared numbering scheme to ensure cross-document traceability:

| Prefix | Meaning | Numbering policy |
|--------|---------|------------------|
| `FR-##` | Functional requirement (platform) | Sequential within parent platform PRD |
| `FR-R##` | Functional requirement (receptionBOX-specific) | Sequential within this PRD |
| `NFR-##` | Non-functional requirement (platform) | Sequential within parent platform PRD |
| `NFR-R##` | Non-functional requirement (receptionBOX-specific) | Sequential within this PRD |
| `DR-##` | Decision record | Continuous global sequence across all platform and pack documents |
| `SM-##` | Success metric | Continuous global sequence across all platform and pack documents |
| `NC-##` | Open question / NEEDS_CLARIFICATION (platform) | Sequential within parent platform PRD |
| `NC-R##` | Open question (receptionBOX-specific) | Sequential within this PRD's discovery and PRD scope |
| `KC-##` | Kill criterion (discovery-phase only) | Defined in discovery addendum |

DR and SM numbers are **continuous and global** rather than per-document because decisions and metrics frequently apply across pack boundaries, and a single global sequence prevents collision when packs reference each other.

As of this PRD: DR-1 through DR-19 are defined in platform PRDs. DR-20 through DR-30 are defined in receptionBOX documents (discovery addendum, hardware pivot addendum, this PRD). SM-1 through SM-65 are defined in platform PRDs. SM-66 through SM-79 are defined in this PRD.

### §0.5 Authority Hierarchy

In any conflict between documents, authority flows in this order:

1. **Parent thUMBox technical PRD v2.1** (platform-level, authoritative on cross-cutting concerns)
2. **Parent thUMBox business PRD v2.1** (platform-level, authoritative on commercial structure)
3. **This receptionBOX technical PRD v0.2** (pack-level, authoritative on voice-specific behavior)
4. **receptionBOX addenda** — discovery, hardware pivot (pack-level, authoritative on their respective scoped topics)
5. **Feasibility memo, virtual benchmark plan** (engineering-decision artifacts, subordinate to PRD)
6. **Sales artifacts** — partnership pitch, interactive deck (subordinate to all PRDs)

Any finding in a sales artifact that contradicts this PRD requires a PRD update before sales material is shipped. Any decision in this PRD that contradicts the parent platform PRD requires either a platform PRD revision or an explicit Mode 3 override (§0.3) with justification.

### §0.6 Why This Layering Matters

Two reasons beyond documentation hygiene:

**First, it keeps receptionBOX from becoming an island.** When the next voice-modality pack is built — a medical-intake variant, a dental front-desk variant, a real-estate inquiry handler — the work does not start from scratch. A new pack-level PRD inherits from the same parent platform. Privilege handling, plugin architecture, encryption, hardware abstraction, update mechanism, and cost guards are all solved at the platform layer. The new pack PRD only specifies what is vertical-specific.

**Second, it supports the platform investor narrative.** A product (MailBOX) is one thing. A product family (MailBOX + receptionBOX + financeBOX) is more interesting. A platform (thUMBox) that hosts any pack and admits any future vertical without architectural rework is the story that supports a Series A or strategic partnership conversation. The parent-platform framing in this PRD is consistent with that narrative and intentional.

### §0.7 Pattern for Future Pack PRDs

This §0 should be replicated (with minor wording adjustments) at the top of every future pack-level PRD. The expected structure of a pack PRD mirrors the platform PRD's section structure (§1 Functional Requirements, §2 Non-Functional Requirements, §3 Hardware Specification, etc.) so that readers familiar with the platform PRD can navigate any pack PRD without re-orienting.

Future pack PRDs should:

1. Begin with §0 defining the parent platform relationship for that specific pack.
2. Mirror the platform PRD section numbering wherever possible.
3. Use the appropriate identifier prefix for pack-specific FRs and NFRs (e.g., `FR-F##` for a hypothetical financeBOX, `FR-M##` for medical-receptionBOX).
4. Cite parent platform sections explicitly when inheriting, extending, or overriding.
5. Document any Mode 3 overrides in §0.3 of that PRD with explicit justification.

---

---

## §1. Functional Requirements

### §1.1 Telephony Connectivity

| ID | Requirement |
|----|------------|
| FR-R1 | Connect to customer's PSTN via SIP trunk. Supported carriers in v1: Twilio, Telnyx, Bandwidth. Customer-provided BYO SIP trunk supported via standard SIP/TLS configuration. |
| FR-R2 | Support inbound call answering on a configurable phone number assigned during onboarding. v1 ships with one inbound DID per appliance; multi-DID support deferred to v2. |
| FR-R3 | Support live-transfer escalation via SIP REFER to firm-configured destination numbers (front-desk extension, attorney cell, hunt group). |
| FR-R4 | Support after-hours behavior: configurable per-day-of-week and per-time-window. Default: 8am–6pm local time → live-transfer escalation; otherwise → message-take and email/SMS notification. |
| FR-R5 | Audio codec support: G.711 μ-law (mandatory), G.722 (preferred when carrier and caller agree), Opus (WebRTC ingress for testing). |
| FR-R6 | Recording consent disclosure: configurable preamble plays automatically before any audio is captured to disk. Disclosure text and recording-on/off behavior is per-jurisdiction and is set during onboarding (FR-R32). |

[NEEDS_CLARIFICATION: Single-tenant SIP trunk per appliance vs. shared multi-tenant trunk operated by UMB Group | Affects: FR-R1, FR-R2, COGS, complexity of customer onboarding, regulatory posture | NC-R11]

### §1.2 Speech Recognition (STT)

| ID | Requirement |
|----|------------|
| FR-R7 | Streaming speech-to-text with partial-hypothesis output. First-token latency target: < 200ms p90. |
| FR-R8 | Word error rate (WER) on phone-codec audio (G.711 μ-law) target: < 12% on neutral speech, < 18% on stressed/emotional speech. |
| FR-R9 | Speaker confidence scoring on every transcribed segment. Segments with confidence below configurable threshold (default: 0.6) trigger graceful clarification: *"I'm sorry, could you repeat that?"* — at most twice per turn before escalating to human. |
| FR-R10 | Inference runs entirely on local appliance — no audio data leaves the box during STT processing. |
| FR-R11 | Default engine: distil-whisper-large-v3 INT8 on ROCm. STT engine is pluggable via the same abstraction pattern as TTS (§1.4). |

### §1.3 Conversation Management

| ID | Requirement |
|----|------------|
| FR-R12 | Voice activity detection (VAD) and semantic turn detection on every audio chunk. Default end-of-turn threshold: 800ms silence after final word. |
| FR-R13 | Barge-in handling: if caller speaks while assistant is speaking, assistant pauses TTS within 200ms and resumes listening. |
| FR-R14 | Filler-word latency masking: assistant prepends short verbal acknowledgments (*"Mm-hm,"* *"So,"* *"Okay—"*) to most responses. Behavior is configurable per persona; default ON. |
| FR-R15 | Per-call conversation state stored in memory for the duration of the call; persisted to Postgres on call end. State includes full transcript, classification, intake fields captured, escalation triggers, and confidence trajectory. |
| FR-R16 | Maximum call duration: 15 minutes hard cap. At 12 minutes, assistant offers to take a message or escalate. At 15 minutes, call ends with a polite closure. |

### §1.4 Speech Synthesis (TTS) — Pluggable

| ID | Requirement |
|----|------------|
| FR-R17 | Streaming text-to-speech with first-audio latency < 180ms p90. |
| FR-R18 | TTS engine MUST be pluggable. The voice runtime defines a `TTSEngine` interface; engine selection is a single Postgres config row per appliance. Engine swap is a dashboard operation, not a code change. |
| FR-R19 | v1 default engine: Chatterbox-Turbo (Resemble AI, MIT license) on ROCm. Voice cloning supported from 5–10s reference audio. |
| FR-R20 | v1 fallback engine: Kokoro-82M (Apache 2.0) — no cloning, ships with 11 curated neutral voices. Used as: (a) onboarding default before clone is recorded, (b) graceful-degradation path if Chatterbox-Turbo fails to load, (c) the always-available fallback voice. |
| FR-R21 | Phase 2 candidate engines (no commitment): VoxCPM2, Fish Audio S2 Pro (subject to license review), Qwen3-TTS, Voxtral. Pluggable interface allows swap without code change. |
| FR-R22 | Voice cloning workflow: managing partner records ~30s of professional speech via the dashboard's onboarding voice-capture step. System generates a clone, presents A/B preference test against Kokoro default, and only enables the clone if the firm prefers it (G7 gate). |

### §1.5 Intent Classification & Skill Routing

| ID | Requirement |
|----|------------|
| FR-R23 | Classify every caller intent into one of: `new-matter-inquiry`, `existing-client-service`, `attorney-callback`, `vendor`, `unsolicited-sales`, `wrong-number`, `urgent-escalation`, `unknown`. |
| FR-R24 | Classification runs on local Qwen3-4B with grammar-constrained generation. p90 latency target: < 250ms TTFT. |
| FR-R25 | Confidence scoring on every classification. Below threshold → ask clarifying question rather than guess. |
| FR-R26 | Skill routing follows the existing thUMBox three-tier deterministic pattern (parent platform §6, DR-3): deterministic templates for known patterns (greeting, hours, location, parking) → local LLM for novel intake → cloud LLM only for fallback. The cloud-fallback toggle (FR-R49) is OFF by default for receptionBOX. |

### §1.6 Intake Capture

| ID | Requirement |
|----|------------|
| FR-R27 | Capture caller name (first + last), callback number, email (optional), nature of matter at a privilege-safe level of detail, adverse party names, preferred callback window, and any specific attorney requested. |
| FR-R28 | Adverse party capture is privilege-aware: assistant prompts only for names, not case facts. Sample script: *"For our conflict check, can I get the name of the other party involved?"* — explicitly avoiding *"What happened?"* prompts. |
| FR-R29 | Intake fields written directly to Postgres `receptionbox.intake` table on call end. Triggers downstream skills (FR-R30). |
| FR-R30 | On intake completion, n8n triggers configured side effects: conflict-check submission to firm's case management system, daily digest entry, escalation notification if `urgent-escalation` was classified. |
| FR-R31 | Grammar-constrained generation enforces structured capture: name capture, phone-number capture, date/time parsing, email capture all use constrained decoding rather than open-ended LLM sampling. |

### §1.7 Recording, Consent, and Privilege Posture

| ID | Requirement |
|----|------------|
| FR-R32 | Recording-consent module is per-jurisdiction-configurable. Defaults: two-party-consent jurisdictions → audio recording OFF, transcripts only. One-party-consent jurisdictions → audio recording configurable, default OFF, opt-in only via dashboard toggle. |
| FR-R33 | Audio recordings, when enabled, are stored encrypted at rest on the appliance, retained for a customer-configurable period (default: 90 days, max: 7 years), and never transmitted off the appliance. |
| FR-R34 | Transcripts are stored on the appliance regardless of audio retention setting. Transcripts are subject to the same retention controls. |
| FR-R35 | Recording disclosure preamble (when recording is ON) is hardcoded at runtime to play before any audio reaches disk. The preamble cannot be skipped or disabled by the caller. |
| FR-R36 | Privilege-incident response runbook: if any audio or transcript is suspected to have been exposed (off-appliance backup, RMA event, support session), an automatic incident log is written and the firm's designated privilege officer is notified within 4 hours. |

### §1.8 UPL (Unauthorized Practice of Law) Guardrails

| ID | Requirement |
|----|------------|
| FR-R37 | Hardcoded refusals on the following caller request patterns: substantive legal questions ("Do I have a case?"), fee quotes beyond general fee structure, statute-of-limitations advice, procedural deadline advice, case outcome predictions. |
| FR-R38 | Refusal pattern is consistent and logged: assistant says *"An attorney will need to answer that — let me take your details and have someone call you back."* and the refusal event is recorded with the offending caller utterance, classification confidence, and timestamp. |
| FR-R39 | Refusal logs are visible in the dashboard for attorney review. Daily digest includes refusal count and any patterns flagged for prompt-tuning. |
| FR-R40 | UPL test suite of 200+ probes runs nightly against the production system prompt. Any new escape triggers a P0 alert and rollback to the last known-good prompt. |
| FR-R41 | Prompt injection guard: caller utterances are sanitized before being passed into any tool-call path. SQL injection, prompt-injection-style instructions (*"ignore previous instructions"*), and structured-data smuggling are all caught by an input filter prior to LLM invocation. |

### §1.9 Escalation Logic

| ID | Requirement |
|----|------------|
| FR-R42 | Escalate to live human (firm staff) when any of the following triggers: (a) caller explicitly requests an attorney, (b) classification = `urgent-escalation`, (c) caller is detected as emotionally distressed (sentiment + prosody analysis), (d) caller has refused or failed clarification three times, (e) caller asks for legal advice (FR-R37 trigger fires). |
| FR-R43 | Escalation behavior depends on time-of-day and configured destination: business hours → SIP REFER live transfer to firm's hunt group; after hours → take detailed message and send SMS+email to on-call attorney within 2 minutes. |
| FR-R44 | Escalations are logged with the trigger reason, transcript-up-to-escalation, and outcome (transferred, voicemail, message taken). |
| FR-R45 | Caller is informed of the escalation transparently: *"Let me get one of our attorneys on the line — please hold one moment."* No silent transfers. |

### §1.10 Customer Dashboard (Plugin Integration)

| ID | Requirement |
|----|------------|
| FR-R46 | receptionBOX integrates as a plugin set within the existing Optimus Brain dashboard (parent platform §7). Required plugins: `receptionbox.call-monitor` (live call queue), `receptionbox.transcripts` (searchable history with redaction support), `receptionbox.intake` (intake records and conflict-check status), `receptionbox.persona` (voice + system prompt tuning), `receptionbox.refusal-log` (UPL refusal audit), `receptionbox.escalation-history`. |
| FR-R47 | All receptionBOX plugins respect the platform's plugin tier system. Base tier: call monitor, transcripts (basic), persona settings. Enhanced tier: refusal log, escalation history, redaction tools. Enterprise tier: full audit export, custom retention configuration, multi-DID support. |
| FR-R48 | Plugins follow the platform's mobile-responsive convention. Call monitor and intake plugins are mobile-first (office manager will use these on phone). Transcript review and refusal log plugins are desktop-first (attorney review). |

### §1.11 Cloud Fallback and Cost Control

| ID | Requirement |
|----|------------|
| FR-R49 | Cloud LLM fallback (Anthropic Claude or equivalent) is OFF by default for receptionBOX. Firm may enable on a per-classification basis. When enabled, the cloud-API budget guard from parent platform §5.3 applies — receptionBOX inherits the daily/monthly cap and refusal behavior. |
| FR-R50 | If cloud fallback is enabled, the disclosure shown in the dashboard explicitly states which classifications route to cloud and what data is sent (intake fields, no audio, no full transcript). |
| FR-R51 | Cloud fallback is **never** enabled for the recording-disclosure preamble, UPL refusals, or escalation triggers — these are always hardcoded local responses. |

### §1.12 First-Boot and Onboarding (receptionBOX-specific)

| ID | Requirement |
|----|------------|
| FR-R52 | Onboarding wizard guides firm through: (1) SIP trunk configuration, (2) jurisdiction selection (drives consent disclosure templates), (3) practice-area selection (drives system prompt tuning), (4) attorney/extension directory upload, (5) hours-of-operation configuration, (6) reference voice recording + clone preference test, (7) UPL guardrail test live walkthrough, (8) first 10 supervised calls (assistant runs in shadow mode — caller hears human receptionist, assistant generates parallel responses for review). |
| FR-R53 | Onboarding handhold session (live Zoom, 90–120 min) included with purchase. Covers: live test calls, persona tuning, dashboard walkthrough, escalation-destination configuration, on-call attorney workflow, weekly review cadence setup. |
| FR-R54 | Shadow mode (FR-R52 step 8): the appliance answers calls in parallel with the firm's existing human receptionist for the first 7 days. The human handles every call live; the assistant generates what *it would have said* and the firm reviews these on the dashboard before going live. This is the trust-building period analogous to MailBOX auto-send thresholds (parent FR-18). |

### §1.13 Notifications and Reporting

| ID | Requirement |
|----|------------|
| FR-R55 | Daily digest (email or dashboard plugin) summarizing: calls answered, intake records created, appointments booked, escalations, refusals, total minutes, missed calls. |
| FR-R56 | Real-time push notification to office manager when escalation queue exceeds threshold or when an `urgent-escalation` classification fires. |
| FR-R57 | Weekly report (auto-generated): comparison of call patterns week-over-week, classification distribution, refusal patterns flagged for system prompt review, voice-clone preference drift if ongoing A/B is enabled. |

---

## §2. Non-Functional Requirements

| ID | Requirement |
|----|------------|
| NFR-R1 | **End-to-end latency.** From caller's last spoken syllable to assistant's first spoken syllable: p90 < 900ms, p99 < 1200ms. |
| NFR-R2 | **Concurrency.** Single appliance handles 4 concurrent calls at NFR-R1 latency; stretch goal 6. Beyond capacity, additional calls overflow to firm's existing staff (DR-26, §1.9). |
| NFR-R3 | **Availability.** Voice service uptime ≥ 99.5% measured over rolling 30 days, excluding firm-side internet outages. (Internet outage handling: the appliance can answer calls but cannot reach cloud-fallback or external services; it falls back to message-taking mode and notifies the firm.) |
| NFR-R4 | **Data residency.** All call audio (when retained), all transcripts, all intake records, and all conversation state remain on the appliance. The only customer data that may leave the appliance under any condition is what the firm explicitly opts into via cloud-fallback (FR-R49) or off-site backup (parent §8.4). |
| NFR-R5 | **Privilege preservation.** No third party (including UMB Group support staff) may access call audio or transcripts without explicit firm authorization on a per-incident basis, logged and time-limited. |
| NFR-R6 | **Security.** All audio and transcript files at rest are encrypted with AES-256-GCM. Encryption keys are stored in the appliance's TPM (or equivalent secure element) and never leave it. |
| NFR-R7 | **Deployment.** All services run under Docker with systemd supervision on Ubuntu 24.04 LTS. The voice runtime path may run native (outside Docker) at engineering discretion if validation shows Docker overhead is material; this is a per-component choice within the same OS. |
| NFR-R8 | **Audio quality.** Outbound audio MOS (Mean Opinion Score) target: > 4.0 in subjective testing on synthetic phone path. Recording quality target: 16 kHz minimum capture, transcoded to G.711 only at carrier handoff. |
| NFR-R9 | **Maintainability.** Configuration changes (system prompt, voice swap, jurisdiction settings, escalation destinations) take effect within 60 seconds of dashboard save without restarting the voice runtime. |
| NFR-R10 | **Auditability.** Every call produces a complete audit trail: classification decisions with confidence scores, refusal events, escalation triggers, intake fields captured, side effects fired. Audit trails retained for the same period as transcripts. |
| NFR-R11 | **Pluggability.** TTS and STT engines are pluggable per §1.4 and §1.2. LLM is pluggable via existing platform `llm-router` (parent §5.3). Carrier (SIP trunk) is pluggable via standard SIP/TLS. |

---

## §3. Hardware Specification

### §3.1 Hardware Platform

receptionBOX targets the **T3 hardware tier** of the thUMBox platform — superseding the platform's previous T3 (Mac mini M4) definition per **DR-24** (April 23, 2026 hardware pivot). receptionBOX is **not viable** on T2 (Jetson Orin Nano 8GB); the memory budget is exhausted before voice services load. T0 and T1 are excluded.

| Tier | Platform | Memory | receptionBOX support |
|------|----------|--------|----------------------|
| T0 | Raspberry Pi 5 | 8GB | Not supported — insufficient compute |
| T1 | Mini PC x86 | 16GB | Not supported — insufficient compute for concurrent STT + LLM + TTS |
| T2 | Jetson Orin Nano 8GB | 8GB | **Excluded** — memory budget blown; see DR-21 (superseded) and DR-24 |
| **T3** | **Framework Desktop (Strix Halo)** | **128GB LPDDR5X** | **Primary platform.** Supports all v1 functionality. |
| T4 | Higher-tier Strix Halo (Bosgame, Corsair, GMKtec) | 128GB LPDDR5X | Supported as fail-up option from T3 if performance demands exceed Framework specs |
| T5 | NVIDIA DGX Spark or equivalent | 128GB+ unified | Supported; reserved for enterprise multi-line deployments |

### §3.2 T3 Standard — Bill of Materials (Reference Unit)

| Component | Specification | Cost (USD, est. 2026-05) |
|-----------|---------------|--------------------------|
| Compute | Framework Desktop, AMD Ryzen AI Max+ 395 "Strix Halo" | $2,200 |
| Memory | 128GB LPDDR5X-8000 (soldered, included) | (included) |
| Storage | 2TB NVMe Gen4 SSD | $180 |
| Networking | Onboard 5GbE + Wi-Fi 7 | (included) |
| TPM / Secure element | Integrated TPM 2.0 (Framework) | (included) |
| OS license | Ubuntu 24.04 LTS | $0 |
| Chassis | Framework-designed (Cooler Master / Noctua collaboration) | (included) |
| Cabling, PSU | Included with Framework Desktop | (included) |
| **Subtotal (hardware)** | | **~$2,380** |
| Carrier setup (Twilio test number, 1 month) | | $20 |
| **Total per appliance** | | **~$2,400** |

### §3.3 T3 Assembly Process

receptionBOX appliances are not user-assembled. UMB Group performs the following intake on each Framework Desktop unit before shipping to a customer:

1. BIOS update to latest Framework firmware
2. Ubuntu 24.04 LTS install with full-disk encryption (LUKS)
3. ROCm 6.x installation and validation (Whisper + Chatterbox-Turbo + Ollama smoke test)
4. thUMBox base platform deployment (n8n, Postgres, Qdrant, Optimus Brain, llm-router)
5. receptionBOX pack deployment (LiveKit SFU, agent worker, STT, TTS engines)
6. SIP trunk credentials provisioned (customer-specific, generated at order time)
7. First-boot wizard pre-configured with customer's jurisdiction + practice area
8. End-to-end acceptance test (10 simulated calls covering greeting, intake, escalation, UPL refusal)
9. Ship to customer with onboarding session pre-scheduled

### §3.4 Hardware-Specific Model & Service Mapping

| Service | T3 (Strix Halo, 128GB) | T4 (Higher-tier Strix Halo) | T5 (DGX Spark) |
|---------|------------------------|------------------------------|-----------------|
| LLM (dialogue + classification) | Qwen3-4B Q4_K_M | Qwen3-4B Q4_K_M or Qwen3-8B | Qwen3-8B or 14B |
| STT | distil-whisper-large-v3 INT8 | distil-whisper-large-v3 INT8 | whisper-large-v3 FP16 |
| TTS (primary) | Chatterbox-Turbo | Chatterbox-Turbo | Chatterbox-Turbo or Fish S2 |
| TTS (fallback) | Kokoro-82M | Kokoro-82M | Kokoro-82M |
| Concurrency target | 4 (stretch 6) | 6–8 | 10+ |
| Memory headroom (post-load) | ~110 GB | ~110 GB | ~190 GB |

### §3.5 Dev/Test Environment

The receptionBOX dev/test environment supplements the platform dev/test server (parent §3.5) with:

- **Cloud benchmark substrate (Phase 0 only):** MI300X via Vultr or TensorWave for ROCm path validation; H100 via RunPod for CUDA pre-flight. See §14 Phase Plan and the virtual benchmark plan companion document.
- **Local Strix Halo dev unit:** Framework Desktop dev unit ordered at engineering bench, used for post-Phase-0 validation and ongoing regression testing.
- **Telephony test rig:** Twilio test SIP trunk, FreeSWITCH-based simulated PSTN for synthetic call-load testing without real carrier costs during regression runs.

---

## §4. Software Architecture

### §4.1 Runtime Environment

receptionBOX runs on the parent thUMBox platform runtime (parent §4.1) with the following deltas:

- **Operating system:** Ubuntu 24.04 LTS (matching parent platform on T3+).
- **Container runtime:** Docker Engine 24+ with systemd supervision. Voice runtime services (LiveKit SFU, agent worker) may run native (non-Docker) under engineering discretion if Docker overhead is shown to be material; this is a per-service decision documented in §4.2.
- **GPU runtime:** ROCm 6.x for Strix Halo. CUDA 12.x for T5 NVIDIA tier. No MPS path; the macOS path was retired in DR-24.
- **Process supervisor:** systemd, with the platform's existing service-unit conventions.

### §4.2 Service Topology

receptionBOX adds four new services to the parent thUMBox topology. The parent services (Ollama, Qdrant, Postgres, Optimus Brain, n8n, llm-router) are reused without modification.

```
┌──────────────────────────────────────────────────────────────────────┐
│  receptionBOX Service Topology (additions to thUMBox platform)       │
│                                                                       │
│  ┌──────────────────────────────────────────────────────────────┐    │
│  │  Telephony Ingress (outside appliance)                       │    │
│  │  Customer's SIP carrier (Twilio/Telnyx/BYO)                  │    │
│  │  → SIP/TLS over public internet                              │    │
│  │  → Caddy reverse proxy on appliance, terminating TLS         │    │
│  │  → LiveKit SIP bridge                                        │    │
│  └───────────────────────────┬──────────────────────────────────┘    │
│                              │                                        │
│  ┌───────────────────────────┴──────────────────────────────────┐    │
│  │  Voice Runtime (NEW)                                         │    │
│  │                                                               │    │
│  │  ┌────────────────┐  ┌──────────────────┐  ┌──────────────┐ │    │
│  │  │ livekit-sfu    │  │ agent-worker     │  │ vad + turn   │ │    │
│  │  │ (media + SIP)  │←→│ (orchestrator)   │←→│ detector     │ │    │
│  │  │ Docker         │  │ Python, native   │  │ in-process   │ │    │
│  │  └───────┬────────┘  └─────────┬────────┘  └──────────────┘ │    │
│  │          │                     │                              │    │
│  │  ┌───────┴────────┐  ┌─────────┴───────┐  ┌────────────────┐ │    │
│  │  │ whisper-stt    │  │ tts-engine      │  │ guardrail-     │ │    │
│  │  │ (ROCm, ONNX)   │  │ (PLUGGABLE)     │  │ filter         │ │    │
│  │  │ Docker         │  │ Docker          │  │ in-process     │ │    │
│  │  └────────────────┘  └─────────────────┘  └────────────────┘ │    │
│  └──────────────────────────────┬───────────────────────────────┘    │
│                                 │                                     │
│  ┌──────────────────────────────┴───────────────────────────────┐    │
│  │  Shared Platform Services (REUSED — parent platform §4.2)    │    │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────┐ │    │
│  │  │ ollama   │  │ qdrant   │  │ postgres │  │ optimus-brain│ │    │
│  │  │ (Qwen3)  │  │ (RAG)    │  │ (state)  │  │ (Next.js)    │ │    │
│  │  └──────────┘  └──────────┘  └──────────┘  └──────────────┘ │    │
│  │  ┌──────────┐  ┌─────────────┐                              │    │
│  │  │ n8n      │  │ llm-router  │                              │    │
│  │  │ (skills) │  │ (3-tier)    │                              │    │
│  │  └──────────┘  └─────────────┘                              │    │
│  └──────────────────────────────────────────────────────────────┘    │
│                                                                       │
│  Escalation: SIP REFER via livekit-sfu back to firm PBX or cell      │
│  After-hours: SMS+email via n8n side-effect (parent §6 skill bus)    │
└──────────────────────────────────────────────────────────────────────┘
```

**New services (four):**

| Service | Image / Source | Runtime | Memory | Purpose |
|---------|---------------|---------|--------|---------|
| `livekit-sfu` | `livekit/livekit-server:latest` + `livekit/sip:latest` | Docker | ~400MB | WebRTC SFU + SIP bridge. Terminates carrier SIP, publishes audio tracks to agent workers. |
| `agent-worker` | Custom Python (LiveKit Agents framework) | **Native** (systemd unit) | ~300MB per active call | Orchestrates STT → LLM → TTS pipeline per call. Handles turn detection, barge-in, escalation logic, tool calls into n8n/Postgres. **Native execution chosen** to avoid Docker audio-stack latency. |
| `whisper-stt` | `faster-whisper` served via ONNX Runtime, ROCm build | Docker | ~1.2GB VRAM | Streaming STT. distil-whisper-large-v3 INT8. |
| `tts-engine` | Pluggable. Default: `resemble-ai/chatterbox-turbo` ROCm build. Fallback: `hexgrad/kokoro-82M`. | Docker | ~1.5GB | Streaming neural TTS. |

**Reused parent services** are unchanged. The receptionBOX agent-worker invokes Ollama via the existing llm-router HTTP interface, queries Qdrant directly for firm-specific RAG context, writes to Postgres `receptionbox.*` tables, and triggers n8n workflows for side effects. Optimus Brain hosts the receptionBOX dashboard plugins (FR-R46).

### §4.3 Call Processing Pipeline

```
1. Inbound SIP INVITE arrives at carrier-facing edge (Caddy → LiveKit SIP bridge)
2. LiveKit SIP bridge accepts, allocates room, attaches SIP audio track
3. agent-worker spawns conversation context, loads firm persona + system prompt
4. Recording disclosure preamble (FR-R35) plays if recording is enabled
5. agent-worker subscribes to caller audio track, begins streaming to whisper-stt
6. VAD + turn detector run in-process on agent-worker, emit turn events
7. On end-of-turn:
   a. Final STT hypothesis written to conversation state
   b. guardrail-filter scans utterance for injection patterns (FR-R41)
   c. Classifier (Qwen3-4B with grammar constraints) emits intent + confidence
   d. Skill router decides: deterministic template | local LLM | refusal | escalation
   e. Response generation streams tokens from Ollama
   f. Filler-word prefix (FR-R14) ships to TTS immediately
   g. tts-engine streams PCM chunks back to agent-worker
   h. agent-worker publishes audio frames to LiveKit room outbound track
   i. Caller hears assistant response
8. Loop until: caller hangs up, escalation triggered, or 15-minute hard cap (FR-R16)
9. On call end:
   a. Full transcript persisted to postgres.receptionbox.transcripts
   b. Intake fields written to postgres.receptionbox.intake
   c. Audit log written to postgres.receptionbox.audit_log
   d. Side-effect skills fire via n8n (conflict-check, digest, escalation notification)
   e. Audio file (if recording enabled) encrypted and stored to local disk
```

### §4.4 Classification Router Logic

receptionBOX inherits the parent platform's three-tier classifier router (parent §4.4, DR-3) and extends it with voice-specific deterministic templates.

| Tier | Use case | Latency target | Cloud risk |
|------|----------|----------------|-----------|
| 1 — Deterministic | Greeting, hours, location, parking, practice areas, simple FAQs | < 50ms | None |
| 2 — Local LLM | Novel intake, conflict capture, message taking, escalation routing | < 250ms TTFT | None |
| 3 — Cloud LLM | OFF by default. Optional fallback for ambiguous cases the firm explicitly opts into. | < 800ms (network-dependent) | Customer-controlled |

For receptionBOX specifically, the cloud-fallback toggle (FR-R49) is OFF by default and must be enabled per-classification by the firm. UPL refusals, recording disclosures, and escalation triggers are **always** Tier-1 deterministic — never routed to cloud.

### §4.5 Streaming Optimization

Per-stage latency optimizations the system applies by default:

1. **KV cache persistence across calls.** Qwen3-4B remains resident in VRAM. Prompt prefix (system prompt + persona) is pre-cached at boot. Per-call state is appended; pre-cache is never invalidated by per-call content.
2. **Speculative greeting playback.** The greeting *"Thanks for calling [Firm Name], how can I help?"* is pre-rendered at boot and cached as PCM. Played directly from cache on call start; LLM and TTS warm in parallel during caller's first utterance.
3. **Grammar-constrained generation.** Name capture, phone-number capture, date/time parsing all use constrained decoding rather than open sampling. Cuts generation time 40–60% on structured turns.
4. **Filler-word latency masking (FR-R14).** First spoken token is a brief acknowledgment shipped to TTS immediately while main response continues generating. Adds ~80ms of perceived-latency cover.
5. **Streaming partial-hypothesis STT.** agent-worker reads partial hypotheses from whisper-stt at 100ms intervals. Full final transcript only required for guardrail-filter and intake-capture; LLM begins generating on confident partials with rollback if final differs materially. (Phase 2 — not in v1.)

---

## §5. Intelligence Stack

### §5.1 RAG Pipeline (receptionBOX-specific corpora)

receptionBOX uses the parent platform's RAG pipeline (parent §5.1) with firm-specific corpora indexed during onboarding:

| Corpus | Source | Indexed at | Query trigger |
|--------|--------|-----------|---------------|
| Firm directory | Onboarding upload | First boot | Caller asks for specific attorney |
| Practice areas | Onboarding form | First boot | Caller asks "do you handle [X]?" |
| Fee structure (general) | Onboarding form | First boot | Caller asks about fees |
| FAQ library | Onboarding form + ongoing additions | First boot + incremental | Ambiguous classification, fallback context |
| Conflict-check name list | Firm's case management system, daily pull | Daily 4am cron | Adverse-party capture validation |
| After-call intake history | Self-generated, the firm's prior calls | After every call | Returning-caller recognition (Phase 2) |

### §5.2 Relationship Graph Layer

Inherits parent platform §5.2 with receptionBOX-specific node types:

- `Caller` — phone number, derived name, call history
- `Matter` — captured during intake, anonymized identifier
- `Attorney` — from firm directory
- `AdverseParty` — captured for conflict screening, never cross-referenced with caller history
- `Escalation` — triggered events with context

Relationship edges follow parent platform conventions. Privilege-aware redaction is applied at the relationship-graph query layer: any query that would surface a caller's matter description to a non-authorized dashboard plugin is filtered.

### §5.3 Model Selection

receptionBOX inherits the parent platform's model selection with two voice-specific additions:

| Tier | Model | Source | Use |
|------|-------|--------|-----|
| Local LLM (dialogue) | Qwen3-4B Q4_K_M | Ollama | All in-call generation |
| Local STT | distil-whisper-large-v3 INT8 | ONNX/ROCm | Streaming transcription |
| Local TTS (primary) | Chatterbox-Turbo (350M) | Resemble AI, MIT, ROCm | Voice cloning + neutral |
| Local TTS (fallback) | Kokoro-82M | Apache 2.0, ROCm | Default neutral, fallback |
| Cloud LLM (optional, OFF default) | Anthropic Claude Haiku | Anthropic API | Fallback only on opt-in |
| Embedding | all-MiniLM-L6-v2 (parent platform) | Local | RAG retrieval |

### §5.4 Persona System

receptionBOX extends the parent platform persona system (§5.4) with voice-specific persona elements:

- **Voice clone** — optional, recorded during onboarding (FR-R22)
- **Speaking pace** — slow / normal / brisk (default: normal)
- **Filler-word style** — minimal / natural / warm (default: natural) per FR-R14
- **Greeting template** — firm-customized, validated against UPL guardrail
- **Refusal language** — firm-customized within UPL-safe templates (FR-R37)
- **Escalation language** — firm-customized within transparency requirements (FR-R45)

### §5.5 Edit-to-Skill Learning Loop (deferred)

receptionBOX v1 does **not** include the edit-to-skill learning loop from parent §5.5. The voice modality makes correction-based learning expensive (a 30-minute call cannot be "edited" the way a draft email can). Instead, receptionBOX uses:

- **Refusal log review** (FR-R39) — attorney reviews UPL refusals weekly and adjusts system prompt
- **Classification correction** — office manager re-classifies any miscategorized call from the dashboard, drives nightly prompt-tuning
- **Voice-clone preference drift A/B** — ongoing optional A/B test where a small percentage of calls use the alternate voice; preference data informs whether to swap default

Phase 2 will incorporate a voice-specific learning loop. Out of scope for v1.

### §5.6 Update Mechanism

Inherits parent §5.6 with one receptionBOX-specific consideration: voice-runtime services (`livekit-sfu`, `agent-worker`, `tts-engine`) cannot be hot-restarted during an active call. Update orchestration enforces a **drain-before-restart** pattern: configurable maintenance windows during which the appliance refuses new inbound calls (returning a "please call back" message), waits for active calls to end, applies the update, and resumes service. Default maintenance window: 2am–4am local time, opt-in only.

### §5.7 Model Optimization Roadmap (receptionBOX-specific)

| Phase | Optimization | Latency target |
|-------|--------------|----------------|
| v1 | KV cache persistence, grammar constraints, filler-word masking, speculative greeting | < 900ms p90 |
| v1.5 | Speculative decoding for common intake flows | < 700ms p90 |
| v2 | Streaming partial-hypothesis STT (LLM begins on partials, rolls back on final) | < 600ms p90 |
| v2 | Phase 2 TTS bakeoff (VoxCPM2, Voxtral, Qwen3-TTS) | TTS first-audio < 100ms |
| v2 | Speculative TTS pre-render for common acknowledgments | Cache hit: 0ms |
| v3 | Smaller specialized intake model (distilled from Qwen3-4B for legal intake specifically) | LLM TTFT < 150ms |

---

## §6. Personality Pack Architecture

### §6.1 Pack Definition

receptionBOX is a personality pack within the thUMBox platform per parent §6.1. It conforms to the pack contract:

- **Name:** receptionBOX
- **Version:** 0.1 (PRD draft); 1.0 at v1 ship
- **Required tier:** T3 minimum (Strix Halo Framework Desktop, per DR-24)
- **Required services:** All parent platform services + `livekit-sfu`, `agent-worker`, `whisper-stt`, `tts-engine`
- **Dashboard plugins:** Six receptionBOX plugins under `receptionbox.*` namespace (FR-R46)
- **n8n skills:** Conflict-check submission, daily digest, escalation notification, weekly report
- **Cloud-fallback toggle:** OFF by default (FR-R49)
- **Multi-pack co-residency:** receptionBOX **cannot** co-reside with other packs on the same appliance in v1. Voice latency budget consumes the available compute. Multi-pack co-residency deferred to v2 on T4/T5 hardware. See DR-25.

### §6.2 Pack Isolation & Shared Resources

receptionBOX follows parent §6.2 isolation rules:

- **Database:** Postgres schema `receptionbox.*` — isolated from other packs
- **Vector store:** Qdrant collections prefixed `receptionbox_*`
- **Skill namespace:** n8n workflows tagged `pack:receptionbox`
- **Plugin namespace:** Dashboard plugins under `receptionbox.*`

Shared with parent platform: Ollama (single LLM instance serves all packs), llm-router (cost guard, routing logic), Optimus Brain shell (plugin host).

### §6.3 Multi-Pack Orchestration

Not applicable in v1. receptionBOX runs as the only active pack on a deployed appliance per DR-25. v2 considerations for multi-pack co-residency on T4/T5 hardware are out of scope for this PRD.

---

## §7. Optimus Brain Dashboard Integration

receptionBOX integrates as a plugin set within the existing Optimus Brain dashboard architecture (parent §7). No changes to the dashboard shell, plugin API, or workspace presets are required.

### §7.1 Plugin Inventory

| Plugin ID | Tier | Purpose |
|-----------|------|---------|
| `receptionbox.call-monitor` | Base | Live call queue. Active calls, recent calls, escalation status. Mobile-first. |
| `receptionbox.intake` | Base | Intake records list, conflict-check status, follow-up reminders. Mobile-first. |
| `receptionbox.persona` | Base | Voice clone management, system-prompt tuning, A/B preference. Desktop-first. |
| `receptionbox.transcripts` | Enhanced | Searchable call transcript library. Redaction tooling. Desktop-first. |
| `receptionbox.refusal-log` | Enhanced | UPL refusal audit trail. Attorney-review interface. Desktop-first. |
| `receptionbox.escalation-history` | Enhanced | Escalation analytics, trigger-pattern review. Desktop-first. |
| `receptionbox.audit-export` | Enterprise | Full audit-trail export (CSV, JSON). Custom retention configuration. |
| `receptionbox.multi-did` | Enterprise | Multiple inbound DID management (v2). |

### §7.2 Workspace Presets

receptionBOX ships with two workspace presets:

- **"Front Desk"** — optimized for office manager: call-monitor + intake + escalation-history. Mobile-friendly grid.
- **"Attorney Review"** — optimized for partner review: refusal-log + transcripts + escalation-history. Desktop-friendly grid.

Both follow parent §7.6 workspace-preset conventions.

### §7.3 Permission Model

receptionBOX inherits parent §7.8 permission tiers. Two new permissions are added:

- `receptionbox.transcript_read` — gates access to call transcripts. Default: granted to attorney roles; not granted to general staff.
- `receptionbox.audio_read` — gates access to call audio recordings. Default: granted to managing partner only; explicit per-call grant for others.

---

## §8. Security & Data Architecture

### §8.1 Encryption

Inherits parent §8.1 with:

- All call audio at rest: AES-256-GCM
- All transcripts at rest: AES-256-GCM
- Encryption keys stored in TPM 2.0
- Outbound SIP/TLS to carrier: TLS 1.3, certificate-pinned to firm-approved carrier

### §8.2 Data Flow Boundaries

| Flow | Off-appliance? | Notes |
|------|---------------|-------|
| Caller audio (carrier → appliance) | Carrier transports; appliance terminates | DR-22 caveat: transport handled by carrier, content stays on appliance |
| Caller audio (appliance → carrier) | Carrier transports outbound | Same caveat |
| Transcripts | Stored on appliance only | NFR-R4 |
| Intake records | Stored on appliance only; conflict-check fields may be pushed to firm's case management system per FR-R30 (firm-controlled) | Customer-authorized only |
| LLM inference | On-appliance (Qwen3-4B). Cloud fallback OFF by default per FR-R49 | Customer-controlled |
| TTS generation | On-appliance | NFR-R4 |
| Telemetry to UMB Group | None unless customer opts in to support telemetry. Telemetry, when on, **never** includes call content | Default OFF |

### §8.3 Security Threat Model

Inherits parent §8.3 threat model. receptionBOX-specific additions:

| Threat | Likelihood | Impact | Mitigation |
|--------|-----------|--------|-----------|
| Caller exploits prompt injection to exfiltrate intake data | Medium | High | guardrail-filter (FR-R41), grammar-constrained intake (FR-R31), no tool-call paths exposed to caller utterances |
| SIP trunk credential theft | Low | High | Credentials stored in appliance secure storage, rotated per onboarding, scoped to single DID |
| Audio recording leak via misconfigured backup | Low | Critical (privilege waiver) | Audio is excluded from off-site backup by default; explicit opt-in required; backup encryption at the same standard as appliance encryption |
| Privilege exposure via UMB Group support session | Low | Critical | Support sessions never expose call content; session telemetry is content-free; per-incident authorization required for any content access (NFR-R5) |
| Replay attack on captured audio | Very low | Medium | Audio at rest is encrypted; no API surface exposes raw audio externally |
| UPL guardrail escape | Medium (during tuning) | High (regulatory) | Nightly probe suite (FR-R40), rollback automation, refusal-log monitoring (FR-R39) |

### §8.4 Backup, Disaster Recovery, and Hardware RMA

Inherits parent §8.4 with the following receptionBOX-specific provisions:

- **Audio backup:** Off by default. Customer-controlled per-firm setting. When enabled, backups are encrypted with customer-supplied key and shipped to customer-designated S3-compatible target. UMB Group never holds the key.
- **Transcript backup:** Same posture as audio.
- **Hardware RMA:** Before any RMA shipment, the appliance's encrypted volumes are wiped via cryptographic erase (TPM key destruction). The replacement appliance is shipped pre-staged from the customer's most recent backup (if backups are enabled) or as a fresh appliance with onboarding wizard (if not). The wiped unit is re-imaged before any other use.
- **Privilege incident response (FR-R36):** Documented runbook with 4-hour notification SLA on any suspected exposure event.

---

## §9. External Dependencies

receptionBOX inherits the parent platform's external dependency matrix (§9) with the following additions:

| Dependency | Type | Purpose | Failure mode |
|-----------|------|---------|--------------|
| SIP carrier (Twilio / Telnyx / customer BYO) | Cloud service | Inbound and outbound call transport | Inbound calls fail to reach appliance. Mitigation: redundant carrier configuration optional in Phase 2. |
| Resemble AI (Chatterbox-Turbo) | Open-source model weights | TTS primary | Engine swap to Kokoro fallback (FR-R20) |
| Hugging Face / Hexgrad (Kokoro) | Open-source model weights | TTS fallback | Pre-bundled with appliance image; offline-capable |
| LiveKit (Apache 2.0) | Open-source voice infrastructure | SFU + SIP bridge | Pinned version in appliance image; no live update dependency |
| ROCm | AMD GPU runtime | Inference substrate | Pinned version; ROCm 6.x branch tracked |
| Anthropic API (Claude Haiku) | Cloud service | Optional cloud-fallback per FR-R49 | Falls back to local-only mode; cloud-fallback toggle is opt-in anyway |

---

## §10. Technical Success Metrics

| ID | Metric | Target | Measured at |
|----|--------|--------|-------------|
| SM-66 | End-to-end latency (p90) | < 900ms | G1 benchmark (Phase 0 cloud, Phase 1 hardware) |
| SM-67 | End-to-end latency (p99) | < 1200ms | G1 benchmark |
| SM-68 | STT word error rate on G.711 | < 12% neutral, < 18% stressed | G2 benchmark |
| SM-69 | Turn-detection false-positive rate | < 2% on hesitation-heavy speech | G3 benchmark |
| SM-70 | Concurrency at G1 latency | 4 (stretch 6) | G4 benchmark |
| SM-71 | UPL guardrail probe pass rate | 100% (zero escapes) on 200-probe suite | G5 benchmark + nightly regression |
| SM-72 | TTS naturalness preference (cloned voice vs. Kokoro) | ≥ 60% prefer cloned in blind A/B with well-recorded reference | G7 benchmark |
| SM-73 | Voice service uptime (rolling 30-day) | ≥ 99.5% | Production telemetry post-pilot |
| SM-74 | Recording-disclosure compliance | 100% of recorded calls play disclosure preamble | Audit log |
| SM-75 | Privilege incident count | 0 | Incident log (FR-R36) |
| SM-76 | Daily digest delivery success rate | ≥ 99% | Side-effect telemetry |
| SM-77 | Escalation transparency | 100% of escalations precede with caller notification | Audit log |
| SM-78 | Cold-start LLM latency on appliance boot | < 60s before first call accepted | Boot telemetry |
| SM-79 | Pluggable TTS swap operation time | < 5 minutes from dashboard config change to next-call live | Change log telemetry |

---

## §11. Technical Risk Register

| Risk | Probability | Impact | Mitigation | Kill condition? |
|------|------------|--------|-----------|-----------------|
| Latency p90 stays > 1200ms after optimization on Strix Halo | Medium | Critical | Phase 0 cloud benchmark on MI300X with derating; hardware fail-up to T4/T5 if needed; product redesign as "asynchronous voice" if sub-1200ms is unachievable | Yes — kills v1 if T5 also fails |
| Chatterbox-Turbo ROCm path is non-functional | Medium-High | High | Pluggable TTS architecture allows swap to Kokoro (no clone) or VoxCPM2 (alternative clone) without code change | No — graceful degradation path exists |
| STT WER on G.711 phone audio exceeds 18% on stressed speech | Medium | High | Audio-enhancement preprocessing pass (RNNoise, DeepFilterNet); fine-tuning Whisper on phone-quality corpus | No — can be tuned |
| Turn detector false-positives during stressed speech | Medium | High (UX-killing) | Conservative threshold (800ms silence default); barge-in handling on resumption; configurable per-firm tuning | No — tunable |
| Prompt injection escapes UPL guardrails | Medium | Critical (regulatory) | guardrail-filter (FR-R41), grammar-constrained intake, nightly probe suite, automated rollback | Soft kill — must be solved before any go-live |
| TTS clone produces uncanny-valley output | Medium | Medium | Pluggable TTS, A/B preference test, fall back to Kokoro neutral | No — graceful degradation |
| SIP integration with firm's existing PBX is non-trivial | High | Medium | Discovery engagement includes firm IT team; v1 may require firm to procure a fresh DID rather than integrate with existing PBX | No — workaround exists |
| Strix Halo ROCm driver instability under sustained load | Medium-Low | High | 30-day soak test required before production; rollback to Phase 0 NVIDIA path possible if needed | No — tier-up to T5 NVIDIA path |
| State bar issues new AI-disclosure rule mid-deployment | Low | Medium | Disclosure preamble is configurable; firm counsel notified of regulatory changes via discovery deliverable | No — adjust configuration |
| Carrier SIP outage takes down inbound | Low | High | Redundant carrier in Phase 2; v1 documented as "single carrier dependency" in customer agreement | No — known limitation |

---

## §12. Decision Records (receptionBOX-specific)

The following decision records continue from the platform's DR-1 through DR-19 and the receptionBOX discovery-phase DR-20 through DR-24 already established in companion documents.

### DR-20 (inherited from discovery addendum v0.2)
*receptionBOX is a paid discovery engagement, not a roadmap pack until kill criteria pass.* See addendum-receptionbox-discovery-v0_2-2026-04-22.md §9.

### DR-21 (SUPERSEDED by DR-24)
*T3 Mac mini M4 is the minimum viable platform for voice.* Superseded April 23, 2026 by DR-24.

### DR-22 (inherited from discovery addendum v0.2)
*Telephony transport is a caveated exception to the data sovereignty pillar (DR-19).* See addendum-receptionbox-discovery-v0_2-2026-04-22.md §9.

### DR-23 (inherited from discovery addendum v0.2)
*Position receptionBOX against Smith.ai specifically, not Ruby/Posh.* See addendum-receptionbox-discovery-v0_2-2026-04-22.md §13.

### DR-24 (inherited from hardware-pivot addendum v0.1)
*T3 platform is Framework Desktop on AMD Ryzen AI Max+ 395 "Strix Halo" 128GB. Supersedes DR-21.* See addendum-hardware-pivot-strix-halo-v0_1-2026-04-23.md.

### DR-25: receptionBOX is single-pack on appliance in v1
**Context:** The voice latency budget consumes most of the available concurrent compute on T3 Strix Halo. Multi-pack co-residency would force latency degradation or memory pressure that compromises voice service quality.

**Decision:** v1 receptionBOX deployments run as the only active pack on the appliance. Multi-pack co-residency (e.g., MailBOX + receptionBOX on the same box for a small firm) is deferred to v2 on T4/T5 hardware.

**Consequences:**
- A small firm wanting both MailBOX and receptionBOX in v1 needs two appliances.
- Bundling pricing must reflect this — multi-pack discount, but no single-box bundle.
- v2 roadmap includes multi-pack orchestration on T4/T5.

**Status:** Accepted.

### DR-26: receptionBOX positioning is overflow + after-hours, not primary line
**Context:** Single-appliance concurrency on T3 is bounded at ~4–6 concurrent calls. A large firm's peak intake load can exceed this. Positioning the product as a primary-line replacement creates a capacity ceiling that can fail customers.

**Decision:** receptionBOX is positioned and sold as **overflow coverage and after-hours handling**, not as a primary-line replacement. The firm's existing receptionist (if any) remains the primary line during business hours. The appliance handles overflow during peak periods and full coverage after hours.

**Consequences:**
- Sales conversations explicitly position the product this way.
- Onboarding configures the appliance to ring through to firm staff first during business hours, with the appliance picking up only after configurable ring count or when firm staff is busy.
- Marketing materials avoid "AI replaces your receptionist" framing.
- The legal-vertical pitch (DR-23) gains additional credibility — overflow positioning aligns with privilege retention (firm's human handles primary, AI handles spillover).

**Status:** Accepted.

### DR-27: TTS engine is pluggable from v1
**Context:** The TTS landscape is moving fast (Chatterbox-Turbo, VoxCPM2, Fish Audio S2 Pro, Voxtral, Qwen3-TTS all shipped within an 8-month window in 2025–2026). Hard-coding a specific engine into the voice runtime creates a refactor every time a better engine ships.

**Decision:** receptionBOX defines a `TTSEngine` abstraction. Engine selection is a Postgres config row. Engine swap is a dashboard operation, not a code change. v1 ships with Chatterbox-Turbo (primary) and Kokoro-82M (fallback). Future engines are added via the same interface.

**Consequences:**
- Slightly more code at v1 (the abstraction layer).
- Onboarding and persona-tuning workflows reference the engine abstraction, not engine-specific concepts.
- License-tracking matrix in the engine catalog is part of the dashboard plugin (§7.1).
- Future cloud-TTS option (for premium voice quality at the cost of breaking strict on-prem on outbound audio only) becomes a plugin choice, not a re-architecture.

**Status:** Accepted.

### DR-28: Phase 0 cloud benchmark is required before any discovery SOW signature
**Context:** The latency budget is the load-bearing technical risk. Discovering on Strix Halo hardware that the budget is unmet during Week 3 of a discovery engagement (after the SOW is signed, after the firm has paid) damages the relationship and exposes UMB Group to refund obligations.

**Decision:** Before signing any discovery SOW with the law firm or any future receptionBOX customer, a Phase 0 cloud benchmark on MI300X must complete and produce predicted Strix Halo latency within budget. If Phase 0 fails, the discovery engagement is not offered or is offered with a disclosed feasibility risk.

**Consequences:**
- ~$150 of cloud spend and ~30–40 hours of engineering before any sales commitment.
- Phase 0 results are referenced in the SOW as preliminary feasibility evidence.
- Phase 0 becomes a standard pre-sales practice for receptionBOX in any future deployments.

**Status:** Accepted.

### DR-29: Voice runtime agent-worker may run native (non-Docker)
**Context:** Docker on Linux generally has minimal audio-stack overhead, but the LiveKit Agents framework has documented latency advantages when run natively on the host. Voice latency budget is tight enough that this matters.

**Decision:** The `agent-worker` service may run native under systemd (not Docker), at engineering discretion based on benchmark data. Other services (`livekit-sfu`, `whisper-stt`, `tts-engine`, all parent platform services) remain in Docker. This is a per-service decision documented in §4.2.

**Consequences:**
- One service has a different deployment path. systemd unit file is part of the appliance image.
- Update orchestration (parent §5.6) handles native and Docker paths uniformly via systemd.
- The exception is documented and reviewed per release.

**Status:** Accepted.

### DR-30: receptionBOX v1 excludes outbound calling
**Context:** Outbound calling introduces TCPA (Telephone Consumer Protection Act) and state-level restrictions on automated calls. The regulatory surface is substantially larger than inbound-only. Customer value of inbound-only is ~80% of full-bidirectional value.

**Decision:** v1 receptionBOX is inbound-only. Outbound calling (callbacks, follow-ups, reminders) is deferred to v2 with separate regulatory review.

**Consequences:**
- Daily-digest outbound notifications use SMS/email (n8n side-effects), not voice.
- Callback workflows depend on firm staff using a separate dialing path.
- v2 roadmap includes a TCPA-compliant outbound module with explicit consent capture.

**Status:** Accepted.

---

## §13. NEEDS_CLARIFICATION (Open Questions)

Open questions inherited from discovery addendum v0.2 (NC-R1 through NC-R10) plus new questions surfaced by this PRD:

| ID | Question | Affects | Owner |
|----|----------|---------|-------|
| NC-R1 | Firm size: how many attorneys, how many incoming lines, how many concurrent peak calls? | KC-4, hardware tier selection, pricing | Dustin |
| NC-R2 | Does the firm have an existing PBX or does receptionBOX become primary phone system? | Architecture, integration scope | Dustin |
| NC-R3 | Practice areas of the firm? | KC-2, system prompts, guardrails | Dustin |
| NC-R4 | Does the firm record calls today, and under what consent regime? | KC-2, FR-R32, default audio retention | Dustin |
| NC-R5 | What is the firm's willingness to pay for discovery (KC-3)? | Go/no-go trigger | Dustin |
| NC-R6 | Which outside counsel does UMB Group retain for KC-2? | KC-2 execution | Dustin + board |
| NC-R7 | Voice synthesis: ElevenLabs cloud vs. local Chatterbox? Resolved by DR-27 (pluggable, default local). | DR-27 | Resolved |
| NC-R8 | Does the firm accept "overflow coverage" positioning? Resolved by DR-26 (yes, this is the only positioning offered). | DR-26 | Resolved |
| NC-R9 | Pricing target: premium pack or SMB pricing? | Commercial model | Dustin (companion business PRD) |
| NC-R10 | IT/procurement process — vendor security review requirements? | §4, sales cycle length | Dustin |
| NC-R11 (new) | Single-tenant SIP trunk per appliance vs. shared multi-tenant trunk operated by UMB Group | FR-R1, COGS, customer onboarding | Engineering + Dustin |
| NC-R12 (new) | Recording disclosure preamble: hardcoded UMB Group default or firm-counsel-authored per deployment? | FR-R35, customer agreement | Firm counsel + UMB Group counsel |
| NC-R13 (new) | Off-site backup target: customer-specified S3 only, or do we offer a UMB Group–managed encrypted backup as an option? | NFR-R4, §8.4 | Engineering + Dustin |
| NC-R14 (new) | Phase 0 cloud benchmark — share results with the firm during discovery sales conversation, or hold for the discovery SOW deliverable? | Sales posture | Eric (per virtual benchmark plan §6) |
| NC-R15 (new) | TTS clone retention — does the firm own the cloned voice model, or does UMB Group retain operational copy for support? | DR-27, §7.1 plugin spec, customer agreement | UMB Group counsel |
| NC-R16 (new) | Multi-DID support — defer to v2 or include in v1 if firm has multiple inbound numbers? | FR-R2, hardware concurrency budget | Discovery phase |

---

## §14. Phase Plan — Technical Deliverables

### Phase 0: Cloud Benchmark (this week, ~$150 spend, ~30–40 hours)

Per virtual benchmark plan v0.1.

| Deliverable | Status |
|-------------|--------|
| RunPod H100 CUDA pre-flight (pipeline assembles end-to-end) | Pending |
| Vultr/TensorWave MI300X ROCm validation (Chatterbox-Turbo runs) | Pending |
| G1 latency on MI300X (500-call corpus) | Pending |
| G2 STT WER on G.711 (200 clips) | Pending |
| G3 turn detection (hesitation-heavy adversarial set) | Pending |
| G5 UPL guardrail probes (200 probes) | Pending |
| G7 TTS A/B preference (30-pair blind, 5 listeners) | Pending |
| Synthesis report with derated Strix Halo predictions | Pending |
| Update of feasibility memo to v0.4 with measured numbers | Pending |

**Phase 0 gate:** All gates pass with derated Strix Halo predictions within budget. Failure → discovery SOW is not signed.

### Phase 1: Discovery Engagement (6 weeks, paid by firm)

Per discovery addendum v0.2 §5. Phase 1 starts only after Phase 0 passes and the firm signs the SOW.

| Week | Deliverable |
|------|-------------|
| 1 | Requirements audit, 90-day call volume pull, existing PBX documentation |
| 2 | Outside counsel ethics opinion (UPL + privilege) |
| 3–4 | Hardware benchmark on actual Framework Desktop (G1 through G7) |
| 5 | Feasibility synthesis, proposed pilot architecture, pricing model |
| 6 | Joint review with firm leadership and UMB Group board |

**Phase 1 gate:** All five kill criteria (KC-1 through KC-5 in discovery addendum) pass. Failure → graceful exit, firm retains all deliverables.

### Phase 2: Founding Partner Pilot (8–12 weeks, contracted with firm)

If Phase 1 passes and firm proceeds:

| Workstream | Duration | Deliverable |
|-----------|----------|-------------|
| Appliance assembly and pre-staging | 1 week | Framework Desktop assembled per §3.3 |
| SIP trunk provisioning and PBX integration | 1–2 weeks | Live test calls on firm's number |
| Onboarding wizard execution (FR-R52) | 1 week | Persona, jurisdiction, escalation, voice clone configured |
| Shadow mode (FR-R54) | 1 week | 7 days of parallel operation, no live caller exposure |
| Limited go-live (after-hours only) | 2 weeks | Appliance handles after-hours calls, daytime stays human |
| Full go-live (overflow + after-hours) | Ongoing | Production operation with weekly review cadence |
| 30-day production stability soak | 4 weeks | NFR-R3 uptime validation, SM-73 measurement |

### Phase 3: Productization for Subsequent Customers

Out of scope for this PRD revision. Captured in companion business PRD.

---

## §15. Cross-References and Inheritance Map

> **See also §0** for the conceptual framing of how this pack PRD relates to the parent platform. This section provides the detailed inheritance table — which specific parent sections are inherited in which mode (§0.3).

### §15.1 Inherited from parent thUMBox technical PRD v2.1

| Parent section | Behavior |
|----------------|----------|
| §1.6 Customer Dashboard (FR-25 through FR-41) | Inherited; receptionBOX adds plugins per §7.1 |
| §2 Non-Functional Requirements | Inherited; receptionBOX adds NFR-R1 through NFR-R11 voice-specific |
| §4.1 Runtime Environment | Inherited with deltas in §4.1 |
| §4.2 Service Topology | Extended in §4.2 |
| §5.1 RAG Pipeline | Reused with receptionBOX corpora per §5.1 |
| §5.2 Relationship Graph | Extended with voice node types per §5.2 |
| §5.3 Model Selection | Inherited; receptionBOX adds STT and TTS per §5.3 |
| §5.4 Persona System | Extended with voice persona elements per §5.4 |
| §5.6 Update Mechanism | Inherited with drain-before-restart constraint per §5.6 |
| §6 Personality Pack Architecture | receptionBOX is one such pack, conforms to §6.1 contract |
| §7 Optimus Brain Dashboard | Reused unchanged; plugins added per §7.1 |
| §8 Security & Data Architecture | Inherited; threat-model additions per §8.3 |
| §9 External Dependencies | Extended with voice-specific dependencies per §9 |
| §15 OpenClaw/NemoClaw Integration | Not used in v1 receptionBOX; possible v2 integration |

### §15.2 Companion documents

| Document | Relationship |
|----------|-------------|
| `addendum-receptionbox-discovery-v0_2-2026-04-22.md` | Discovery gate, kill criteria, regulatory posture. **Authoritative on commercial gating and legal review.** |
| `addendum-hardware-pivot-strix-halo-v0_1-2026-04-23.md` | DR-24 (platform pivot) authority. |
| `receptionbox-technical-feasibility-memo-v0_3-2026-04-23.md` | Eric-facing feasibility brief. **Subordinate to this PRD; preserved as historical artifact.** |
| `receptionbox-virtual-benchmark-plan-v0_1-2026-05-03.md` | Phase 0 execution plan. **Authoritative on Phase 0 procedures.** |
| `receptionbox-firm-partnership-pitch-v0_2-2026-04-22.md` | Sales-facing pitch. **Subordinate to this PRD; sales artifact.** |
| `law-firm-pitch-deck-v0_1-2026-04-22.jsx` | Interactive pitch deck. **Subordinate to this PRD; sales artifact.** |

### §15.3 Authority Hierarchy

See §0.5. The hierarchy defined there is canonical and applies wherever this PRD's content conflicts with another document.

---

## §16. Glossary (receptionBOX-specific terms)

| Term | Definition |
|------|-----------|
| Filler-word masking | Latency-hiding technique where the assistant prepends a brief verbal acknowledgment ("Mm-hm," "So,") to its response, allowing TTS to start streaming while the main LLM response continues generating. |
| Grammar-constrained generation | LLM decoding mode where output is constrained to a specific grammar (e.g., only valid phone numbers, only valid dates), reducing generation time and eliminating hallucinated structure. |
| Overflow coverage | The DR-26 positioning of receptionBOX as a secondary line that handles spillover and after-hours, with the firm's existing staff remaining the primary contact during business hours. |
| Privilege-aware redaction | Database-query layer that filters caller matter descriptions from any plugin or report not explicitly authorized to see them. |
| Shadow mode | Onboarding period (FR-R54) during which the appliance answers calls in parallel with the human receptionist; the human handles every call live, the assistant generates what it would have said, and the firm reviews these for trust-building before going live. |
| SIP REFER | The SIP protocol mechanism for transferring an active call from the assistant's voice runtime to a human destination (firm staff, attorney cell). |
| Strix Halo | AMD Ryzen AI Max+ 395 platform, the v1 hardware substrate (DR-24). |
| Turn detection | The audio-pipeline component that decides when the caller has finished a turn and the assistant should respond. Distinguishable from voice-activity detection (VAD) by use of semantic/prosody features beyond raw silence. |
| UPL | Unauthorized Practice of Law. The category of utterances the assistant must refuse to make (substantive legal advice, fee quotes, statute-of-limitations advice, case-outcome predictions). |

---

**END OF receptionBOX TECHNICAL PRD v0.2**
