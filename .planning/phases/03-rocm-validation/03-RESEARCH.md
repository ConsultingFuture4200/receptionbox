# Phase 3: ROCm Validation — Research

**Researched:** 2026-05-10
**Domain:** ROCm 6.4 vLLM/MI300X benchmark harness; co-residency + gfx1151 op-coverage audits
**Confidence:** HIGH on the established stack on MI300X (vLLM, faster-whisper, jiwer, silero, LiveKit, ffmpeg). MEDIUM on the Chatterbox-Turbo ROCm install path (devnen fork; #92 confirmed open). LOW on the gfx1151 audit methodology (must be hand-rolled from PyTorch issues #171687 + #6034 + ROCm/TheRock signals — no off-the-shelf gfx942→gfx1151 op-diff tool exists in 2026).

## Summary

Phase 3 ports the proven CUDA-rail substrate from Phase 2 to MI300X under the constraints already locked in CONTEXT.md: Vultr as Day-1 provider (D-31), separate `rbox-pod-rocm` image baked from `rocm/vllm:rocm6.4_mi300_*` (D-32), Chatterbox kill-switch with 2-hr / $4 timebox (D-35/D-36), config-row TTS primary swap (D-37). The picks themselves are not in question — the question is *what to wield carefully*.

Three pieces of Phase 3 have published prior art that should drive task structure:

1. **vLLM ROCm benchmarking is a solved problem.** `vllm/benchmarks/benchmark_serving.py` with `--max-concurrency {1,2,4}`, `--percentile-metrics ttft,tpot,itl,e2el`, and `--output-json` is the AMD-validated path for G1 LLM-stage measurement. Three pod runs (one per concurrency) keep cold-cache effects clean and align with D-Discretion (Concurrency rig) in CONTEXT.md. [CITED: docs.vllm.ai/en/latest/benchmarking/cli/]

2. **The gfx1151 audit is hand-rolled but cheap.** PyTorch issue #171687 (Nov 2025) confirms gfx1151 LLM decode is dominated by `hipMemcpyWithStream` rather than compute kernels — a load-bearing finding for derating that did not exist when CLAUDE.md §7.2 was written. The audit methodology should capture a torch profiler trace per model on MI300X (gfx942), then cross-reference operator names against (a) ROCm/TheRock release notes for gfx1151 native kernels, (b) PyTorch issue #6034 (5 critical bf16 bugs documented on gfx1151), (c) the `hipBLASLt` supported-arch list (gfx942 yes, gfx1151 falls back to `hipBLAS`). Tooling = `torch.profiler` Chrome-JSON export + a manual gfx1151 registry — no separate tool to evaluate. [CITED: github.com/pytorch/pytorch/issues/171687, github.com/ROCm/ROCm/issues/6034]

3. **The Chatterbox Day-1 risk is concrete and named.** devnen/Chatterbox-TTS-Server issue #92 (contradictory torch requirements for ROCm) is open and represents the specific install failure mode CLAUDE.md §5.1 was warning about. The fix is the `--no-deps` install pattern already merged upstream. Plan should pre-load the Dockerfile.rocm from upstream rather than reinventing the install. [VERIFIED: github.com/devnen/Chatterbox-TTS-Server/issues/92, github.com/devnen/Chatterbox-TTS-Server/blob/main/Dockerfile.rocm]

**Primary recommendation:** Treat Phase 3 as three concurrent threads. (a) Substrate + provisioning + Chatterbox Day-1 (high-risk install path; isolate to one pod), (b) gate runners G1-G5 + co-residency (mostly substrate-agnostic carry-forward from Phase 2), (c) gfx1151 op-audit script (offline-runnable on the MI300X pod; no separate provisioning). The op-audit script is the lowest-cost, highest-leverage Phase 3 deliverable for Phase 4 derate credibility — schedule it first within the warm MI300X pod, not last.

## User Constraints (from CONTEXT.md)

### Locked Decisions

Carried forward from Phase 1 + Phase 2 (do NOT relitigate):

- **D-09** substrate ABC contract — `substrate/rocm.py` MUST implement `async def` methods returning `AsyncIterator[Chunk]`. No sync wrappers.
- **D-10** GateResult schema — every Phase 3 row pydantic-validated with `schema_version="1.0"`, `substrate="rocm"`. Error rows kept (`status="error"`, measurements NULL).
- **D-11** result storage — JSONL append per call to `results/{gate}/{run_id}.jsonl`; SQLite index rebuilt by `make report`.
- **D-12** env.json sidecar — every Phase 3 run emits `results/{gate}/{run_id}.env.json`. ROCm version + PyTorch ROCm wheel + vLLM version recorded.
- **D-14** substrate composition — single `substrate/rocm.py` class composing 4 backend adapters; mirrors `substrate/cuda.py:CUDASubstrate`.
- **D-15** LiveKit Agents 1.x `AgentSession` for E2E pipeline rig.
- **D-16** in-instance watchdog at `MAX_MINUTES`; `tools/pod_entrypoint.sh` provider-agnostic.
- **D-17** rsync result-pull on SIGTERM.
- **D-22 / D-23** pre-teardown audit via `tools/audit_pod_state.py`.
- **DEV-1021 provenance pattern** — `RBOX_IMAGE_DIGEST` env + `/workspace/.git_commit` baked file; both populate every result row.
- **Cost-ledger gate** — `authorize_spend()` MUST be first call in every `provision()` (AST-asserted).
- **DR-27 pluggable TTS** — Chatterbox unhealthy → Kokoro fallback in `synthesize()`; Day-1 kill-switch decides which is *primary*.
- **DR-31 sharing policy** — two-tier presentation (Measured cloud / Predicted appliance) if any number leaves harness.

Phase 3 specific:

- **D-31** Day-1 provider = **Vultr** ($1.85/hr on-demand). `orchestration/vultr_mi300x.py` is wired to real provisioning first. TensorWave stays Phase-1-stub until sales unblocks.
- **D-32** Image strategy = separate `rbox-pod-rocm` image FROM `rocm/vllm:rocm6.4_mi300_ubuntu22.04_py3.11_vllm_0.10.x`. Same `ENTRYPOINT tools/pod_entrypoint.sh`, same `ARG GIT_COMMIT`. Pushed to `ghcr.io/consultingfuture4200/rbox-pod-rocm`. `_DEFAULT_IMAGE_ROCM` digest-pinned.
- **D-33** `config/budget.yaml` `phase3.max_minutes_per_gate`: chatterbox_d1: 120, g1: 120, g2: 45, g3: 20, g5: 30, g7: 45.
- **D-34** Cost tracking = wall-clock × $/hr; Vultr `/v2/billing/pending-charges` reconciles; TensorWave stub-with-warning.
- **D-35** Chatterbox kill-switch pass = (1) container starts + reports `device count > 0`, (2) `/v1/audio/speech` 200 within 60s, (3) output PCM `sf.read` parses with RMS > 0.01 and duration > 1s, (4) zero exceptions in 30s test render. **Does NOT measure latency.**
- **D-36** Day-1 timebox = **2-hr wall-clock, $4 spend cap.** On bust → flip primary to Kokoro per D-37, re-scope G1/G7.
- **D-37** Fallback mechanism = config-row `tts.primary: chatterbox|kokoro` in `config/sanity_strata.yaml`. P3.7 mid-session swap flips this row.
- **D-38** Decision audit trail: STATE.md one-liner + Linear DEV-1022 comment + `audit/chatterbox_d1_decision.md` long-form.

### Claude's Discretion

Operator-flagged defaults Phase 3 plans should follow (operator may override before plan-phase):

- **G2 dual-path** — same gate runner emits two rows per asset with `extras.engine: faster-whisper-int8 | onnx-rt-rocm`. Sequential within a single pod.
- **G1 concurrency rig** — `gates/g1/runner.py --concurrency N`; `asyncio.gather()` N copies of single-call coroutine against N `AgentSession`s sharing vLLM/Whisper/Chatterbox endpoints. Three pod runs at N=1, 2, 4 (separate pods).
- **Co-residency profile (P3.7)** — 5-min sustained run replays a randomly-permuted slice of 500-call corpus at N=2 with all 3 model classes loaded; records ROCm memory headroom every 10s. Mid-run TTS swap at 2:30.
- **gfx1151 op coverage method (P3.8)** — `tools/audit_op_coverage.py` runs each model through a single representative inference call with op-by-op kernel dispatch capture, cross-references against gfx1151 kernel registry. Output: `audit/gfx1151_op_status.md`.

### Deferred Ideas (OUT OF SCOPE)

- TensorWave real provisioning (waits on sales unblock; tracked as follow-up).
- Live MI300X→Strix-Halo op comparison (requires Framework Desktop dev unit; post-Phase-0).
- Engine-swap via hot reload (sub-second swap-time); current plan = config-row flip; backlog if swap-time is embarrassing.
- Concurrency stress beyond N=4 (T3 hardware is single-pack-per-appliance per DR-25).
- `make verify-provenance` target (DEV-1021 AC #4 deferred; folded into Phase 4 repro-manifest).
- Multi-pack co-residency, Cloud LLM fallback measurement.

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| HARNESS-03 | `substrate/rocm.py` implements ABC for Vultr/TensorWave MI300X (vLLM ROCm, faster-whisper INT8 ROCm, devnen Chatterbox, moritzchow Kokoro, LiveKit 1.x) | Mirror `substrate/cuda.py` composition (D-14); only model-dir paths + endpoint URLs change. Pitfalls §1–§6 below cover ROCm-specific failure modes. |
| GATE-CHATTERBOX-D1 | Day-1 ROCm load smoke for Chatterbox-Turbo; pass→primary, fail→Kokoro primary | Pre-load `devnen/Chatterbox-TTS-Server/Dockerfile.rocm` as install recipe; #92 fix (torch version conflict) is upstream-merged via `--no-deps`. |
| GATE-G1 | 500-call corpus E2E latency at N=1/2/4 with per-stage decomposition | vLLM `benchmark_serving.py --max-concurrency N --percentile-metrics ttft,tpot,itl,e2el --output-json` is the AMD-validated rig. LiveKit `AgentSession` emits per-turn timestamps natively (`ChatMessage.metrics`). |
| GATE-G2 | STT WER on 200 G.711 μ-law clips with faster-whisper INT8 + ONNX-RT ROCm parallel | DEV-1083 codec-aware decode fix on `main` carries forward. jiwer ≥4.0 (per Phase 1 lock) + Whisper `BasicTextNormalizer`. Determinism: `beam_size=1`. |
| GATE-G3 | Turn-detection FPR sweep 400–1500ms in 100ms steps (12 thresholds) | silero-vad v5 `activation_threshold` + `min_silence_duration` + LiveKit `min_endpointing_delay`. Roll our own — no published sweep rig exists. |
| GATE-G5 | 200 UPL probes + 50 benign control vs receptionBOX-shaped reference prompt with grammar-ON | vLLM `--guided-decoding-backend xgrammar` + per-row `extras.constraint_status`. Three discrete outcomes: `constraint_ok`, `constraint_miss_invalid_json`, `engine_error`. |
| GATE-G7 | TTS A/B preference — warm + cold first-audio across 30 stimulus pairs | First-audio measured at first PCM chunk return from `/v1/audio/speech` streaming endpoint. Cold = container restart between renders; warm = serial in same process. |
| AUDIT-01 | Co-residency stack-load ≥5 min, all 3 model classes loaded under N=2 sustained | `rocm-smi --showmeminfo vram --json` polled every 10s. Detect: VRAM% > 90 (OOM proximity), kernel errors in `dmesg`/journal, process crash. |
| AUDIT-02 | gfx1151 op-coverage table (`audit/gfx1151_op_status.md`) | torch.profiler Chrome trace per model + manual cross-reference against PyTorch #171687, ROCm/ROCm #6034, hipBLASLt supported-arch list. No existing tool. |
| AUDIT-03 | Engine-swap-under-load demo (Chatterbox→Kokoro mid-session) | Config-row write (D-37) → `substrate/rocm.py:synthesize()` re-reads at next session start. Measure: time between row-write and first Kokoro audio chunk in new session. |

## Standard Stack

### Core (locked; do NOT relitigate)

| Library | Version | Purpose | Source |
|---------|---------|---------|--------|
| vLLM | 0.10.x ROCm wheel (verify against image at provisioning) | LLM serve + grammar-constrained gen via xgrammar | `rocm/vllm:rocm6.4_mi300_ubuntu22.04_py3.11_vllm_0.10.x` [CITED: hub.docker.com/r/rocm/vllm] |
| xgrammar | bundled with vLLM 0.10+ | Guided-decoding backend (`--guided-decoding-backend xgrammar`) | [VERIFIED: docs.vllm.ai/en/latest/features/structured_outputs/] |
| faster-whisper | 1.x (CTranslate2 backend) | STT INT8 measurement engine | [CITED: github.com/SYSTRAN/faster-whisper] |
| onnxruntime-rocm | latest matching ROCm 6.4 (verify at install) | G2 parallel STT path (production-runtime parity per CLAUDE.md §4.2) | [CITED: rocm.blogs.amd.com/artificial-intelligence/ctranslate2/README.html] |
| devnen/Chatterbox-TTS-Server | upstream `main` + `Dockerfile.rocm` | TTS primary (if Day-1 passes) | [VERIFIED: github.com/devnen/Chatterbox-TTS-Server/blob/main/Dockerfile.rocm] |
| moritzchow/Kokoro-FastAPI-ROCm | upstream `main` | TTS fallback / Day-1-fail primary | [CITED: github.com/moritzchow/Kokoro-FastAPI-ROCm] |
| silero-vad | v5 | Frame-level VAD | [CITED: github.com/snakers4/silero-vad] |
| livekit-agents | 1.x (Phase 2 pinned 1.2.9 due to openai-version constraint) | E2E pipeline + per-turn timestamps via `ChatMessage.metrics` | [VERIFIED: github.com/livekit/agents] |
| livekit-plugins-turn-detector | upstream | Semantic end-of-turn (text-first transformer) | [CITED: blog.livekit.io/using-a-transformer-to-improve-end-of-turn-detection] |
| jiwer | ≥4.0 (Phase 1 lock; STACK.md §4.4 reference to 3.x is stale per Phase 1 STATE.md) | WER scoring | [VERIFIED: pypi.org/project/jiwer/] |
| whisper-normalizer | bundled with `BasicTextNormalizer` | Reference + hypothesis normalization | [CITED: STACK.md §4.4] |
| ffmpeg | 7.x `pcm_mulaw` codec | G.711 μ-law transcoding (Phase 1 asset; Phase 3 reuses) | [VERIFIED: Phase 1 ASSETS-07 complete] |
| pydantic | v2 | GateResult + env.json validation | [VERIFIED: Phase 1 lock] |

### Supporting (instrumentation)

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| torch.profiler | bundled with torch ROCm wheel | Op-by-op kernel dispatch capture for AUDIT-02 | Per-model warm-call inside `tools/audit_op_coverage.py` |
| rocm-smi | bundled with ROCm 6.4 image | VRAM headroom + kernel-error polling for AUDIT-01 | 10s interval during 5-min co-residency window |
| amd-smi | bundled with ROCm 6.4 image | Backup memory probe; NOTE: amd-smi reports N/A on gfx1151 per ROCm/ROCm #6035 — do NOT rely on it for the gfx1151 registry side of the audit | MI300X (gfx942) only |
| scipy.stats.bootstrap | latest | 95% CIs on per-stage measurements (matches Phase 4 expectation) | Per-row aggregation in gate runners or Phase 4 |
| pandas 2.x | latest | Result aggregation | Per-gate post-processing |

### Alternatives Considered (and rejected)

| Instead of | Could Use | Rejected Because |
|------------|-----------|------------------|
| vLLM ROCm | SGLang ROCm | Less battle-tested at MI300X scale per CLAUDE.md §3.1 |
| faster-whisper CTranslate2 | whisper.cpp ROCm | INT8 ROCm path undersupported per CLAUDE.md §11; not measurement-grade |
| `rocm/vllm:rocm6.4_mi300_*` image (deprecated) | `vllm/vllm-openai-rocm:<tag>` | **NEW finding 2026:** AMD has deprecated `rocm/vllm` and `rocm/vllm-dev` in favor of official `vllm/vllm-openai-rocm`. [VERIFIED: docs.vllm.ai/en/stable/deployment/docker/] **HOWEVER:** CLAUDE.md §2.1 pin to `rocm/vllm` is still valid at ROCm 6.4 — operator chose this pin deliberately. Image deprecation does not invalidate digest pins. Plan should record this asymmetry and at plan-phase verify the digest still pulls. |

**Installation reference (in `Dockerfile.rocm`):**

```dockerfile
FROM rocm/vllm:rocm6.4_mi300_ubuntu22.04_py3.11_vllm_0.10.x

ARG GIT_COMMIT
RUN echo "${GIT_COMMIT}" > /workspace/.git_commit

# Harness deps. Pin faster-whisper + onnxruntime-rocm to ROCm 6.4 wheels.
RUN apt-get update && apt-get install -y --no-install-recommends \
    rsync openssh-client ca-certificates curl jq && \
    rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir \
    faster-whisper>=1.0,<2.0 \
    onnxruntime-rocm \
    livekit-agents==1.2.9 \
    livekit-plugins-silero \
    livekit-plugins-turn-detector \
    httpx[http2] \
    pydantic>=2.0 \
    jiwer>=4.0 \
    whisper-normalizer \
    pyloudnorm \
    pandas \
    scipy

# Pull our harness code last so changes don't bust the layer cache above.
COPY . /workspace/
ENTRYPOINT ["bash", "/workspace/tools/pod_entrypoint.sh"]
```

**Version verification at plan time:**

```bash
# In a Vultr MI300X pod after image pull:
python -c "import vllm; print(vllm.__version__)"      # expect 0.10.x
python -c "import torch; print(torch.__version__, torch.version.hip)"  # expect 2.5.x +rocm6.4 OR 2.6.x +rocm6.4.1
python -c "import faster_whisper; print(faster_whisper.__version__)"   # expect 1.0.x+
rocm-smi --version
```

Document the exact resolved versions in `env.json` per D-12.

## Architecture Patterns

### Recommended File Layout (new files Phase 3 introduces)

```
substrate/
└── rocm.py                          # HARNESS-03 — mirrors cuda.py composition
dockerfiles/rocm/
├── Dockerfile                       # FROM rocm/vllm:rocm6.4_mi300_*
└── (no .dockerignore — reuse repo-root)
scripts/
└── build_pod_image_rocm.sh          # mirrors build_pod_image.sh; --rail rocm
gates/g7/
└── runner.py                        # new — TTS A/B render (warm + cold)
tools/
├── audit_op_coverage.py             # AUDIT-02 — torch.profiler trace + gfx1151 cross-ref
├── audit_co_residency.py            # AUDIT-01 — 5-min sustained + rocm-smi poll
└── chatterbox_d1_smoke.py           # GATE-CHATTERBOX-D1 — kill-switch probe
audit/
├── chatterbox_d1_decision.md        # D-38 long-form
└── gfx1151_op_status.md             # AUDIT-02 deliverable
orchestration/
└── vultr_mi300x.py                  # fill stub with real /v2/instances provisioning
```

### Pattern 1: Substrate Composition (mirrors Phase 2)

**What:** Single `ROCmSubstrate` class composing 4 adapters; HTTP-only seams for vLLM / Chatterbox / Kokoro; in-process for faster-whisper.

**When to use:** Drop-in replacement for `_StubSubstrate` on the ROCm rail.

**Example:**
```python
# substrate/rocm.py — mirrors substrate/cuda.py:CUDASubstrate exactly
# Only changes: image lock entry name, model_dir paths, and:
#   - device="cuda" → device="cuda" stays the same (ROCm exposes HIP as CUDA-shim through torch)
#   - But verify torch.cuda.is_available() returns True — see Pitfall 1
class ROCmSubstrate(Substrate):
    def __init__(self, *, vllm_url, vllm_model, whisper_model_dir, chatterbox_url, kokoro_url, ...):
        self._vllm = VLLMClient(base_url=vllm_url, model=vllm_model)
        self._stt = FasterWhisperEngine(model_dir=whisper_model_dir, device="cuda", compute_type="int8")
        self._chatterbox = ChatterboxClient(base_url=chatterbox_url)
        self._kokoro = KokoroClient(base_url=kokoro_url)
        # ...exactly the same composition as CUDASubstrate from here on.
    # ...async transcribe/generate/synthesize with DR-27 fallback in synthesize() — identical to cuda.py.
    # env_fingerprint returns substrate="rocm"; _query_gpu uses rocm-smi instead of nvidia-smi.
```

[VERIFIED: substrate/cuda.py:39-241 in repo]

### Pattern 2: vLLM Concurrency Sweep for G1

**What:** Three discrete pod runs at concurrency N=1, 2, 4. Each pod runs `benchmark_serving.py` once with `--max-concurrency N` against the full 500-call corpus.

**When to use:** GATE-G1 LLM-stage measurement (TTFT / ITL / decode tokens-per-sec).

**Why three pods, not one walk:** Cold-cache effects bleed between concurrency levels in a single process. AMD's own MI300X benchmarking guide (issue #9070) runs each concurrency level as a fresh process invocation. [CITED: github.com/vllm-project/vllm/issues/9070]

**Example serve command (inside pod):**
```bash
# vLLM serve (from rocm/vllm image)
python -m vllm.entrypoints.openai.api_server \
    --model Qwen/Qwen3-4B \
    --revision <SHA from bench/models.lock.yaml> \
    --quantization awq \
    --dtype auto \
    --max-num-seqs 4 \
    --guided-decoding-backend xgrammar \
    --host 0.0.0.0 --port 8000 &

# Benchmark client (separate process; from upstream vllm repo)
python vllm/benchmarks/benchmark_serving.py \
    --backend openai \
    --base-url http://localhost:8000 \
    --model Qwen/Qwen3-4B \
    --dataset-name custom \
    --custom-output-len 64 \
    --max-concurrency ${N} \
    --num-prompts 500 \
    --percentile-metrics ttft,tpot,itl,e2el \
    --metric-percentiles 50,90,99 \
    --output-json results/g1/N${N}_${RUN_ID}.json
```

[CITED: docs.vllm.ai/en/latest/benchmarking/cli/, github.com/vllm-project/vllm/blob/main/benchmarks/benchmark_serving.py]

**Note:** The vLLM `benchmark_serving.py` measures *LLM stage only*. For end-to-end per-stage decomposition (STT TTFT + LLM TTFT + LLM decode + TTS first-audio), use the LiveKit `AgentSession` rig that already exists from Phase 2 (`substrate/livekit_pipeline.py`). The vLLM benchmark is a *ceiling check* on the LLM stage; the LiveKit rig is the E2E truth. Both rows go into `results/g1/`, discriminated by `extras.measurement_source: vllm_bench | livekit_e2e`. [CITED: docs.livekit.io/agents/build/session/]

### Pattern 3: Co-residency Sustained Run (AUDIT-01)

**What:** Single Python harness loads all 3 model classes, runs a 5-min loop of N=2 concurrent E2E calls (random-permuted 500-call slice), polls `rocm-smi` every 10s, fires the D-37 config-row TTS-swap at the 2:30 mark.

**When to use:** P3.7 AUDIT-01 deliverable.

**Why hand-rolled:** No off-the-shelf "load 3 models concurrently on one GPU and watch them" tool exists. The minimal methodology exercises (a) memory headroom, (b) kernel error capture, (c) the actual D-37 swap mechanism — three concerns one harness covers.

**Example skeleton (`tools/audit_co_residency.py`):**
```python
import asyncio, json, subprocess, time, random
from substrate.rocm import ROCmSubstrate
# ... build substrate, load_stt/load_llm/load_tts up front (warm-load) ...

async def _run_call(substrate, audio_bytes, prompt):
    # full E2E: transcribe → generate → synthesize, discarding outputs
    ...

async def _poll_rocm_smi(stop_evt, log_path):
    # rocm-smi --showmeminfo vram --json every 10s
    # Also: dmesg | tail -50 every 10s grepping for "amdgpu" errors
    ...

async def main():
    substrate = ROCmSubstrate(...)
    await substrate.load_stt(); await substrate.load_llm(); await substrate.load_tts()
    # Pre-load: confirm all 3 are healthy before starting
    corpus = _load_random_slice(N=200)  # ~5 min at conc=2
    stop_evt = asyncio.Event()
    poll_task = asyncio.create_task(_poll_rocm_smi(stop_evt, "results/audit_01/rocm_smi.jsonl"))
    swap_task = asyncio.create_task(_schedule_tts_swap_at(150))  # T+2:30
    try:
        await asyncio.wait_for(
            asyncio.gather(*[_run_call(substrate, *c) for c in corpus]),
            timeout=300,
        )
    finally:
        stop_evt.set()
        await poll_task
```

[VERIFIED: rocm-smi `--showmeminfo vram` + `--json` flag pattern, manpages.ubuntu.com/manpages/noble/man1/rocm-smi.1.html]

### Pattern 4: gfx1151 Op-Coverage Audit (AUDIT-02)

**What:** torch.profiler Chrome-JSON capture per model, then a manual+scripted cross-reference against a hand-curated gfx1151 kernel registry.

**When to use:** P3.8 AUDIT-02 deliverable. THE load-bearing input for Phase 4 derating.

**Why hand-rolled:** As of May 2026, no tool enumerates "which aten/HIP ops are native on gfx1151 vs fall back to CPU." The information is scattered across (a) ROCm/TheRock release notes per wheel cut, (b) PyTorch issue tracker (especially #171687, #6034, #5853, #5643), (c) hipBLASLt supported-arch list. The audit *codifies that scattered knowledge into one table per op used by our 4 models*.

**Methodology (4 steps):**

1. **Capture op trace on MI300X (gfx942) — one per model.** Wrap a single representative inference call with `torch.profiler.profile(activities=[CPU, CUDA], record_shapes=True)`, export Chrome trace JSON. The trace lists every aten op + GPU kernel name + input shapes that fired. [CITED: docs.pytorch.org/docs/stable/profiler.html]

2. **Extract the op set per model.** Parse the Chrome JSON, collect distinct `(aten_op, kernel_name)` pairs. Expect ~50-200 distinct ops per model.

3. **Build the gfx1151 kernel registry (one-time, manual).** From the sources below, populate `audit/gfx1151_registry.yaml`:
   - **PyTorch issue #171687** (gfx1151 decode = ~90% `hipMemcpyWithStream` in FP16 + 4-bit) — flags memory-copy intensive ops as "compute-bound on MI300X, memory-bound on gfx1151."
   - **PyTorch issue #6034** (5 critical bf16 bugs on gfx1151; AOTriton 19× speedup undocumented) — flags bf16 ops, attention ops.
   - **hipBLASLt supported-arch list** (gfx90a + gfx94x supported; gfx11xx falls back to hipBLAS) — flags `aten::mm`, `aten::addmm`, `aten::bmm` as "MI300X uses hipBLASLt; gfx1151 uses hipBLAS (slower path)."
   - **ROCm/TheRock release notes** — flags ops with native gfx1151 kernels (post ROCm 7.0) vs ops compiled via `gfx11-generic` ISA target (compatibility path, lower performance).
   - **ROCm/ROCm issue #5853** (Strix Halo segfault on VRAM access with torch nightly) — flags unstable ops on the most recent wheels.

4. **Emit the cross-reference table** as `audit/gfx1151_op_status.md`:

```markdown
| Op (aten name) | Used By | gfx942 Status | gfx1151 Status | Source | Derate Hint |
|----------------|---------|---------------|----------------|--------|-------------|
| aten::mm | Qwen3-4B, Whisper | native (hipBLASLt) | fallback (hipBLAS) | hipBLASLt issue #1243 | LLM prefill compute-bound, expect 3-5× slowdown beyond bandwidth ratio |
| aten::sdpa (flash) | Qwen3-4B | AOTriton native | AOTriton native (post ROCm 7.0) | ROCm/ROCm #6034 | minimal extra derate |
| aten::layer_norm (bf16) | Qwen3-4B | native | KNOWN BUG #6034 | ROCm/ROCm #6034 | flag as RISK in synthesis |
| aten::conv1d (Whisper encoder) | Whisper | native | native via gfx11-generic | TheRock release notes | bandwidth-bound; standard derate |
| ... | ... | ... | ... | ... | ... |
```

[CITED: github.com/pytorch/pytorch/issues/171687, github.com/ROCm/ROCm/issues/6034, github.com/ROCm/ROCm/issues/5853, github.com/ROCm/hipBLASLt/issues/1243]

**Output to Phase 4:** The "Derate Hint" column feeds the CLAUDE.md §7.3 compute-bound-vs-bandwidth-bound classification per op rather than per stage. This tightens the derating model materially.

### Pattern 5: Chatterbox Kill-Switch Probe (D-35)

**What:** A 4-check probe that runs on Day 1, writes `audit/chatterbox_d1_decision.md`, and writes the decision row that drives D-37.

**When to use:** First thing on the MI300X pod after Chatterbox container starts.

**Example skeleton (`tools/chatterbox_d1_smoke.py`):**
```python
import httpx, soundfile as sf, io, time, subprocess
TEST_PROMPT = "The quick brown fox jumps over the lazy dog. " * 3  # ~5 sec audio

def check_1_container_started() -> tuple[bool, str]:
    # docker ps / podman ps grep chatterbox; check GPU device count > 0 via:
    # docker exec <container> python -c "import torch; print(torch.cuda.device_count())"
    ...

def check_2_endpoint_responds_in_60s() -> tuple[bool, str, bytes]:
    start = time.monotonic()
    try:
        r = httpx.post("http://localhost:8004/v1/audio/speech",
                       json={"input": TEST_PROMPT, "voice": "default"},
                       timeout=60.0)
        elapsed = time.monotonic() - start
        return (r.status_code == 200 and elapsed < 60.0, f"status={r.status_code} elapsed={elapsed:.1f}s", r.content)
    except Exception as e:
        return (False, f"exception: {type(e).__name__}: {e}", b"")

def check_3_pcm_valid(audio_bytes: bytes) -> tuple[bool, str]:
    try:
        data, sr = sf.read(io.BytesIO(audio_bytes))
        rms = (data**2).mean()**0.5
        dur = len(data) / sr
        ok = rms > 0.01 and dur > 1.0
        return (ok, f"sr={sr} rms={rms:.3f} dur={dur:.2f}s")
    except Exception as e:
        return (False, f"sf.read failed: {type(e).__name__}: {e}")

def check_4_no_exceptions_in_logs() -> tuple[bool, str]:
    # docker logs <container> --since 30s; grep -i "exception|traceback|error"
    ...
```

[VERIFIED: D-35 pass criteria in CONTEXT.md §Chatterbox kill-switch]

### Anti-Patterns to Avoid

- **Building a custom WER scorer.** Use jiwer 4.x. STACK.md §4.4 / Phase 1 lock already settled this.
- **Building a custom audio loudness normalizer.** Use `pyloudnorm`. (Locked in CLAUDE.md §10.)
- **Latency-gating the Chatterbox kill-switch.** D-35 explicitly excludes latency; mixing it in creates thermal/first-pull flake.
- **Single-pod concurrency walk N=1→2→4.** Cold-cache effects bleed; use three pods (per Claude's-Discretion default).
- **Trusting `amd-smi` on gfx1151.** ROCm/ROCm #6035 — amd-smi reports N/A for all fields on gfx1151. Only matters when we eventually validate on Strix Halo, but document so we don't write code that depends on it.
- **`torch.cuda.device_count()` without a sanity check.** CLAUDE.md §5.1 Pitfall: ROCm device enumeration can show count=0 even when rocminfo succeeds, due to torch/ROCm version mismatch. Use *both* `rocminfo` and `torch.cuda.device_count()` in the kill-switch.
- **Mixing `rocm/vllm` and `vllm/vllm-openai-rocm` images in one rail.** Pick one (CLAUDE.md says `rocm/vllm`); plan-phase verifies digest still pulls.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| LLM concurrency / TTFT / ITL measurement | Custom request driver | `vllm/benchmarks/benchmark_serving.py` with `--max-concurrency`, `--percentile-metrics ttft,tpot,itl,e2el`, `--output-json` | Battle-tested at MI300X; emits identical JSON shape across CUDA / ROCm rails for cross-substrate consistency [CITED: docs.vllm.ai/en/latest/benchmarking/cli/] |
| Per-turn pipeline timestamps | Manual `time.monotonic()` between substrate calls | LiveKit `AgentSession` emits `ChatMessage.metrics` per turn | Native instrumentation; matches production runtime (PRD §4.2) [CITED: docs.livekit.io/agents/build/session/] |
| WER scoring | Custom edit-distance | `jiwer>=4.0` + Whisper `BasicTextNormalizer` | Phase 1 lock |
| G.711 μ-law transcoding | Custom codec | `ffmpeg 7.x` `pcm_mulaw` (Phase 1 `assets/g711.py` reuses) | Phase 1 ASSETS-07 complete |
| Confidence intervals | Manual stats | `scipy.stats.bootstrap` (n=10000, percentile method) | CLAUDE.md §10 lock |
| TTS loudness normalization for A/B | Manual RMS scaling | `pyloudnorm` (EBU R128) | CLAUDE.md §10 lock |
| Op-by-op kernel capture for AUDIT-02 | Custom hooks | `torch.profiler.profile(activities=[CPU, CUDA], record_shapes=True)` + Chrome JSON export | The standard PyTorch instrumentation; works on ROCm via the HIP/CUDA shim [CITED: docs.pytorch.org/docs/stable/profiler.html] |
| ROCm memory monitoring | `nvidia-smi`-style polling re-implementation | `rocm-smi --showmeminfo vram --json` | Bundled with image; structured JSON output [VERIFIED: manpages.ubuntu.com/manpages/noble/man1/rocm-smi.1.html] |
| Grammar-constrained generation | Custom JSON schema validator | `--guided-decoding-backend xgrammar` in vLLM serve | Phase 2 already established this; xgrammar is 100× faster than outlines [CITED: docs.vllm.ai/en/latest/features/structured_outputs/] |
| Vultr provisioning | shell-out to `curl /v2/instances` | Vultr Python SDK or existing `cost/adapters/vultr.py` shape (extend with `create_instance`/`delete_instance`) | `cost/adapters/vultr.py` is already real; adding provisioning calls keeps one auth path |

**Key insight:** Phase 3 has nearly zero greenfield code. The substrate + gate runners + watchdog + audit + rsync + provenance are all carried forward from Phase 2 with provider/image swap. The actual new code is `vultr_mi300x.py:provision()` (mirrors `runpod_h100.py`), `g7/runner.py` (mirrors g1-5 structure), `audit_op_coverage.py` (greenfield, ~150 LOC), `audit_co_residency.py` (greenfield, ~200 LOC), `chatterbox_d1_smoke.py` (greenfield, ~100 LOC). Total estimate: ~600-800 LOC of new code + ~200 LOC of cuda.py→rocm.py port. Most Phase 3 time should land in *real-spend execution + debug*, not authoring.

## Common Pitfalls

### Pitfall 1: ROCm device enumeration shows count=0 when rocminfo succeeds
**What goes wrong:** `torch.cuda.device_count()` returns 0 inside the Chatterbox container even though `rocminfo` from the same container shows MI300X cleanly.
**Why it happens:** torch ROCm wheel mismatched with the container's ROCm runtime version. devnen issue #92 documents exactly this for ROCm 6.4 vs torch 2.5.1 vs torch 2.6.0+rocm6.4.1.
**How to avoid:** Use the `Dockerfile.rocm` from devnen upstream directly, which pins torch via `--no-deps` install and avoids the version conflict. In the kill-switch (D-35 check 1), probe *both* `rocminfo` (kernel/runtime) and `torch.cuda.device_count()` (Python/ABI) — they must agree.
**Warning signs:** `torch.cuda.is_available() == False` despite a healthy `rocminfo`; "HSA: error" or "hipErrorNoBinaryForGpu" in container logs.
[VERIFIED: github.com/devnen/Chatterbox-TTS-Server/issues/92]

### Pitfall 2: hipBLASLt → hipBLAS fallback (not a bug; expected on gfx1151)
**What goes wrong:** PyTorch emits warning "Attempting to use hipBLASLt on a unsupported architecture!" when running on gfx1151 (Strix Halo). Workload still completes, but at ~3-5× slower for gemm-heavy ops.
**Why it happens:** hipBLASLt is supported on gfx90a + gfx94x (MI300X is gfx942 → supported). gfx1151 falls back to hipBLAS.
**How to avoid:** Cannot avoid on Strix Halo. **On MI300X this does NOT happen** — but the audit must flag every `aten::mm` / `aten::addmm` / `aten::bmm` use as "MI300X uses hipBLASLt; Strix Halo uses hipBLAS slower path" in the op-status table. Phase 4 derate hint = additional 3-5× factor on gemm-heavy stages beyond bandwidth ratio.
**Warning signs:** Warning in stderr on the Strix Halo side; on MI300X side, *no* warning — which is the point of the audit. If a future operator silences the warning with `TORCH_BLAS_PREFER_HIPBLASLT=0`, the derate goes away too.
[VERIFIED: github.com/ROCm/hipBLASLt/issues/1243, github.com/pytorch/pytorch/issues/138067]

### Pitfall 3: gfx1151 decode dominated by hipMemcpyWithStream
**What goes wrong:** On gfx1151, LLM decode is consistently dominated (~90% of time) by `hipMemcpyWithStream` operations rather than compute kernels. Tokens/sec on a 70B model: 1.4-1.6, far below what bandwidth alone predicts.
**Why it happens:** Strix Halo's iGPU shares memory with the CPU via a different memory path than discrete GPUs. PyTorch's HIP path emits more sync `hipMemcpy` calls than necessary in this regime.
**How to avoid:** Cannot fix on Strix Halo (root cause is upstream PyTorch ROCm + kernel boundary). Phase 4 derate model must include a `hipMemcpy` overhead term beyond the bandwidth ratio — this is the *new* finding that CLAUDE.md §7.2 does not capture. Op-audit must flag memory-copy-heavy code paths in the per-op table.
**Warning signs:** Strix Halo decode tok/s far below the (bandwidth ÷ model size) prediction; absent on MI300X.
[VERIFIED: github.com/pytorch/pytorch/issues/171687 (Nov 2025; load-bearing for derating)]

### Pitfall 4: amd-smi reports all-N/A on gfx1151
**What goes wrong:** `amd-smi monitor` returns N/A for power, temperature, VRAM, utilization on gfx1151 even though the kernel exposes the data.
**Why it happens:** User-space `amd-smi` tools haven't been updated for gfx1151's SMI surface.
**How to avoid:** Use `rocm-smi` (which works on MI300X for VRAM headroom polling in AUDIT-01) and read sysfs directly on Strix Halo. **Phase 0 cloud-only does not actually run on Strix Halo, so this is a future-Phase concern** — but the AUDIT-02 deliverable should call it out so Phase 1+ scripting doesn't assume `amd-smi` works.
[VERIFIED: github.com/ROCm/ROCm/issues/6035]

### Pitfall 5: CTranslate2 ROCm determinism varies by build
**What goes wrong:** `faster-whisper` with `beam_size=1` (deterministic decode) can produce slightly different WER on MI300X vs H100 even with identical input bytes, due to numerical reduction order differences in CTranslate2's ROCm kernel.
**Why it happens:** Floating-point non-associativity in reduction kernels.
**How to avoid:** Treat WER deltas <0.5 percentage points across rails as expected. If WER differs by >1 point H100 vs MI300X with same `beam_size=1` + same normalizer, **fall back to the ONNX-RT ROCm path for the WER-of-record** — G2's dual-path design (D-Discretion) anticipated this.
**Warning signs:** `metrics.wer` differs by >0.5 pp between substrate=cuda and substrate=rocm rows on the same asset.
[VERIFIED: rocm.blogs.amd.com/artificial-intelligence/ctranslate2/README.html; expected behavior per CT2 docs]

### Pitfall 6: vLLM AWQ quantization on ROCm 6.4 — version surface
**What goes wrong:** AWQ INT4 support in vLLM ROCm matured between 0.10.0 and 0.10.x. The `rocm/vllm:rocm6.4_mi300_*` image's exact vLLM version drift may not include AITER-MOE / AWQ optimizations described in later release notes.
**Why it happens:** CLAUDE.md §3.1 confidence MEDIUM acknowledges this; vLLM 0.14.x is the latest with AITER-MOE auto-defaults but it requires ROCm 7.0+.
**How to avoid:** At plan-phase, verify `python -c "import vllm; print(vllm.__version__)"` inside the pulled image; record exact version in `bench/images.lock.yaml` and `env.json`. If AWQ throws "unsupported quantization", fall back to FP16 measurement and document the substitution per CLAUDE.md §14 (already flagged MEDIUM confidence on AWQ ↔ Q4_K_M).
[CITED: rocm.blogs.amd.com/software-tools-optimization/vllm-omni/README.html, github.com/vllm-project/vllm/releases]

### Pitfall 7: vLLM benchmark concurrency reporting in table omits per-N rows
**What goes wrong:** `benchmark_serving.py` aggregates across the full run; if you pass `--max-concurrency 4` it does not report N=1 / N=2 / N=4 within one run.
**Why it happens:** That's the design — concurrency is a *workload knob*, not a sweep dimension.
**How to avoid:** Three discrete invocations (one per N), three JSON files, three rows per asset in our results. GitHub issue #21094 confirms this and tracks a feature request to add concurrency to the result table. Our G1 design (D-Discretion) already runs three pods.
[VERIFIED: github.com/vllm-project/vllm/issues/21094]

### Pitfall 8: AgentSession concurrency model is process-per-session
**What goes wrong:** Naive `asyncio.gather(session_a.run(), session_b.run())` may not actually parallelize at the backend level because LiveKit's design point is one process per session.
**Why it happens:** LiveKit horizontally scales by *worker process*; concurrency inside one Python process is not the primary path.
**How to avoid:** For G1 N=2/4 concurrency, use `asyncio.gather` against N independent `AgentSession` instances **all pointing at the same vLLM + Chatterbox + Kokoro server URLs** so concurrency lands at the backend level where it actually matters. Verify by inspecting vLLM server-side `running_requests` metric — it should peak at N during the run.
**Warning signs:** vLLM server-side `running_requests` stays at 1 during N=4 run; TTFT scales linearly with N rather than sub-linearly.
[CITED: docs.livekit.io/agents/build/session/]

### Pitfall 9: xgrammar constraint failures vs engine errors — separate, don't collapse
**What goes wrong:** G5 reports a single "fail rate" that conflates (a) xgrammar successfully constrained output but the LLM produced a refusal in JSON shape, (b) xgrammar's compiler rejected the schema, (c) generation timeout / OOM, (d) HTTP 500.
**Why it happens:** vLLM logs distinguish these but `extras.error` doesn't out of the box.
**How to avoid:** Add a per-row `extras.constraint_status` field with discrete values: `constraint_ok` (output parsed as valid JSON matching schema), `constraint_miss_invalid_json` (engine yielded chunks but JSON.parse failed), `engine_error_5xx` (vLLM threw), `engine_timeout` (generation exceeded `max_tokens` without close-brace). Phase 4 reports per-category pass rate broken out from raw refusal rate.
**Warning signs:** G5 SM-71 fail at high rate but no clear root cause; raw rate of "fails" mixes 4 mechanisms.
[CITED: developers.redhat.com/articles/2025/06/03/structured-outputs-vllm-guiding-ai-responses; arxiv.org/html/2509.06631v1]

### Pitfall 10: vultr_mi300x.py provisioning — same pod-image-CMD gap as Phase 2 incident
**What goes wrong:** Phase 2 plan 06 documented a 21-min pod that burned $1.05 because `BOOTSTRAP_MODE=1` env was set but the upstream image's CMD ignored it and `pod_entrypoint.sh` never ran. Same trap exists on the ROCm rail unless `Dockerfile.rocm` has `ENTRYPOINT ["bash", "/workspace/tools/pod_entrypoint.sh"]`.
**Why it happens:** Pulling a vendor's image (rocm/vllm) without overriding ENTRYPOINT lands you on the vendor's CMD (vLLM serve), not our entrypoint.
**How to avoid:** **D-32 already mandates a separate `rbox-pod-rocm` image with `tools/pod_entrypoint.sh` baked as ENTRYPOINT.** The plan MUST NOT shortcut to `image=rocm/vllm:...` directly on the ROCm rail — that is the exact mistake that cost $1.05 on the CUDA rail and would cost similar on Vultr. The `_DEFAULT_IMAGE_ROCM` loud-fail sentinel pattern from Phase 2 plan 06 must be replicated.
[VERIFIED: .planning/phases/02-cuda-pre-flight/02-06-SUMMARY.md; same incident pattern]

### Pitfall 11: gfx1151 PyTorch wheel sourcing — pytorch.org wheels do not work
**What goes wrong:** Standard `pip install torch --index-url https://download.pytorch.org/whl/rocm6.4` works on MI300X. The same install on Strix Halo loads the wheel cleanly but fails on first compute with `HIP error: invalid device function`.
**Why it happens:** pytorch.org's torch ROCm wheels are built for gfx90a + gfx94x + gfx110x but NOT gfx1151 native kernels.
**How to avoid:** For the AUDIT-02 cross-reference, the gfx1151 side must use **TheRock nightlies** (`rocm.nightlies.amd.com/v2/gfx1151/`) or **scottt/rocm-TheRock prebuilt wheels**, NOT pytorch.org wheels. Phase 0 doesn't install on Strix Halo, but the registry side of the audit must cite the wheel source explicitly so Phase 1+ doesn't pick the wrong wheel.
[VERIFIED: github.com/ROCm/TheRock/discussions/655, llm-tracker.info/_TOORG/Strix-Halo]

## Code Examples

### Example 1: ROCmSubstrate composition (HARNESS-03)
```python
# substrate/rocm.py — mirrors substrate/cuda.py exactly; only env_fingerprint() differs.
class ROCmSubstrate(Substrate):
    def __init__(self, *, vllm_url, vllm_model, whisper_model_dir, chatterbox_url, kokoro_url,
                 images_lockfile=_DEFAULT_IMAGES_LOCK, models_lockfile=_DEFAULT_MODELS_LOCK):
        self._vllm = VLLMClient(base_url=vllm_url, model=vllm_model)
        self._stt = FasterWhisperEngine(model_dir=whisper_model_dir, device="cuda", compute_type="int8")
        self._chatterbox = ChatterboxClient(base_url=chatterbox_url)
        self._kokoro = KokoroClient(base_url=kokoro_url)
        self._loaded = {"stt": False, "llm": False, "tts": False}
        self._images_lockfile = images_lockfile
        self._models_lockfile = models_lockfile
        self._vllm_url = vllm_url

    # ...load_stt/load_llm/load_tts/transcribe/generate/synthesize — IDENTICAL to cuda.py...

    def env_fingerprint(self) -> EnvFingerprint:
        from harness import env_fingerprint as efp
        image_digest = self._lookup_image_digest()  # reads RBOX_IMAGE_DIGEST env first (DEV-1021)
        model_shas = self._lookup_model_shas()
        gpu_sku, gpu_count = self._query_gpu()  # uses rocm-smi instead of nvidia-smi
        rocm_version, pytorch_version = self._query_torch_versions()
        vllm_version = self._query_vllm_version()
        return efp.capture(
            substrate="rocm",
            image_digest=image_digest, model_shas=model_shas,
            gpu_sku=gpu_sku, gpu_count=gpu_count,
            rocm_version=rocm_version, pytorch_version=pytorch_version,
            vllm_version=vllm_version,
        )

    @staticmethod
    def _query_gpu() -> tuple[str, int]:
        try:
            result = subprocess.run(
                ["rocm-smi", "--showproductname", "--json"],
                capture_output=True, text=True, check=False, timeout=5,
            )
            if result.returncode != 0:
                return ("unknown", 0)
            data = json.loads(result.stdout)
            # rocm-smi --json schema: {"card0": {"Card series": "MI300X", ...}, ...}
            cards = [v for k, v in data.items() if k.startswith("card")]
            if not cards:
                return ("unknown", 0)
            return (cards[0].get("Card series", "unknown"), len(cards))
        except (FileNotFoundError, subprocess.TimeoutExpired, json.JSONDecodeError):
            return ("unknown", 0)
```
[VERIFIED: substrate/cuda.py:39-241 pattern; rocm-smi --json output confirmed via rocm.docs.amd.com]

### Example 2: vLLM serve command for G1 LLM-stage measurement
```bash
# Inside the rbox-pod-rocm container. Started by pod_entrypoint.sh when GATE=g1.
python -m vllm.entrypoints.openai.api_server \
    --model /models/qwen3_4b_awq \
    --quantization awq \
    --dtype auto \
    --max-model-len 4096 \
    --max-num-seqs 4 \
    --guided-decoding-backend xgrammar \
    --host 0.0.0.0 --port 8000 \
    > /tmp/vllm.log 2>&1 &

# Wait for server ready
until curl -s http://localhost:8000/health > /dev/null; do sleep 2; done

# Run concurrency sweep — three separate processes, three JSON outputs
for N in 1 2 4; do
    python /workspace/vllm/benchmarks/benchmark_serving.py \
        --backend openai \
        --base-url http://localhost:8000 \
        --model /models/qwen3_4b_awq \
        --dataset-name custom \
        --dataset-path /workspace/assets/g1_corpus_500.jsonl \
        --num-prompts 500 \
        --max-concurrency $N \
        --percentile-metrics ttft,tpot,itl,e2el \
        --metric-percentiles 50,90,99 \
        --output-json /workspace/results/g1/vllm_bench_N${N}.json
done
```
[CITED: docs.vllm.ai/en/latest/benchmarking/cli/]

### Example 3: torch.profiler op trace for AUDIT-02
```python
# tools/audit_op_coverage.py — capture op trace for one model, emit Chrome JSON.
import torch
from torch.profiler import profile, ProfilerActivity, record_function
from substrate.adapters import VLLMClient, FasterWhisperEngine, ChatterboxClient, KokoroClient
import json, pathlib

def capture_model_ops(model_name: str, warm_call_fn, output_dir: pathlib.Path) -> set[str]:
    """Run one warm call under torch.profiler, dump Chrome JSON, return op set."""
    # Warm up — first call always JITs / compiles kernels we don't want in the trace.
    warm_call_fn()

    trace_path = output_dir / f"{model_name}_ops.json"
    with profile(
        activities=[ProfilerActivity.CPU, ProfilerActivity.CUDA],
        record_shapes=True,
        with_stack=False,
    ) as prof:
        with record_function(f"{model_name}_inference"):
            warm_call_fn()
    prof.export_chrome_trace(str(trace_path))

    # Extract distinct (aten_op, kernel_name) pairs from the Chrome JSON.
    with open(trace_path) as f:
        trace = json.load(f)
    ops = set()
    for ev in trace.get("traceEvents", []):
        name = ev.get("name", "")
        cat = ev.get("cat", "")
        if cat in ("kernel", "gpu_op", "cpu_op") and name:
            ops.add((cat, name))
    return ops

# Then cross-reference each op against audit/gfx1151_registry.yaml and emit
# the per-op row in audit/gfx1151_op_status.md (see Pattern 4 above).
```
[CITED: docs.pytorch.org/docs/stable/profiler.html]

### Example 4: rocm-smi VRAM headroom polling for AUDIT-01
```python
# Inside tools/audit_co_residency.py — polls every 10s during sustained run.
async def _poll_rocm_smi(stop_evt: asyncio.Event, log_path: pathlib.Path):
    while not stop_evt.is_set():
        try:
            result = await asyncio.create_subprocess_exec(
                "rocm-smi", "--showmeminfo", "vram", "--showuse", "--json",
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await result.communicate()
            data = json.loads(stdout)
            # Schema: {"card0": {"VRAM Total Memory (B)": "...", "VRAM Total Used Memory (B)": "...", "GPU use (%)": "..."}}
            for card_key, card in data.items():
                if not card_key.startswith("card"):
                    continue
                total_b = int(card["VRAM Total Memory (B)"])
                used_b = int(card["VRAM Total Used Memory (B)"])
                util = card.get("GPU use (%)", "0")
                pct_used = 100.0 * used_b / total_b if total_b else 0.0
                row = {
                    "ts": time.time(), "card": card_key,
                    "vram_pct": pct_used, "gpu_util": util,
                }
                with open(log_path, "a") as f:
                    f.write(json.dumps(row) + "\n")
                if pct_used > 90.0:
                    logger.warning(f"[audit-01] VRAM pressure: {pct_used:.1f}% on {card_key}")
        except Exception as e:
            logger.warning(f"[audit-01] rocm-smi probe failed: {type(e).__name__}: {e}")
        await asyncio.sleep(10)
```
[VERIFIED: manpages.ubuntu.com/manpages/noble/man1/rocm-smi.1.html]

### Example 5: G3 threshold sweep (silero + LiveKit turn-detector)
```python
# gates/g3/runner.py — single-substrate loop over 12 thresholds.
THRESHOLDS_MS = list(range(400, 1600, 100))  # 400, 500, ..., 1500

async def run_g3_sweep(substrate, asset_set):
    for threshold_ms in THRESHOLDS_MS:
        # silero-vad min_silence_duration_ms = threshold_ms
        # LiveKit min_endpointing_delay_ms = threshold_ms
        for asset in asset_set:
            detected_ms = await substrate.detect_endpoint(
                asset.audio,
                vad_min_silence_ms=threshold_ms,
                endpoint_min_delay_ms=threshold_ms,
            )
            row = build_result(
                gate="g3", substrate="rocm", asset_id=asset.id,
                metrics={
                    "detected_endpoint_ms": detected_ms,
                    "ground_truth_endpoint_ms": asset.gt_endpoint_ms,
                    "false_positive": detected_ms < asset.gt_endpoint_ms,
                },
                extras={"threshold_ms": threshold_ms},
            )
            write_jsonl(row, f"results/g3/{run_id}.jsonl")
```
[CITED: docs.livekit.io/agents/build/turns/turn-detector/, github.com/snakers4/silero-vad]

## Runtime State Inventory

> Phase 3 is greenfield code on the ROCm rail. No rename/refactor of existing runtime state. This section is included only for completeness.

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | None — Phase 3 only writes new `results/g{1,2,3,5,7}/` JSONL + `audit/*.md` artifacts; no schema migration of prior Phase 2 results | None |
| Live service config | None — Vultr/TensorWave are stateless cloud pods; no service-side config to update | None |
| OS-registered state | None — Phase 3 runs ephemeral pods, no OS registration | None |
| Secrets / env vars | New env vars on ROCm rail: `VULTR_API_KEY`, `RBOX_IMAGE_DIGEST` (ROCm digest, distinct from CUDA digest). No existing secrets renamed. | Operator adds `VULTR_API_KEY` to secret store; `RBOX_IMAGE_DIGEST` is injected by `provision()` per DEV-1021 |
| Build artifacts | New: `ghcr.io/consultingfuture4200/rbox-pod-rocm:vN` registry path. Distinct from CUDA `ghcr.io/.../rbox-pod`. | `scripts/build_pod_image_rocm.sh` (or `--rail rocm` flag on existing script) builds + pushes |

## Environment Availability

> Phase 3 runs on a Vultr MI300X cloud pod, not the operator workstation. The "available" column reflects what the chosen base image provides.

| Dependency | Required By | Available in `rocm/vllm:rocm6.4_mi300_*` | Version | Fallback |
|------------|------------|------------------------------------------|---------|----------|
| Python 3.11 | All harness code | ✓ | 3.11 | — |
| ROCm runtime | torch, vllm, faster-whisper | ✓ | 6.4 | — |
| torch (ROCm) | substrate adapters, profiler | ✓ | 2.5.x or 2.6.x +rocm6.4 (verify at plan-phase) | — |
| vllm | LLM serve | ✓ | 0.10.x | — |
| faster-whisper | STT | ✗ (must `pip install`) | 1.x | onnxruntime-rocm path |
| onnxruntime-rocm | STT parallel | ✗ (must `pip install`) | latest matching ROCm 6.4 | — |
| devnen/Chatterbox-TTS-Server | TTS primary | ✗ (separate container, sidecar) | upstream main + Dockerfile.rocm | Kokoro |
| moritzchow/Kokoro-FastAPI-ROCm | TTS fallback / primary on D-1 fail | ✗ (separate container, sidecar) | upstream main | ONNX Kokoro |
| livekit-agents | E2E pipeline | ✗ (must `pip install`) | 1.2.9 (Phase 2 lock) | shim path |
| jiwer ≥4.0 | WER | ✗ (must `pip install`) | 4.x | — |
| ffmpeg 7.x | G.711 transcode | ✓ (typically present in rocm/vllm; verify) | 7.x | apt install if missing |
| rocm-smi | AUDIT-01 polling | ✓ | bundled with ROCm 6.4 | — |
| Vultr CLI / SDK | Provisioning | ✗ (operator workstation only) | latest | curl /v2/instances |
| jq | shell scripting in entrypoint | ✗ (must `apt install`; matches Phase 2 Dockerfile pattern) | latest | — |

**Missing dependencies with no fallback:** None — every required dependency either ships with the base image or is `pip install`-able into the derived `rbox-pod-rocm` image. The `Dockerfile.rocm` from devnen handles the Chatterbox install path; Kokoro upstream README handles its install.

**Missing dependencies with fallback:** Chatterbox-Turbo ROCm — fallback is Kokoro per DR-27 + D-37. This is the load-bearing fallback the Day-1 kill-switch (D-35) exists to make a binary decision on.

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `rocm/vllm` + `rocm/vllm-dev` Docker images | `vllm/vllm-openai-rocm:<tag>` upstream image | Q1 2026 (AMD deprecation announcement) | Phase 3 pin to `rocm/vllm:rocm6.4_mi300_*` still pulls; digest pinning insulates from registry-tag deprecation. Verify at plan-phase. [CITED: docs.vllm.ai/en/stable/deployment/docker/] |
| vLLM 0.10.x default backend = outlines | vLLM 0.10.x+ default backend = xgrammar | Late 2024 / early 2025 | Already locked. xgrammar is 10-100× faster than outlines for structured outputs. [CITED: docs.vllm.ai/en/latest/features/structured_outputs/] |
| jiwer 3.x | jiwer ≥4.0 + whisper-normalizer (separate dep) | Phase 1 STATE.md pinned this; CLAUDE.md §4.4 / STACK.md §4.4 reference to 3.x is stale | Use 4.0+ in `Dockerfile.rocm` pip install |
| Phoronix Nov 2025 Strix Halo "barely beats CPU" prompt processing | PyTorch issue #171687 quantifies: gfx1151 decode = ~90% `hipMemcpyWithStream` in FP16 + 4-bit | Nov 2025 issue filing | New derate input for Phase 4 beyond bandwidth ratio; AUDIT-02 should flag |
| `HSA_OVERRIDE_GFX_VERSION` hacks for gfx1151 with pytorch.org wheels | TheRock nightlies ship native gfx1151 kernels — no override needed | Q4 2025 (ROCm 7.0 release) | Phase 0 doesn't run on Strix Halo, but registry side of AUDIT-02 must source from TheRock, not pytorch.org [CITED: github.com/ROCm/TheRock/discussions/655] |

**Deprecated / outdated (do NOT regress to):**
- `outlines` library — use xgrammar (10-100× faster).
- `whisper.cpp` on cloud GPUs for INT8 measurement — use faster-whisper.
- Ollama for cloud-GPU LLM benchmarking — use vLLM (Ollama is correct for *appliance*, not for *cloud ceiling measurement*).
- pyannote-audio for streaming VAD — use silero-vad.
- pytorch.org torch ROCm wheels for any future gfx1151 work — use TheRock.

## Assumptions Log

> Claims tagged `[ASSUMED]` in this research that need user confirmation. Empty table = all claims verified or cited.

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | The `rocm/vllm:rocm6.4_mi300_ubuntu22.04_py3.11_vllm_0.10.x` tag still resolves to a valid digest as of plan-phase execution | Standard Stack, Architecture Pattern 1 | Plan-phase must `docker pull` and record the digest in `bench/images.lock.yaml` before any pod spend. If tag is removed, fall back to a later `rocm/vllm` tag at ROCm 6.4 OR switch to `vllm/vllm-openai-rocm` (different config surface — would require D-32 amendment). |
| A2 | LiveKit `AgentSession` 1.2.9 (Phase 2 lock) supports `record_metrics`-style per-turn timestamp emission that integrates with our `build_result()` flow | Architecture Pattern 1, Don't Hand-Roll | Phase 2 ran on this version; if `ChatMessage.metrics` surface changed across LiveKit minor versions, plan should pin and verify. |
| A3 | torch.profiler on ROCm 6.4 exports a Chrome trace JSON whose `traceEvents` schema matches the CUDA-side schema closely enough that AUDIT-02's parser is portable | Architecture Pattern 4, Code Example 3 | Plan-phase smoke: run profiler on a tiny matmul inside a Vultr MI300X pod *first*; confirm Chrome JSON schema before authoring `audit_op_coverage.py`. |
| A4 | Vultr's `/v2/instances` API for MI300X provisioning has the same shape as their general GPU endpoint already exercised by `cost/adapters/vultr.py` (billing path) | Don't Hand-Roll | Plan-phase verifies via Vultr API docs + a dry-run call (no real provisioning until cost-ledger gate passes). Adapter-only API ≠ provisioning API; this is the assumption with highest provisioning-bug risk. |
| A5 | Chatterbox-TTS-Server upstream `Dockerfile.rocm` builds cleanly on MI300X (not just on consumer Radeon cards) | Architecture Pattern 5, Pitfall 1 | If build fails on MI300X due to gfx942 vs gfx110x kernel differences, fall back to Kokoro per D-35/D-36 immediately — the 2-hr / $4 timebox is calibrated for exactly this kind of fail-fast. |
| A6 | `aten::mm` / `aten::addmm` show up in the torch.profiler trace for Qwen3-4B inference under vLLM (i.e., vLLM's compiled kernel does not bypass the aten dispatcher in a way that hides them) | Architecture Pattern 4 | If vLLM uses its own AITER kernels that bypass aten, AUDIT-02 must instead trace at the HIP kernel layer using `rocprof` or `omnitrace`. Plan-phase smoke validates the trace shape. |
| A7 | The 5-minute co-residency window is sufficient to surface OOM / kernel-mismatch failure modes that would otherwise emerge over hours of production | Architecture Pattern 3, CLAUDE.md §11 | Operator-set in D-Discretion. If MI300X stays healthy for 5 min and crashes at 30 min, AUDIT-01 declares pass but production fails. Mitigated by Phase 4 caveat language ("co-residency window: 5 min") and by Phase 1+ stability soak (STRIX-03, v2 requirement). |

**Recommendation:** Plan-phase should make A1, A2, A3, A4 explicit pre-execution checks in the first task ("Pod-image smoke + provisioning dry-run"), gating real-spend on their resolution.

## Open Questions

1. **Does `rocm/vllm:rocm6.4_mi300_ubuntu22.04_py3.11_vllm_0.10.x` still exist as a pullable tag in May 2026?**
   - What we know: AMD deprecated the `rocm/vllm` and `rocm/vllm-dev` Docker Hub images in favor of `vllm/vllm-openai-rocm`. Tag-deprecation timeline unclear.
   - What's unclear: Whether the specific `rocm6.4_mi300_*` tag remains pullable or has been removed.
   - Recommendation: Plan-phase task 1 = `docker pull` the tag, record digest, fail loudly if the pull fails. If failed, switch base image to `vllm/vllm-openai-rocm:<rocm6.4-tag>` and re-validate the harness pip-install list (most should be identical).

2. **Is `aten::mm` traceable via torch.profiler when vLLM is the LLM serve path, or does vLLM bypass aten dispatch?**
   - What we know: torch.profiler traces aten ops; vLLM's hot path uses Triton / AITER kernels that may or may not register at the aten layer.
   - What's unclear: Whether the gfx1151 op-coverage table is meaningful when the serving engine uses kernels-of-record that bypass aten.
   - Recommendation: AUDIT-02 captures profiler trace at *two* levels: (a) the model's forward pass run directly in PyTorch (one-time outside vLLM) for the aten-level op set, (b) inside vLLM serve for the actual production op set. The first feeds gfx1151 cross-reference; the second confirms the production code path uses those ops.

3. **Does the Vultr API support MI300X provisioning the same way as general GPU instances, or is it a separate sales-touched flow like TensorWave?**
   - What we know: `cost/adapters/vultr.py` is real and exercises `/v2/billing/pending-charges` cleanly. Provisioning side is stubbed.
   - What's unclear: Whether MI300X provisioning hits self-serve `/v2/instances` or requires reserved-instance contact (24-mo prepaid path in Vultr's pricing).
   - Recommendation: Plan-phase task = dry-run `POST /v2/instances` with MI300X plan-id (operator must obtain from Vultr docs / dashboard). If response is "contact sales", scope falls back to the same blocker as TensorWave and D-31's Day-1-Vultr decision needs operator override.

4. **Does devnen/Chatterbox-TTS-Server's `Dockerfile.rocm` work on MI300X (gfx942) or is it tuned for consumer Radeon (gfx110x)?**
   - What we know: Dockerfile.rocm exists upstream, addresses issue #92 via `--no-deps`, targets ROCm 6.4.1.
   - What's unclear: Whether the gfx942 vs gfx110x kernel-arch differences cause torch wheel/ROCm runtime mismatch even with `--no-deps`.
   - Recommendation: Build attempt happens inside the D-36 2-hr/$4 timebox. Fast pass-fail decision is the *point* of the kill-switch; this question doesn't need to be answered pre-Phase-3.

## Sources

### Primary (HIGH confidence)

- vLLM benchmark CLI — [docs.vllm.ai/en/latest/benchmarking/cli/](https://docs.vllm.ai/en/latest/benchmarking/cli/)
- vLLM structured outputs / xgrammar — [docs.vllm.ai/en/latest/features/structured_outputs/](https://docs.vllm.ai/en/latest/features/structured_outputs/)
- vLLM ROCm benchmark recipe — [rocm.docs.amd.com/en/latest/how-to/rocm-for-ai/inference/benchmark-docker/vllm.html](https://rocm.docs.amd.com/en/latest/how-to/rocm-for-ai/inference/benchmark-docker/vllm.html)
- vLLM `benchmark_serving.py` source — [github.com/vllm-project/vllm/blob/main/benchmarks/benchmark_serving.py](https://github.com/vllm-project/vllm/blob/main/benchmarks/benchmark_serving.py)
- vLLM concurrency-table feature request (confirms current behavior) — [github.com/vllm-project/vllm/issues/21094](https://github.com/vllm-project/vllm/issues/21094)
- vLLM MI300X benchmarking issue (concurrency + tensor parallel constraints) — [github.com/vllm-project/vllm/issues/9070](https://github.com/vllm-project/vllm/issues/9070)
- ROCm-enabled vLLM image deprecation — [docs.vllm.ai/en/stable/deployment/docker/](https://docs.vllm.ai/en/stable/deployment/docker/)
- ROCm becomes first-class in vLLM (AITER, MI300X) — [rocm.blogs.amd.com/software-tools-optimization/vllm-omni/README.html](https://rocm.blogs.amd.com/software-tools-optimization/vllm-omni/README.html)
- faster-whisper repo — [github.com/SYSTRAN/faster-whisper](https://github.com/SYSTRAN/faster-whisper)
- CTranslate2 ROCm AMD GPU guide — [rocm.blogs.amd.com/artificial-intelligence/ctranslate2/README.html](https://rocm.blogs.amd.com/artificial-intelligence/ctranslate2/README.html)
- silero-vad — [github.com/snakers4/silero-vad](https://github.com/snakers4/silero-vad)
- LiveKit AgentSession docs — [docs.livekit.io/agents/build/session/](https://docs.livekit.io/agents/build/session/)
- LiveKit Silero plugin — [docs.livekit.io/agents/logic/turns/vad/](https://docs.livekit.io/agents/logic/turns/vad/)
- LiveKit turn-detector blog — [blog.livekit.io/using-a-transformer-to-improve-end-of-turn-detection](https://blog.livekit.io/using-a-transformer-to-improve-end-of-turn-detection)
- torch.profiler — [docs.pytorch.org/docs/stable/profiler.html](https://docs.pytorch.org/docs/stable/profiler.html)
- rocm-smi manpage — [manpages.ubuntu.com/manpages/noble/man1/rocm-smi.1.html](https://manpages.ubuntu.com/manpages/noble/man1/rocm-smi.1.html)
- AMD SMI overview — [rocm.blogs.amd.com/software-tools-optimization/amd-smi-overview/README.html](https://rocm.blogs.amd.com/software-tools-optimization/amd-smi-overview/README.html)
- devnen Chatterbox-TTS-Server Dockerfile.rocm — [github.com/devnen/Chatterbox-TTS-Server/blob/main/Dockerfile.rocm](https://github.com/devnen/Chatterbox-TTS-Server/blob/main/Dockerfile.rocm)
- devnen issue #92 (torch / ROCm version conflict — the named Day-1 risk) — [github.com/devnen/Chatterbox-TTS-Server/issues/92](https://github.com/devnen/Chatterbox-TTS-Server/issues/92)
- PyTorch issue #171687 (gfx1151 decode hipMemcpyWithStream dominance — load-bearing for derating) — [github.com/pytorch/pytorch/issues/171687](https://github.com/pytorch/pytorch/issues/171687)
- ROCm/ROCm issue #6034 (gfx1151 bf16 bugs + AOTriton speedup) — [github.com/ROCm/ROCm/issues/6034](https://github.com/ROCm/ROCm/issues/6034)
- ROCm/ROCm issue #6035 (amd-smi N/A on gfx1151) — [github.com/ROCm/ROCm/issues/6035](https://github.com/ROCm/ROCm/issues/6035)
- ROCm/ROCm issue #5853 (Strix Halo segfault on VRAM access) — [github.com/ROCm/ROCm/issues/5853](https://github.com/ROCm/ROCm/issues/5853)
- hipBLASLt issue #1243 (unsupported architecture warning) — [github.com/ROCm/hipBLASLt/issues/1243](https://github.com/ROCm/hipBLASLt/issues/1243)
- TheRock gfx1151 wheels — [github.com/ROCm/TheRock/discussions/655](https://github.com/ROCm/TheRock/discussions/655)
- Strix Halo system optimization — [rocm.docs.amd.com/en/latest/how-to/system-optimization/strixhalo.html](https://rocm.docs.amd.com/en/latest/how-to/system-optimization/strixhalo.html)

### Secondary (MEDIUM confidence)

- vLLM structured-output performance comparison (xgrammar vs LLGuidance vs outlines) — [blog.squeezebits.com/guided-decoding-performance-vllm-sglang](https://blog.squeezebits.com/guided-decoding-performance-vllm-sglang)
- Guided decoding in RAG (failure-mode characterization) — [arxiv.org/html/2509.06631v1](https://arxiv.org/html/2509.06631v1)
- vLLM benchmark walkthrough — [www.gpu-mart.com/blog/how-to-benchmark-vllm-online-serving](https://www.gpu-mart.com/blog/how-to-benchmark-vllm-online-serving)
- LLM-tracker Strix Halo overview — [llm-tracker.info/_TOORG/Strix-Halo](https://llm-tracker.info/_TOORG/Strix-Halo)
- ROCm 7.2 Strix Halo guide — [tinycomputers.io/posts/upgrading-rocm-7.0-to-7.2-on-amd-strix-halo-gfx1151.html](https://tinycomputers.io/posts/upgrading-rocm-7.0-to-7.2-on-amd-strix-halo-gfx1151.html)
- AMD ROCm system optimization for Strix Halo — [rocm.docs.amd.com/en/latest/how-to/system-optimization/strixhalo.html](https://rocm.docs.amd.com/en/latest/how-to/system-optimization/strixhalo.html)

### Tertiary (LOW confidence — flagged for plan-phase validation)

- Phoronix Nov 2025 Strix Halo "barely beats CPU" prompt-processing (referenced in CLAUDE.md §7) — single source, extrapolated derate ratios.
- 5-min co-residency window sufficiency (D-Discretion default) — operator-set, no empirical validation in the literature.

## Metadata

**Confidence breakdown:**
- Standard stack on MI300X (vLLM, faster-whisper, jiwer, silero, LiveKit, ffmpeg, rocm-smi): HIGH — all locked in CLAUDE.md, multiple authoritative sources.
- Chatterbox ROCm install path: MEDIUM — devnen Dockerfile.rocm exists + addresses #92, but MI300X-specific testing not yet validated (the kill-switch *exists* for this reason).
- gfx1151 audit methodology: MEDIUM-LOW — no off-the-shelf tool; methodology hand-rolled from torch.profiler + 4 GitHub issues. Verifiable on first MI300X pod via smoke test (A3, A6).
- Common pitfalls 1-5 (ROCm enumeration, hipBLASLt fallback, hipMemcpy decode, amd-smi N/A, CTranslate2 determinism): HIGH — each has a verified GitHub issue or AMD blog as source.
- Concurrency rig: HIGH — vLLM benchmark_serving.py path is AMD-validated.
- Vultr provisioning shape: MEDIUM — billing adapter is real; provisioning surface assumed (A4).

**Research date:** 2026-05-10
**Valid until:** 2026-06-10 (30 days; ROCm + vLLM release cadence is fast — verify version pins at plan-phase). Critical re-check items: A1 (image tag pullable), A4 (Vultr MI300X provisioning surface), Pitfall 6 (vLLM ROCm AWQ version surface).
