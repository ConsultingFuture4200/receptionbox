<!-- GSD:project-start source:PROJECT.md -->
## Project

**receptionBOX Phase 0 — Cloud Benchmark Validation**

A pre-discovery cloud benchmark effort that validates whether receptionBOX (a voice AI personality pack for the thUMBox edge-AI appliance platform, targeting law firms) can hit its end-to-end latency and quality budgets on the planned T3 hardware (Framework Desktop / AMD Ryzen AI Max+ 395 "Strix Halo"). Phase 0 runs entirely on rented cloud GPUs (RunPod H100 for CUDA pre-flight, MI300X via Vultr or TensorWave for ROCm validation) and produces derated Strix Halo predictions plus an updated feasibility memo. **It is the gate that determines whether UMB Group offers a paid discovery SOW to the inbound large-law-firm lead.**

**Core Value:** Produce trustworthy go/no-go evidence on receptionBOX feasibility — derated Strix Halo predictions for latency/WER/turn-detection/UPL/TTS — *before* any sales commitment is made to the firm. If Phase 0 says "no", we walk away cleanly with $150 spent instead of refunding a discovery engagement.

### Constraints

- **Budget**: ~$150 cloud GPU spend ceiling for Phase 0 — exceeded only with explicit operator approval. Methodology must be reproducible at this cost.
- **Timeline**: ~30–40 engineering hours over ~1 calendar week ("this week" per PRD §14). Phase 0 cannot drag — sales velocity depends on it.
- **Hardware**: Cloud-only. RunPod H100 for CUDA pre-flight; MI300X via Vultr or TensorWave for ROCm validation. No local Strix Halo dev unit available.
- **Tech stack**: ROCm 6.x for AMD path; CUDA 12.x for NVIDIA pre-flight. Models are pinned: distil-whisper-large-v3 INT8 (STT), Qwen3-4B Q4_K_M (LLM), Chatterbox-Turbo (TTS primary), Kokoro-82M (TTS fallback). Phase 0 does not deviate.
- **Audio**: G.711 μ-law is the mandatory codec for STT WER measurement. Synthetic phone-path transcoding required (16 kHz capture → 8 kHz μ-law).
- **Regulatory / privilege**: Phase 0 uses only synthetic or open-licensed audio. No real client calls, no PII. UPL probe set is content-free of real legal facts.
- **Data residency posture**: Phase 0 is cloud-based by necessity (DR-19 sovereignty pillar applies to product, not benchmarks). Cloud benchmark results are non-sensitive — no privilege exposure risk.
- **Reproducibility**: Every benchmark must be re-runnable from `~/RBOX` against pinned model weights and pinned cloud images. Synthesis report must cite hash-pinned artifacts.
- **Gate semantics**: Per DR-28, Phase 0 is a hard pre-condition for SOW signing. A "soft pass with caveats" outcome is allowed; a fail blocks the discovery offer or downgrades it to a disclosed-risk offer.
<!-- GSD:project-end -->

<!-- GSD:stack-start source:research/STACK.md -->
## Technology Stack

## TL;DR
| Layer | Pick | Why |
|---|---|---|
| H100 cloud | RunPod Secure Cloud | Cheapest reliable H100 SXM/PCIe (~$2.39–$2.69/hr); per-second billing; first-class CLI |
| MI300X cloud | **TensorWave** primary, **Vultr** as backup | TensorWave is AMD-first ($1.71/hr starting), provisioning friction lowest; Vultr ($1.85/hr) is more general but has reservation friction |
| ROCm container | `rocm/vllm:latest` (ROCm 6.4 / 7.0 path) for LLM; `rocm/pytorch:latest` for STT/TTS | Pre-validated by AMD for MI300X |
| CUDA container | `vllm/vllm-openai:v0.10.x` + NVIDIA NGC `pytorch:25.04-py3` | Standard, version-tagged |
| LLM serve | **vLLM 0.10+** (ROCm path) with **xgrammar** backend for grammar-constrained gen | xgrammar is the default structured-output engine in vLLM 2026; up to 100× faster than alternatives |
| STT | **faster-whisper** (CTranslate2) for measurement, with separate ONNX-Runtime ROCm path validated as the production backend | CTranslate2 INT8 is the standard for distil-whisper-large-v3 INT8 measurement; ONNX path matches the production-runtime PRD §4.2 |
| TTS primary | **devnen/Chatterbox-TTS-Server** (ROCm fork) | The only actively maintained Chatterbox ROCm path; expect rough edges, see Pitfalls |
| TTS fallback | **moritzchow/Kokoro-FastAPI-ROCm** | The only Kokoro ROCm fork; matches PRD FR-R20 |
| Turn detection | **silero-vad v5** (RTF ~0.004) + **LiveKit turn-detector** transformer model | silero is the de facto streaming VAD; LiveKit's text-first end-of-turn classifier is the 2026 SOTA for semantic endpointing |
| WER | **jiwer 3.x** (RapidFuzz-backed) | Standard ASR eval library; fast; trivial API |
| Audio codec sim | **ffmpeg 7.x** with `pcm_mulaw` codec | Standard 16 kHz → 8 kHz μ-law transcode for phone-path simulation |
| Pipeline orchestration | **LiveKit Agents Python SDK 1.x** for E2E latency rig | Same framework intended for production agent-worker (PRD §4.2); using it here de-risks Phase 1 |
| Reproducibility | **HF revision pinning by SHA**, **Docker image digest pinning**, configs committed | Standard 2026 reproducibility pattern |
| Reporting | Python + pandas + matplotlib + scipy.stats (bootstrap CIs) | Lightweight; no external dependencies; sufficient for Phase 0 audience |
## §1 Cloud GPU Provisioning
### §1.1 H100 (CUDA Pre-flight)
| Item | Value | Confidence |
|---|---|---|
| Provider | RunPod | HIGH |
| GPU | H100 PCIe 80GB or H100 SXM 80GB | HIGH |
| Price (May 2026) | ~$2.39/hr (PCIe) / $2.69/hr (SXM) on-demand Secure | HIGH |
| Spot/Community price | ~$1.30–$1.60/hr (interruptible) | MEDIUM |
| CLI | `runpodctl` (Go-based; pod create/list/stop) + REST `https://rest.runpod.io/v1/` | HIGH |
| Container start | `runpodctl pod create --image=nvcr.io/nvidia/pytorch:25.04-py3 --gpu-id=NVIDIA_H100_PCIE` | MEDIUM |
| Billing | Per-second | HIGH |
| Network volume | Available (persisted between pod stop/start) — pay attention; storage charges accrue when pod is stopped | HIGH |
- **Lambda, CoreWeave:** Higher friction sign-up, longer minimum commits. Overkill for a $14 pre-flight.
- **Modal, Replicate:** Serverless models are wrong for this — you want a persistent dev environment with shell access.
- **Thunder Compute:** Cheaper on paper but newer provider with thinner tooling.
### §1.2 MI300X (ROCm Validation — primary substrate)
| Item | TensorWave | Vultr |
|---|---|---|
| Price (May 2026) | $1.71/GPU-hr starting (Dedicated MI300X+) | $1.75/GPU-hr (24-mo prepaid); $1.85/hr on-demand |
| ROCm posture | AMD-first; ROCm pre-installed; "easier than CUDA" per user reports | General cloud; ROCm via container, but more setup friction |
| Provisioning friction | Self-serve | May require sales contact for some regions |
| Bare-metal option | Yes | Yes |
| Confidence | HIGH (pricing); MEDIUM (provisioning UX from search) | HIGH (pricing); MEDIUM (UX) |
- **Hot Aisle, Crusoe:** Smaller MI300X providers; less standardized tooling. Worth a follow-up if TensorWave + Vultr both fall through.
- **AMD Developer Cloud:** Free tier exists but with strict usage caps and queue latency. Not suitable for a time-boxed ~30–40 hour run.
### §1.3 Cost Cap Mechanism
## §2 Container Images and Runtime
### §2.1 ROCm Path (MI300X)
| Service | Image (May 2026) | Why |
|---|---|---|
| LLM (vLLM) | `rocm/vllm:rocm6.4_mi300_ubuntu22.04_py3.11_vllm_0.10.x` | AMD-validated, MI300X-tuned; ROCm 6.4 is current stable |
| LLM alt (development) | `rocm/vllm-dev:nightly` | Only for chasing bugs; do NOT pin benchmarks to nightly |
| PyTorch base (STT/TTS) | `rocm/pytorch:rocm6.4_ubuntu22.04_py3.10_pytorch_2.5.1` | AMD-validated PyTorch ROCm |
| ROCm-only base | `rocm/dev-ubuntu-22.04:6.4` | For from-scratch builds (Chatterbox ROCm install) |
### §2.2 CUDA Path (H100)
| Service | Image | Why |
|---|---|---|
| LLM (vLLM) | `vllm/vllm-openai:v0.10.x` (CUDA 12.4) | Official upstream; matches ROCm version for parity |
| PyTorch base | `nvcr.io/nvidia/pytorch:25.04-py3` (PyTorch 2.5+, CUDA 12.4) | NVIDIA NGC validated |
### §2.3 Image Pinning Discipline
# Wrong:
# Right (record SHA after first pull):
## §3 LLM Stack (Qwen3-4B + Grammar-Constrained)
### §3.1 Inference Engine
| Component | Choice | Confidence | Rationale |
|---|---|---|---|
| Engine | vLLM (ROCm path on MI300X, CUDA path on H100) | HIGH | First-class ROCm support since 2025; AMD treats vLLM as flagship engine; standard `--quantization` flags |
| Quantization | Q4_K_M for Strix Halo target; FP16 / W8A8 for cloud measurement | MEDIUM | Q4_K_M is a llama.cpp-format quantization; on cloud GPUs use AWQ/GPTQ-Int4 as the equivalent because vLLM's GGUF support is still limited. Document the substitution explicitly in the synthesis report. |
| Grammar engine | **xgrammar** | HIGH | Default structured-output backend in vLLM since late 2024; up to 100× faster than guidance/outlines for this use case; integrated as `--guided-decoding-backend xgrammar` |
| Model | `Qwen/Qwen3-4B` pinned to a specific commit SHA | HIGH | Hugging Face revision pinning is the 2026 reproducibility standard |
- llama.cpp is the right pick for Strix Halo (Vulkan + FA backend per Phoronix Nov 2025 Strix Halo benchmarks), but for MI300X / H100 cloud measurement vLLM is the dominant production engine and matches what production receptionBOX will use under PRD §4.2 (which goes through Ollama, which itself wraps llama.cpp — but at production we measure via Ollama, here we measure via vLLM for ceiling).
- **Important caveat for derating:** the production runtime uses Ollama (llama.cpp). Your cloud benchmark using vLLM measures a *higher ceiling* than production will see. Document this clearly: vLLM TTFT on MI300X → derate to Strix Halo → then add an Ollama overhead factor. See §7 Derating Methodology.
- SGLang on ROCm is improving but not as battle-tested as vLLM at MI300X scale. Stay on vLLM.
- TensorRT-LLM is NVIDIA-only — defeats the point of MI300X validation.
- MLC is interesting but its ROCm story is still rougher than vLLM's.
### §3.2 Grammar-Constrained Generation (UPL + Intake)
- **FR-R31** intake field capture (name, phone, date, email)
- **FR-R24** intent classification with constrained label set
# vLLM serving call with xgrammar backend
### §3.3 LLM Benchmarking Tooling
- Located at `vllm/benchmarks/benchmark_serving.py` in the upstream repo.
- Reports Mean/Median/P99 TTFT, ITL, throughput.
- Knobs: `--request-rate`, `--burstiness`, `--max-concurrency`, `--metric-percentiles`, `--output-json`.
- Use `--output-json` for every run; commit JSON outputs to the repo as raw evidence.
## §4 STT Stack (distil-whisper-large-v3 INT8 on G.711)
### §4.1 Inference Engine
| Component | Choice | Confidence | Rationale |
|---|---|---|---|
| Engine | faster-whisper 1.x (CTranslate2 backend) | HIGH | INT8 quantization is first-class; up to 4× faster than openai/whisper; widely used reference for distil-whisper measurement |
| Model | `Systran/faster-distil-whisper-large-v3` (HF mirror, CTranslate2-converted) | HIGH | Pinned-revision standard available |
| Quantization | INT8 | HIGH | Matches PRD FR-R11 "distil-whisper-large-v3 INT8" |
| Streaming | Chunked-with-overlap (faster-whisper supports `vad_filter=True` and `streaming` patterns via wrapper libs) | MEDIUM | Streaming partial hypotheses are implemented per the PRD §4.5 v2 line, but for Phase 0 G2 (WER measurement) you don't need streaming — measure on full clips |
- **G2 WER on MI300X:** run faster-whisper on MI300X via CTranslate2 ROCm build. Verify output matches CUDA output bit-for-bit (deterministic decode setting); if it doesn't, fall back to ONNX Runtime ROCm path.
- **Backup:** `beecave-homelab/insanely-fast-whisper-rocm` is a community-maintained ROCm fork specifically for AMD GPUs (ROCm 6.1–7.1).
### §4.2 ONNX Runtime ROCm Path (matches production)
### §4.3 G.711 μ-Law Transcoding
# 16 kHz WAV → 8 kHz G.711 μ-law (carrier path) → 16 kHz WAV (reconstructed for STT)
### §4.4 WER Measurement
| Component | Choice | Why |
|---|---|---|
| Library | jiwer 3.x (PyPI) | Standard ASR eval library; RapidFuzz C++ backend |
| Normalization | Use Whisper's `BasicTextNormalizer` for both reference and hypothesis | Levels case, punctuation, common contractions |
| Reference | Hand-curated transcripts of the 200 G.711 clips | NFR-R8 |
| Stress stratum | Tag each clip as "neutral" / "stressed" so WER can be computed per stratum (FR-R8: <12% / <18%) | Required by gate G2 |
## §5 TTS Stack (Chatterbox-Turbo primary + Kokoro-82M fallback)
### §5.1 Chatterbox-Turbo on ROCm
| Component | Choice | Confidence |
|---|---|---|
| Server | `devnen/Chatterbox-TTS-Server` (community fork with documented ROCm support) | MEDIUM |
| Model | Resemble AI Chatterbox-Turbo 350M, MIT license, pinned revision | HIGH |
| Streaming | `davidbrowne17/chatterbox-streaming` (community streaming fork; reports first-chunk latency ~0.47s on RTX 4090) | LOW–MEDIUM |
| ROCm install path | Installed `--no-deps` per recent fix (avoids torch version conflicts and ONNX build failures) | MEDIUM |
- ROCm device enumeration sometimes shows count=0 even when `rocminfo` succeeds — usually a torch/ROCm version mismatch.
- Windows ROCm path is unsupported; Linux MI300X is the supported configuration.
- A documented "How to install Chatterbox with ROCM support on Fedora 42" issue (#445) is the closest thing to a recipe.
- The PRD's risk register flags "Chatterbox-Turbo ROCm path is non-functional" as Medium-High probability with the Pluggable TTS architecture (DR-27) as mitigation. Phase 0 must validate this risk early.
- **Day 1 of MI300X work:** smoke-test Chatterbox-Turbo first. If it loads and streams audio, proceed. If it fails, switch primary measurement to Kokoro fallback and document Chatterbox as a feasibility risk in the gate package.
### §5.2 Kokoro-82M on ROCm
| Component | Choice | Confidence |
|---|---|---|
| Server | `moritzchow/Kokoro-FastAPI-ROCm` (fork of `remsky/Kokoro-FastAPI` with AMD GPU PyTorch support) | MEDIUM |
| Model | `hexgrad/Kokoro-82M` (Apache 2.0, pinned revision) | HIGH |
| ONNX option | `onnx-community/Kokoro-82M-v1.0-ONNX` (fp32/fp16/q8/q4 variants) — backup if PyTorch ROCm path is rough | HIGH |
### §5.3 First-Audio Latency Measurement
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
## §7 Derating Methodology (Strix Halo Prediction)
### §7.1 Bandwidth-Bound Decode Derating
| Hardware | Effective bandwidth | Confidence |
|---|---|---|
| MI300X | 5.3 TB/s HBM3 (peak), realized ~80% | HIGH |
| H100 SXM | 3.35 TB/s HBM3 | HIGH |
| Strix Halo (Ryzen AI Max+ 395) | 256 GB/s LPDDR5X-8000 spec; ~212 GB/s realized via `rocm_bandwidth_test` | HIGH |
- At small batch sizes (1 concurrent call) the H100/MI300X compute units are underutilized; bandwidth is the dominant axis but not the only one.
- Qwen3-4B Q4_K_M weights are ~2.4 GB. At Strix Halo 212 GB/s realized, the *theoretical* memory-bound decode rate is ~88 tokens/sec — comfortably above what's needed for a 250ms TTFT classification.
- TTFT is *prefill* dominated (compute), not decode. Compute on Strix Halo (Radeon 8060S iGPU) is materially weaker than MI300X. Phoronix Nov 2025 numbers show Strix Halo HIP backend at "barely beats CPU" for prompt processing — this is a real risk for TTFT.
### §7.2 Recommended Derating Approach
### §7.3 Compute-Bound Pieces Get Different Derates
- **STT prefill (Whisper encoder):** compute-bound, not bandwidth-bound. Use the Strix Halo prompt-processing penalty (10–15× slower than MI300X for prompt processing per Phoronix data) rather than the bandwidth ratio.
- **TTS first-chunk:** dominated by transformer prefill — compute-bound. Same derate as STT.
- **LLM TTFT under grammar:** mostly prefill — compute-bound.
- **LLM decode tokens/sec (response generation):** bandwidth-bound — use bandwidth ratio.
- **End-to-end latency:** sum the per-stage derated numbers.
### §7.4 Reporting
- Raw measurements (MI300X and H100) with N, mean, p50, p90, p99, CI.
- Both derates, plus a "central estimate" using the geometric mean.
- A clear "What we do NOT know" section: production Ollama overhead vs vLLM, real PSTN audio vs synthetic μ-law, ROCm 7 stability under sustained load.
## §8 Pipeline Orchestration (E2E Latency Rig — G1)
| Component | Choice | Why |
|---|---|---|
| Framework | `livekit-agents` 1.x | The same framework used in production receptionBOX agent-worker (PRD §4.2) |
| STT plugin | Custom plugin wrapping faster-whisper / ONNX-RT ROCm | Matches production interface |
| LLM plugin | LiveKit OpenAI-compatible plugin pointed at vLLM serve endpoint | Standard |
| TTS plugin | Custom plugin wrapping Chatterbox / Kokoro server endpoints | Matches production |
| VAD + turn | LiveKit silero plugin + turn-detector plugin | Standard |
- Phase 1+ uses LiveKit Agents in production. Validating it on cloud GPU now de-risks Phase 1.
- LiveKit's `AgentSession` (1.0 release) handles streaming, turn-detection, interruption — you'd reinvent these in a custom rig.
- The framework emits per-stage timestamps natively, which is exactly what G1 needs.
### §8.1 G1 Measurement Loop
## §9 Reproducibility Stack
| Item | Tool | Pattern |
|---|---|---|
| Model weight pinning | HF `revision=` parameter with commit SHA | `AutoModel.from_pretrained("Qwen/Qwen3-4B", revision="abc123...")` |
| Container pinning | Docker image digest | `image: rocm/vllm@sha256:...` |
| Config-as-code | YAML configs in `bench/configs/` | One config per gate; committed to repo |
| Run metadata | JSON sidecar per run | `bench/runs/<gate>/<timestamp>/run.json` with image digest, model SHA, GPU SKU, ROCm version, vLLM version |
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
| **whisper.cpp on cloud GPUs for measurement** | INT8 ROCm path is unsupported / underdeveloped on MI300X; the standard cloud-GPU INT8 distil-whisper measurement engine is CTranslate2 / faster-whisper. (whisper.cpp is fine for Strix Halo local validation post-Phase-0.) | faster-whisper 1.x INT8 |
| **Ollama for cloud GPU LLM benchmarking** | Ollama is correct for production receptionBOX (PRD §4.2) on Strix Halo, but on MI300X / H100 it under-utilizes the hardware vs vLLM. Use vLLM to get the *ceiling* number, then add a documented Ollama-overhead derate (~1.3–1.5×). | vLLM 0.10+ |
| **`outlines` library for structured generation** | Slower than xgrammar (10–100× per benchmarks); xgrammar is the default in vLLM 2026. | xgrammar (built into vLLM via `--guided-decoding-backend xgrammar`) |
| **Pyannote-audio for streaming VAD** | Designed for offline diarization; not streaming-optimized; slower. | silero-vad v5 |
| **DGX Spark / cloud H200 / cloud B200** | Out of scope for receptionBOX hardware tier (T5 is DGX Spark but Phase 0 is T3-focused); H200/B200 are overkill for the budget. | RunPod H100 (CUDA) + TensorWave MI300X (ROCm) |
| **Modal, Replicate, Banana for benchmarking** | Serverless wrong abstraction for iterative benchmark dev; per-request billing punishes the dev loop. | RunPod / TensorWave persistent pods |
| **`pip` for dependency management on the harness** | Reproducibility-hostile. | `uv` + `requirements.lock` (matches operator tooling preference) |
| **`docker compose up` for one-off benchmark runs** | Adds orchestration complexity without benefit for a single-pod harness. | `docker run --rm` with explicit env / volume flags |
| **Anthropic Claude API as cloud LLM in Phase 0** | Phase 0 measures the *local-only* path (PRD FR-R49 OFF default; "Cloud LLM fallback" is explicitly out of scope per PROJECT.md). | Skip entirely; not relevant to the gate package |
| **Real customer audio of any kind** | PRD constraint: "synthetic or open-licensed audio only. No real client calls, no PII." | Synthetic + Switchboard/Fisher/CommonVoice subsets |
## §12 Installation Sketch
### §12.1 ROCm Pod (MI300X on TensorWave)
# On TensorWave pod with rocm/pytorch:rocm6.4_ubuntu22.04_py3.10_pytorch_2.5.1
# Pull pinned models (revisions to be locked in models.lock.yaml)
### §12.2 CUDA Pod (H100 on RunPod) Pre-flight
# On RunPod H100 with nvcr.io/nvidia/pytorch:25.04-py3
# Same uv pip install set, with vllm (CUDA wheel, no [rocm] extra):
### §12.3 vLLM Serve Command (both rails)
## §13 Cost Estimate Per Gate (MI300X primary substrate)
| Gate | What runs | Est. GPU hours | Est. cost @ $1.71/hr |
|---|---|---|---|
| Setup + smoke tests | Pull images, model warm-loads, sanity runs | 4 | $7 |
| H100 pre-flight (RunPod) | E2E pipeline assembles once on CUDA | 6 | $14 (@ $2.39/hr) |
| G1 latency (500 calls, MI300X) | Full LiveKit pipeline ×500 | 5 | $9 |
| G2 STT WER (200 clips, MI300X) | Whisper INT8 ×200 plus transcoding | 2 | $4 |
| G3 turn detection (adversarial set) | Silero + LiveKit turn-detector ×N | 1 | $2 |
| G5 UPL probes (200 probes) | vLLM with grammar ×200 | 2 | $4 |
| G7 TTS A/B (30 pairs, 2 engines) | Chatterbox + Kokoro render + listening | 3 | $5 |
| Re-runs / contingency | | 10 | $17 |
| Storage + idle | Pod stop/start friction; persistent volumes | — | $10 |
| **MI300X subtotal** | | **23 GPU-hr** | **~$54** |
| **H100 subtotal** | | **6 GPU-hr** | **~$14** |
| **Storage/network/contingency** | | | **~$30** |
| **Grand total** | | | **~$98** |
## §14 Stack Summary Table (for the orchestrator)
| Concern | Pick | Confidence |
|---|---|---|
| H100 cloud | RunPod Secure Cloud | HIGH |
| MI300X cloud | TensorWave (Vultr backup) | HIGH (pricing); MEDIUM (UX) |
| ROCm container | `rocm/vllm:rocm6.4_mi300_*` + `rocm/pytorch:rocm6.4_*` | HIGH |
| CUDA container | `vllm/vllm-openai:v0.10.*` + NGC `pytorch:25.04-py3` | HIGH |
| LLM engine | vLLM 0.10+ with xgrammar | HIGH |
| LLM model | Qwen3-4B AWQ-Int4 (cloud equivalent of Q4_K_M) | MEDIUM (substitution risk; document explicitly) |
| STT engine | faster-whisper 1.x INT8 (CTranslate2) | HIGH |
| STT model | distil-whisper-large-v3 (Systran CTranslate2 build) | HIGH |
| TTS primary | devnen Chatterbox-TTS-Server ROCm fork | MEDIUM (ROCm risk per PRD §11 risk register) |
| TTS fallback | moritzchow Kokoro-FastAPI-ROCm | MEDIUM-HIGH |
| VAD | silero-vad v5 | HIGH |
| Turn detector | LiveKit turn-detector plugin | HIGH |
| WER | jiwer 3.x | HIGH |
| Audio codec | ffmpeg 7.x `pcm_mulaw` | HIGH |
| Pipeline | LiveKit Agents Python SDK 1.x | HIGH |
| Reporting | pandas + matplotlib + scipy.stats | HIGH |
| Reproducibility | HF revision SHAs + Docker digests + lock files | HIGH |
| Cost guard | Provider monthly cap + local cost-watch script | HIGH |
## §15 Sources
### High-confidence (Context7 / official docs / verified multi-source)
- RunPod pricing & CLI — runpod.io/pricing, github.com/runpod/runpodctl, docs.runpod.io
- TensorWave / Vultr MI300X pricing — tensorwave.com, vultr.com/products/cloud-gpu/amd-mi325x-mi300x/, getdeploying.com/gpus/amd-mi300x
- ROCm Docker images — hub.docker.com/r/rocm/pytorch, hub.docker.com/r/rocm/vllm, rocm.docs.amd.com
- AMD vLLM MI300X recipe — amd.com/en/developer/resources/technical-articles/how-to-use-prebuilt-amd-rocm-vllm-docker-image-with-amd-instinct-mi300x-accelerators.html
- vLLM benchmark CLI — docs.vllm.ai/en/latest/benchmarking/cli/, github.com/vllm-project/vllm/tree/main/benchmarks
- vLLM structured outputs / xgrammar integration — docs.vllm.ai/en/latest/features/structured_outputs/, github.com/mlc-ai/xgrammar
- faster-whisper — github.com/SYSTRAN/faster-whisper, pypi.org/project/faster-whisper/
- jiwer — pypi.org/project/jiwer/, github.com/jitsi/jiwer
- silero-vad — github.com/snakers4/silero-vad
- LiveKit Agents framework — docs.livekit.io/agents/, github.com/livekit/agents
- LiveKit turn-detector — docs.livekit.io/agents/logic/turns/turn-detector/, blog.livekit.io/using-a-transformer-to-improve-end-of-turn-detection/
- ffmpeg G.711 — ffmpeg.org docs, en.wikipedia.org/wiki/G.711
- HF revision pinning — discuss.huggingface.co/t/does-a-pinned-model-get-automatically-updated/23978, baseten.co/blog/pinning-ml-model-revisions-for-compatibility-and-security/
### Medium-confidence (search-verified, multiple sources)
- Strix Halo (Ryzen AI Max+ 395) ROCm benchmarks — phoronix.com/review/amd-rocm-7-strix-halo, llm-tracker.info/AMD-Strix-Halo-(Ryzen-AI-Max+-395)-GPU-Performance, forum.level1techs.com/t/strix-halo-ryzen-ai-max-395-llm-benchmark-results/233796, kyuz0.github.io/amd-strix-halo-toolboxes/
- Strix Halo memory bandwidth (256 GB/s spec, ~212 GB/s realized) — chipsandcheese.com/p/amds-chiplet-apu-an-overview-of-strix, news.ycombinator.com/item?id=42619752
- MI300X FP16 / INT8 specs (1307.4 TFLOPS FP16, 5.3 TB/s) — amd.com data sheet, arxiv.org/pdf/2510.27583 (MI300X performance analysis)
- Chatterbox ROCm (devnen fork, install issues) — github.com/devnen/Chatterbox-TTS-Server, github.com/resemble-ai/chatterbox/issues/445, github.com/davidbrowne17/chatterbox-streaming
- Kokoro ROCm — github.com/moritzchow/Kokoro-FastAPI-ROCm, github.com/remsky/Kokoro-FastAPI, huggingface.co/onnx-community/Kokoro-82M-v1.0-ONNX
- insanely-fast-whisper-rocm — github.com/beecave-homelab/insanely-fast-whisper-rocm
### Low-confidence (single-source or extrapolated; flagged for validation)
- Specific MI300X-to-Strix-Halo derate ratios (10× community-measured) — extrapolated from Phoronix Nov 2025 + community Strix Halo benchmarks; needs Phase 0 validation
- vLLM 0.10.* exact version match for ROCm 6.4 — vLLM Dockerfile.rocm supports ROCm 5.7–7.0 across older branches but the "current" pin should be verified at provisioning time
- Chatterbox-Turbo first-audio latency on MI300X specifically — no published benchmarks found; the 4090 streaming numbers (~470ms first chunk) are the closest reference
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
