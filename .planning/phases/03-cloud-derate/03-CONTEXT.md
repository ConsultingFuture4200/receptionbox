# Phase 03: cloud-derate — Context

**Gathered:** 2026-05-12
**Status:** Ready for planning
**Source:** DR-39 v0.3.0 methodology refinement (ratified 2026-05-11) + CLAUDE.md as authoritative tech-stack pin
**Supersedes:** `.planning/phases/03-rocm-validation-archived/03-CONTEXT.md` (pre-pivot, ROCm-centric — NOT to be revived)

<domain>
## Phase Boundary

Produce derated Jetson AGX Orin 64GB predictions for receptionBOX Phase 0 gates (G1, G2, G3, G5, G7) and audits (AUDIT-01 co-residency, AUDIT-03 engine-swap) by:

1. **Measuring on RunPod NVIDIA H100 PCIe / SXM** (the same substrate validated in Phase 02; `substrate/cuda.py` + `orchestration/runpod_h100.py` reused as-is).
2. **Derating measurements to Orin 64GB** using a **spec-sheet ratio + NVIDIA's published Jetson Orin Performance Benchmarks** (developer.nvidia.com/embedded/jetson-orin-benchmarks) as the cross-substrate basis. Same-vendor, same-stack (CUDA 12.x → JetPack 6 CUDA 12.x), one-hop derate chain.
3. **Producing a synthesis-ready evidence pack** that Phase 4 can use to build the feasibility memo with bounded confidence intervals.

**Out of scope:**
- Any AMD ROCm path (MI300X, gfx1151, Strix Halo, Chatterbox-ROCm forks, Kokoro-ROCm, devnen-fork install). Entire AMD rail killed by DR-39.
- Orin Developer Kit purchase (~$2k, ~1 week ship) — **deferred to post-Phase-0** per CLAUDE.md §1.1 and DR-39 v0.3.0 §11. Phase 3 critical path is **cloud-only**.
- GATE-CHATTERBOX-D1 (already validated on Phase 02 H100 smoke), AUDIT-02 gfx1151 op-coverage (no AMD silicon).
- Production Orin deployment, JetPack 6 image build, TensorRT-LLM Orin port — all are Phase 1+ work.

</domain>

<decisions>
## Implementation Decisions

All decisions below are **locked** by CLAUDE.md (rewritten 2026-05-11 for DR-39) and the DR-39 v0.3.0 methodology document. Planner MUST honor them.

### Measurement substrate
- **RunPod Secure Cloud** — H100 PCIe 80GB (~$2.39/hr) or H100 SXM 80GB (~$2.69/hr) on-demand, per-second billing. Reused from Phase 02 (account live, `RUNPOD_API_KEY` in env, `substrate/cuda.py` validated, `orchestration/runpod_h100.py:_DEFAULT_IMAGE` pinned to v18 `sha256:abcf19f8…ea9d217`).
- **No H200** unless H100 stock is out and H200 is cheaper-equivalent — H200 would only inflate the cloud→Orin gap and complicate the derate. Default to H100.
- **No MI300X.** No TensorWave. No Vultr. No Lambda. No CoreWeave. No Modal/Replicate/Banana. (All explicitly killed per CLAUDE.md §11.)

### Derate target
- **NVIDIA Jetson AGX Orin 64GB** (PRD-locked SoC per DR-39).
- Per CLAUDE.md §7 (derating methodology):
  - **Decode tokens/sec**: bandwidth-bound (batch=1). Ratio: H100 SXM 3350 GB/s → Orin 204 GB/s ≈ 16.4× slower.
  - **LLM TTFT prefill**: compute-bound. FP16 ratio: H100 SXM 989 TFLOPS → Orin 32 TFLOPS ≈ 31×. INT8 ratio: 3957 TOPS → 275 TOPS ≈ 14× (mitigates via W8A8 / AWQ-Int4).
  - **STT Whisper encoder + TTS prefill**: same compute-bound logic.
  - **Production runtime overhead**: Phase 0 measures vLLM on H100; production Orin uses Ollama (llama.cpp). Add **1.3–1.5× Ollama overhead** to LLM stages in the derate.
  - **CPU/ARM integration penalty**: 10–20% conservative addition (Orin's 12-core ARM Cortex-A78AE vs EPYC/Xeon).
- **Cross-check** every derated number against NVIDIA's published Jetson Orin Performance Benchmarks page (Whisper, Qwen2/3, generic LLM throughput) — flag any prediction that diverges >50% from the NVIDIA-published number for a similar workload.

### Model stack (locked, CLAUDE.md §3-§5)
- LLM: **Qwen3-4B** — AWQ-Int4 on H100 measurement / Q4_K_M (llama.cpp) on production Orin. Document the substitution explicitly in synthesis. vLLM 0.10+ with `--guided-decoding-backend xgrammar` for G5 grammar-constrained generation.
- STT: **distil-whisper-large-v3 INT8** — faster-whisper 1.x (CTranslate2 CUDA backend). Same engine across H100 measurement and Orin deployment.
- TTS primary: **Resemble AI Chatterbox-Turbo** (mainline CUDA — DR-27 risk DEAD under DR-39).
- TTS fallback: **hexgrad Kokoro-82M** (remsky/Kokoro-FastAPI mainline; ONNX option available).
- VAD: **silero-vad v5**; turn: **LiveKit `turn-detector` plugin**.

### Pipeline orchestration
- **LiveKit Agents 1.x Python SDK** for E2E latency rig (matches PRD §4.2 production agent-worker).
- Substrate-agnostic gate runners from Phase 02 (`gates/_runner_base.py` + per-gate concrete classes) reused as-is.

### Reproducibility (CLAUDE.md §9)
- HF revision pinning by SHA (already populated for all 4 models in `bench/models.lock.yaml`).
- Docker image digest pinning (rbox-pod v18 already pinned).
- Per-run env.json sidecar emission via Phase 02 substrate fingerprint code.
- All result JSONLs committed to repo as raw evidence.

### Budget (CLAUDE.md §13)
- **Phase 0 ceiling: ~$50 cloud spend**, hard cap. Per-gate estimates:
  - Setup + smoke tests: $5
  - G1 latency (500 calls): $12
  - G2 STT WER (200 clips): $4
  - G3 turn detection: $1
  - G5 UPL probes (200): $3
  - G7 TTS A/B (30 pairs): $4
  - Re-runs/contingency: $10
  - Storage/idle: $10
  - **Total: ~$49**
- AST-asserted ledger gate (`tests/test_orchestration_skeletons.py::test_orchestration_modules_call_authorize_spend_first`) enforces `authorize_spend()` FIRST in every `provision()`.

### Synthesis / reporting (CLAUDE.md §7.3, §10)
- Per gate: raw H100 measurements (N, mean, p50, p90, p99) + bootstrap 95% CIs.
- Per gate: derated Orin predictions with explicit ratio used, FP16/INT8/bandwidth assumption stated, NVIDIA-published-benchmark cross-check.
- "What we do NOT know" section: real PSTN audio vs synthetic μ-law, Ollama-vs-vLLM sustained-load behavior on Orin, MAXN power-mode sustained behavior, TensorRT-LLM Orin speedup, CPU/ARM integration penalty exactness.
- **Post-Phase-0 validation plan**: ONLY after Phase 0 gate decision passes, buy 1× Jetson AGX Orin 64GB Developer Kit (~$2k, ~1 week), run the same harness, confirm predicted ratios within ±20%, re-issue synthesis as v0.2 with measured-vs-predicted comparison. NOT in Phase 3 scope.

### Claude's Discretion (planner decides within these guardrails)
- Plan granularity / wave grouping. Suggest: one plan per gate (G1, G2, G3, G5, G7), plus a synthesis-prep plan, plus one consolidating audit plan covering AUDIT-01+AUDIT-03.
- Whether AUDIT-01 + AUDIT-03 fold into G1's pod session (efficient — all 4 models co-resident anyway during G1) or get their own plan.
- Statistical sample sizes per gate within the published $-budget envelope.
- Order of gate execution. Recommend G1 last (most expensive) to fail-fast on cheaper gates first.

</decisions>

<canonical_refs>
## Canonical References

**Planner MUST read these before drafting any plan.** They are authoritative; CONTEXT decisions above derive from them.

### Methodology (authoritative)
- `./CLAUDE.md` — Tech-stack pins, DR-39 rationale, derate methodology §7, cost table §13, what-NOT-to-use §11
- `.planning/STATE.md` — Project state including DR-39 ratification + methodology refinement entries
- `.planning/PROJECT.md` — Project-level decision log
- `.planning/REQUIREMENTS.md` — REQ-NN traceability

### Inherited from Phase 02 (load-bearing, do NOT modify)
- `substrate/cuda.py` — `CUDASubstrate(Substrate)` ABC implementation, env_fingerprint, DR-27 TTS fallback
- `substrate/adapters/` — 4 backend adapters (VLLMClient, FasterWhisperEngine, ChatterboxClient, KokoroClient)
- `substrate/livekit_pipeline.py` — D-15 `build_session()`
- `gates/_runner_base.py` — substrate-agnostic GateRunner base (REPRO-03 enforcement)
- `orchestration/runpod_h100.py` — `_DEFAULT_IMAGE` pinned to v18 digest, AST-asserted authorize_spend ordering
- `tools/pod_entrypoint.sh` — pod entrypoint with audit + rsync teardown
- `tools/audit_pod_state.py` — pre-teardown D-22/D-23 audit (manifest/extension/PII)
- `tools/run_preflight.py` — bootstrap / smoke / sanity orchestrator
- `tools/fetch_results.py` — diag-pod result pull pattern
- `bench/models.lock.yaml` — HF revision-pinned model SHAs
- `bench/images.lock.yaml` — Docker image digest pins
- `cost/ledger.sqlite` — cost-tracking DB (gitignored; ledger code in `cost/`)

### Archive (FOR REFERENCE ONLY — do NOT carry forward any decisions)
- `.planning/phases/03-rocm-validation-archived/` — pre-DR-39 Phase 3 with 7 plans (4 obsolete, 3 redirect). Read only to understand pivot history; do NOT use as a planning template.

### External (cite, do not re-derive)
- developer.nvidia.com/embedded/jetson-orin-benchmarks — NVIDIA's published Jetson Orin Performance Benchmarks. **Derate-basis citation for synthesis.**
- developer.nvidia.com/embedded/jetson-agx-orin-developer-kit — Orin spec sheet
- nvidia.com/en-us/data-center/h100/ — H100 spec sheet
- docs.vllm.ai/en/latest/features/structured_outputs/ — xgrammar integration
- github.com/SYSTRAN/faster-whisper — STT engine docs

</canonical_refs>

<specifics>
## Specific Ideas

### Gates in scope (REWRITTEN per DR-39 v0.3.0)

| Gate | Measurement | Derate target | Reuse from Phase 02 |
|------|-------------|---------------|---------------------|
| G1 latency | 500-call corpus at N=1/2/4, full LiveKit pipeline on H100, per-stage timings | Orin via FP16 prefill + bandwidth-decode ratio + Ollama overhead + ARM penalty | LiveKit pipeline rig (substrate/livekit_pipeline.py); smoke validated on session 20260509T231720Z |
| G2 WER | faster-whisper INT8 on 200 G.711 clips (8 kHz μ-law transcoded to 16 kHz) | Orin via FP16 encoder ratio (same engine on both sides) | DEV-1083 fix verified; jow8x9kugpkgxm G2 row WER 2.55% baseline |
| G3 turn detection | silero-vad v5 + LiveKit turn-detector on adversarial hesitation set, threshold sweep 400-1500ms in 100ms steps | Semantic detector substrate-agnostic; latency component derates via FP16 ratio | gate runner base + livekit silero plugin |
| G5 UPL probes | 200 grammar-constrained UPL probes via vLLM xgrammar against receptionBOX-shaped reference prompt | Orin via INT8/AWQ TFLOPS ratio (xgrammar is CPU-side; LLM compute is GPU-side) | reference prompt at assets/, gate runner |
| G7 TTS A/B | Chatterbox-Turbo + Kokoro-82M, 30 stimulus pairs, warm-path + cold-path first-audio | Orin via FP16 prefill ratio (TTS transformer prefill is compute-bound) | TTS adapters validated on Phase 02 |
| AUDIT-01 co-residency | All 4 models simultaneously resident on one H100 pod, observe VRAM + cross-model latency interaction | N/A (verifies Orin 64 GB VRAM is sufficient) | bench/images.lock.yaml + substrate/cuda.py |
| AUDIT-03 engine-swap | Demonstrate Ollama-equivalent llama.cpp execution path on H100 to ground the 1.3-1.5× Ollama-vs-vLLM overhead factor used in derate | Direct measurement → derate-input scalar | Ollama package available in image; load Qwen3-4B Q4_K_M alongside vLLM AWQ-Int4 |

### Anticipated plan structure (planner refines)

Recommend ~5-7 atomic plans:
- 03-01: substrate harness audit + bootstrap (verify Phase 02 substrate still healthy on a fresh pod under the v18 image; sets the spend baseline)
- 03-02: G2 STT WER + G3 turn detection (cheap; ~$5 total; serves as integration smoke)
- 03-03: G5 UPL probes (~$3; verifies xgrammar path; surfaces any vllm regression)
- 03-04: G7 TTS A/B (~$4; closes Chatterbox/Kokoro question on H100)
- 03-05: AUDIT-01 + AUDIT-03 (co-residency + engine-swap; ~$3)
- 03-06: G1 latency (~$12; most expensive; runs LAST so cheaper gates have surfaced any regression first)
- 03-07: Derate synthesis prep (Python `pandas` + `scipy.stats.bootstrap` pipeline that ingests all gate JSONLs and produces the Orin-derated table for Phase 4 to format)

Planner has discretion to merge / split / reorder, but the FAIL-CHEAP-FIRST ordering principle (G1 last) is important.

</specifics>

<deferred>
## Deferred Ideas

- **Orin Developer Kit hardware validation** — buy + bench post-Phase-0 (~$2k, ~1 week ship), confirm derate within ±20%, re-issue synthesis as v0.2. NOT in Phase 3.
- **TensorRT-LLM Orin port** — 1.5-2× faster than Ollama per NVIDIA Jetson AI Lab; relevant to Phase 1+ capacity planning, NOT to Phase 0 gate decision.
- **Real PSTN audio benchmark** — Phase 0 uses synthetic μ-law only (PRD constraint). Real-call benchmark is post-discovery-SOW work.
- **JetPack 6 production image build** — Phase 1+.
- **MAXN power-mode sustained-load characterization** — needs hardware; deferred to post-Phase-0.
- **AMD ROCm reactivation** — preserved at git tag `pivot/strix-halo-end-state` and branch `archive/amd-rocm-substrate`. Reactivate only if product team reverses DR-39 (not in Phase 3 scope).

</deferred>

---

*Phase: 03-cloud-derate*
*Context gathered: 2026-05-12 (post-DR-39 v0.3.0)*
*Authority: CLAUDE.md (DR-39 rewrite) + DR-39 v0.3.0 methodology refinement*
