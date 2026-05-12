# Phase 3: ROCm Validation - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-10
**Phase:** 03-rocm-validation
**Areas discussed:** MI300X provider + Day-1 substrate; Chatterbox kill-switch criteria + Kokoro fallback policy

---

## Gray Area Selection

| Option | Description | Selected |
|--------|-------------|----------|
| MI300X provider + Day-1 substrate | TensorWave (sales pending) vs Vultr (ready) vs both. Determines orchestration adapter wired first; Day-1 Chatterbox substrate. | ✓ |
| Chatterbox kill-switch criteria + Kokoro fallback policy | Day-1 pass criteria, timebox before flipping, downstream propagation. Dominant scope-shrink lever. | ✓ |
| G2 dual-path STT mechanism (faster-whisper INT8 + ONNX-RT ROCm) | Same pod sequential vs separate pods vs same runner emitting two rows. | (deferred to Claude's Discretion) |
| G1 concurrency rig (N=1/2/4) + co-residency stack-load profile | Existing harness only does conc=1; how to drive 2/4 concurrent calls. | (deferred to Claude's Discretion) |

---

## Area: MI300X provider + Day-1 substrate

### Q1: Day-1 substrate

| Option | Description | Selected |
|--------|-------------|----------|
| Vultr now (Recommended) | Vultr MI300X provisioned + adapter-verified per STATE; $1.85/hr; start today. Wire vultr_mi300x.py first; add tensorwave_mi300x.py when sales unblocks. | ✓ |
| Wait for TensorWave | $1.71/hr, AMD-first, easier per user reports. Sales pending. Day-1 work blocks indefinitely. | |
| Both: build adapters in parallel | Implement both to real-provisioning. Day 1 on Vultr; switch later. More upfront work. | |

**User's choice:** Vultr now (Recommended) — keep off the sales-cycle critical path.

### Q2: Image strategy

| Option | Description | Selected |
|--------|-------------|----------|
| Separate rbox-pod-rocm image (Recommended) | New Dockerfile FROM rocm/vllm:rocm6.4_mi300_*. Mirrors v18 patterns (ENTRYPOINT, GIT_COMMIT, RBOX_IMAGE_DIGEST). Separate digest pin. | ✓ |
| Unified rbox-pod with --build-arg RAIL=rocm\|cuda | One Dockerfile, conditional install. Less surface but heavier and slower. | |
| rbox-pod-rocm built off devnen Chatterbox-TTS-Server image | Trades base-image control for Chatterbox-readiness. Higher coupling to community fork — bad reproducibility. | |

**User's choice:** Separate rbox-pod-rocm image (Recommended).

### Q3: Per-gate max_minutes ceilings

| Option | Description | Selected |
|--------|-------------|----------|
| Wider ceilings to fit full corpora (Recommended) | g1=120, g2=45, g3=20, g5=30, g7=45. ~$11.7/sanity at Vultr. Inside $54. | ✓ |
| Tight ceilings + iterative — burn ladder | Match Phase 2 (30/15/10/15) + subset corpora first. Lower per-pod risk; more pod transitions. | |
| Default 30 min, tune after Day-1 | Pragmatic; defers a knowable decision. | |

**User's choice:** Wider ceilings (Recommended).

### Q4: Cost-tracking

| Option | Description | Selected |
|--------|-------------|----------|
| Wall-clock × $/hr estimate per provider (Recommended) | Tensorwave: estimate from wall-clock. Vultr: real billing via existing /v2/billing/pending-charges adapter. Audit log writes both. | ✓ |
| Block ROCm gates until TensorWave billing API access lands | Most defensible cost-rail purity; blocks Day-1 indefinitely. | |
| Vultr only for cost-tracked work; TensorWave only when budget headroom obvious | Splits substrate by cost-tracking confidence. | |

**User's choice:** Wall-clock × $/hr per provider (Recommended).

---

## Area: Chatterbox kill-switch criteria + Kokoro fallback policy

### Q1: Pass criteria

| Option | Description | Selected |
|--------|-------------|----------|
| Loads + synthesizes 30s test text + outputs valid PCM (Recommended) | Container starts, GPU device count > 0, /v1/audio/speech 200 within 60s, sf.read parses, RMS > 0.01. No latency in kill-switch (that's G7). | ✓ |
| Loads + synthesizes + first-audio latency under 1s | Adds latency check. Mixes kill-switch with G7 measurement; thermal/first-pull variance risk. | |
| Loads + clones reference voice + audible cloned output | Most thorough; most surface area to fail. Mixes Chatterbox kill-switch with G7 quality. | |

**User's choice:** Loads + synthesizes + valid PCM (Recommended).

### Q2: Timebox

| Option | Description | Selected |
|--------|-------------|----------|
| 2 hr wall-clock, $4 spend cap (Recommended) | Generous enough for 1-2 ROCm install issues; small enough not to sink the day. ~2.3 hr at Vultr $1.71/hr. | ✓ |
| 4 hr wall-clock, $8 spend cap | Buys debugging room. Risk: half a Phase-3 day on one risk that may not be solvable today. | |
| 1 hr / $2 — fail fast, Kokoro by lunch | Most aggressive. Risk: 90-min fixable issue gets miscategorized as fundamental. | |

**User's choice:** 2 hr / $4 (Recommended).

### Q3: Fallback shape

| Option | Description | Selected |
|--------|-------------|----------|
| Config-row in config/sanity_strata.yaml + substrate respects it (Recommended) | tts.primary: chatterbox\|kokoro. substrate/rocm.py:synthesize() reads it; DR-27 fallback still applies. P3.7 engine-swap flips this row. Single source of truth. | ✓ |
| Env var TTS_PRIMARY at pod boot — simpler but per-pod | No engine-swap-under-load (P3.7) without pod restart. | |
| Code-level constant + redeploy on flip | Maximum auditability via git log; zero runtime flexibility for P3.7. | |

**User's choice:** Config-row mechanism (Recommended).

### Q4: Decision audit trail

| Option | Description | Selected |
|--------|-------------|----------|
| .planning/STATE.md + Linear DEV-1022 + audit/chatterbox_d1_decision.md (Recommended) | Three artifacts: state line, Linear comment, long-form audit doc with install commands, prompts, output WAV SHA, GPU evidence. Phase 4 cites the audit doc. | ✓ |
| Linear comment only | Lightweight; Linear is offline-prone. | |
| audit/ directory only — git is the audit trail | Cleaner git-only provenance; loses cross-team visibility. | |

**User's choice:** All three artifacts (Recommended).

---

## Claude's Discretion

The following gray areas were deferred — defaults captured in CONTEXT.md `<decisions>` Claude's Discretion subsection:

- G2 dual-path mechanism (P3.3) — default: same gate runner, two rows per asset, sequential within a single pod
- G1 concurrency rig (P3.2) — default: `--concurrency N` flag, `asyncio.gather`d, three pods at N=1/2/4
- Co-residency stack-load profile (P3.7) — default: 5-min sustained replay of 500-call corpus slice at N=2 with all three model classes loaded
- gfx1151 op coverage audit method (P3.8) — default: `tools/audit_op_coverage.py` captures op-by-op kernel dispatch, cross-references against gfx1151 kernel registry

Operator can override any of these by editing CONTEXT.md before plan-phase.

## Deferred Ideas

(See CONTEXT.md `<deferred>` section for the full list — TensorWave provisioning timing, Strix Halo live comparison, hot-reload engine swap, concurrency beyond N=4, make verify-provenance target, multi-pack co-residency, cloud LLM fallback.)
