# Phase 1: Foundation - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in `01-CONTEXT.md` — this log preserves the alternatives considered.

**Date:** 2026-05-04
**Phase:** 01-foundation
**Areas discussed:** Asset corpus generation pipeline, ASSETS-05 reference prompt content, Harness shape (substrate ABC + result schema)
**Areas declined:** DR-31 sharing policy (NC-R14) — defaulted to defensive default per PROJECT.md

---

## Gray-area selection

| Area | Description | Selected |
|---|---|---|
| Asset corpus generation pipeline | Producing all 5 corpora under zero-GPU + ~40hr budget | ✓ |
| DR-31 sharing policy (NC-R14) | Pre-SOW sharing stance, sales-artifact discipline | |
| ASSETS-05 reference prompt content | UPL evaluation prompt shape | ✓ |
| Harness shape (substrate ABC + result schema) | Streaming/async/return types + result storage | ✓ |

---

## Asset corpus generation pipeline

### 500-call conversation corpus (G1)

| Option | Description | Selected |
|--------|-------------|----------|
| LLM-author + local-CPU TTS render | Claude-generates 500 dialogue scripts, render with Kokoro-82M on local CPU; free; ~4-8hr unattended | |
| LLM-author + cloud TTS API (paid) | Same scripts, ElevenLabs/OpenAI TTS render; ~$5-15; ~30 min | |
| Curate open-licensed legal audio | LibriVox / podcasts / mock-trial; 12-15hr curation | |
| Hybrid: LLM scripts + render + open clips | Best epistemic coverage; highest implementation cost | |

**User's choice:** Option 1 modified — LLM-author + render on **local GTX 1070 (not CPU)**.
**Notes:** Operator clarified hardware: dual GTX 1070 + i7 + Biostar TB250-BTC. Hardware feasibility confirmed (Kokoro-82M on Pascal sm_61, ~20-50× realtime, ~30-60 min wall clock total). Pascal sm_61 PyTorch wheel availability flagged (pin ≤ 2.5.x). Mining-board PCIe x1 caveat noted (model load slow, inference fine). Don't run Chatterbox on Pascal — flow-matching prefill on no-tensor-cores hurts. Kokoro is the right pick for *generating* the corpus regardless of which TTS gets evaluated in G7.

### Hesitation adversarial set (G3)

| Option | Description | Selected |
|--------|-------------|----------|
| TTS-generated only, document the gap | Kokoro-rendered hesitations; soft-pass with caveats per DR-28 | ✓ |
| Two-source: TTS + open-licensed clips | Adds LibriVox/CommonVoice rejected clips; +4-6hr | |
| Three-source: TTS + open + operator-recorded | Pitfall 6 ideal; +6-10hr including recording | |

**User's choice:** TTS-generated only.
**Notes:** Synthesis report frames G3 result as "soft pass with caveats." Pitfall 6 gap named, not hidden. Three-source backlog'd to Phase 1 discovery.

### UPL probe authorship (200 + 50 control)

| Option | Description | Selected |
|--------|-------------|----------|
| Claude-author, operator-review, content-free by construction | Claude generates against category matrix; operator reviews each before commit | ✓ |
| Adapt from public prompt-injection corpora + Claude legal-domain | Garak/PromptBench injection axis; Claude legal axes; license review needed | |
| Operator hand-authors entire suite | Highest control; 8-12hr operator time | |

**User's choice:** Claude-author + operator-review.
**Notes:** Pitfall 7 (CRITICAL — regulatory exposure) drove this area. Category matrix locked at ≥30 prompt-injection, ≥20 fee-quote, ≥20 SoL, ≥20 case-outcome, ≥20 procedural-deadline, balance generic. Public-corpus integration deferred to Phase 1 discovery.

### 200 G.711 clips (G2) and 30 TTS pairs (G7)

**Defaulted (no question asked):**
- 200 G.711 = stratified subset of the 500-call corpus (100 neutral / 100 stressed by adversity-level metadata), transcoded via `ffmpeg aresample=resampler=soxr:precision=28 -c:a pcm_mulaw`. Spectral-mask validated against one Twilio→Twilio reference (Pitfall 4).
- 30 TTS pairs = hand-authored text scripts in Phase 1 (legal terminology, numbers, proper nouns). Clone-reference clip = synthetic operator-style sample. Actual A/B render is Phase 3 work.

---

## ASSETS-05 reference prompt content

| Option | Description | Selected |
|--------|-------------|----------|
| Generic-firm shape, permissive-default | Realistic placeholder firm + 3 practice areas; explicit refusal categories; permissive enough to surface escapes | ✓ |
| Deliberately conservative shape | Tighter refusal language; easier G5 pass; HIGHER false-pass risk per Pitfall 7 | |
| Two-prompt comparison run | Build both, run both, report the gap; +harness work, +2× G5 runtime | |

**User's choice:** Generic-firm shape, permissive-default. Preview accepted verbatim.
**Notes:** Preview content locked into `assets/reference_prompt.md` (5 refusal categories: fees & rates, SoL, case outcome, procedural deadlines, substantive legal; two refusal phrasings). Synthesis report MUST include unstrippable caveat: "real firm prompt requires re-run during Phase 1 discovery before go-live." Two-prompt comparison run deferred to Phase 3 backlog.

---

## Harness shape (substrate ABC + result schema)

### Substrate ABC interface

| Option | Description | Selected |
|--------|-------------|----------|
| Async + streaming returns | `async def`, `AsyncIterator[Chunk]`; matches LiveKit Agents 1.x natively | ✓ |
| Sync + batch returns | Simpler; doesn't expose TTFT/first-audio natively; G1 needs manual wrapping | |
| Hybrid: streaming + batch convenience wrappers | Maximum flexibility; biggest API surface | |

**User's choice:** Async + streaming. Preview accepted verbatim.
**Notes:** ABC method signatures locked from preview. `generate()` accepts optional `Grammar` for xgrammar-constrained generation (G5). Gate runners may NOT import torch/onnxruntime/vllm directly (HARNESS-01 enforced).

### Result schema and storage

| Option | Description | Selected |
|--------|-------------|----------|
| JSONL primary, SQLite index, Parquet on demand; error rows kept | Errors visible (`status='error'`), Liotta-survivable; SQLite rebuilt by `make report` | ✓ |
| SQLite primary, JSONL audit log; errors not stored as rows | Faster query; reconciliation burden | |
| Parquet primary, DuckDB query layer | Compression + analytical speed; Phase 0 volume too small to justify | |

**User's choice:** JSONL + SQLite index + Parquet on demand. Preview accepted verbatim.
**Notes:** GateResult pydantic schema locked from preview. Error rows keep schema with NULL measurements + populated `error_kind`/`error_msg`. `env.json` sidecar emitted per run.

---

## Companion documents (DECISION-DOCS) — status check

| Option | Description | Selected |
|--------|-------------|----------|
| Available now — will drop into docs/ this week | Operator has files; explicit Phase 1 task | ✓ |
| Available but not yet copied — do during Foundation | Files exist; checklist item | |
| Some missing / need to fetch — may delay Phase 1 close | Risk flag; planner schedules drop early | |
| Already done — ignore | Files already in docs/ | |

**User's choice:** Available now — will drop during Phase 1 execution.
**Notes:** All 5 companion docs (parent thUMBox tech+business v2.1, discovery addendum v0.2, hardware-pivot addendum v0.1, feasibility memo v0.3, virtual benchmark plan v0.1) locally available. Planner includes drop as explicit early task.

---

## Claude's Discretion

User declined to discuss DR-31 sharing policy (NC-R14). Defensive default from PROJECT.md applies; Claude drafts `docs/decisions/dr-31-sharing-policy.md` against PRD §13 + Pitfall 10. Stance: methodology + prediction range only pre-SOW; PRD-update review gates any sales-artifact reference; two-tier (Measured/Predicted) presentation mandatory.

Other Claude-discretion items (not surfaced as questions):
- Cost ledger projection mechanism — static per-gate config in `config/budget.yaml` × 1.5 safety
- Pre-commit no-real-audio assertion shape — manifest-presence check via grep over `assets/`
- Foundation execution wave order — planner decides

---

## Deferred Ideas

- Two-prompt comparison run (permissive vs conservative) for G5 — Phase 3 backlog if budget allows
- Three-source hesitation set with operator-recorded human samples — Phase 1 discovery backlog
- Public prompt-injection corpora (Garak, PromptBench) integration — Phase 1 discovery
- Cloud TTS API rendering path (ElevenLabs/OpenAI) — fallback if local Kokoro insufficient
- Dynamic cost-projection refinement from prior-run actuals — Phase 4 candidate
