# Project Research Summary

**Project:** receptionBOX Phase 0 — Cloud Benchmark Validation
**Domain:** Cloud-GPU voice-AI benchmark harness producing derated Strix Halo (gfx1151) predictions for a commercial go/no-go gate
**Researched:** 2026-05-04
**Confidence:** MEDIUM-HIGH

## Executive Summary

Phase 0 is not a product build — it is a one-week, $150-ceiling, ~30–40-hour cloud benchmark *harness* whose only deliverable is a defensible derated prediction of receptionBOX latency/quality on AMD Strix Halo (Ryzen AI Max+ 395, gfx1151), packaged as a feasibility memo v0.4 update plus a sales-safe gate decision. Its commercial weight is asymmetric: a false pass walks UMB Group into a paid SOW the appliance cannot deliver; a false fail walks away from a real opportunity. The four research files converge on a single architectural conclusion — Phase 0 must be built as a substrate-abstracted, content-addressed, cost-capped harness that produces *per-stage roofline-derated* numbers with explicit confidence bands, not a single end-to-end multiplier. Anything less is not survivable under adversarial review and is not survivable as a SOW basis.

The recommended approach is a four-stage build: (A) foundation with zero GPU spend — repo skeleton, Substrate ABC, asset builders for all five corpora, cost ledger, reproducibility manifest; (B) RunPod H100 CUDA pre-flight (~$14, 6 GPU-hours) to assemble the LiveKit Agents → vLLM → faster-whisper → Chatterbox/Kokoro pipeline once on a known-working substrate; (C) TensorWave MI300X ROCm validation (~$54, 23 GPU-hours) running G1/G2/G3/G5/G7 against pinned 500-call / 200-G.711 / hesitation / 200-UPL / 30-pair corpora, including a co-residency stack-load test and gfx1151 kernel-coverage audit; (D) synthesis with per-stage derating, 80% confidence bands, sales-safe excerpt, and feasibility memo v0.4. Total projected spend ~$98 with ~$52 headroom against the $150 ceiling, contingent on Step 0 (account provisioning, cost-cap config, asset curation, manifest, reference prompt) being load-bearing rather than rushed.

The dominant risk is the **gfx942 (MI300X CDNA3) → gfx1151 (Strix Halo RDNA 3.5) kernel-availability gap**: a model that runs cleanly on MI300X can silently fall back to CPU on Strix Halo because PyTorch/ONNX-Runtime wheels lack compiled `gfx1151` kernels. This is invisible to a single-multiplier derating and is the single most likely path from a green Phase 0 to a red Phase 2. Mitigation is an explicit op-by-op kernel-coverage audit against the planned appliance ROCm minor + PyTorch wheel cut, an op-class-aware roofline derating per stage, and confidence intervals widened to reflect the LPDDR5X regime change. Secondary critical risks: UPL probes evaluated against a generic prompt rather than a receptionBOX-shaped prompt (regulatory exposure); cloud numbers leaking into sales material as if appliance numbers (NC-R14 unresolved); reproducibility decay between Phase 0 and Phase 1 (SHA-pinning is mandatory).

## Key Findings

### Recommended Stack

The harness is built around **vLLM 0.10+ with xgrammar** for grammar-constrained Qwen3-4B inference (AWQ-Int4 substituted for Q4_K_M on cloud, with the substitution explicitly documented), **faster-whisper 1.x INT8** for distil-whisper WER measurement, **devnen Chatterbox-TTS-Server** primary with **moritzchow Kokoro-FastAPI-ROCm** mandatory fallback, **silero-vad v5 + LiveKit turn-detector** for G3, and **LiveKit Agents Python SDK 1.x** for the E2E latency rig (matches production-runtime PRD §4.2 framework, de-risking Phase 1 simultaneously). Cloud substrates are **RunPod Secure Cloud H100** (CUDA pre-flight) and **TensorWave MI300X** primary / Vultr backup (ROCm validation). Reporting is plain `pandas + matplotlib + scipy.stats.bootstrap` with `jinja2`-templated Markdown — no dashboards.

**Core technologies:**
- **vLLM 0.10+ (ROCm + CUDA paths) with xgrammar backend** — LLM serve, grammar-constrained generation; AMD's MI300X flagship engine, ~100× faster guided decoding than `outlines`
- **faster-whisper 1.x (CTranslate2 INT8)** — STT WER measurement; ONNX-Runtime ROCm parallel path used for STT TTFT to match production
- **devnen Chatterbox-TTS-Server (ROCm fork) + moritzchow Kokoro-FastAPI-ROCm** — TTS primary + fallback; engine-swap is a Phase 0 deliverable
- **LiveKit Agents Python SDK 1.x with silero-vad v5 + turn-detector plugin** — E2E pipeline orchestration; per-stage timestamps native; same framework as production
- **TensorWave MI300X (~$1.71/hr) + RunPod H100 (~$2.39/hr)** — cloud substrates with provider-level cost caps + local cost-watch script (dual rails)
- **HF SHA-revision pinning + Docker image digest pinning + uv lockfile + git commit SHA** — reproducibility stack; non-optional
- **ffmpeg 7.x `pcm_mulaw` + soxr precision=28** — G.711 transcoding with explicit polyphase resampler; spectral-mask validation required
- **jiwer 3.x with Whisper BasicTextNormalizer** — WER scoring with pinned normalization

### Expected Features

Phase 0 "features" are gates, harnesses, and corpora — not user-facing functionality. Maps directly to PRD §10 SM-66 through SM-72 and DR-28 gate semantics.

**Must have (table stakes):**
- **G1 latency harness with per-stage decomposition** (SM-66/67) — 500-call corpus, p90 < 900ms / p99 < 1200ms; per-stage decomposition is MVP, not stretch
- **G2 STT WER on G.711 μ-law** (SM-68) — 200 clips, neutral + stressed, < 12% / < 18%
- **G3 turn-detection FP-rate** (SM-69) — hesitation adversarial set, < 2% FPR
- **G5 UPL guardrail probes** (SM-71) — 200 probes against a **receptionBOX-shaped reference prompt** (not generic), 100% pass with benign-question control set showing zero refusals
- **G7 TTS A/B preference** (SM-72) — Chatterbox-Turbo vs Kokoro-82M, 30 pairs, 5 listeners, ≥ 60% prefer cloned
- **CUDA pre-flight on H100** — pipeline assembles end-to-end before MI300X spend
- **ROCm validation on MI300X with engine-swap demonstration** — Chatterbox + Whisper + Qwen3-4B all load; Kokoro fallback proven; co-residency stack-load test
- **All 5 evaluation corpora curated with provenance manifest** — synthetic + open-licensed only, every asset SHA-pinned, no real client audio
- **Cloud account provisioning + dual cost-cap rails** — provider-side cap + local cost-watch script
- **Synthesis report with per-stage derated Strix Halo predictions and 80% confidence bands**
- **Feasibility memo v0.4 update + Phase 0 gate decision package with sales-safe excerpt**
- **Reproducibility tooling** — SHA-pinned weights, Docker digests, uv lockfile, git commit pin, canary re-run

**Should have (P2 — promote into MVP if hours allow):**
- **Confidence intervals on derated predictions** (already promoted — aggregate p90 cannot defend a derating)
- **STT preprocessing ablation** (RNNoise / DeepFilterNet on/off)
- **Turn-detector threshold sweep** (400–1500ms in 100ms steps)
- **Documented derating methodology** as standalone synthesis-report section
- **"What we did not measure" section**
- **TTS A/B with edge-case prompts** (numbers, proper nouns, legal terminology)

**Defer (P3 / out of scope):**
G4 concurrency benchmark (full); G6 (deferred); local Strix Halo validation; 30-day soak; real client audio (anti-feature); production runtime code; cloud-LLM fallback measurement; outbound calling/TCPA; multi-pack co-residency; additional TTS engines.

### Architecture Approach

Local control plane (Ubuntu 22.04, `~/RBOX`) — asset builders, cloud orchestrator, synthesis/reporting — pushes code+assets via rsync to ephemeral RunPod or TensorWave/Vultr GPU instances, where a **substrate-abstracted gate runner layer** invokes either `substrate/cuda.py` or `substrate/rocm.py` against pinned model caches. Results return to a content-addressed local result store (JSONL + Parquet + SQLite index), and `make report` is the single entrypoint that renders the synthesis Markdown and feasibility-memo fragment via pandas + jinja2. The cost ledger sits structurally between the orchestrator and any provisioning call — no GPU instance is spun up without a budget check.

**Major components:**
1. **Substrate Layer (`substrate/__init__.py` ABC)** — `load_stt`, `load_llm`, `load_tts`, `transcribe`, `generate`, `synthesize`, `env_fingerprint`; blocks gate runners from importing torch/onnxruntime directly
2. **Asset Builder + Content-Addressed Asset Store** — deterministic Python under `assets/builders/`, 5 SHA-pinned corpora with `manifest.json`; provenance line per asset is mandatory
3. **Cost Ledger + Cloud Orchestrator** — SQLite-backed budget enforcement, per-gate projection × 1.5× safety factor; in-instance watchdog auto-terminates after `max_minutes`
4. **Gate Runners (`gates/g{1,2,3,5,7}/runner.py`)** — substrate-agnostic; emit JSONL + `env.json` sidecar; standalone via `make gN`
5. **Result Store (JSONL + Parquet + SQLite)** — schema-pinned with `schema_version`
6. **Derating Model (`derating/strix_model.py`)** — per-stage roofline projections (STT compute-bound INT8 TOPS; LLM TTFT/decode bandwidth-bound; TTS first-audio compute-bound), summed in quadrature with 80% confidence bands; isolated module with own unit tests
7. **Synthesis & Reporting (`synthesis/render_report.py`)** — pandas → jinja2 → Markdown; one `make report` target
8. **Reproducibility Manifest** — `bench/images.lock.yaml`, `bench/models.lock.yaml`, `requirements.lock`, `assets/manifest.sha256.txt`, git tags, end-of-week canary re-run

### Critical Pitfalls

Eleven named risks; four CRITICAL, four HIGH, three MEDIUM-HIGH. Top five are non-negotiable:

1. **gfx942 → gfx1151 kernel-availability gap (CRITICAL — false pass)** — MI300X (CDNA3, gfx942) and Strix Halo (RDNA 3.5, gfx1151) do not share compiled kernels in standard wheels; ROCm 7 / TheRock nightly required for gfx1151. Avoid via op-by-op kernel-coverage audit *against the planned appliance ROCm minor + PyTorch wheel cut*; synthesis names every critical op and its gfx1151 status; a 30-minute kernel-presence smoke test on borrowed/cloud Strix Halo silicon before SOW signature is worth more than 100 hours of MI300X benchmarking.
2. **Naive single-multiplier derating (CRITICAL — methodology error)** — single MI300X-to-Strix scalar (~21× by bandwidth) overpredicts compute-bound stages and underpredicts memory-bound stages and ignores LPDDR5X regime change under concurrency. Avoid via per-stage, per-concurrency (N=1, 2, 4) roofline derating with arithmetic-intensity classification; report a range, not a point; use *upper bound* of band against PRD targets for gate decision.
3. **UPL probes against a generic prompt (CRITICAL — regulatory exposure)** — 100% pass on generic prompt does not generalize to firm-customized production prompt. Avoid via a *Phase 0 reference receptionBOX-shaped prompt* committed as a deliverable; ≥30 prompt-injection probes; ≥20 fee-quote probes; mandatory benign-question control set (50 probes, target zero refusals); grammar-constrained generation ON during evaluation; synthesis explicitly states the firm's actual prompt requires Phase 1 re-run.
4. **Cloud numbers leaked into sales material as appliance numbers (CRITICAL — commercial damage; NC-R14 open)** — sales artifacts compress; the distinction gets lost. Avoid via two-tier presentation in every sales-touching artifact (Measured cloud / Predicted appliance, predicted always wider); synthesis report contains an unstrippable sales-safe excerpt; **NC-R14 must be resolved before any sales conversation references the work** — Phase 0 prerequisite, not an afterthought.
5. **Real client audio or sensitive legal content leaking into the benchmark (CRITICAL — privilege exposure with no recovery)** — operational shortcut under deadline. Avoid via mandatory `assets/manifest.csv` provenance line per asset, harness-enforced; pre-teardown cloud-storage audit; no syncing local audio directories.

Additional load-bearing pitfalls: PyTorch ROCm vs ONNX-Runtime ROCm version skew (HIGH — co-residency stack-load test required); G.711 transcoding artifacts contaminating WER (HIGH — single canonical pipeline + spectral validation); warm-path-only TTS first-audio (HIGH — both warm and cold-path must be reported); cloud cost overrun via forgotten instance overnight (HIGH — provider-level cap is structural, not operator vigilance); reproducibility decay Phase 0 → Phase 1 (HIGH — end-of-week canary re-run is the cheapest detection).

## Implications for Roadmap

Roadmap follows **dependency order, not gate order**. Six of eleven critical pitfalls are prevented in Step 0 or not at all.

### Phase 1: Foundation (Step 0 — no GPU spend, ~6–8 hours)
**Rationale:** Six of eleven critical pitfalls (asset provenance, UPL prompt design, cost-cap rails, reproducibility manifest, kernel-coverage audit list, derating module skeleton) are prevented here or not at all. ROCm/MI300X spend cannot begin until this stage is complete.
**Delivers:** Repo skeleton; Makefile; `pyproject.toml` + uv lockfile; `config/{models,substrates,gates,budget}.yaml`; Substrate ABC; result schema (pydantic + `schema_version`); cost ledger (local-only test); `assets/manifest.json` + provenance CSV; **all 5 evaluation corpora curated** (500-call, 200 G.711 with neutral+stressed splits, hesitation 3-source adversarial, 200 UPL probes + benign-control + receptionBOX-shaped reference prompt, 30-pair TTS A/B); G.711 transcoding pipeline with spectral validation against one real-PSTN reference; cloud account provisioning with **provider-level $75 caps each on RunPod and TensorWave**; cost-watch script; derating module skeleton with unit tests on synthetic data; **op-list for gfx1151 kernel-coverage audit** drafted.
**Resolves:** **NC-R14** is a hard prerequisite — no Phase 0 work continues without an answer recorded in `docs/decisions/`.
**Avoids:** Pitfalls 3, 4, 6, 7, 8, 9, 11.

### Phase 2: CUDA Pre-flight on RunPod H100 (Step 1 — ~$14, 6 GPU-hours)
**Rationale:** Per virtual benchmark plan v0.1 and PRD §14, pipeline must assemble on CUDA before MI300X spend. Same code path catches harness bugs at known-working-substrate cost. The 5-call smoke test is the single most important $1 spend in Phase 0.
**Delivers:** `substrate/cuda.py`; `orchestration/runpod_h100.py`; **5-call G1 smoke** proves substrate + orchestration; once smoke passes, full G1/G2/G3/G5 sanity-runs on H100 (G7 deferred to MI300X).
**Uses:** vLLM 0.10+ CUDA wheel, faster-whisper INT8, LiveKit Agents 1.x, NGC `pytorch:25.04-py3` digest-pinned.
**Implements:** Substrate Layer (CUDA), Cloud Orchestrator + Cost Ledger (first real spend), Gate Runners (functional, not measurement-grade), Result Store.

### Phase 3: ROCm Validation on TensorWave MI300X (Step 2 — ~$54, 23 GPU-hours)
**Rationale:** Load-bearing measurement. Chatterbox-Turbo ROCm risk per PRD §11 must be validated **on Day 1** of MI300X work — fails = switch primary measurement to Kokoro and document Chatterbox as a feasibility risk. **Co-residency stack-load test (Pitfall 3) and gfx1151 kernel-coverage audit (Pitfall 1) are non-negotiable deliverables.**
**Delivers:** `substrate/rocm.py`; `orchestration/tensorwave_mi300x.py` (Vultr backup); 5-call G1 smoke on MI300X; **full G1 latency at N=1, N=2, N=4** with per-stage decomposition on 500-call corpus; G2 WER on 200-clip G.711 (faster-whisper + ONNX-RT ROCm parallel paths); G3 turn-detection with threshold sweep 400–1500ms; G5 UPL on receptionBOX-shaped prompt + benign control with grammar ON; G7 TTS A/B render (listening offline/async); **co-residency stack-load test**; engine-swap under load; both warm-path AND cold-path TTS first-audio; `gfx1151` kernel-coverage status per critical op.
**Sequencing within phase:** Day 1 = Chatterbox smoke (kill-switch decision); Day 2 = co-residency + kernel audit + G1 5-call smoke; Day 3 = full G1/G2/G3/G5; Day 4 = G7 render + ablations + buffer.
**Avoids:** Pitfalls 1, 2 (data collection), 3, 5, 6, 7, 8.

### Phase 4: Synthesis & Gate Decision (Step 3 — no GPU spend, ~6–8 hours)
**Rationale:** Synthesis report's defensibility — not measurement quality — determines whether Phase 0 produces a survivable SOW basis.
**Delivers:** Ingest results into SQLite; **per-stage roofline derating with 80% confidence bands**; cross-substrate consistency check (H100→MI300X projection within 25%); `make report` produces synthesis Markdown; **sales-safe excerpt** with explicit "predicted, not measured" language; **feasibility memo v0.4 fragment**; **Phase 0 gate decision package** using band upper bound vs PRD targets; reproducibility manifest sealed; **end-of-week canary re-run**.
**Avoids:** Pitfalls 2, 9, 10.

### Phase Ordering Rationale

- **Foundation before any GPU spend** — six of eleven critical pitfalls are CPU-only-preventable. Cost-cap config in particular is structural; one MI300X overnight = $50–140 = entire budget.
- **CUDA before ROCm** — PRD §14 + virtual benchmark plan v0.1 mandate; H100 is cheaper to debug on than MI300X.
- **ROCm phase co-locates highest-risk components** — Chatterbox-Turbo, gfx1151 audit, co-residency, per-stage per-concurrency collection share substrate state and dominant cost line.
- **Synthesis last, derating module built in parallel** — module's unit tests run on synthetic data during Phase 1; calibration against real measurements is Phase 4.
- **NC-R14 resolution gates Phase 1 completion** — without a decision, Phase 4's sales-safe excerpt has no shape and Pitfall 10 is unaddressed.

### Research Flags

Phases likely needing deeper research during planning:
- **Phase 3 (ROCm validation):** Chatterbox-Turbo ROCm install on TensorWave MI300X is highest-risk surface — devnen fork install issues #192/#445 documented but unresolved; no MI300X-specific first-audio benchmarks. Recommend `/gsd-research-phase` before Phase 3 begins to lock install recipe + Day-1 kill-switch decision tree.
- **Phase 4 (Synthesis) — but actually run before Phase 3:** Op-class-aware roofline derating methodology deserves a dedicated research pass — STACK.md §7 and ARCHITECTURE.md "Derating Methodology" overlap but neither fully specifies per-op arithmetic-intensity classification or cross-substrate consistency validation. 1–2 hour research pass to lock the math *before measurement begins* (so Phase 3 collects the right data) is high-leverage.

Phases with standard patterns (skip research-phase):
- **Phase 1 (Foundation):** Standard repo-skeleton, uv-lockfile, content-addressed asset store, SQLite result schema. Asset builders covered by STACK.md §4 + FEATURES.md.
- **Phase 2 (CUDA pre-flight):** Standard RunPod H100 + NGC pytorch + vLLM CUDA wheel; STACK.md §1.1, §2.2, §12.2 cover it.

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | MEDIUM-HIGH | HIGH on RunPod/TensorWave pricing/CLIs (multi-source), HIGH on vLLM/xgrammar/faster-whisper/jiwer/silero/LiveKit (Context7-grade docs), MEDIUM on Chatterbox-Turbo ROCm path (devnen fork only maintained route; install issues documented but unresolved), MEDIUM on Q4_K_M-to-AWQ-Int4 substitution validity. Strix Halo derating ratios LOW confidence and explicitly flagged for Phase 0 validation. |
| Features | HIGH | Driven directly by PRD §10 SM-66 through SM-72, §11, §14, DR-28. MVP set is non-negotiable per regulatory and SOW requirements. |
| Architecture | HIGH | Anchored to PRD v0.2 §3.5/§4/§14 + $150/30–40-hour envelope. Substrate ABC + content-addressed asset store + cost ledger are well-established patterns; per-stage derating module is contestable surface and isolated for independent review. |
| Pitfalls | HIGH on technical (ROCm/MI300X kernel issues, derating math, library version skew — verified against ROCm docs, Chatterbox issue tracker, Strix Halo bandwidth measurements), MEDIUM on G.711 WER methodology, MEDIUM on commercial/sales pitfalls (judgment-driven). |

**Overall confidence:** MEDIUM-HIGH. Harness design is defensible. Dominant residual uncertainty is the gfx1151 kernel-coverage status of every critical op on the planned appliance ROCm minor + PyTorch wheel cut — only resolvable by direct test; Phase 0 produces a *predicted* number with that audit as a load-bearing caveat.

### Gaps to Address

- **NC-R14 (share-with-firm posture) is open.** Resolution must precede Phase 1 completion. Defensive default: share methodology + prediction range; do not share raw cloud numbers without predicted-Strix-Halo translation. Record in `docs/decisions/` before Phase 4.
- **Strix Halo gfx1151 kernel-coverage status of every critical op is unknown until directly tested.** Phase 0 produces an audit list; "unknown" ops widen prediction confidence. 30-minute kernel-presence smoke test on borrowed/cloud Strix Halo silicon before SOW signature is recommended even though technically post-Phase-0.
- **Q4_K_M (Strix target) ↔ AWQ-Int4 (cloud measurement) substitution validity is documented but unproven.** Must be called out in synthesis with documented Ollama-overhead derate (~1.3–1.5×) when projecting from vLLM cloud to Ollama appliance.
- **Real PSTN audio reference for G.711 corpus validation is needed but limited to one Twilio→Twilio reference.** Document what reference is and is not; synthetic μ-law is *floor* on degradation.
- **vLLM 0.10.* exact version match for ROCm 6.4 should be verified at provisioning time** — Dockerfile.rocm supports 5.7–7.0; current pin not nailed.
- **Companion documents not yet in repo** — `addendum-receptionbox-discovery-v0_2`, `addendum-hardware-pivot-strix-halo-v0_1`, `feasibility-memo-v0_3`, `virtual-benchmark-plan-v0_1`. Operator must drop into `docs/` before Phase 1 completion; otherwise Phase 4 memo-v0.4 update has no v0.3 baseline.

## Sources

### Primary (HIGH confidence)
- `/home/bob/RBOX/.planning/PROJECT.md` — Phase 0 scope, $150 ceiling, 30–40 hour budget, DR-28, NC-R14 open
- `receptionbox-technical-prd-v0_2-2026-05-03 (1).md` §3.5, §4.1–4.5, §10, §11, §12 (DR-25–DR-30), §14
- RunPod docs/pricing — runpod.io/pricing, github.com/runpod/runpodctl, docs.runpod.io
- TensorWave/Vultr MI300X — tensorwave.com, vultr.com/products/cloud-gpu/amd-mi325x-mi300x/
- ROCm Docker — hub.docker.com/r/rocm/{pytorch,vllm}, rocm.docs.amd.com
- AMD vLLM MI300X recipe — amd.com developer technical articles
- vLLM benchmarking & structured outputs — docs.vllm.ai, github.com/vllm-project/vllm/tree/main/benchmarks, github.com/mlc-ai/xgrammar
- faster-whisper, jiwer, silero-vad, LiveKit — github.com/SYSTRAN/faster-whisper, pypi/jiwer, github.com/snakers4/silero-vad, docs.livekit.io/agents/
- ROCm release notes & compatibility matrix — rocm.docs.amd.com/en/latest/compatibility/
- Chatterbox / gfx1151 evidence — github.com/resemble-ai/chatterbox/issues/{445,192}, github.com/devnen/Chatterbox-TTS-Server, medium.com/@bkpaine1
- MI300X bandwidth & inference — chipsandcheese.com/p/testing-amds-giant-mi300x, rocm.blogs.amd.com/artificial-intelligence/LLM_Inference/

### Secondary (MEDIUM confidence)
- Strix Halo ROCm benchmarks — phoronix.com/review/amd-rocm-7-strix-halo, llm-tracker.info, forum.level1techs.com/t/233796, kyuz0.github.io/amd-strix-halo-toolboxes/
- Strix Halo memory bandwidth — chipsandcheese.com/p/amds-chiplet-apu-an-overview-of-strix
- MI300X FP16/INT8 — AMD data sheet, arxiv.org/pdf/2510.27583
- Kokoro ROCm — github.com/moritzchow/Kokoro-FastAPI-ROCm, huggingface.co/onnx-community/Kokoro-82M-v1.0-ONNX
- insanely-fast-whisper-rocm — github.com/beecave-homelab/insanely-fast-whisper-rocm
- Memory-wall theory — spheron.network/blog/ai-memory-wall-inference-latency-guide-2026/
- Whisper INT8/distil-whisper — huggingface.co/distil-whisper/distil-large-v3{,5-ONNX}

### Tertiary (LOW confidence — flagged for Phase 0 validation)
- Specific MI300X-to-Strix-Halo derate ratios (~10× community-measured) — extrapolated from Phoronix Nov 2025 + community Strix Halo benchmarks
- vLLM 0.10.* exact version match for ROCm 6.4 — verify at provisioning
- Chatterbox-Turbo first-audio latency on MI300X — no published; 4090 streaming (~470ms first chunk) closest reference

---
*Research completed: 2026-05-04*
*Ready for roadmap: yes*
