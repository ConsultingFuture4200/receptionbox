# thUMBox — Business Plan PRD

## v2.1

> **Created:** 2026-04-04
> **Last updated:** 2026-04-16
> **Author:** Dustin (UMB Group)
> **Status:** Draft
> **Product type:** Hardware + software appliance platform, sold as managed product with subscription
> **Companion document:** `thumbox-technical-prd.md` — full software architecture, hardware specifications, task decomposition, and implementation details
> **Changelog:**
> - v2.1 — Consolidation merge of `addendum-openclaw-integration.md`, `addendum-optimus-brain-plugin-dashboard-v0_1-2026-04-05.md`, and `addendum-v21-consolidation-v0_1-2026-04-16.md`. Hardware tier table gained NemoClaw compatibility column (§5). Subscription tiers gained OpenClaw rows (§6.3). Access tier matrix replaced with plugin-based matrix (§7.2). OpenClaw onboarding subsection added (§8.5). Graduated autonomy thresholds formalized with rollback triggers (§8.3). Top 10 failure modes enumerated (§11 Phase 3). SM numbering legend added (§12). Regulatory posture added (§12.5). Pack SDK scope added (§10.6). SocialBOX messaging clarification (§9.3).
> - v2.0 — Unified merge of PRD v1.2, addendum-model-optimization, addendum-learning-loop, addendum-platform-expansion, and task-decomposition-learning-loop. Rebranded from MailBox One / Glue Co / Glue Box to thUMBox / UMB Group. Target customer broadened from CPG-only to SMB + solo entrepreneur. Business and technical concerns split into companion documents.

---

## §1. Product Identity

**thUMBox** is an edge AI appliance platform sold as hardware + subscription. Each appliance runs a shared platform stack (local LLM inference, vector search, workflow automation, encrypted storage, local dashboard) and loads one or more **personality packs** — modular agent configurations that transform the box into a domain-specific AI assistant.

**MailBox One** is the first personality pack. It handles inbound email triage, drafting, and response for operational business communications. The customer plugs in a box, connects their email, completes a guided onboarding session, and gets an always-on assistant that triages, drafts, and (with approval) sends email responses on their behalf.

The platform is **not** a general-purpose AI chatbot, a cloud SaaS product, or a developer framework. It is a managed, opinionated hardware+software product with **graduated autonomy** as its core constraint across all packs: the system proposes, the human approves. No automated action occurs without explicit human opt-in, and that opt-in is earned through demonstrated accuracy over time.

### Platform vs. Pack

| Layer | What it is | Examples |
|-------|-----------|----------|
| **thUMBox Platform** | Shared infrastructure that runs on every appliance | Local AI inference engine, vector database, workflow orchestrator, encrypted storage, dashboard shell, graduated autonomy engine |
| **Personality Pack** | A modular agent configuration for a specific domain | MailBox One (email), Research Agent, Social Agent, Calendar Agent, Sales Ops Agent |

A single appliance runs one or more packs depending on hardware tier. Packs share platform infrastructure but maintain isolated workflows, credentials, and learned intelligence.

### Phase Activation

- **Phase 1:** Ship MailBox One as a standalone product on initial hardware. Platform branding is introduced but only one pack exists.
- **Phase 2:** Platform architecture formalized. Personality pack module system built. Second pack enters development.
- **Phase 3:** Multi-pack support on mid-tier and higher hardware. Full subscription tiers activated.

---

## §2. Target Customer

### Primary: Small-to-Medium Business Owners (1–25 person teams)

Business operators who are drowning in operational communications — email, social, scheduling — and lack the staff or systems to manage it efficiently. They are technically capable enough to use a web browser but not to configure Docker, API keys, or agent frameworks.

**Common characteristics:**

- Receive 20–200+ operational emails/day from clients, partners, vendors, and service providers
- Spend 1–4 hours/day on email triage, drafting, and follow-up
- Wear multiple hats — operations, sales, finance — and email is the connective tissue between all of them
- Lack staff or budget to delegate communications management
- Value privacy and data ownership — uncomfortable sending all business communications through cloud AI
- May run their business from a phone and need mobile-friendly tools

### Secondary: Solo Entrepreneurs and Freelancers

Individuals running one-person operations where every dropped email is a dropped opportunity. Often managing multiple client relationships, juggling proposals, invoices, scheduling, and follow-up from a single inbox.

### Vertical Examples (Non-Exhaustive)

| Vertical | Email Pain | Pack Relevance |
|----------|-----------|----------------|
| **CPG / Food & Beverage brands** | Retailer inquiries, broker follow-ups, reorder confirmations, distributor coordination | MailBox One (primary launch vertical) |
| **Professional services** (consultants, agencies, accountants) | Client onboarding, proposal follow-up, scheduling, scope management | MailBox One + Calendar Agent |
| **E-commerce operators** | Supplier negotiations, wholesale inquiries, logistics coordination | MailBox One + Sales Ops Agent |
| **Real estate professionals** | Buyer/seller inquiries, showing coordination, transaction follow-up | MailBox One + Calendar Agent |
| **Skilled trades / contractors** | Estimate requests, scheduling, vendor coordination, permit follow-up | MailBox One + Calendar Agent |
| **Creative professionals** (photographers, designers, writers) | Client inquiries, project coordination, invoice follow-up | MailBox One |

### Excluded from v1

- Enterprise organizations (50+ person teams) with existing CRM/helpdesk software (Zendesk, Front, Help Scout)
- Businesses whose email volume is primarily consumer support (returns, complaints, order status)
- Organizations requiring compliance-grade audit trails (addressed in Enterprise tier, Phase 3)

---

## §3. Jobs to Be Done

| # | Job | Current Solution | Pain |
|---|-----|-----------------|------|
| J-1 | Respond to client/partner inquiries (pricing, availability, lead times, capabilities) | Owner manually drafts each reply | 30–90 min/day; slow response loses deals |
| J-2 | Follow up with prospects, partners, and sales contacts | Owner remembers (or forgets) | Dropped follow-ups = lost revenue |
| J-3 | Confirm repeat orders and standard requests | Manual copy-paste of templates | Tedious, error-prone, delays fulfillment |
| J-4 | Coordinate scheduling (meetings, site visits, calls, deliveries) | Back-and-forth email chains | 5–10 emails per scheduling event |
| J-5 | Triage and prioritize inbound email | Read everything, mentally sort | Urgent items buried under noise |
| J-6 | Maintain consistent professional communication voice | Owner is the only one who "sounds right" | Can't delegate; bottleneck on the owner |
| J-7 | Keep context across long client relationships | Relies on memory and scrolling through old threads | Missing context = unprofessional responses |

---

## §4. Core Product Principles

### 4.1 Graduated Autonomy

This is the product's defining constraint and its primary differentiator. Every autonomous capability follows the same lifecycle:

1. **Observe:** The system watches and learns from the customer's behavior (email patterns, editing preferences, communication style).
2. **Propose:** The system proposes an action (draft email, classification rule, learned skill) and surfaces it for review.
3. **Approve:** The customer reviews and approves, edits, or rejects the proposal.
4. **Trust:** After demonstrated accuracy over a trust-building period, the customer can optionally enable auto-execution for specific categories.
5. **Monitor:** Even auto-executed actions are logged, auditable, and revocable.

This principle governs the auto-send system, the learned skills pipeline, persona tuning, and every future pack's autonomous capabilities. No automated change occurs without human review at the appropriate gate.

### 4.2 Local-First Privacy

All customer data — email content, knowledge base, learned intelligence, relationship graph — is stored on the local appliance and encrypted at rest. Cloud API calls send only the minimum context needed for a single draft generation and never bulk-transmit the customer's corpus. The customer's intelligence stays on their desk.

### 4.3 The Box Gets Smarter Over Time

Unlike static software, thUMBox learns from the customer's behavior. Every draft edit teaches the system a new drafting rule. Every email processed enriches the relationship graph. Every approval or rejection refines classification accuracy. The appliance on day 90 is meaningfully better than the appliance on day 1 — and that improvement is specific to each customer's business.

### 4.4 Hardware is the Razor, Packs are the Blades

Hardware is sold at modest margin. Recurring subscription revenue — unlocking OTA updates, personality packs, dashboard features, and support — is the primary business model. The open-source release strategy (§10) creates community goodwill and a funnel from free to paid.

---

## §5. Hardware Tiers

Six hardware tiers spanning pocket devices to enterprise servers. Each tier maps to a customer segment and capability ceiling.

| Tier | Name | Est. COGS | Target Use | Max Packs | Max Model Size | NemoClaw Support |
|------|------|-----------|------------|-----------|----------------|------------------|
| T0 | Pocket | $75–120 | Single lightweight pack, notification-only, personal use | 1 | 1–2B | Not supported |
| T1 | Lite | $180–250 | Single pack, standard tasks (email triage, social monitoring) | 1 | 3–4B | Constrained (single bridge, sequential inference) |
| T2 | Standard | $320–400 | Single pack with full capability, GPU-accelerated inference | 1–2 | 4–8B | Blocked pending NC-2-OPENSHELL |
| T3 | Pro | $550–700 | Multi-pack, complex reasoning, research workloads | 2–4 | 8–14B | Fully supported |
| T4 | Heavy | $1,200–2,000 | Multi-pack with large models, multi-agent, small team | 4–8 | 14–30B | Fully supported |
| T5 | Enterprise | $4,000–10,000+ | Fleet deployment, full multi-agent, departmental/org use | Unlimited | 30–70B+ | Fully supported (fleet-wide policy) |

> Full hardware specifications (BOM, assembly, platform-specific model stacks) are in the Technical PRD §6.

### Hardware Selection Guidance

| Customer Profile | Recommended Tier | Rationale |
|------------------|-----------------|-----------|
| Solo entrepreneur, 1 email account, < 50 emails/day | T1 Lite | Cost-effective, sufficient for single-pack email |
| Solo operator wanting email + social | T2 Standard or T3 Pro | GPU acceleration for concurrent packs |
| Small business, 2–3 team members | T3 Pro | Multi-pack, handles complex reasoning |
| Agency managing multiple brands/clients | T4 Heavy | Multi-agent orchestration, larger models |
| Mid-size company, 10+ users | T5 Enterprise | Fleet deployment, compliance, custom models |
| Personal/hobbyist, notifications only | T0 Pocket | Minimal cost, notification forwarding |

### Phase Activation

- **Phase 1:** Ship T2 (Standard) as primary. T1 (Lite) and T3 (Pro) validated in parallel.
- **Phase 2:** T1 and T3 available as SKUs. T0 as beta/community edition.
- **Phase 3:** T4 and T5 available. Fleet management features for T5.

---

## §6. Pricing Model

### §6.1 Pricing Philosophy

**Hardware is the razor, personality packs are the blades.**

The hardware is sold at modest margin (targeting 40–50% gross). Recurring subscription revenue is the primary business model. The subscription unlocks OTA updates, personality packs, the Optimus Brain dashboard, and support services. The open-source release strategy (§10) creates community goodwill and a funnel from free to paid.

Inspiration models: Tesla FSD (hardware near-cost, software subscription is the business), JetBrains Toolbox (tiered subscriptions with credit-based consumption), GoPro (hardware + subscription diversification), MariaDB BSL (time-delayed open-source builds trust).

### §6.2 Hardware Pricing

| Tier | Hardware Price | Included | Margin Target |
|------|--------------|----------|---------------|
| T0 Pocket | $149–199 | Hardware + platform OS + 1 pack (community) + 30-day trial of Base sub | 40% |
| T1 Lite | $399–499 | Hardware + platform OS + 1 pack + 60-day Base sub included | 45% |
| T2 Standard | $599–749 | Hardware + platform OS + 1 pack + 60-day Plus sub included | 45% |
| T3 Pro | $899–1,099 | Hardware + platform OS + 2 packs + 90-day Plus sub included | 50% |
| T4 Heavy | $1,999–2,999 | Hardware + platform OS + all packs + 90-day Pro sub included | 50% |
| T5 Enterprise | $5,999–12,999+ | Custom config. All packs + 6-month Pro sub + onboarding | 55%+ |

All tiers include free OTA security updates regardless of subscription status. Feature updates and new pack releases require an active subscription.

### §6.3 Subscription Tiers

| Tier | Monthly | Annual (20% discount) | Key Features |
|------|---------|----------------------|--------------|
| **Community** (free) | $0 | $0 | Platform OS, 1 pack (open-source version), community forum, security updates only, delayed feature updates (~30 days after Pro), basic dashboard (read-only status) |
| **Base** | $19/mo | $182/yr | 1 pack (full version), OTA feature updates (delayed 2–4 weeks), dashboard with monitoring + basic analytics, email support (48hr), 100 cloud API credits/mo |
| **Plus** | $39/mo | $374/yr | 2 packs, OTA updates (delayed 1 week), full analytics + cross-pack insights, email support (24hr), 300 cloud API credits/mo, idle-time intelligence features, OpenClaw runtime (1 messaging bridge, T3+ hardware), 3 core thUMBox OpenClaw skills |
| **Pro** | $69/mo | $662/yr | All packs (current + future), daily OTA updates (first access), full dashboard with orchestration controls, 1-on-1 onboarding call, dedicated support (12hr), 800 cloud API credits/mo, fine-tuning pipeline access, multi-agent orchestration, early access to beta packs, OpenClaw runtime (all bridges), all thUMBox OpenClaw skills, full bidirectional Skill Bridge, UMB Group managed backup |
| **Enterprise** | Custom | Custom | Everything in Pro + fleet management, SSO/SAML, compliance audit trails, custom model training, SLA guarantees, dedicated account manager, on-site setup available, unlimited cloud API credits, custom pack development consultation, fleet-wide OpenClaw policy management |

#### OpenClaw Feature Gating

| Feature | Community | Base | Plus | Pro | Enterprise |
|---------|-----------|------|------|-----|------------|
| OpenClaw agent runtime | — | — | ✓ (1 messaging bridge, T3+ only) | ✓ (all bridges) | ✓ (fleet) |
| thUMBox OpenClaw skills (§15.6 Technical PRD) | — | — | 3 core skills | All skills | All skills + custom |
| Skill Bridge (pack ↔ OpenClaw) | — | — | Notifications only (pack → OpenClaw) | Full bidirectional | Full bidirectional |
| NemoClaw policy customization | — | — | Presets only | Full YAML policy editing | Fleet-wide policy management |
| ClawHub community skills | — | — | Blocked by default | Operator-approved | Policy-managed |

**Rationale:** OpenClaw is gated at Plus+ because it requires meaningfully more hardware resources (T3+) and a larger support surface. Base-tier customers on T1/T2 hardware with tight resource budgets get the most value from the focused personality pack experience.

### §6.4 Personality Pack Pricing (À la Carte)

| Item | Price | Notes |
|------|-------|-------|
| Additional pack (beyond tier allowance) | $15/mo per pack | Stacks with subscription |
| Pack bundle (all current packs) | $29/mo | Cheaper than 3+ individual packs. Included free in Pro tier. |

### §6.5 Add-On Services

| Service | Price | Availability |
|---------|-------|-------------|
| White-glove setup / personal configuration | $199 one-time | Required for Community/Base. Included in Plus (basic), Pro (full), Enterprise (full + on-site) |
| Persona tuning session (1-on-1, 30 min) | $49/session | All tiers. 1 free/quarter for Pro. Unlimited for Enterprise. |
| Custom pack development consultation | $150/hr | Enterprise or by arrangement |
| Priority support upgrade (any tier → 4hr response) | $29/mo | Available to Base and Plus |
| Additional cloud API credits (beyond tier allowance) | $10 per 100 credits | All tiers |
| Hardware upgrade trade-in program | 30% credit toward new tier | Must return functional unit. Refurbished units sold as "thUMBox Renewed" at 20% discount. |

### §6.6 Operating Cost Model (Per Unit, Monthly)

| Cost | Low | High | Notes |
|------|-----|------|-------|
| Cloud API (customer usage beyond included) | $0/mo | $30/mo | Depends on pack count, volume, cloud-routing ratio |
| OTA delivery infrastructure | $0.50/mo | $2/mo | CDN + update server, amortized across fleet |
| Support labor (per customer) | $2/mo | $20/mo | Varies by tier: Community ($0), Base ($2), Pro ($10–20) |
| Open-source repo maintenance | $0.10/mo | $0.50/mo | Amortized — CI, hosting, community management |

### §6.7 Revenue Composition Target (Steady-State, 1000+ Units)

| Stream | % of Revenue | Margin |
|--------|-------------|--------|
| Hardware sales | 25–35% | 40–55% |
| Subscriptions (recurring) | 45–55% | 80–90% |
| Add-on services | 10–15% | 70–85% |
| Cloud API passthrough | 5–10% | 20% |

---

## §7. Bundling Strategy & Value Propositions

### §7.1 Bundle Offers

| Bundle | Contents | Price | Savings | Target |
|--------|----------|-------|---------|--------|
| **Starter** | T1 Lite + Base sub (12 months prepaid) + 1 pack | $549 | ~15% | Solo founders, try-before-committing |
| **Operator** | T2 Standard + Plus sub (12 months prepaid) + 2 packs | $899 | ~20% | Small business operators — the core market |
| **Power** | T3 Pro + Pro sub (12 months prepaid) + all packs + white-glove | $1,599 | ~25% | Multi-hat founders wanting email + social + research |
| **Team** | T4 Heavy + Pro sub (12 months prepaid) + all packs + 3 persona tuning sessions | $3,299 | ~20% | Small team / agency |
| **Enterprise Pilot** | 3× T3 Pro + Enterprise sub (6 months) + custom pack consultation (10 hrs) + on-site | $7,999 | Custom | Enterprise proof-of-concept |

### §7.2 Upgrade Paths

**Hardware upgrade path:**

- T0 → T1: Customer outgrows notification-only mode. Trade-in: $75 credit.
- T1 → T2: Customer wants GPU acceleration or second pack. Trade-in: $120 credit.
- T2 → T3: Customer adds research or wants multi-pack. Trade-in: $200 credit.
- T3 → T4: Team grows beyond single-user. Trade-in: $300 credit.
- Returned hardware is refurbished and sold as "thUMBox Renewed" at 20% discount, creating an entry-level pipeline.

**Subscription upgrade path:**

- Community → Base: Customer wants full pack features and faster updates. Friction-free in-dashboard upgrade.
- Base → Plus: Customer adds second pack or wants analytics. Dashboard prompt when second pack is explored.
- Plus → Pro: Customer wants daily updates, fine-tuning, or multi-agent. Triggered when usage patterns indicate advanced needs.
- Pro → Enterprise: Customer has 3+ boxes or needs compliance. Sales-assisted.

### §7.3 Value Proposition Matrix

| Customer Need | Relevant Tier | Key Value Prop | Proof Point |
|---------------|--------------|----------------|-------------|
| "I spend 2 hours/day on email" | T2 + Base | "Get 90 minutes back every day" | SM-3: > 50% time saved |
| "I need to manage email AND social" | T3 + Plus | "One brain, two domains, zero context switching" | SM-18: < 5% latency degradation multi-pack |
| "I want the latest AI improvements first" | Any + Pro | "Daily OTA updates — your box gets smarter every morning" | Staggered release schedule |
| "I don't trust cloud AI with my data" | T2+ | "Everything runs on your desk. Your data never leaves the box." | LUKS encryption, local-first architecture |
| "I want to tinker and customize" | T0/T1 + Community | "Open-source core, build your own packs, join the community" | GitHub repo, pack SDK |
| "I need this for my whole team" | T4/T5 + Pro/Enterprise | "Fleet management, shared intelligence, compliance-ready" | Fleet dashboard, audit trails, SSO |
| "What if this company disappears?" | Any | "Open-source core means your box keeps working. No vendor lock-in." | AGPLv3 platform license |

### §7.4 Seasonal & Promotional Pricing

| Promotion | Offer | Timing |
|-----------|-------|--------|
| Launch discount | 25% off first-year subscription with hardware purchase | First 90 days of general availability |
| Annual commitment | 20% off monthly rate (built into subscription pricing) | Always available |
| Referral program | Referring customer gets 1 free month; new customer gets 10% off hardware | Ongoing |
| Community contributor | Free Plus tier for 12 months for accepted pack contributions or 10+ merged PRs | Ongoing |
| Upgrade incentive | First month free when upgrading subscription tier | Triggered in-dashboard |

---

## §8. Go-to-Market: Onboarding & Trust-Building

### §8.1 Onboarding Protocol

The onboarding protocol is designed to get the customer from unboxing to first useful draft in under 2 hours, while building the foundation of trust that the graduated autonomy model requires.

**Pre-Shipment:**

| Step | Owner | Duration |
|------|-------|----------|
| O-1 | UMB Group | Schedule onboarding call with customer (within 3 days of order) |
| O-2 | Customer | Confirm email provider (Gmail / Outlook / other IMAP) |
| O-3 | Customer | Prepare: business documents (product catalog, pricing, templates, any SOPs) |
| O-4 | UMB Group | Assemble and QA appliance, ship |

**First-Boot (Customer Self-Service, ~10 min):**

| Step | Action |
|------|--------|
| O-5 | Unbox, connect power + ethernet (or Wi-Fi via quick-start card instructions) |
| O-6 | Navigate to `http://device.local:3000` (or IP shown on quick-start card) |
| O-7 | Create admin account (username + password) |
| O-8 | Wait for system readiness indicator (all services green, ~2 min) |

**Guided Onboarding Call (Zoom, 60–90 min):**

| Step | Action | Duration |
|------|--------|----------|
| O-9 | Connect email account via OAuth2 or IMAP credentials | 5 min |
| O-10 | Initiate email history ingestion (background, ~30–60 min for 6 months) | 2 min |
| O-11 | Upload knowledge base documents (product catalog, pricing, SOPs) | 10 min |
| O-12 | Review auto-generated voice profile, adjust if needed | 10 min |
| O-13 | Walk through 10 sample draft classifications and responses together | 20 min |
| O-14 | Customer marks each draft: good tone / wrong tone / edit | (included above) |
| O-15 | Configure notification preferences (queue threshold, daily digest) | 5 min |
| O-16 | Explain approval queue workflow, demonstrate approve/edit/reject | 10 min |
| O-17 | Set expectations: 2-week human-review-everything phase, then graduated auto-send | 5 min |

### §8.2 Trust-Building Period (Weeks 1–2)

| Condition | Behavior |
|-----------|----------|
| All auto-send rules | OFF |
| All drafts | Require manual approval |
| Daily digest | ON |
| Check-in call | Day 3 and Day 7 (15 min each) |

### §8.3 Graduated Autonomy Activation (Week 3+)

Auto-send activation for any category requires **all** of the following conditions:

| Condition | Specification |
|-----------|---------------|
| **Accuracy gate** | Classification accuracy > 92% over the prior 7 days for the specific category |
| **Volume gate** | Category has processed ≥ 15 emails in the prior 7 days (protects against small-sample illusion) |
| **Confidence gate** | 90% lower confidence bound (Wilson score at α=0.05) on accuracy > 85% |
| **Consent gate** | Customer explicitly opts in per category via dashboard (no silent activation) |
| **Cooldown gate** | Category has not had auto-send disabled due to degradation in the prior 30 days |

#### Per-Category Defaults

| Category | Auto-send eligible? | Accuracy gate | Rollback threshold |
|----------|-------------------|---------------|-------------------|
| `reorder` | Yes | 92% | 88% |
| `scheduling` | Yes | 92% | 88% |
| `follow-up` | Yes | 94% (higher — more context-dependent) | 90% |
| `internal` | Yes | 90% (lower — lower stakes) | 85% |
| `inquiry` | **No** | — | — |
| `escalate` | **No** | — | — |
| `unknown` | **No** | — | — |
| `spam/marketing` | Auto-archive only | — | — |

Thresholds are configurable per-category in the dashboard under an "advanced" expander. Complex inquiries remain manual — too high-stakes for auto-send in v1.

#### Rollback Triggers

Auto-send for a category is **automatically disabled** (reverts to manual approval) when any of the following occurs:

| Trigger | Rationale |
|---------|-----------|
| Classification accuracy < category's rollback threshold over the prior 7 days | Quality degradation |
| Customer rejects or edits > 3 auto-sent drafts in a rolling 24-hour window | Direct customer signal |
| > 2 escalations occur for emails that were auto-sent | System flagged something high-stakes post-hoc |
| Email provider flags outbound volume as suspicious | External signal of quality problem |

When a rollback occurs, the customer receives a dashboard notification and a daily-digest callout explaining which category was disabled and why. Re-enabling requires the customer to go through the full activation flow again plus a 24-hour cooldown.

### §8.4 The Learning Flywheel (Customer-Facing Narrative)

This is how the product value is communicated to customers:

**Week 1:** "Your thUMBox is watching and learning. Every email you approve or edit teaches it your voice. Review everything."

**Week 2:** "Your thUMBox is getting better. Check the Learning tab — it's proposing drafting rules based on your edits. Activate the ones that look right."

**Week 3+:** "Your thUMBox has learned enough to handle routine emails on its own. Enable auto-send for categories where it's consistently accurate. You still review everything else."

**Month 3+:** "Your thUMBox knows your contacts, your pricing history, your communication style. It's drafting responses that sound like you wrote them. The longer you use it, the better it gets."

### §8.5 OpenClaw Onboarding (Plus+ Subscribers, T3+ Hardware)

OpenClaw setup is an optional step after the core platform and first personality pack are configured. Available to Plus+ subscribers on T3+ hardware (T2 pending NC-2-OPENSHELL resolution).

| Step | Action | Owner | Time |
|------|--------|-------|------|
| O-CL-1 | Customer opts in to OpenClaw during setup wizard or later via Brain dashboard | Customer | 1 min |
| O-CL-2 | NemoClaw installer runs: downloads OpenShell sandbox image, configures inference routing to platform Ollama | Automated | 3–5 min |
| O-CL-3 | Messaging channel selection: WhatsApp, Telegram, and/or Discord. QR code or bot token pairing. | Customer | 2–5 min |
| O-CL-4 | thUMBox skills pre-installed (see Technical PRD §15.6). Customer shown skill list with descriptions. | Automated | 1 min |
| O-CL-5 | Security policy review: customer shown the NemoClaw egress policy. Option to add custom allowed hosts. | Customer | 2 min |
| O-CL-6 | Test message: customer sends "hello" via their chosen messaging app. Verified round-trip. | Customer | 1 min |
| O-CL-7 | Skill Bridge activated. Test event: MailBox One sends a test notification via OpenClaw to messaging app. | Automated | 1 min |

**Total added onboarding time:** 10–15 minutes.

#### Messaging Channel Security

| Channel | Pairing Method | Security Notes |
|---------|---------------|----------------|
| WhatsApp | QR code scan (secondary device pairing, like WhatsApp Web) | No phone number exposed to cloud. All messages transit through local gateway only. WhatsApp E2E encryption preserved. |
| Telegram | Bot token via @BotFather. DM allowlist configured during setup. | Bot accessible only from allowlisted Telegram user IDs. No group chat by default. |
| Discord | Bot token. Private server / DM only. | Bot restricted to customer's private server. No public server support in default policy. |
| Web TUI | Terminal-based. Accessible from any device on the local network via SSH tunnel. | Local network only. |

All messaging bridges run inside the NemoClaw sandbox. Messaging credentials are sandbox-scoped and included in the LUKS encryption boundary.

---

## §9. Personality Packs: Product Roadmap

### §9.1 Planned Packs

| Pack | Target Tier | Core Loop | Status |
|------|-------------|-----------|--------|
| **MailBox One** (Email Agent) | T1+ | Inbound email → classify → draft → approve → send | Phase 1 — active development |
| **Research Agent** | T2+ (T3 recommended) | Ingest sources → chunk/embed → multi-step synthesis → report | Phase 2 — design |
| **Social Agent** | T1+ | Monitor mentions → draft replies/posts → schedule → publish | Phase 2 — design |
| **Calendar/Scheduling Agent** | T1+ | Parse scheduling requests → check availability → propose times → confirm | Phase 3 — concept |
| **Sales Ops Agent** | T2+ | Track pipeline → draft follow-ups → update CRM → alert on stale deals | Phase 3 — concept |
| **Inventory/Reorder Agent** | T2+ | Monitor stock levels → predict reorder points → draft POs → alert | Future — concept |

### §9.2 Pack Monetization

Each pack follows the same graduated autonomy lifecycle. Each generates value through the subscription model — new packs are included in Pro tier and available à la carte for lower tiers ($15/mo per additional pack). Pack releases create upgrade pressure: when a customer discovers they want a second pack, they either upgrade their subscription tier or add it à la carte.

### §9.3 Multi-Pack Value Multiplier

On T3+ hardware, packs running **co-located on a single appliance** share a common relationship graph — the contact/company/product network built by MailBox One enriches the Research Agent's synthesis and the Calendar Agent's scheduling context. This shared intelligence makes each additional pack more valuable than the first, reinforcing subscription upgrades.

**Messaging clarification — single-appliance multi-pack vs. SocialBOX standalone:**

| Scenario | Narrative |
|----------|-----------|
| **Single-tenant multi-pack (T3+):** MailBox One + Calendar Agent + Research Agent on one box | "One brain, many domains, shared intelligence" |
| **SocialBOX standalone appliance (per brand):** | "Dedicated appliance per brand, for privacy and performance" |
| **Cross-appliance sync (Phase 3 future):** MailBox One appliance + SocialBOX appliance intelligence sharing | Addressed in the SocialBOX §15.10 cross-box intelligence section as a Phase 3 feature, not a default |

SocialBOX ships as a separate appliance per brand customer (not co-located with MailBox One) because brand content production has a fundamentally different workload profile — voice generation, video assembly, weekly batch cadence — that benefits from dedicated hardware. The shared-graph value proposition applies within a single multi-pack appliance, not across appliances in v1.

---

## §10. Open-Source & Community Strategy

### §10.1 Model: Time-Delayed Open-Core

Inspired by MariaDB's Business Source License approach.

| Component | License | Open-Source Timing |
|-----------|---------|-------------------|
| Platform OS (Docker Compose, base config, health monitoring) | AGPLv3 | Immediate — always open |
| Pack framework (pack spec, module interface, SDK) | AGPLv3 | Immediate — always open |
| Individual pack implementations (MailBox, Social, Research) | BSL 1.1 → AGPLv3 | Proprietary for 90 days after Pro release. Auto-relicenses to AGPLv3 on day 91. |
| Optimus Brain dashboard (core shell) | AGPLv3 | Immediate |
| Brain dashboard (premium features: orchestration, fleet, API) | Proprietary | Premium features remain proprietary. Core analytics open-sourced after 180 days. |
| Fine-tuning pipeline | Proprietary | Remains proprietary. Research methodology published. |
| Learned skills (customer-generated) | Customer-owned | Never published. Customer's data. Encrypted at rest. |

### §10.2 Why This Model

The moat is hardware + service + learned intelligence (fine-tuned models, customer-specific skills), not the software itself. A motivated developer can replicate the software stack with open-source tools in a weekend. What they can't replicate is the polished hardware, white-glove onboarding, daily OTA updates, and growing intelligence from the installed base.

Making the software open-source after 90 days turns a liability (easily copied) into an asset (community, trust, contributor pipeline). The BSL license during the 90-day window prevents commercial competition while allowing source-available inspection for security-conscious customers.

### §10.3 OTA Update Cadence by Subscription Tier

| Tier | Feature Update Cadence | Security Updates | Release Channel |
|------|----------------------|------------------|-----------------|
| Pro / Enterprise | Daily (as available) | Immediate (< 24hr) | `edge` |
| Plus | Weekly (batched, every Monday) | Immediate (< 24hr) | `stable` |
| Base | Bi-weekly to monthly (2–4 week delay) | Immediate (< 24hr) | `stable-delayed` |
| Community | Monthly (after ~30 days in stable) | Immediate (< 24hr) | `community` |

Security updates are never delayed. Feature updates follow a graduated rollout: Pro users are early adopters and provide feedback that improves stability for downstream tiers.

### §10.4 Community Funnel

The open-source base creates a DIY community (Raspberry Pi tinkerers, homelab enthusiasts) — a percentage convert to paid tiers when they want reliability, support, and premium features. Target: > 5% conversion from Community to paid tiers within 6 months.

### §10.5 GitHub Repository Structure

```
umb-group/thumbox/
├── platform/          # AGPLv3 — Docker Compose, base configs, health monitoring
├── pack-sdk/          # AGPLv3 — Pack development framework and interfaces
├── packs/
│   ├── mailbox-one/   # BSL → AGPLv3 after 90 days
│   ├── social-agent/  # BSL → AGPLv3 after 90 days
│   └── research-agent/# BSL → AGPLv3 after 90 days
├── brain-dashboard/
│   ├── core/          # AGPLv3 — Status, basic analytics
│   └── premium/       # Proprietary — orchestration, fleet, API
├── docs/              # CC-BY-4.0
└── community-packs/   # Community-contributed packs, MIT or AGPLv3
```

### §10.6 Pack SDK Scope

SM-30 targets "> 3 community-contributed packs within 12 months of SDK release." This section establishes scope for a future dedicated SDK addendum rather than attempting a full specification inline.

#### Minimum Viable SDK

| Component | Purpose |
|-----------|---------|
| Pack manifest schema | Declarative config: name, version, required platform version, data dependencies, required subscription tier |
| Connector interface | Standard API for external service integration (OAuth flow, credential storage, polling) |
| Classification + drafting hooks | Plug-in points for custom categories, prompts, and n8n workflow templates |
| Dashboard plugin hooks | Plug-in points consistent with Technical PRD §7.3 Plugin API |
| Testing harness | Local dev environment (Docker Compose subset) for pack authors |
| Publishing guide | How to submit to the community pack registry; UMB Group review criteria |
| License requirements | AGPLv3 or MIT required for acceptance; BSL not accepted for community packs |

#### Review Gate

A community-submitted pack is accepted into the official registry only after:

1. Automated security scan (secrets, known-malicious dependencies, AGPL-firewall violations)
2. Manual security review by UMB Group engineering
3. Resource footprint validation (must not exceed stated tier requirements)
4. Basic functional test (pack installs, starts, doesn't crash)

Approved packs appear in the Brain dashboard pack marketplace with a "Community" badge, distinct from UMB Group first-party packs.

#### Deferred Decisions

The following are intentionally unspecified pending a dedicated SDK addendum:
- Revenue share model for paid community packs
- Signing + verification chain for pack updates
- Pack deprecation and compatibility policy across platform versions
- Community pack support model (community forum only? UMB Group minimum?)

#### Phase Activation

- Phase 2: Placeholder only. SDK not yet built.
- Phase 3: Dedicated Pack SDK addendum authored. SocialBOX as a "pack-like" deliverable informs SDK design.
- Post-launch: First community pack accepted (SM-30 clock starts at SDK addendum + reference implementation + publishing guide going public).

---

## §11. Phase Plan

### Phase 1: Prototype (Internal Dogfood)

> Phase 1 of 3 | Duration estimate: 4–6 weeks
> Budget cap: $800 (1 unit hardware + cloud API for testing)
> Entry criteria: PRD approved, open questions resolved
> Depends on: Nothing

**Objective:** Prove the end-to-end email processing pipeline works on target hardware with a real email account.

**Business Deliverables:**

| # | Deliverable | Exit Criteria |
|---|------------|---------------|
| 1 | Assembled appliance running full stack | All services start and pass health checks within 3 min of boot |
| 2 | End-to-end email pipeline | 50 consecutive inbound emails processed without error |
| 3 | Local model classification | Accuracy > 80% on test email corpus (100-email test set) |
| 4 | Cloud API draft generation | Drafts generated for 10 complex inquiry emails; 7/10 rated "sendable with minor edits" |
| 5 | RAG pipeline with email history | Retrieved context is relevant for 8/10 test queries (manual evaluation) |
| 6 | Dashboard with approval queue | Approve, edit, reject actions work end-to-end; approved email sends via SMTP |

**Kill Criteria:**

- Hardware cannot run all services simultaneously without OOM or thermal throttle under sustained load
- Classification accuracy < 70% after prompt tuning (model is insufficient)
- End-to-end latency > 120 seconds for local-model path

**Cost Estimate:**

| Category | Low | High |
|----------|-----|------|
| Hardware (1 unit) | $344 | $344 |
| Cloud API (testing) | $20 | $50 |
| Development time | 60 hrs | 100 hrs |
| **Total** | **$364** | **$394** + time |

---

### Phase 2: Beta (3–5 Paying Customers)

> Phase 2 of 3 | Duration estimate: 6–8 weeks
> Budget cap: $3,000
> Entry criteria: Phase 1 exit criteria met
> Depends on: Phase 1

**Objective:** Validate the product with real SMB operators and prove the onboarding protocol works without the builder present.

**Business Deliverables:**

| # | Deliverable | Exit Criteria |
|---|------------|---------------|
| 1 | 3–5 appliances shipped to beta customers | All units operational within 24 hours of receipt |
| 2 | Onboarding protocol executed | All customers complete onboarding in single 90-min session |
| 3 | 30-day operation | All units maintain > 99% uptime over 30 days |
| 4 | Customer satisfaction | NPS > 30 across beta cohort |
| 5 | Classification accuracy | > 85% average across all customers at day 30 |
| 6 | OTA update mechanism | At least 1 update pushed and successfully applied to all units |

**Technical deliverables (7–13) are specified in the Technical PRD §14.**

**Kill Criteria:**

- 2+ customers churn within 30 days citing product quality (not pricing or fit)
- Average onboarding time exceeds 2 hours
- Classification accuracy < 80% for any customer after 30 days

**Cost Estimate:**

| Category | Low | High |
|----------|-----|------|
| Hardware (5 units) | $1,720 | $1,720 |
| Cloud API (5 customers × 2 months) | $60 | $200 |
| Support labor (onboarding + check-ins) | $500 | $1,000 |
| Technical development (see Technical PRD) | 42 hrs | 70 hrs |
| **Total** | **$2,280** | **$2,920** + dev time |

---

### Phase 3: Commercial Launch

> Phase 3 of 3 | Duration estimate: Ongoing
> Budget cap: $10,000 initial inventory
> Entry criteria: Phase 2 exit criteria met, positive unit economics validated
> Depends on: Phase 2

**Objective:** Sell thUMBox as a repeatable product through direct sales, referral, and community channels.

**Business Deliverables:**

| # | Deliverable | Exit Criteria |
|---|------------|---------------|
| 1 | 20-unit initial production run | All units assembled, QA'd, and shelf-ready |
| 2 | Sales page + checkout flow | Live on dedicated product domain |
| 3 | Self-service onboarding documentation | Customer can complete first-boot without Zoom (Zoom still included but optional) |
| 4 | Fleet monitoring dashboard (UMB Group internal) | View status of all deployed units |
| 5 | Support runbook | Documented troubleshooting for top 10 failure modes (enumerated below). Each entry includes symptom, diagnostic steps, resolution, and escalation path. |

**Top 10 Failure Modes (support runbook scope):**

| # | Failure Mode | Symptom | First-Line Resolution |
|---|--------------|---------|-----------------------|
| F-1 | IMAP connection dropped | Queue stops growing; dashboard shows "email disconnected" | Check OAuth refresh; re-authenticate via dashboard; confirm customer's email provider status |
| F-2 | OAuth token expired | Same as F-1 for Gmail/Outlook | Dashboard "Reconnect email" button runs OAuth flow |
| F-3 | Ollama OOM | Classification latency spikes; queue slows; docker logs show OOM | Restart ollama container; check for simultaneous skill-synthesis jobs; verify KV cache quantization is enabled |
| F-4 | NVMe fill-up | Dashboard shows < 10% disk free; backups fail | Prune old audit logs; compact Postgres; upsell NVMe upgrade if repeat offender |
| F-5 | Thermal throttle | Classification accuracy drops; GPU clock throttled | Check enclosure airflow; confirm customer hasn't placed box in enclosed cabinet; recommend active cooling accessory |
| F-6 | Docker restart loop | Service repeatedly crashes | Identify failing container via logs; common causes: corrupted volume, version mismatch after OTA, config drift |
| F-7 | Cloud API quota exceeded | Drafts stuck "awaiting cloud"; digest flags over-budget | Reference Technical PRD §5.3.1 budget guard; offer credit purchase; remind customer of local-only fallback |
| F-8 | Classifier accuracy drift | Customer reports "it used to be better"; accuracy log shows trending down | Review recent prompt updates; check for email volume shift; trigger persona re-tuning session |
| F-9 | Approval queue backlog | > 50 pending drafts; customer overwhelmed | Recommend auto-send activation for low-risk categories; help prioritize category-by-category review |
| F-10 | Backup failure | Nightly backup job repeatedly failing | Verify backup target credentials; test NAS/cloud connectivity; restore confidence with a manual test backup |

**Kill Criteria:**

- Fewer than 10 units sold in first 90 days
- Support cost per customer exceeds $30/month sustained
- Product returns exceed 20%

---

## §12. Success Metrics

> **SM Numbering:** Success metrics share a single numbering space across both PRDs. Business SMs are defined here; Technical SMs are defined in Technical PRD §10. Current allocation:
> - **SM-1, SM-3, SM-6, SM-7, SM-8, SM-21–SM-24, SM-32–SM-34:** Business PRD §12 (this section)
> - **SM-2, SM-4, SM-5, SM-9–SM-16, SM-19, SM-20, SM-25–SM-28:** Technical PRD §10
> - **SM-17, SM-18, SM-29–SM-31:** Platform/community — Business PRD §12.2 below
> - **SM-35–SM-49:** OpenClaw integration (Technical PRD §15)
> - **SM-50–SM-52:** Security threat model (Technical PRD §8.3)
> - **SM-53–SM-55:** Backup and RMA (Technical PRD §8.4)
> - **SM-56–SM-57:** Cloud API budget guard (Technical PRD §5.3.1)
> - **SM-58–SM-59:** Multi-pack message bus (Technical PRD §6.3)
> - **SM-60–SM-61:** Graduated autonomy thresholds (Business PRD §8.3)
> - **SM-62–SM-63:** Regulatory posture (Business PRD §12.5)
> - **SM-64:** Support runbook MTTR (Business PRD §11 Phase 3)

### §12.1 Business Metrics

| ID | Metric | Target | Measurement |
|----|--------|--------|-------------|
| SM-1 | Time-to-first-draft | < 5 minutes from email connection | Dashboard timestamp |
| SM-3 | Customer email time saved | > 50% reduction self-reported | Post-30-day survey |
| SM-6 | Customer retention (paid subscribers) | > 70% at 6 months | Subscription data |
| SM-7 | Net Promoter Score | > 40 | Post-60-day survey |
| SM-8 | Unit economics | Positive contribution margin by unit 10 | Revenue – COGS – support labor |
| SM-21 | Subscription revenue exceeds hardware revenue | By month 18 of GA | Revenue reporting |
| SM-22 | Blended gross margin > 65% | At 500+ units deployed | Financial reporting |
| SM-23 | Subscription churn < 8% monthly | Across all paid tiers | Subscription data |
| SM-24 | Plus-or-higher tier adoption > 40% | Of active subscribers | Subscription data |
| SM-32 | Bundle attach rate > 60% | Customers purchasing bundles vs. individual | Sales data |
| SM-33 | Hardware trade-in rate > 15% | Within 18 months of program launch | Trade-in tracking |
| SM-34 | Referral-driven acquisition > 10% | Of new customers | Referral tracking |
| SM-60 | Zero "embarrassing auto-send" incidents | Customer complaint + content review attributable to a category still within activation thresholds | Incident tracking |
| SM-61 | Rollback trigger accuracy | Correctly triggers within 24 hours of degradation onset in ≥ 95% of manually-reviewed cases | Manual audit |
| SM-62 | DPA signature rate | 100% of paid customers sign DPA before appliance ship (Phase 2+) | Legal records |
| SM-63 | Regulatory complaints | Zero escalated to UMB Group over any 12-month period | Incident tracking |
| SM-64 | Support runbook MTTR | < 4 hours for Pro+, < 24 hours for Base across F-1 through F-10 | Support tracking |

### §12.2 Platform & Community Metrics

| ID | Metric | Target | Measurement |
|----|--------|--------|-------------|
| SM-17 | Second personality pack feature parity | Within 120 days of development start | Feature checklist |
| SM-18 | Multi-pack latency degradation < 5% | p95 response latency vs. single-pack on same hardware | System monitoring |
| SM-29 | GitHub stars > 1,000 | Within 6 months of repo launch | GitHub |
| SM-30 | Community-contributed packs > 3 | Within 12 months of Pack SDK addendum + reference implementation + publishing guide going public (§10.6) | GitHub |
| SM-31 | Community-to-paid conversion > 5% | Within 6 months | Subscription data |

> Technical success metrics (classification accuracy, token acceptance rate, skill generation rate, etc.) are in the Technical PRD §10.

### §12.5 Regulatory and Legal Posture

#### Scope

thUMBox processes business email on behalf of customers and sends on their behalf. This creates regulatory obligations that §8 Onboarding and §13 Risk Register touch on but do not systematically address. This section establishes the v1 posture and the additional work required to ship.

#### Regulatory Matrix

| Regulation | Applies When | v1 Posture |
|------------|--------------|------------|
| **GDPR** (EU) | Customer or any correspondent is in EU; customer is an EU business; customer has EU employees | thUMBox is a processor; customer is controller. Customer-facing DPA template required. Technical measures already in place (local-only storage, encryption at rest, access controls). Customer responsible for lawful basis for their counterparties' data. |
| **CCPA/CPRA** (California) | Customer has California consumer data in email corpus | Similar posture to GDPR. DPA covers both. |
| **CAN-SPAM** (US) | Auto-sent emails = commercial email | v1 auto-send categories (reorder, scheduling, follow-up) are transactional and exempt from most CAN-SPAM requirements. Marketing/outbound campaigns are explicitly out of scope (§15). Clear opt-out language to be included in the auto-send footer template. |
| **Wiretap / two-party consent** (various US states) | Storing counterparty emails | Email is a stored communication, not a real-time interception; no wiretap issue. However, retention of counterparty data is subject to privacy law. Customer's privacy policy must disclose use of an AI email assistant. Onboarding guide includes sample policy language. |
| **Right to erasure / deletion requests** | Counterparty requests deletion of their data | Customer can delete contacts and associated data via `optimus.contact-explorer` plugin (Phase 2). Forensic deletion (zeroing disk sectors) is out of scope for v1. |
| **HIPAA** | Customer's email contains PHI | **Explicitly out of scope for v1.** Onboarding disqualifies customers whose email volume is primarily PHI. Future Enterprise tier may offer a HIPAA-compliant configuration (BAA, audit logs, stricter retention). |
| **SOC 2** | Enterprise customers require attestation | Not attempted in v1. Phase 3 target for Enterprise tier. Technical foundations (encryption, access controls, audit log) already in place. |

#### Required Legal Artifacts

| Artifact | Owner | Deadline |
|----------|-------|----------|
| Customer Terms of Service | UMB Group counsel | Before Phase 2 ships |
| Data Processing Addendum (DPA) template | UMB Group counsel | Before Phase 2 ships |
| Privacy Policy (UMB Group) | UMB Group counsel | Before Phase 3 launch |
| Customer-facing privacy policy template (for customer to adapt) | UMB Group counsel | Before Phase 3 launch |
| Acceptable Use Policy | UMB Group counsel | Before Phase 3 launch |
| OpenClaw / third-party license compliance doc | UMB Group + counsel | Before Phase 2 ships (AGPLv3, BSL, Apache 2.0 inventory) |
| Security whitepaper (customer-facing) | UMB Group | Before Phase 3 launch |

#### Phase Activation

- Phase 1: Internal dogfood — no external customer data, no legal artifacts required.
- Phase 2: ToS, DPA template, and license compliance doc ready before first external beta customer.
- Phase 3: Full privacy policy, AUP, and security whitepaper before general availability.

#### Out of Scope (v1)

- HIPAA / PHI workflows
- Export control (EAR/ITAR) — Jetson hardware is ECCN 5A992; commercial export allowed to most jurisdictions; revisit for international expansion
- FERPA — education sector not targeted
- FTC consumer protection beyond CAN-SPAM

---

## §13. Business Risk Register

| Risk | Probability | Impact | Mitigation |
|------|------------|--------|------------|
| Customer sends embarrassing auto-approved email | Low | Very High — reputational, product-killing | Auto-send OFF by default; graduated autonomy requires explicit per-category opt-in; full audit trail |
| Support cost per customer exceeds target | Medium | Medium — erodes unit economics | Phase 2 validates support load; self-service documentation; community forum for peer support |
| Hardware supply chain disruption (Jetson, Mac mini) | Low | High — can't ship units | 2-unit buffer inventory; T1 (Intel N100) uses commodity hardware with short lead times; multi-tier hardware reduces single-supplier risk |
| Subscription churn exceeds 8%/month | Medium | High — undermines recurring revenue model | OTA updates as ongoing value delivery; learned intelligence as switching cost; annual commitment discounts |
| Fork competition from open-source release | Low | Medium | Moat is hardware + service + learned intelligence, not software; 90-day proprietary window captures commercial value |
| Multi-pack complexity overwhelms customers | Low | Medium — churn, support load | Phase 1 ships single-pack only; progressive disclosure in dashboard; bundles pre-select appropriate combinations |
| Cloud API provider price increases | Medium | Medium — squeezes margins on API passthrough | Model-agnostic API wrapper; speculative decoding reduces cloud dependency 40–60%; local-first architecture minimizes cloud reliance |

---

## §14. Decision Records (Business-Strategic)

### DR-8: Open-Core with Time-Delayed Release vs. Fully Proprietary

**Decision:** Adopt a time-delayed open-core model. Platform infrastructure is always open-source (AGPLv3). Pack implementations are proprietary for 90 days then auto-relicense to AGPLv3. Premium dashboard features remain proprietary.

**Alternatives Considered:**

| Option | Pros | Cons |
|--------|------|------|
| Fully proprietary | Maximum control, no competitive forks | No community, no contributor pipeline, vendor lock-in fear, harder to sell to privacy-conscious customers |
| Fully open-source (Red Hat model) | Maximum community trust, easiest adoption | Revenue depends entirely on support/services (low margin for hardware company) |
| Open-core (GitLab model, static boundary) | Clear free/paid boundary, community for core | Community may resent permanently locked features |
| **Time-delayed open-core (chosen)** | Community trust, early-access as subscription value, contributor pipeline, anti-vendor-lock-in messaging | 90-day window may be too short for some features; must maintain two release processes |

**Rationale:** The moat is hardware + service + learned intelligence, not the software. Making software open-source after 90 days turns a liability into an asset. The BSL license prevents commercial competition while allowing source-available inspection.

**Cost Implications:** CI/CD for open-source repo, community management (~5 hrs/week), CLA infrastructure. Estimated $500–1,000/mo. Community tier generates $0 direct revenue but serves as acquisition funnel.

---

### DR-9: Hardware Tier Count and Segmentation Rationale

**Decision:** Six hardware tiers (T0–T5) spanning pocket devices to enterprise servers.

**Alternatives Considered:**

| Option | Pros | Cons |
|--------|------|------|
| Single SKU (Jetson only) | Simple supply chain, one test matrix | Prices out hobbyists, underserves power users |
| Two tiers (Lite + Pro) | Simple choice, clear positioning | Misses enterprise, no community entry point |
| Three tiers (Lite + Standard + Pro) | Covers most use cases | No enterprise path, no ultra-low-cost entry |
| **Six tiers (chosen)** | Full market coverage, clear upgrade path, community-to-enterprise funnel | Complex supply chain, 6 test matrices, choice paralysis risk |

**Rationale:** The platform model requires a hardware funnel that matches the subscription funnel. T0 serves the same role as a free tier in SaaS — the curiosity-driven entry point. T5 captures high-ARPU customers. Choice paralysis mitigated by hardware selection guidance and bundle strategy.

**Cost Implications:** 6 BOM sources, 6 assembly processes, 6 test suites. Mitigated by phased rollout (T2 first, then T1/T3, then T0/T4/T5). T0 and T1 use commodity hardware with short lead times. T4 and T5 are built-to-order.

### Cross-Referenced Technical Decisions Affecting Business Strategy

The following Technical PRD decision records have material impact on business strategy, pricing, or go-to-market. They are documented in detail in Technical PRD §12 and summarized here:

| DR | Summary | Business Impact |
|----|---------|-----------------|
| DR-10 (Technical) | NemoClaw-wrapped OpenClaw as agent runtime | Enables OpenClaw value prop at Plus+ tier; requires T3+ hardware pending NC-2-OPENSHELL |
| DR-11 (Technical) | OpenClaw as complementary runtime, not replacement for n8n | Supports "one brain, two runtimes" marketing narrative |
| DR-12 (Technical) | Plugin-host workspace dashboard | Enables per-plugin subscription gating; supports unified customer + fleet codebase |
| DR-13 (Technical) | Unified customer + internal dashboard codebase | Halves dashboard dev cost; enables board/internal views without separate product |
| DR-14 (Technical) | v2.1 consolidation merge | This document's v2.1 versioning |
| DR-15 (Technical) | Three-target backup architecture | Pro+ tier gains "UMB Group managed backup" as a differentiating value prop; see §6.3 |

---

## §15. Scope Boundaries

### In Scope (v1 — MailBox One Pack)

- Inbound email triage and response drafting for operational business communications
- Gmail and Outlook OAuth2 + generic IMAP/SMTP
- Local + cloud hybrid inference
- Human-in-the-loop approval workflow with graduated autonomy
- RAG over customer's email history and uploaded documents
- Local web dashboard (LAN access)
- White-glove onboarding (1 Zoom session + 2 check-in calls)
- OTA container updates (customer-initiated)

### Out of Scope (v1)

- Consumer support email (returns, complaints, order status)
- Email marketing or outbound campaign generation
- CRM integration (HubSpot, Salesforce, Pipedrive)
- Multi-user access control (v1 is single admin user)
- E-commerce platform integration (Shopify, Amazon)
- Voice/phone integration
- Mobile app (dashboard is mobile-responsive web only)
- Remote access outside LAN
- Custom carrier board or production-grade hardware (v1 uses dev kit)
- Automated persona tuning without human review

### Future Consideration (v2+)

- Tailscale/WireGuard remote access
- Multi-user roles (admin, reviewer, read-only)
- CRM sync (bi-directional with HubSpot)
- E-commerce order context injection into RAG
- Fleet management dashboard (UMB Group internal — monitor all deployed appliances)
- Custom molded enclosure with branding
- Higher-memory hardware upgrade path for high-volume customers
- Outbound campaign drafting (follow-up sequences)
- Relationship graph dashboard view (visual map of contacts, companies, products, and deal flows)
- Graph-powered proactive follow-up suggestions (detect stale threads where follow-up is overdue)
- Cross-account graph merge (if customer adds a second email account, unify the contact/company graph)
- MoE expert streaming from NVMe for local 30–50B inference (pending CUDA runtime availability)
- On-device model fine-tuning using customer's approved corpus
- Multi-NVMe carrier board design for higher storage bandwidth

---

## §16. Ecosystem & Inspiration References

| Source | Key Takeaway | Applicability |
|--------|-------------|---------------|
| Tesla FSD / Optimus OTA model | "Updates are the product" — the device on day 1 is not the device on day 365. Software subscription is the real revenue. | OTA cadence, pricing philosophy, staggered rollout by tier |
| Tesla Optimus task skill packs | Industry-specific neural network layers delivered as OTA modules on shared hardware. | Personality pack concept |
| MariaDB Business Source License (BSL 1.1) | Time-delayed open-sourcing — proprietary for fixed period, then auto-relicenses to GPL. | Open-source release strategy |
| Open-core model (GitLab, MongoDB, Confluent) | Free core drives adoption; premium features drive revenue. CLA enables dual-licensing. | Platform architecture, community funnel |
| JetBrains AI tiered subscriptions | Free → Pro → Ultimate → Enterprise with credit-based consumption. | Subscription tier structure |
| GoPro subscription model | Hardware company added recurring software/service revenue. Diversified from one-time sales. | Business model validation for hardware + subscription |
| 1X NEO Robot-as-a-Service | $499/mo subscription includes hardware + software + support. Lowers barrier for expensive hardware. | Future consideration for T4/T5 RaaS option |
| Adobe Creative Cloud tier restructuring (2025) | AI features as value justification for tiered pricing. ~27% effective increase accepted by market. | Pricing psychology — AI capability justifies tiers |

---

## §17. Open Questions

> **NC Numbering:** NC IDs share a single namespace across both PRDs. See Technical PRD §17 for the full allocation legend.

| # | Question | Section | Impact |
|---|----------|---------|--------|
| NC-1 | Remote access (WireGuard/Tailscale) in v1 or defer to v2? | §8 Onboarding | Security architecture, onboarding complexity |
| NC-2 | SMS/Slack notifications in v1 or email-only? | §8 Onboarding | Notification service scope |
| NC-2-OPENSHELL | Is OpenShell available as an ARM64 image for Jetson Orin Nano (T2)? | §5 Hardware, §6.3 Subscriptions, §8.5 OpenClaw Onboarding | T2 OpenClaw eligibility; subscription tier gating; go-to-market narrative. See Technical PRD §17 for specification. |
| NC-3 | Target initial production run size? | §5 Hardware | Volume pricing, enclosure customization |
| NC-5 | Cloud API credits included in hardware price or billed separately? | §6 Pricing | Cash flow, perceived value |

> Technical open questions (BYOK API keys, container registry hosting, Anthropic API speculative decoding support) are in the Technical PRD §17.
