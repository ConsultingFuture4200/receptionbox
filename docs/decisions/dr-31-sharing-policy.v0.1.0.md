# DR-31: Phase 0 Sharing Policy

**File version:** v0.1.0
**Status:** Approved 2026-05-06
**Decided by:** Claude drafted (per CONTEXT.md "Claude's Discretion" mandate); operator approves
**Decision date:** 2026-05-04
**Resolves:** NC-R14 (PRD §13)
**Phase:** Phase 1 Foundation — gates phase completion (ROADMAP success criterion #3)

## §1 Decision (operator-facing)

receptionBOX Phase 0 produces *cloud* benchmark data (RunPod H100 / TensorWave MI300X)
that is *derated* to predict Strix Halo (gfx1151) appliance behavior. The cloud
numbers and the derated predictions are NOT the same kind of evidence and must
not be conflated when sharing with the inbound large-law-firm lead.

This decision establishes how Phase 0 outputs may travel into sales material,
the discovery SOW, and partner-facing artifacts before the firm signs the
discovery engagement.

### §1.1 Stance (locked)

| Audience | What may be shared pre-SOW | What must NOT be shared pre-SOW |
|----------|---------------------------|----------------------------------|
| Inbound firm lead | Methodology summary; prediction range (e.g., "p90 estimated 750-1100ms band on appliance"); gate verdicts (pass/soft-pass/fail) using band upper bound | Raw cloud numbers; per-stage MI300X measurements; specific gate scores at point estimates |
| Internal (Eric, Dustin, UMB) | All Phase 0 numbers | — |
| Discovery-engagement-signed firm | All Phase 0 numbers (post-SOW) | — |

### §1.2 Two-tier presentation rule (MANDATORY)

When ANY appliance-relevant number travels outside the harness — sales artifacts,
synthesis report, feasibility memo v0.4 fragment, partner update, etc. — it MUST
appear in two-tier form:

> **Measured (cloud):** {value} on MI300X / H100, N={n}, 80% CI=[lo, hi]
> **Predicted (Strix Halo appliance):** {derated_band_lower}–{derated_band_upper}, derated per §Methodology

A single-tier number ("the latency is X ms") is forbidden in any external context.
Phase 4 synthesis report (REPORT-05) enforces this in the sales-safe excerpt.

### §1.3 PRD-update review gate

Any sales artifact (pitch deck, partnership PDF, email reply, partner worksheet)
that proposes referencing Phase 0 results MUST first ground the claim in an
updated PRD (parent thUMBox or receptionBOX) per §0.5 authority hierarchy. The
PRD update is the audit trail; the sales artifact is downstream.

If a Phase 0 finding contradicts an existing PRD, the PRD updates BEFORE the
sales artifact moves. (Cited from CLAUDE.md: "Any Phase 0 finding that
contradicts a higher-authority doc requires updating that doc before sales
material moves.")

## §2 External-sharing rules (firm-facing rationale)

If the firm asks "what's the latency on the appliance?" before signing the
discovery SOW, the receptionBOX team responds with the prediction range and an
explicit caveat:

> "Phase 0 produces *predicted* appliance latency by derating measurements taken
> on cloud hardware. The 80% confidence band on the predicted appliance latency
> is X-Y ms. Final appliance numbers come from Phase 1 hardware validation,
> which begins after the discovery engagement is signed."

Reasoning the firm must be able to follow:
1. The benchmark hardware (MI300X) is not the appliance hardware (Strix Halo)
2. The methodology applies a per-stage roofline derate plus an explicit
   compute-vs-bandwidth classification (see §Methodology in synthesis report)
3. The prediction explicitly includes uncertainty (gfx1151 kernel-coverage
   gap; Q4_K_M ↔ AWQ-Int4 substitution error; Ollama overhead)

## §3 Caveats

### §3.1 What this policy does NOT cover

- Internal sharing within UMB Group (full disclosure permitted)
- Post-SOW disclosure (full disclosure permitted; firm has signed)
- Engineering documentation outside `docs/decisions/` and `docs/feasibility-memo-*.md` (treated as internal by default)

### §3.2 Provider-asymmetry transparency

Phase 0 measures cloud cost via three providers with documented asymmetry
(Pitfall B/C in RESEARCH.md): Vultr has a documented billing API; RunPod uses
a "$75 prepaid credit" cap mechanism (no programmatic cumulative-cap API);
TensorWave's billing API is undocumented as of May 2026. The reproducibility
manifest (REPRO-05, Phase 4) records this asymmetry. It does not affect the
appliance prediction but is named so external reviewers can audit our cost
discipline.

### §3.3 Generic-firm reference prompt caveat (carryover from D-08)

G5 UPL guardrail evaluation uses a generic-firm reference prompt
(assets/reference_prompt.md). The synthesis report (REPORT-04) reproduces the
caveat verbatim:

> "G5 results are evaluated against a generic-firm reference prompt. The
> firm-customized production prompt requires a re-run of the probe suite
> during Phase 1 discovery before any go-live."

This caveat is unstrippable in any sales-safe excerpt that includes G5 numbers.

### §3.4 Soft-pass framing (DR-28)

Per DR-28 (PRD §14), Phase 0 may produce "soft pass with caveats" outcomes.
G3 (turn detection) is the most likely candidate because the hesitation
adversarial set is TTS-generated only (D-03). When the firm asks about
turn-detection performance, the soft-pass framing is shared with its caveat
("synthetic-only adversarial set; real-PSTN performance requires Phase 1
acoustic validation").

## §4 Enforcement and review

- This decision is reviewed by the operator at each milestone boundary
  (currently milestone v0.4)
- File version follows operator preference: `dr-31-sharing-policy.v0.1.0.md`
  (semver per CLAUDE.md operator-global rules; bump patch for typos, minor for
  added sections, major for stance changes)
- Phase 4 synthesis report (REPORT-05) is the primary enforcement surface;
  any sales-safe excerpt that violates the two-tier rule fails review

## Sources

- receptionBOX PRD v0.2 §0.5 (authority hierarchy)
- receptionBOX PRD v0.2 §13 (NC-R14 — sharing question)
- `.planning/research/PITFALLS.md` Pitfall 10 (sales-artifact / PRD drift)
- `.planning/phases/01-foundation/01-CONTEXT.md` (Claude's Discretion: DR-31)
- `CLAUDE.md` (file versioning convention)
