# Feature Research

**Domain:** Voice-AI cloud benchmark suite (Phase 0 feasibility validation)
**Researched:** 2026-05-04
**Confidence:** HIGH (driven by PRD §10/§11/§14 success metrics, virtual benchmark plan v0.1, DR-28 gate semantics)

## Framing

For a Phase 0 benchmark project, "features" are not user-facing functionality. They are the **set of measurements, eval harnesses, evaluation assets, and reporting deliverables** that the project must produce in order to constitute a defensible go/no-go gate per DR-28. The taxonomy below maps directly to the seven-gate scheme (G1–G7, with G4 and G6 deferred) plus the operational and reporting wrap.

Categories:
- **Table stakes** = the gate fails or the synthesis report is non-defensible without these. No Phase 0 sign-off.
- **Differentiators** = these raise stakeholder confidence in the derated Strix Halo prediction. They are what distinguishes a "credible" benchmark from a "we ran some numbers" benchmark, and they are what makes the deliverable usable by Eric for the v0.4 feasibility memo and by sales as a SOW excerpt.
- **Anti-features** = deliberately NOT in Phase 0. Building these now blows the $150 / 40-hour envelope, leaks scope into Phase 1/2, or creates legal/regulatory exposure.

## Feature Landscape

### Table Stakes (Gate Cannot Pass Without These)

These are the non-negotiables. Each maps to a numbered gate (G*) or a non-gate operational deliverable from PROJECT.md "Active" requirements and PRD §14.

| Feature | Why Required | Complexity | Notes |
|---------|--------------|------------|-------|
| **G1 — End-to-end latency harness (500-call corpus)** | SM-66 / SM-67. Load-bearing technical risk. Without measured p90/p99 on MI300X there is no derated Strix Halo prediction, which is the entire reason Phase 0 exists (DR-28). | HEAVY | Must measure full STT → LLM → TTS chain with realistic call audio. Requires the call corpus asset and the deployed pipeline on both H100 (pre-flight) and MI300X (target). Latency must be decomposed per stage to enable derating. |
| **G2 — STT WER harness on G.711 μ-law (200 clips, neutral + stressed)** | SM-68. G.711 is the mandatory phone codec; native 16 kHz WER is irrelevant to deployment reality. Without this, STT accuracy claims are unsupported. | MODERATE | Requires the G.711 transcoding pipeline (16 kHz → 8 kHz μ-law → back to model input). Stratified into neutral and stressed splits with per-split WER. |
| **G3 — Turn-detection FP-rate harness (hesitation-heavy adversarial set)** | SM-69. Turn detector failures are UX-killing on real phone calls (caller pauses → AI interrupts). Must measure on adversarial, not just clean speech. | MODERATE | Adversarial corpus generation is the hard part; measurement itself is straightforward once the corpus exists. |
| **G5 — UPL guardrail probe suite (200 adversarial probes, 100% pass required)** | SM-71. Regulatory critical. Even one prompt-injection escape that elicits substantive legal advice creates an unauthorized-practice-of-law exposure that kills the deal. | HEAVY | Probe corpus must cover: substantive legal Qs, fee quotes, statute-of-limitations, deadline advice, case-outcome predictions, prompt-injection variants, jailbreak chains. Must pass with 100% margin, not "best effort." |
| **G7 — TTS A/B preference test (Chatterbox-Turbo vs Kokoro-82M, 30 pairs, 5 listeners)** | SM-72. Validates DR-27 pluggable TTS choice and the Chatterbox-Turbo primary / Kokoro fallback architecture. Without it, the engine selection is unjustified. | MODERATE | Blind-pairing methodology, listener recruitment (5), pair construction (30), preference aggregation. Listeners need not be experts. |
| **CUDA pre-flight on RunPod H100 (end-to-end pipeline assembles once)** | Risk reduction before paying MI300X bills. Many failure modes (model loading, audio codec plumbing, glue code) surface on any GPU; finding them on cheap H100 time before expensive ROCm validation is essential cost discipline. | MODERATE | Functional, not measurement-grade. Goal is "it runs once cleanly," not "it benchmarks." |
| **ROCm validation on MI300X (Chatterbox-Turbo + Whisper + Qwen3-4B all run; engine swap to Kokoro proven)** | Highest-impact risk per §11 ("Chatterbox-Turbo ROCm path is non-functional"). Must demonstrate both the primary path and the documented graceful-degradation path. | HEAVY | Includes ROCm 6.x setup, model loading, smoke-test inference. Engine swap must be exercised, not just claimed possible. |
| **Synthesis report with derated Strix Halo predictions** | The actual deliverable to Eric and sales. Cloud numbers without a derating method connecting MI300X → Strix Halo are not actionable. | MODERATE | Must include methodology, confidence ranges, per-gate verdict, and explicit derating math (memory bandwidth, compute, thermal). |
| **Feasibility memo v0.4 (update from v0.3)** | Eric's authored doc per §0.5; this is how Phase 0 numbers reach the sales conversation in canonical form. | LOW | Editorial update once synthesis report exists. Mostly mechanical merge of measured numbers into existing prose. |
| **Phase 0 gate decision package (pass/fail + SOW excerpt)** | DR-28 explicitly: Phase 0 result is the precondition for SOW signature. The package must be in a form sales can read and excerpt directly. | LOW | One-pager with verdict, evidence, caveats, and SOW-ready language. Depends on synthesis report. |
| **Cloud account provisioning + cost-cap plan (~$150 ceiling)** | Without enforced cost caps the budget constraint is theatrical. Need RunPod, Vultr (or TensorWave), billing alerts, hard ceilings. | LOW | Operational; not technical complexity but blocking on day-1 of Phase 0. |
| **Evaluation asset curation (5 corpora)** | Every gate above depends on its corpus. No corpus = no measurement = no gate decision. | HEAVY | Five distinct assets: 500-call corpus (G1), 200 G.711 clips with neutral/stressed splits (G2), hesitation adversarial set (G3), 200 UPL probes (G5), 30-pair TTS A/B set (G7). All from synthetic + open-licensed sources only — no real client audio (regulatory). |

### Differentiators (Raise Confidence in the Derated Prediction)

These are not strictly required to fail/pass the gates, but their absence weakens the synthesis report and makes the Phase 0 → Strix Halo prediction harder for Eric to defend in his memo and for sales to defend in front of the firm. Adding them is what distinguishes a credible benchmark from a checkbox benchmark.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| **Per-stage latency decomposition (STT / LLM / TTS / network) within G1** | Aggregate p90 alone gives no derating signal; per-stage timing is what enables a defensible "MI300X → Strix Halo" projection because each stage scales differently with memory bandwidth and compute. | MODERATE | Already implied by good G1 instrumentation but worth calling out as a first-class output. |
| **Confidence intervals on derated predictions (not just point estimates)** | A prediction of "p90 ≈ 850ms" without a CI is uncalibrated. CIs let Eric speak honestly to the firm: "we expect 750–950ms with 80% confidence." | MODERATE | Requires bootstrap or analytical method on per-stage measurements plus a documented derating model with stated assumptions. |
| **Reproducibility tooling (hash-pinned model weights, pinned cloud images, single-command re-run)** | The synthesis report has to cite hash-pinned artifacts (per Constraints in PROJECT.md). It also lets a future operator (or skeptical reviewer at the firm) re-run the benchmark. | MODERATE | Pin model SHAs, pin Docker/RunPod template versions, store run manifests. |
| **Ablation: STT preprocessing on/off (RNNoise / DeepFilterNet)** | §11 lists "STT WER on G.711 exceeds 18% on stressed speech" as a Medium/High risk with audio-enhancement preprocessing as the documented mitigation. Measuring with and without preprocessing tests whether the mitigation actually works before we commit to it in Phase 1. | MODERATE | Doubles the G2 measurement matrix but is cheap once the harness exists. |
| **Ablation: turn-detector threshold sweep (e.g., 600/800/1000ms silence)** | §11 cites "Conservative threshold (800ms silence default)" as the mitigation. A sweep proves there exists a threshold that meets SM-69 without killing UX, rather than asserting it. | LOW | Same corpus, three threshold settings. Cheap. |
| **TTS A/B with stressed/edge-case prompts (not only clean reference)** | The vanilla 30-pair test on clean reference is the SM-72 floor. Including hard cases (numbers, proper nouns, partial sentences, legal terminology) tells us whether Chatterbox-Turbo holds up on the actual phone-receptionist content type. | LOW | Augment the 30-pair set with ~10 edge cases. Recruits same listeners. |
| **Concurrency probe (light — even though G4 deferred)** | G4 is deferred but a lightweight 2- and 4-call concurrent run on MI300X gives a directional answer about whether SM-70 (concurrency=4 at G1 latency) is even within reach, which de-risks Phase 1 dramatically. | MODERATE | Stops short of a full concurrency benchmark; just enough to know if it's plausible. Explicitly framed as "indicative, not gating." |
| **UPL probe nightly regression scaffold** | SM-71 explicitly says "G5 benchmark + nightly regression." Setting up the regression harness in Phase 0 (even if it only runs once) means Phase 1 inherits a working CI hook rather than starting from scratch. | LOW | Just a script + cron stub committed to repo. Doesn't need to actually run nightly during Phase 0. |
| **Cost telemetry per gate (actual $ spent on G1 vs G2 vs G3 …)** | Calibrates the $150 envelope for future Phase 0 runs (DR-28 says Phase 0 becomes a standard pre-sales practice). Tells us which gates are expensive and which are cheap. | LOW | Read RunPod / Vultr billing API or scrape dashboard; attribute by run timestamp. |
| **Documented derating methodology (memory bandwidth, compute, thermal scaling factors)** | The single most important honesty surface in the report. If the derating model is wrong, the prediction is wrong, regardless of how clean the cloud numbers are. Calling out the model explicitly invites scrutiny and is what makes the report defensible. | MODERATE | Section in synthesis report. Cites Strix Halo memory bandwidth (256 GB/s LPDDR5X unified) vs MI300X (5.3 TB/s HBM3) and translates that into per-stage scaling assumptions. |
| **"What we did not measure" section in synthesis report** | Calibrates expectations. Explicitly stating that G4 (concurrency), G6 (whatever was deferred), 30-day soak, real-client audio, and Strix Halo local validation were NOT in scope is what prevents the firm from over-reading the report. | LOW | One paragraph. High signal-to-effort ratio. |

### Anti-Features (Deliberately Out of Scope)

Each of these is something a Phase 0 effort can drift into. The PRD, addenda, and PROJECT.md "Out of Scope" all explicitly prohibit them. Listing them here protects the budget and the timeline.

| Feature | Why Requested / Tempting | Why Problematic | Alternative |
|---------|-------------------------|-----------------|-------------|
| **Production LiveKit SFU + agent-worker code** | "While we're at it, let's just build the runtime." | Phase 2+ deliverable per PROJECT.md. Blows 30–40 hour budget. Phase 0 needs benchmark harnesses, not a product. | Stub the pipeline with the minimum glue code needed for the gates. No real telephony, no real SIP. |
| **Real client call audio in evaluation corpora** | "More realistic than synthetic." | Privilege exposure, no NDA in place yet, contaminates Phase 0 with regulatory risk. PRD Constraints: synthetic + open-licensed only. | Synthetic corpora generated from open-licensed transcripts and TTS, with documented characteristics matching expected phone-call distribution. |
| **Local Strix Halo validation runs** | "Wouldn't measuring on the real target hardware be more accurate?" | No Framework Desktop dev unit available. PROJECT.md Out of Scope: "All Phase 0 work is cloud-only; local Strix validation is post-Phase-0." | Derated prediction with documented methodology and confidence intervals. Local validation is a Phase 1 or post-Phase-1 deliverable. |
| **G4 (concurrency benchmark) full execution** | SM-70 target of 4 concurrent calls is meaningful. | Per scope: G4 is deferred. Doing it properly requires concurrent-call orchestration that Phase 0 can't fund. | Light concurrency probe (see Differentiators) — directional only, explicitly non-gating. |
| **G6 (whatever was deferred) full execution** | Completeness. | Same — explicitly deferred per PROJECT.md scoping. | Note the deferral in synthesis report's "What we did not measure" section. |
| **Cloud LLM fallback measurement (GPT/Claude path)** | "What if local can't hit budget?" | Per FR-R49, cloud fallback is OFF by default and out of scope for Phase 0. Measuring it confuses the question Phase 0 is trying to answer (can the *local* path hit budget?). | Note as a Phase 1+ contingency in synthesis report. |
| **Outside-counsel ethics opinion / Phase 1 deliverables** | Sales pressure to "just keep going." | Per DR-28, Phase 1 only starts after Phase 0 passes and SOW is signed. Pre-doing Phase 1 work means we're spending discovery dollars before getting paid. | Hard stop at Phase 0 gate decision package. Discovery starts when SOW is signed. |
| **TTS engines beyond Chatterbox-Turbo + Kokoro-82M (e.g., VoxCPM2, Fish S2 Pro)** | DR-27 is pluggable, why not test more? | Pluggable architecture is decided; v1 ships with two engines per DR-27. Adding evaluation engines blows G7 budget. | Note as a v1.x or v2 expansion path. |
| **30-day soak / driver stability testing** | §11 lists Strix Halo ROCm driver instability as a Medium-Low/High risk. | This is a Phase 2 pre-production gate, not a Phase 0 gate. Cloud MI300X soak ≠ Strix Halo soak anyway. | Document in synthesis report as "remaining technical risk; addressed in Phase 2 30-day soak." |
| **Multi-pack co-residency tests** | Operational realism. | Per DR-25, v1 is single-pack. No need to model multi-pack interactions in Phase 0. | Out of scope; v2 concern. |
| **Outbound calling / TCPA compliance work** | Symmetry with inbound. | DR-30: v1 is inbound-only at every phase. Outbound has substantially larger regulatory surface. | v2 concern. |
| **Sales pitch deck or partnership PDF updates** | "Let's make sure the pitch reflects the new numbers." | Per §0.5 authority hierarchy, sales artifacts are subordinate. PRD updates first; sales artifacts follow. | Phase 0 produces SOW excerpt only. Pitch deck updates happen after PRD/feasibility memo update. |
| **Modifying parent thUMBox platform services** | "Could improve performance." | PROJECT.md: parent platform treated as available substrate. Phase 0 doesn't modify parent. | Note any platform-level findings in synthesis report; route to parent platform team for Phase 1+. |

## Feature Dependencies

```
Cloud account provisioning (RunPod + Vultr/TensorWave + cost caps)
    ├──enables──> CUDA pre-flight on H100
    │                ├──de-risks──> ROCm validation on MI300X
    │                │                  ├──enables──> G1 latency harness
    │                │                  ├──enables──> G2 STT WER harness
    │                │                  ├──enables──> G3 turn-detection harness
    │                │                  ├──enables──> G5 UPL probe harness
    │                │                  └──enables──> G7 TTS A/B harness
    │                └──validates──> pipeline plumbing before paying for MI300X time

Evaluation asset curation
    ├──500-call corpus──────────> G1 latency harness
    ├──200 G.711 clips (neutral/stressed) > G2 STT WER harness
    ├──hesitation adversarial set ──────> G3 turn-detection harness
    ├──200 UPL probes ──────────────────> G5 UPL probe harness
    └──30-pair TTS A/B set ─────────────> G7 TTS A/B harness

G.711 transcoding pipeline (16k → 8k μ-law)
    └──required by──> G2 STT WER harness (and any harness that uses phone-codec audio)

G1 + G2 + G3 + G5 + G7 results
    └──feed──> Synthesis report (with derated Strix Halo predictions)
                  ├──feeds──> Feasibility memo v0.4 (Eric authors)
                  └──feeds──> Phase 0 gate decision package
                                 └──gates──> Discovery SOW signature (DR-28)

Per-stage latency decomposition (within G1)
    └──enables──> Confidence intervals on derated predictions
                     └──strengthens──> Synthesis report defensibility

Reproducibility tooling (hash-pinned weights, pinned images)
    └──underwrites──> Synthesis report (must cite hash-pinned artifacts per Constraints)

UPL probe nightly regression scaffold
    └──seeds──> Phase 1 CI (zero rework when Phase 1 starts)

ROCm validation
    └──must include──> Engine swap to Kokoro fallback (proves DR-27 graceful degradation)
                           └──de-risks──> "Chatterbox ROCm non-functional" risk in §11
```

### Dependency Notes

- **CUDA pre-flight precedes ROCm validation:** H100 time is cheaper and the failure modes (model loading, glue code, audio plumbing, environment setup) are the same. Catching them on H100 saves MI300X spend. Skipping the pre-flight is a budget mistake.
- **Asset curation precedes every gate harness:** G1 cannot run without the 500-call corpus, G2 cannot run without the 200 G.711 clips, etc. Asset curation must be staged early, in parallel with infrastructure work, because it has the longest critical path that doesn't depend on GPU access.
- **G.711 transcoding pipeline is shared infrastructure:** It is required by G2 and useful for any audio-realism augmentation. Build it once, reuse across gates.
- **Engine-swap demonstration is part of ROCm validation, not separate:** DR-27 credibility depends on Phase 0 actually exercising the swap, not just claiming the architecture supports it.
- **Synthesis report depends on all five gates plus reproducibility tooling:** Cannot be written until G1/G2/G3/G5/G7 all have results AND artifacts are hash-pinned. This is the integration point.
- **Feasibility memo v0.4 and SOW excerpt both depend on synthesis report:** They are downstream editorial work; do not start until synthesis report is final.
- **Per-stage latency decomposition enables CIs:** Aggregate p90 alone does not yield a defensible confidence interval on the derated prediction. The decomposition must happen during G1 measurement, not retroactively.
- **Conflicts:** None among Phase 0 features themselves. Conflicts exist with anti-features — e.g., starting Phase 1 deliverables conflicts with Phase 0 budget; using real client audio conflicts with regulatory posture.

## MVP Definition

The "MVP" framing for Phase 0 is **the minimum set of features that constitutes a defensible go/no-go gate package.**

### Launch With (Phase 0 v1 — required to call Phase 0 complete)

- [ ] **Cloud account provisioning + $150 cost cap** — without this, every other feature is at financial risk.
- [ ] **Evaluation asset curation (all 5 corpora)** — gates cannot run without their corpora.
- [ ] **G.711 transcoding pipeline** — required by G2.
- [ ] **CUDA pre-flight on H100** — risk reduction before MI300X spend.
- [ ] **ROCm validation on MI300X (incl. engine swap to Kokoro)** — proves the target path and DR-27 graceful degradation.
- [ ] **G1 latency harness (500-call, end-to-end, with per-stage decomposition)** — load-bearing risk; per-stage decomposition is required for derating, so it's MVP, not stretch.
- [ ] **G2 STT WER harness (G.711, 200 clips, neutral + stressed)** — required by SM-68.
- [ ] **G3 turn-detection FP-rate harness (hesitation adversarial set)** — required by SM-69.
- [ ] **G5 UPL probe harness (200 probes, 100% pass)** — regulatory critical.
- [ ] **G7 TTS A/B preference test (30 pairs, 5 listeners)** — required by SM-72 and DR-27 validation.
- [ ] **Synthesis report (with derated predictions, methodology, "what we didn't measure" section)** — the actual deliverable.
- [ ] **Feasibility memo v0.4 update** — Eric-authored, downstream of synthesis report.
- [ ] **Phase 0 gate decision package (pass/fail + SOW excerpt)** — DR-28 trigger doc for SOW signature.
- [ ] **Reproducibility tooling (hash-pinned weights, pinned images, run manifest)** — Constraint requirement; not optional.

### Add If Time Permits (Phase 0 v1.x — same week if hours allow)

Trigger: budget remains in the $150 envelope and timeline remains within ~40 hours.

- [ ] **Confidence intervals on derated predictions** — promote from differentiator to MVP if hours allow; the report is meaningfully stronger with CIs than without.
- [ ] **STT preprocessing ablation (RNNoise / DeepFilterNet on/off)** — cheap once G2 harness exists; tests the documented §11 mitigation.
- [ ] **Turn-detector threshold sweep** — cheap, same corpus, three settings.
- [ ] **TTS A/B with edge-case prompts** — adds ~10 pairs to G7; same listeners.
- [ ] **Cost telemetry per gate** — calibrates the envelope for future Phase 0 runs.
- [ ] **Light concurrency probe (2 and 4 concurrent calls)** — directional, non-gating, but de-risks Phase 1.

### Future Consideration (Post-Phase-0)

Trigger: Phase 0 passes, SOW is signed, Phase 1 begins.

- [ ] **G4 concurrency benchmark (full execution)** — Phase 1 deliverable.
- [ ] **G6 (whatever was deferred) full execution** — Phase 1 deliverable.
- [ ] **Local Strix Halo validation** — Phase 1 / pre-Phase-2 once a Framework Desktop dev unit is procured.
- [ ] **30-day soak / driver stability** — Phase 2 pre-production.
- [ ] **UPL nightly regression actually running on schedule** — Phase 1 CI.
- [ ] **TTS engine catalog expansion (VoxCPM2, Fish S2 Pro, etc.)** — v1.x or v2.
- [ ] **Real client audio (post-NDA, post-data-handling-review)** — Phase 2 founding-partner pilot.
- [ ] **Cloud-LLM fallback measurement (FR-R49)** — only if Phase 1 surfaces a need.

## Feature Prioritization Matrix

| Feature | Stakeholder Value | Implementation Cost | Priority |
|---------|-------------------|---------------------|----------|
| G1 latency harness (with per-stage decomposition) | HIGH | HIGH | P1 |
| G5 UPL probe harness | HIGH | HIGH | P1 |
| ROCm validation on MI300X (incl. Kokoro swap) | HIGH | HIGH | P1 |
| Evaluation asset curation (all 5 corpora) | HIGH | HIGH | P1 |
| Synthesis report with derated predictions | HIGH | MEDIUM | P1 |
| G2 STT WER harness | HIGH | MEDIUM | P1 |
| G3 turn-detection harness | HIGH | MEDIUM | P1 |
| G7 TTS A/B harness | HIGH | MEDIUM | P1 |
| CUDA pre-flight on H100 | MEDIUM (risk reduction) | MEDIUM | P1 |
| G.711 transcoding pipeline | HIGH (blocking) | LOW | P1 |
| Cloud provisioning + cost cap | HIGH (blocking) | LOW | P1 |
| Feasibility memo v0.4 | HIGH | LOW | P1 |
| Phase 0 gate decision package | HIGH | LOW | P1 |
| Reproducibility tooling (hash pins, manifests) | HIGH | MEDIUM | P1 |
| Confidence intervals on predictions | HIGH | MEDIUM | P2 |
| Documented derating methodology | HIGH | MEDIUM | P2 (within synthesis report) |
| STT preprocessing ablation | MEDIUM | LOW | P2 |
| Turn-detector threshold sweep | MEDIUM | LOW | P2 |
| TTS edge-case A/B augmentation | MEDIUM | LOW | P2 |
| "What we did not measure" section | HIGH | LOW | P2 |
| Light concurrency probe | MEDIUM | MEDIUM | P3 |
| UPL nightly regression scaffold | MEDIUM | LOW | P3 |
| Cost telemetry per gate | MEDIUM | LOW | P3 |
| G4 (concurrency, full) | — | — | OUT OF SCOPE |
| G6 (deferred) | — | — | OUT OF SCOPE |
| Real client audio | — | — | ANTI-FEATURE |
| Local Strix validation | — | — | OUT OF SCOPE |
| Production runtime code | — | — | ANTI-FEATURE |

**Priority key:**
- P1: MVP — Phase 0 is incomplete without these.
- P2: Should-have — promote into Phase 0 if budget/time allow; meaningfully strengthens the deliverable.
- P3: Stretch — directional value, only if everything above is done and budget remains.

## Mapping Back to Gates

Explicit map from features to gate IDs and PRD success metrics:

| Gate | PRD §10 Metric | Phase 0 Status | MVP Features Required |
|------|----------------|----------------|-----------------------|
| G1 | SM-66, SM-67 (latency p90 < 900ms / p99 < 1200ms) | IN SCOPE | G1 latency harness, 500-call corpus, ROCm validation, per-stage decomposition |
| G2 | SM-68 (STT WER < 12% neutral / < 18% stressed) | IN SCOPE | G2 STT harness, 200 G.711 clips, G.711 transcoding pipeline |
| G3 | SM-69 (turn-detection FP < 2%) | IN SCOPE | G3 harness, hesitation adversarial set |
| G4 | SM-70 (concurrency=4 at G1 latency) | DEFERRED | (light probe in P3 stretch only) |
| G5 | SM-71 (UPL pass 100%) | IN SCOPE | G5 harness, 200 UPL probes |
| G6 | (deferred per scope) | DEFERRED | none |
| G7 | SM-72 (TTS preference ≥ 60%) | IN SCOPE | G7 A/B harness, 30-pair set, 5 listeners |

Gates not appearing in §10 success metrics (SM-73 through SM-79) are explicitly out of Phase 0 — they require production telemetry, audit logs, or boot telemetry that does not exist in a cloud benchmark.

## Sources

- `/home/bob/RBOX/.planning/PROJECT.md` — Active requirements, Out of Scope, Constraints, Key Decisions (HIGH confidence — operator-authored, current)
- `/home/bob/RBOX/receptionbox-technical-prd-v0_2-2026-05-03 (1).md` §10 (Technical Success Metrics SM-66 through SM-79), §11 (Technical Risk Register), §12 (DR-25 through DR-30), §14 (Phase Plan — Phase 0 deliverables) (HIGH confidence — authoritative PRD)
- `receptionbox-virtual-benchmark-plan-v0_1-2026-05-03.md` — referenced as authoritative on Phase 0 procedures (NOT YET READ — operator pending drop into repo; cited by PRD §14 and PROJECT.md context. MEDIUM confidence on procedural specifics until that doc lands.)
- `receptionbox-technical-feasibility-memo-v0_3-2026-04-23.md` — referenced as the doc to be revised to v0.4 as Phase 0 deliverable (NOT YET READ — operator pending drop into repo. LOW confidence on its current content; HIGH confidence on the fact that it's the v0.4 target.)

---
*Feature research for: voice-AI cloud benchmark suite (Phase 0 of receptionBOX)*
*Researched: 2026-05-04*
