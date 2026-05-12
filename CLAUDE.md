<!-- GSD:project-start source:PROJECT.md -->
## Project

**receptionBOX Phase 0 — Cloud Benchmark Validation**

A pre-discovery cloud benchmark effort that validates whether receptionBOX (a voice AI personality pack for the thUMBox edge-AI appliance platform, targeting law firms) can hit its end-to-end latency and quality budgets on the planned T3 hardware (**NVIDIA Jetson AGX Orin 64GB**, per DR-39 RATIFIED 2026-05-11 — supersedes the prior Strix Halo target). Phase 0 runs entirely on rented cloud GPUs (**RunPod H100** for measurement) and produces spec-sheet-derated Jetson AGX Orin 64GB predictions plus an updated feasibility memo. **It is the gate that determines whether UMB Group offers a paid discovery SOW to the inbound large-law-firm lead.**

**Core Value:** Produce trustworthy go/no-go evidence on receptionBOX feasibility — H100-measured numbers derated to the Orin 64GB appliance SoC — *before* any sales commitment is made to the firm. If Phase 0 says "no", we walk away cleanly with <$50 spent (post-pivot budget) instead of refunding a discovery engagement.

### Constraints

- **Budget**: ~$50 cloud GPU spend ceiling for Phase 0 post-DR-39 (was ~$150 before the pivot; the entire MI300X ROCm rail was eliminated). Exceeded only with explicit operator approval. Methodology must be reproducible at this cost.
- **Timeline**: Compressed materially under DR-39 — the cross-stack ROCm risk surface is gone, leaving same-vendor CUDA → CUDA derating. Target: ~5–7 calendar days from ratification to gate decision package.
- **Hardware**: Cloud-only for measurement (RunPod H100). Spec-sheet derate to Jetson AGX Orin 64GB. **No Orin dev kit in Phase 0 critical path** — Orin Developer Kit purchase (~$2k, ~1 week ship) is deferred to post-Phase-0 verification of the H100 → Orin derate prediction.
- **Tech stack**: CUDA 12.x throughout (H100 measurement substrate AND Orin appliance target both run mainline CUDA + JetPack 6). Models pinned: distil-whisper-large-v3 INT8 (STT), Qwen3-4B Q4 (LLM), Chatterbox-Turbo (TTS primary), Kokoro-82M (TTS fallback). All have first-class CUDA paths; no fork hunting required.
- **Audio**: G.711 μ-law is the mandatory codec for STT WER measurement. Synthetic phone-path transcoding required (16 kHz capture → 8 kHz μ-law).
- **Regulatory / privilege**: Phase 0 uses only synthetic or open-licensed audio. No real client calls, no PII. UPL probe set is content-free of real legal facts.
- **Data residency posture**: Phase 0 is cloud-based by necessity (DR-19 sovereignty pillar applies to product, not benchmarks). Cloud benchmark results are non-sensitive — no privilege exposure risk.
- **Reproducibility**: Every benchmark must be re-runnable from `~/RBOX` against pinned model weights and pinned cloud images. Synthesis report must cite hash-pinned artifacts.
- **Gate semantics**: Per DR-28, Phase 0 is a hard pre-condition for SOW signing. A "soft pass with caveats" outcome is allowed; a fail blocks the discovery offer or downgrades it to a disclosed-risk offer.
<!-- GSD:project-end -->

<!-- GSD:stack-start source:research/STACK.md -->
## Technology Stack

> **Note (2026-05-11):** This section was rewritten in place for the DR-39 pivot (Strix Halo → Jetson AGX Orin 64GB). The upstream source `.planning/research/STACK.md` (619 lines) still contains pre-pivot ROCm content and is **stale** until separately rewritten — defer to CLAUDE.md as authoritative for tech-stack pins until that catches up. Archived pre-pivot tech-stack content is preserved at git tag `pivot/strix-halo-end-state` (`4c0bb57`) and on branch `archive/amd-rocm-substrate`. ROCm rationale archived under `.planning/phases/03-rocm-validation-archived/`.

## TL;DR
| Layer | Pick | Why |
|---|---|---|
| Cloud measurement substrate | **RunPod H100 SXM/PCIe (Secure Cloud)** | Per-second billing, first-class CLI, ~$2.39–$2.69/hr on-demand. Already wired up in Phase 02 (working API key, datacenter probe, network-volume pull-back pattern). |
| Appliance target SoC | **NVIDIA Jetson AGX Orin 64GB** | Per DR-39 RATIFIED. ~$2k OEM module (cost-neutral with Strix Halo); 64 GB LPDDR5 unified memory; 15–60 W configurable; mature JetPack 6 / CUDA 12.x in production at scale ~18 months. |
| CUDA container (cloud) | `vllm/vllm-openai:v0.10.x` + NVIDIA NGC `pytorch:25.04-py3` (digest-pinned) | Official upstream; matches Orin's JetPack 6 / CUDA 12.x stack for clean H100 → Orin derate. |
| LLM serve | **vLLM 0.10+** with **xgrammar** backend | xgrammar is the default structured-output engine in vLLM 2026; up to 100× faster than alternatives; same stack across H100 and Orin. |
| STT | **faster-whisper 1.x** (CTranslate2 backend, INT8) | First-class CUDA path; same engine across H100 measurement and Orin deployment. |
| TTS primary | **Resemble AI Chatterbox-Turbo** (mainline CUDA) | First-class CUDA path; no fork hunting required. ~470 ms first-chunk latency on RTX 4090 reference; expect similar order on Orin's Ampere tensor cores. |
| TTS fallback | **hexgrad Kokoro-82M** (mainline + ONNX option) | First-class CUDA path; matches PRD FR-R20. |
| Turn detection | **silero-vad v5** (RTF ~0.004) + **LiveKit turn-detector** transformer model | silero is the de facto streaming VAD; LiveKit's text-first end-of-turn classifier is the 2026 SOTA for semantic endpointing. |
| WER | **jiwer 3.x** (RapidFuzz-backed) | Standard ASR eval library; fast; trivial API. |
| Audio codec sim | **ffmpeg 7.x** with `pcm_mulaw` codec | Standard 16 kHz → 8 kHz μ-law transcode for phone-path simulation. |
| Pipeline orchestration | **LiveKit Agents Python SDK 1.x** for E2E latency rig | Same framework intended for production agent-worker (PRD §4.2); using it here de-risks Phase 1. |
| Reproducibility | **HF revision pinning by SHA**, **Docker image digest pinning**, configs committed | Standard 2026 reproducibility pattern. |
| Reporting | Python + pandas + matplotlib + scipy.stats (bootstrap CIs) | Lightweight; no external dependencies; sufficient for Phase 0 audience. |

## §1 Cloud GPU Provisioning

### §1.1 H100 (RunPod — the single Phase 0 substrate post-DR-39)

| Item | Value | Confidence |
|---|---|---|
| Provider | RunPod Secure Cloud | HIGH |
| GPU | H100 PCIe 80GB or H100 SXM 80GB | HIGH |
| Price (May 2026) | ~$2.39/hr (PCIe) / $2.69/hr (SXM) on-demand Secure | HIGH |
| Spot/Community price | ~$1.30–$1.60/hr (interruptible) | MEDIUM |
| CLI / SDK | `runpodctl` (Go) + REST `https://rest.runpod.io/v1/` + Python `runpod` SDK | HIGH |
| Container start | `runpodctl pod create --image=... --gpu-id=NVIDIA_H100_PCIE` | HIGH (validated in Phase 02) |
| Billing | Per-second | HIGH |
| Network volume | Persisted between pod stop/start; **operator already has volumes in US-CA-2 + US-KS-2** | HIGH |

- **Why not Lambda/CoreWeave:** higher friction sign-up, longer minimum commits. Overkill for a <$50 Phase 0.
- **Why not Modal/Replicate:** serverless models are wrong for this — we want a persistent dev environment with shell access.
- **Why not MI300X:** killed by DR-39. The entire AMD ROCm rail is gone. RunPod's MI300X SKU (`AMD Instinct MI300X OAM`, $1.99/GPU-hr secure cloud) is preserved in repo history at tag `pivot/strix-halo-end-state` if ever reactivated.

### §1.2 Cost Cap Mechanism

- Per-task budget caps enforced in `config/budget.yaml` (Phase 02 pattern).
- Ledger-first contract: every `provision()` call must call `authorize_spend()` first (AST-asserted via `tests/test_orchestration_skeletons.py`).
- 30-min watchdog on every pod (cost-watch loop).
- Cumulative Phase 0 ceiling: ~$50 (post-DR-39 reduction from $150).

## §2 Container Images and Runtime

### §2.1 CUDA Path (Phase 0 measurement on H100)

| Service | Image | Why |
|---|---|---|
| LLM (vLLM) | `vllm/vllm-openai:v0.10.x` (CUDA 12.4) | Official upstream; aligned with JetPack 6 (CUDA 12.x) on Orin |
| PyTorch base | `nvcr.io/nvidia/pytorch:25.04-py3` (PyTorch 2.5+, CUDA 12.4) | NVIDIA NGC validated |
| receptionBOX harness pod | `ghcr.io/consultingfuture4200/rbox-pod:vN` (Phase 02 pattern) | Custom-built; entrypoint bakes harness + pinned models; digest pinned in `bench/images.lock.yaml` |

### §2.2 JetPack Path (Orin appliance — referenced, not built in Phase 0)

JetPack 6 ships an L4T-based PyTorch container at `nvcr.io/nvidia/l4t-pytorch:r36.x.x-pth*-py3` and JetPack-specific TensorRT-LLM images. Phase 0 does NOT build for Orin — the appliance image is a Phase 1+ deliverable. Spec-sheet derating to Orin uses the assumption that the same harness runs on the same model weights under the same CUDA 12.x version, scaled by compute/bandwidth ratios.

### §2.3 Image Pinning Discipline

Always pin by `@sha256:` digest, not by tag — tags rotate. Capture digest after first `docker pull`:

```bash
docker pull <image>:<tag>
docker inspect --format='{{index .RepoDigests 0}}' <image>:<tag>
# Use the returned image@sha256:... in Dockerfiles and orchestration configs
```

## §3 LLM Stack (Qwen3-4B + Grammar-Constrained)

### §3.1 Inference Engine

| Component | Choice | Confidence | Rationale |
|---|---|---|---|
| Engine | vLLM (CUDA — same on H100 and Orin) | HIGH | Production-dominant engine; `--quantization` flag set; mature CUDA path |
| Quantization | **Q4_K_M for Orin target; AWQ-Int4 or W8A8 for cloud measurement** | MEDIUM | Q4_K_M is a llama.cpp-format quantization; vLLM's GGUF support is still limited, so on H100 measure with AWQ-Int4 as the closest equivalent. Document the substitution explicitly in the synthesis report and note that production-runtime Ollama (llama.cpp) on Orin will run Q4_K_M directly. |
| Grammar engine | **xgrammar** | HIGH | Default structured-output backend in vLLM since late 2024; up to 100× faster than `guidance`/`outlines`; integrated as `--guided-decoding-backend xgrammar` |
| Model | `Qwen/Qwen3-4B` pinned to a specific commit SHA | HIGH | Hugging Face revision pinning is the 2026 reproducibility standard |

- **Important caveat for derating:** the production runtime on Orin will use **Ollama (llama.cpp)** under PRD §4.2; the cloud benchmark uses **vLLM** to get the *ceiling* number. The synthesis report must derate vLLM-on-H100 → Orin-spec-sheet → then add an Ollama overhead factor (~1.3–1.5×) to land at a realistic production prediction. See §7.
- TensorRT-LLM is an option on both H100 and Orin — particularly attractive on Orin where it's the NVIDIA-recommended inference path for JetPack 6. Stay on vLLM for Phase 0 measurement to keep the H100 → Orin substrate apples-to-apples; revisit TensorRT-LLM for the Phase 1 Orin deployment.

### §3.2 Grammar-Constrained Generation (UPL + Intake)

- **FR-R31** intake field capture (name, phone, date, email)
- **FR-R24** intent classification with constrained label set

vLLM serving call with xgrammar backend: pass `--guided-decoding-backend xgrammar` at serve time; clients send JSON-schema-shaped grammars per request via the OpenAI-compatible API.

### §3.3 LLM Benchmarking Tooling

- `vllm/benchmarks/benchmark_serving.py` in the upstream repo.
- Reports Mean/Median/P99 TTFT, ITL, throughput.
- Knobs: `--request-rate`, `--burstiness`, `--max-concurrency`, `--metric-percentiles`, `--output-json`.
- Use `--output-json` for every run; commit JSON outputs to the repo as raw evidence.

## §4 STT Stack (distil-whisper-large-v3 INT8 on G.711)

### §4.1 Inference Engine

| Component | Choice | Confidence | Rationale |
|---|---|---|---|
| Engine | faster-whisper 1.x (CTranslate2 backend) | HIGH | INT8 quantization is first-class; up to 4× faster than openai/whisper; standard reference engine for distil-whisper measurement |
| Model | `Systran/faster-distil-whisper-large-v3` (HF mirror, CTranslate2-converted) | HIGH | Pinned-revision available |
| Quantization | INT8 | HIGH | Matches PRD FR-R11 "distil-whisper-large-v3 INT8" |
| Streaming | Chunked-with-overlap | MEDIUM | Streaming partials are PRD §4.5 v2; for Phase 0 G2 (WER measurement) measure on full clips |

Phase 0 measures G2 WER on H100 via faster-whisper CTranslate2 CUDA build. Production runtime on Orin uses the same engine (CTranslate2 CUDA on JetPack 6) or the ONNX Runtime CUDA path — both are mainline and tested.

### §4.2 G.711 μ-Law Transcoding

Standard phone-path simulation: `ffmpeg -i input.wav -ar 8000 -ac 1 -c:a pcm_mulaw out.ulaw` then back to 16 kHz WAV for STT.

### §4.3 WER Measurement

| Component | Choice | Why |
|---|---|---|
| Library | jiwer 3.x (PyPI) | Standard ASR eval library; RapidFuzz C++ backend |
| Normalization | Use Whisper's `BasicTextNormalizer` for both reference and hypothesis | Levels case, punctuation, common contractions |
| Reference | Hand-curated transcripts of the 200 G.711 clips | NFR-R8 |
| Stress stratum | Tag each clip as "neutral" / "stressed" so WER can be computed per stratum (FR-R8: <12% / <18%) | Required by gate G2 |

## §5 TTS Stack (Chatterbox-Turbo primary + Kokoro-82M fallback)

### §5.1 Chatterbox-Turbo on CUDA

| Component | Choice | Confidence |
|---|---|---|
| Server | Resemble AI's mainline `chatterbox` repo (CUDA path is first-class; no fork required post-DR-39) | HIGH |
| Model | Resemble AI Chatterbox-Turbo 350M, MIT license, pinned revision | HIGH |
| Streaming | `davidbrowne17/chatterbox-streaming` (community streaming fork; reports ~470 ms first-chunk latency on RTX 4090; expect similar order on Orin Ampere tensor cores) | MEDIUM |

Note: the ROCm-specific Chatterbox fork risk (DR-27) is moot under DR-39. CUDA path is mainline upstream; no devnen/Fedora install gymnastics required.

### §5.2 Kokoro-82M on CUDA

| Component | Choice | Confidence |
|---|---|---|
| Server | `remsky/Kokoro-FastAPI` (mainline; CUDA out-of-box) | HIGH |
| Model | `hexgrad/Kokoro-82M` (Apache 2.0, pinned revision) | HIGH |
| ONNX option | `onnx-community/Kokoro-82M-v1.0-ONNX` (fp32/fp16/q8/q4 variants) — also good for Orin via ONNX Runtime CUDA execution provider | HIGH |

### §5.3 First-Audio Latency Measurement

Render the same 30 utterances at known load. Measure timestamp from request received → first audio byte emitted. Report warm-path (cached weights) and cold-path (first call after model load) separately.

### §5.4 TTS Quality A/B (G7)

- Render the same 30 utterances via Chatterbox cloned voice and Kokoro neutral voice (matched normalization; matched sample rate; matched loudness via `pyloudnorm`).
- Random-order pair playback in a tiny web UI (`gradio` is fine; ~50 lines).
- Listeners click "A" / "B" / "tie".
- Aggregate: target ≥60% prefer cloned (SM-72).

## §6 Turn Detection (G3)

| Component | Choice | Confidence |
|---|---|---|
| Frame-level VAD | silero-vad v5 (PyPI: `silero-vad`) | HIGH |
| Semantic end-of-turn | LiveKit `turn-detector` plugin (transformer over transcribed text) | HIGH |
| Adversarial set | Hand-curated hesitation-heavy clips with ground-truth turn boundaries | — |
| Metric | False-positive rate on hesitation set (FR-R12, SM-69 target <2%) | — |

### §6.1 Adversarial Set Construction

- **Synthetic** — generate "I... uh... well, I think... maybe..." style hesitations via Chatterbox itself (meta).
- **Open-licensed** — Switchboard, Fisher (CC-licensed subsets), CommonVoice "natural conversation" tags.
- **Ground truth** — hand-mark each clip's *true* end-of-turn timestamp. Compare detector's emitted endpoint.

## §7 Derating Methodology (H100 → Jetson AGX Orin 64GB)

### §7.1 Substrate spec sheet

| Hardware | Compute (relevant) | Memory bandwidth | Power |
|---|---|---|---|
| H100 SXM 80GB | ~989 TFLOPS FP16 (sparse), ~67 TFLOPS FP32, ~3957 TOPS INT8 (sparse) | 3.35 TB/s HBM3 | 700 W |
| H100 PCIe 80GB | ~756 TFLOPS FP16 (sparse), ~51 TFLOPS FP32, ~3026 TOPS INT8 (sparse) | 2.0 TB/s HBM3 | 350 W |
| **Jetson AGX Orin 64GB** | **~32 TFLOPS FP16 (sparse, Ampere tensor cores); ~5.3 TFLOPS FP32; ~275 TOPS INT8 (sparse), ~137 TOPS INT8 (dense)** | **204 GB/s LPDDR5** | **15–60 W configurable (default ~50 W MAXN)** |

Same vendor, same CUDA stack, same arithmetic — the derate is a numerical ratio, not a cross-stack risk.

### §7.2 Per-stage derate logic

**Decode tokens/sec (bandwidth-bound for batch=1):**
- Use the memory-bandwidth ratio.
- H100 SXM → Orin = 3350 / 204 ≈ **16.4× slower on Orin**.
- Sanity check: Qwen3-4B Q4 weights are ~2.4 GB. Orin's 204 GB/s realized would give a theoretical memory-bound decode rate of ~85 tokens/sec for the entire weight read per token — comfortably above what's needed for a 250 ms TTFT classification or a few hundred-token intake response. **Bandwidth is not the binding constraint.**

**LLM TTFT (prefill, compute-bound):**
- Use the FP16 TFLOPS ratio.
- H100 SXM (sparse) → Orin (sparse) = 989 / 32 ≈ **31× slower on Orin** for FP16 prefill.
- For Qwen3-4B short prompts (typical intake exchange, ~200 tokens), this is the dominant factor in TTFT. A 50 ms TTFT on H100 implies ~1.5 s on Orin under FP16 — which exceeds the 900 ms aggregate target. **Mitigation: use INT8 (W8A8 or AWQ-Int4) on Orin to claw back ~4× via INT8 tensor cores** (Orin: 275 sparse TOPS INT8; H100: 3957 — INT8 ratio ~14× rather than 31×). Synthesis report MUST measure with the same quantization on both sides.

**STT Whisper encoder (compute-bound, prefill-like):**
- Use the FP16/INT8 ratio (same engine, same model on both sides).
- Whisper's encoder runs on the full audio context; for short utterances this is the bulk of WER-measurement latency.

**TTS first-chunk (compute-bound, prefill-like):**
- Use the FP16 ratio for the transformer prefill of the prompt; subsequent audio frames are bandwidth-bound.

**Aggregate end-to-end latency:**
- Sum the per-stage derated numbers.
- Add an **Ollama overhead factor (~1.3–1.5×)** to LLM stages, since production runtime on Orin will use Ollama/llama.cpp rather than vLLM. (CLAUDE.md §3.1 caveat.)
- Add a **CPU/ARM integration penalty (~10–20% conservative)** for orchestration overhead — Orin's 12-core ARM Cortex-A78AE is materially weaker than the EPYC/Xeon host on H100 cloud pods; LiveKit pipeline turn-taking and audio I/O hit CPU.

### §7.3 Reporting

- Raw measurements (H100 only) with N, mean, p50, p90, p99, bootstrap 95% CI.
- Derated Orin predictions per stage with the explicit ratio used + the FP16/INT8/bandwidth assumption.
- A "What we do NOT know" section: real PSTN audio vs synthetic μ-law, Ollama vLLM-equivalence behavior under sustained load on Orin, MAXN power-mode behavior under sustained load, eventual TensorRT-LLM speedup on Orin (likely 1.5–2× faster than Ollama, worth measuring post-Phase-0).
- A **post-Phase-0 validation plan**: after Phase 0 passes the gate, buy 1× Jetson AGX Orin 64GB Developer Kit (~$2k, ~1 week ship), run the same harness, and confirm the predicted ratios within ±20%. Re-issue the synthesis report as v0.2 with the measured-vs-predicted comparison before SOW execution.

## §8 Pipeline Orchestration (E2E Latency Rig — G1)

| Component | Choice | Why |
|---|---|---|
| Framework | `livekit-agents` 1.x | The same framework used in production receptionBOX agent-worker (PRD §4.2) |
| STT plugin | Custom plugin wrapping faster-whisper (CTranslate2 CUDA) | Matches production interface |
| LLM plugin | LiveKit OpenAI-compatible plugin pointed at vLLM serve endpoint | Standard |
| TTS plugin | Custom plugin wrapping Chatterbox / Kokoro server endpoints | Matches production |
| VAD + turn | LiveKit silero plugin + turn-detector plugin | Standard |

- Phase 1+ uses LiveKit Agents in production. Validating it on cloud GPU now de-risks Phase 1.
- LiveKit's `AgentSession` (1.0 release) handles streaming, turn-detection, interruption — you'd reinvent these in a custom rig.
- The framework emits per-stage timestamps natively, which is exactly what G1 needs.

### §8.1 G1 Measurement Loop

500-call corpus at N=1/2/4 concurrencies. Per-call: capture STT TTFT, LLM TTFT, LLM decode rate, TTS first-audio, end-to-end. Bootstrap 95% CIs per stage at each concurrency.

## §9 Reproducibility Stack

| Item | Tool | Pattern |
|---|---|---|
| Model weight pinning | HF `revision=` parameter with commit SHA | `AutoModel.from_pretrained("Qwen/Qwen3-4B", revision="abc123...")` |
| Container pinning | Docker image digest | `image: vllm/vllm-openai@sha256:...` |
| Config-as-code | YAML configs in `bench/configs/` | One config per gate; committed to repo |
| Run metadata | JSON sidecar per run | `bench/runs/<gate>/<timestamp>/run.json` with image digest, model SHA, GPU SKU, CUDA version, vLLM version |
| Git tagging | Tag each gate's measurements as `phase0-gN-vYYYYMMDD` | Allows re-pulling exact state for re-runs |
| Random seeds | Fix seeds for: synthetic audio gen, sample order, model (where applicable) | Commit to config |
| Asset SHAs | Hash every WAV / transcript / probe in the eval corpora | `bench/assets/manifest.sha256.txt` |

## §10 Reporting Stack

| Tool | Use |
|---|---|
| `pandas` 2.x | Aggregate per-call metrics into DataFrames |
| `matplotlib` 3.x | Per-gate distribution plots (histogram + CDF + box) |
| `scipy.stats.bootstrap` | 95% CIs via percentile bootstrap (n=10000) |
| `pyloudnorm` | Audio loudness normalization for TTS A/B |
| `jinja2` | Template the synthesis Markdown report from JSON run data |

## §11 What NOT to Use

| Avoid | Why | Use instead |
|---|---|---|
| **whisper.cpp on cloud GPUs for measurement** | The standard cloud-GPU INT8 distil-whisper measurement engine is CTranslate2 / faster-whisper. (whisper.cpp is fine for the Orin appliance path if Ollama parity is desired, post-Phase-0.) | faster-whisper 1.x INT8 |
| **Ollama for cloud GPU LLM benchmarking** | Ollama is correct for the production Orin runtime (PRD §4.2), but on H100 it under-utilizes the hardware vs vLLM. Use vLLM to get the *ceiling* number, then add a documented Ollama overhead factor (~1.3–1.5×) per §7. | vLLM 0.10+ |
| **`outlines` library for structured generation** | Slower than xgrammar (10–100× per benchmarks); xgrammar is the default in vLLM 2026. | xgrammar (built into vLLM via `--guided-decoding-backend xgrammar`) |
| **Pyannote-audio for streaming VAD** | Designed for offline diarization; not streaming-optimized; slower. | silero-vad v5 |
| **DGX Spark / cloud H200 / cloud B200** | Out of scope for receptionBOX hardware tier (Phase 0 is T3-focused on Orin 64GB); H200/B200 are overkill for the budget. | RunPod H100 (CUDA) only |
| **Modal, Replicate, Banana for benchmarking** | Serverless wrong abstraction for iterative benchmark dev; per-request billing punishes the dev loop. | RunPod persistent pods |
| **`pip` for dependency management on the harness** | Reproducibility-hostile. | `uv` + `requirements.lock` |
| **`docker compose up` for one-off benchmark runs** | Adds orchestration complexity without benefit for a single-pod harness. | `docker run --rm` with explicit env / volume flags |
| **Anthropic Claude API as cloud LLM in Phase 0** | Phase 0 measures the *local-only* path (PRD FR-R49 OFF default; cloud LLM fallback explicitly out of scope). | Skip entirely; not relevant to the gate package |
| **Real customer audio of any kind** | PRD constraint: "synthetic or open-licensed audio only. No real client calls, no PII." | Synthetic + Switchboard/Fisher/CommonVoice subsets |
| **AMD ROCm / MI300X / TensorWave / Vultr** | Killed by DR-39 ratified 2026-05-11. The substrate pivot removed the entire AMD rail. Archived at tag `pivot/strix-halo-end-state` and branch `archive/amd-rocm-substrate` if ever reactivated. | RunPod H100 only |
| **Chatterbox / Kokoro ROCm forks (devnen, moritzchow)** | Killed by DR-39. Use mainline CUDA paths. | Resemble AI Chatterbox mainline + remsky/Kokoro-FastAPI mainline |
| **Strix Halo / Framework Desktop / gfx1151 derate math** | Killed by DR-39. Target SoC is Jetson AGX Orin 64GB (CUDA), not Strix Halo (ROCm). | H100 → Orin spec-sheet derate per §7 |

## §12 Installation Sketch

### §12.1 CUDA Pod (H100 on RunPod)

```bash
# On RunPod H100 with nvcr.io/nvidia/pytorch:25.04-py3
# Pull pinned models (revisions locked in bench/models.lock.yaml — pinned per HF SHA)
# uv pip install vllm (CUDA wheel, no [rocm] extra), faster-whisper, livekit-agents, jiwer, silero-vad, etc.
```

The custom `rbox-pod` image at `ghcr.io/consultingfuture4200/rbox-pod:vN` bakes the harness + pinned models + `tools/pod_entrypoint.sh` as ENTRYPOINT. Phase 02 has the iteration history (v8 → v18); current digest pinned in `bench/images.lock.yaml`.

### §12.2 vLLM Serve Command

```bash
vllm serve <model-path> \
  --quantization awq \
  --guided-decoding-backend xgrammar \
  --max-model-len <N> \
  --max-num-seqs <concurrency>
```

## §13 Cost Estimate Per Gate (H100-only, post-DR-39)

| Gate | What runs | Est. GPU hours | Est. cost @ $2.39/hr H100 PCIe |
|---|---|---|---|
| Setup + smoke tests | Pull images, model warm-loads, sanity runs | 2 | $5 |
| G1 latency (500 calls, H100) | Full LiveKit pipeline ×500 at N=1/2/4 | 5 | $12 |
| G2 STT WER (200 clips, H100) | Whisper INT8 ×200 plus G.711 transcoding | 1.5 | $4 |
| G3 turn detection | Silero + LiveKit turn-detector ×N adversarial clips | 0.5 | $1 |
| G5 UPL probes (200 probes) | vLLM with xgrammar ×200 | 1 | $3 |
| G7 TTS A/B (30 pairs, 2 engines) | Chatterbox + Kokoro render + loudness norm | 1.5 | $4 |
| Re-runs / contingency | | 4 | $10 |
| Storage + idle | Pod stop/start friction; persistent volumes | — | $10 |
| **H100 measurement total** | | **~15.5 GPU-hr** | **~$49** |

Post-Phase-0 Orin Developer Kit purchase: ~$2k (~1 week ship; validates the derate prediction). Out of Phase 0 budget; covered by post-gate hardware procurement.

## §14 Stack Summary Table (for the orchestrator)

| Concern | Pick | Confidence |
|---|---|---|
| Cloud measurement substrate | RunPod H100 Secure Cloud | HIGH |
| Appliance target SoC | Jetson AGX Orin 64GB | HIGH (DR-39 ratified) |
| CUDA container | `vllm/vllm-openai:v0.10.*` + NGC `pytorch:25.04-py3` | HIGH |
| receptionBOX harness image | `ghcr.io/consultingfuture4200/rbox-pod:vN` | HIGH |
| LLM engine | vLLM 0.10+ with xgrammar | HIGH |
| LLM model | Qwen3-4B; AWQ-Int4 on H100 measurement, Q4_K_M on Orin production | MEDIUM (substitution risk; document explicitly) |
| STT engine | faster-whisper 1.x INT8 (CTranslate2 CUDA) | HIGH |
| STT model | distil-whisper-large-v3 (Systran CTranslate2 build) | HIGH |
| TTS primary | Resemble AI Chatterbox-Turbo (mainline CUDA) | HIGH |
| TTS fallback | hexgrad Kokoro-82M (mainline; ONNX option) | HIGH |
| VAD | silero-vad v5 | HIGH |
| Turn detector | LiveKit turn-detector plugin | HIGH |
| WER | jiwer 3.x | HIGH |
| Audio codec | ffmpeg 7.x `pcm_mulaw` | HIGH |
| Pipeline | LiveKit Agents Python SDK 1.x | HIGH |
| Reporting | pandas + matplotlib + scipy.stats | HIGH |
| Reproducibility | HF revision SHAs + Docker digests + lock files | HIGH |
| Derate methodology | H100 → Orin 64GB per §7 (same-vendor CUDA spec-sheet ratios) | HIGH (architecture); MEDIUM (specific ratios — validate post-Phase-0 on dev kit) |
| Cost guard | Provider monthly cap + local cost-watch script + AST-asserted authorize_spend() | HIGH |

## §15 Sources

### High-confidence (Context7 / official docs / verified multi-source)
- RunPod pricing & CLI — runpod.io/pricing, github.com/runpod/runpodctl, docs.runpod.io
- NVIDIA H100 spec sheet — nvidia.com/en-us/data-center/h100/
- NVIDIA Jetson AGX Orin 64GB spec sheet — nvidia.com/en-us/autonomous-machines/embedded-systems/jetson-orin/, developer.nvidia.com/embedded/jetson-agx-orin-developer-kit
- JetPack 6 release notes — developer.nvidia.com/embedded/jetpack-sdk-6x
- vLLM CUDA images & benchmark CLI — docs.vllm.ai/en/latest/, github.com/vllm-project/vllm
- vLLM structured outputs / xgrammar integration — docs.vllm.ai/en/latest/features/structured_outputs/, github.com/mlc-ai/xgrammar
- faster-whisper — github.com/SYSTRAN/faster-whisper, pypi.org/project/faster-whisper/
- jiwer — pypi.org/project/jiwer/, github.com/jitsi/jiwer
- silero-vad — github.com/snakers4/silero-vad
- LiveKit Agents framework — docs.livekit.io/agents/, github.com/livekit/agents
- LiveKit turn-detector — docs.livekit.io/agents/logic/turns/turn-detector/, blog.livekit.io/using-a-transformer-to-improve-end-of-turn-detection/
- ffmpeg G.711 — ffmpeg.org docs, en.wikipedia.org/wiki/G.711
- HF revision pinning — discuss.huggingface.co/t/does-a-pinned-model-get-automatically-updated/23978, baseten.co/blog/pinning-ml-model-revisions-for-compatibility-and-security/

### Medium-confidence (search-verified, multiple sources)
- Orin AGX 64GB compute throughput (32 FP16 TFLOPS sparse / 275 INT8 TOPS sparse) — NVIDIA developer.nvidia.com Orin technical brief; cross-checked against jetson-ai-lab benchmarks
- Orin AGX 64GB memory bandwidth (204 GB/s LPDDR5) — NVIDIA Jetson Orin technical specifications
- Chatterbox CUDA mainline — github.com/resemble-ai/chatterbox, davidbrowne17/chatterbox-streaming
- Kokoro CUDA mainline — github.com/remsky/Kokoro-FastAPI, huggingface.co/onnx-community/Kokoro-82M-v1.0-ONNX
- Ollama vs vLLM throughput delta on same hardware (~1.3–1.5× Ollama overhead) — community benchmarks, multiple sources

### Low-confidence (single-source or extrapolated; flagged for post-Phase-0 validation)
- Specific H100 → Orin 64GB per-stage derate ratios — spec-sheet-derived; Phase 0 synthesis produces predictions, post-Phase-0 Orin dev kit measurement validates within ±20%
- TensorRT-LLM speedup on Orin vs Ollama (~1.5–2× faster) — extrapolated from NVIDIA Jetson AI Lab benchmarks; not material to Phase 0 gate but relevant to Phase 1 capacity planning
- CPU/ARM integration penalty on Orin for LiveKit pipeline orchestration (~10–20%) — first-principles estimate; confirmed post-Phase-0 on dev kit
<!-- GSD:stack-end -->

<!-- GSD:conventions-start source:CONVENTIONS.md -->
## Conventions

Conventions not yet established. Will populate as patterns emerge during development.
<!-- GSD:conventions-end -->

<!-- GSD:architecture-start source:ARCHITECTURE.md -->
## Architecture

Architecture not yet mapped. Follow existing patterns found in the codebase.
<!-- GSD:architecture-end -->

<!-- GSD:skills-start source:skills/ -->
## Project Skills

No project skills found. Add skills to any of: `.claude/skills/`, `.agents/skills/`, `.cursor/skills/`, or `.github/skills/` with a `SKILL.md` index file.
<!-- GSD:skills-end -->

<!-- GSD:workflow-start source:GSD defaults -->
## GSD Workflow Enforcement

Before using Edit, Write, or other file-changing tools, start work through a GSD command so planning artifacts and execution context stay in sync.

Use these entry points:
- `/gsd-quick` for small fixes, doc updates, and ad-hoc tasks
- `/gsd-debug` for investigation and bug fixing
- `/gsd-execute-phase` for planned phase work

Do not make direct repo edits outside a GSD workflow unless the user explicitly asks to bypass it.
<!-- GSD:workflow-end -->



<!-- GSD:profile-start -->
## Developer Profile

> Profile not yet configured. Run `/gsd-profile-user` to generate your developer profile.
> This section is managed by `generate-claude-profile` -- do not edit manually.
<!-- GSD:profile-end -->
