# Architecture Research

**Domain:** Cloud-GPU voice-AI benchmarking harness (Phase 0, receptionBOX)
**Researched:** 2026-05-04
**Confidence:** HIGH (anchored to receptionBOX PRD v0.2 §3.5/§4/§14, virtual benchmark plan v0.1, and the hard $150 / 30–40-hour Phase 0 envelope)

This document describes how Phase 0 should be structured *as a benchmark harness repo* — not as the v1 product runtime. The product topology in PRD §4.2 (LiveKit SFU, agent-worker, n8n, etc.) is **deliberately not implemented** in Phase 0; we measure the *components* the product depends on (Whisper STT, Qwen3-4B, Chatterbox-Turbo, Kokoro-82M) running in synthetic harnesses on rented GPUs, and derate to Strix Halo. The architecture below optimizes for: reproducibility, substrate independence (CUDA ↔ ROCm), cost-cap enforcement, and a one-shot synthesis report.

---

## Standard Architecture

### System Overview

```
┌──────────────────────────────────────────────────────────────────────────┐
│  LOCAL CONTROL PLANE  (operator's Ubuntu 22.04 box, ~/RBOX)              │
│                                                                           │
│  ┌────────────────┐  ┌────────────────┐  ┌────────────────────────────┐ │
│  │ Asset Builder  │  │ Cloud Orches-  │  │ Synthesis & Reporting      │ │
│  │ (synthetic     │  │ trator         │  │ (pandas + jinja2 →         │ │
│  │  call corpus,  │  │ (RunPod/Vultr/ │  │  markdown report,          │ │
│  │  G.711 trans-  │  │  TensorWave    │  │  derating model,           │ │
│  │  code, UPL     │  │  CLIs +        │  │  cost ledger view)         │ │
│  │  probes, ...)  │  │  rsync/SSH +   │  │                            │ │
│  │                │  │  cost ledger)  │  │                            │ │
│  └───────┬────────┘  └────────┬───────┘  └──────────────┬─────────────┘ │
│          │                    │                          ▲               │
│          ▼                    │                          │               │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │ Asset Store (content-addressed, SHA-pinned)                       │   │
│  │ assets/{corpus,g711,hesitation,upl,tts_ab}/<sha>.{wav,jsonl,...}  │   │
│  └──────────────────────────────────────────────────────────────────┘   │
│          │                    │                          ▲               │
│          ▼                    ▼                          │               │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │ Result Store (JSONL + Parquet + SQLite)                           │   │
│  │ results/<gate>/<run_id>/{result.jsonl, summary.parquet, env.json} │   │
│  └──────────────────────────────────────────────────────────────────┘   │
└────────────────────┬─────────────────────────────────────────────────────┘
                     │ rsync over SSH (push assets+code, pull results)
                     ▼
┌──────────────────────────────────────────────────────────────────────────┐
│  REMOTE GPU SUBSTRATE  (ephemeral; one of two)                           │
│                                                                           │
│  ┌──────────────────────────────┐    ┌──────────────────────────────┐   │
│  │ RunPod H100 (CUDA 12.x)      │    │ Vultr / TensorWave MI300X    │   │
│  │ — pre-flight: assemble       │    │ (ROCm 6.x)                   │   │
│  │   pipeline once on known-    │    │ — primary measurement target │   │
│  │   working substrate          │    │   (G1, G2, G3, G5, G7)       │   │
│  └──────────────┬───────────────┘    └──────────────┬───────────────┘   │
│                 │                                    │                    │
│                 ▼                                    ▼                    │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │ Substrate Layer (substrate.py interface)                          │   │
│  │   load_stt() / load_llm() / load_tts() — provider-specific impl   │   │
│  └──────────────────────────────────────────────────────────────────┘   │
│                                  │                                        │
│                                  ▼                                        │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │ Gate Runners (substrate-agnostic)                                 │   │
│  │   G1 latency │ G2 WER │ G3 turn │ G5 UPL │ G7 TTS A/B            │   │
│  │   each writes results/<gate>/<run_id>/result.jsonl                │   │
│  └──────────────────────────────────────────────────────────────────┘   │
│                                                                           │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │ Model Cache (persistent volume, SHA-pinned)                       │   │
│  │   /workspace/models/<model_name>/<sha>/...                        │   │
│  └──────────────────────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────────────────┘
```

### Component Responsibilities

| Component | Responsibility | Typical Implementation |
|-----------|----------------|------------------------|
| **Asset Builder** | Deterministic generation of all evaluation inputs (call corpus, G.711-transcoded clips, hesitation-heavy adversarial set, UPL probe set, TTS A/B reference clips). Outputs SHA-pinned files + manifest. | Python scripts under `assets/builders/` driven by `make assets`. TTS-synthesized seed audio (Kokoro local, or piper) + sox/ffmpeg for codec passes. Manifest is `assets/manifest.json` keyed by sha256. |
| **Asset Store** | Content-addressed, immutable, SHA-pinned storage of inputs. The contract that decouples builders from runners. | Filesystem under `assets/`, with `manifest.json` enforcing SHA + version. Optional gitignore + push-to-remote via rsync. |
| **Cloud Orchestrator** | Spin up GPU instance, push code+assets, run gate, pull results, destroy instance. Enforces hard cost cap per run. | Bash/Python wrappers around `runpodctl`, Vultr CLI, and TensorWave SSH. Cost ledger updated before each spin-up; spin-up is refused if remaining budget < projected run cost. |
| **Substrate Layer** | Single Python interface (`Substrate` ABC) that hides whether models load via CUDA/PyTorch, ROCm/PyTorch, ONNX Runtime ROCm, or llama.cpp. Gate runners depend only on this interface. | `substrate/cuda.py` and `substrate/rocm.py` implementing the same `load_stt() / load_llm() / load_tts() / synth_tts() / transcribe()` contract. Selected at runtime via `SUBSTRATE=cuda|rocm` env var. |
| **Gate Runners** | Each gate is a self-contained script: read pinned assets, exercise substrate, write JSONL result + env-capture sidecar. Substrate-agnostic. | Python modules under `gates/g1_latency/`, `gates/g2_wer/`, etc. Each exposes `run(asset_manifest, output_dir, config)` and a `Makefile` target. |
| **Result Store** | Schema-stable, append-only result records. One run = one directory. Schema validated at write-time. | JSONL per record (one per call/probe/clip), Parquet rollup per run, SQLite index across runs at `results/index.db`. Schema defined in `schemas/result.schema.json` and pinned via `schema_version`. |
| **Synthesis & Reporting** | Read all run results from SQLite/Parquet, apply derating model, render markdown synthesis report and updated feasibility memo excerpt. One target: `make report`. | pandas + jinja2 + matplotlib (for inline charts). Output: `reports/synthesis.<date>.md` + memo-update fragment. |
| **Derating Model** | Project cloud-substrate measurements (H100 / MI300X) onto Strix Halo with stated assumptions and uncertainty bands. | Python module `derating/strix_model.py` parameterized by published H100/MI300X/Strix-Halo TFLOPS, memory bandwidth, and INT8 throughput. Outputs point estimate + 80% confidence band. Documented in `docs/derating-methodology.md`. |
| **Cost Ledger** | Per-gate, per-run, per-substrate cost accounting with $150 ceiling enforcement. Refuses to spin up instances that would breach the cap. | SQLite table `cost_ledger(run_id, substrate, started_at, ended_at, hourly_rate, projected_cost, actual_cost, budget_remaining)`. Updated by Cloud Orchestrator on every state transition. |
| **Environment Capture** | Snapshot of every dimension that could affect reproducibility (model SHAs, driver/runtime versions, instance SKU, git SHA of harness, asset manifest SHA). Written alongside every result. | `env.json` written by gate runner on start; `make report` cross-checks consistency across runs and flags drift. |

---

## Recommended Project Structure

```
~/RBOX/
├── Makefile                       # canonical entrypoint for everything
├── pyproject.toml                 # uv-managed Python deps
├── .env.example                   # credentials template (no real secrets)
│
├── docs/
│   ├── derating-methodology.md    # how cloud → Strix Halo projection works
│   ├── reproducibility.md         # SHA-pinning, cache contract, rerun procedure
│   └── cost-model.md              # hourly rates, projected costs per gate
│
├── config/
│   ├── models.yaml                # model name → hf_repo + sha256 + quantization
│   ├── substrates.yaml            # runpod-h100, vultr-mi300x, tensorwave-mi300x
│   ├── gates.yaml                 # per-gate parameters (sample counts, thresholds)
│   └── budget.yaml                # $150 ceiling, per-gate projected cost
│
├── assets/
│   ├── manifest.json              # sha256 → relative path, schema-validated
│   ├── builders/
│   │   ├── build_call_corpus.py   # 500 synthetic calls (TTS + dialogue templates)
│   │   ├── build_g711_clips.py    # 200 clips, 16k → 8k μ-law transcode
│   │   ├── build_hesitation.py    # adversarial set for G3
│   │   ├── build_upl_probes.py    # 200 UPL adversarial probes
│   │   └── build_tts_ab.py        # 30-pair A/B set + reference clips
│   ├── corpus/                    # generated, gitignored, regenerable
│   ├── g711/
│   ├── hesitation/
│   ├── upl/
│   └── tts_ab/
│
├── substrate/
│   ├── __init__.py                # Substrate ABC (load_stt/llm/tts, synth, transcribe)
│   ├── cuda.py                    # PyTorch CUDA path; faster-whisper, llama.cpp CUDA
│   ├── rocm.py                    # PyTorch ROCm path; faster-whisper ONNX-ROCm,
│   │                              #   llama.cpp ROCm, Chatterbox-Turbo ROCm wheel
│   └── model_cache.py             # SHA-pinned download + verify
│
├── gates/
│   ├── g1_latency/
│   │   ├── runner.py              # exercises full STT→LLM→TTS pipeline per call
│   │   ├── config.yaml            # 500-call sample, p50/p90/p99 metrics
│   │   └── README.md
│   ├── g2_wer/                    # WER on G.711, neutral + stressed splits
│   ├── g3_turn/                   # turn-detection FP rate
│   ├── g5_upl/                    # 200 UPL probes, 100% pass required
│   ├── g7_tts_ab/                 # 30 pairs, 5-listener blind preference (manual)
│   └── _common/
│       ├── result_schema.py       # pydantic model for result rows
│       ├── env_capture.py         # writes env.json
│       └── timing.py              # high-resolution timers, percentile rollup
│
├── orchestration/
│   ├── runpod_h100.py             # CLI wrapper: provision, push, run, pull, destroy
│   ├── vultr_mi300x.py
│   ├── tensorwave_mi300x.py
│   ├── cost_ledger.py             # the $150 enforcer
│   ├── remote_run.sh              # the one script that runs on the GPU box
│   └── cloud_init.yaml            # base image bootstrap (Docker, ROCm/CUDA)
│
├── results/
│   ├── index.db                   # SQLite, cross-run summary
│   └── <gate>/<run_id>/
│       ├── result.jsonl           # per-record results
│       ├── summary.parquet        # rolled-up percentiles
│       └── env.json               # full reproducibility snapshot
│
├── derating/
│   ├── strix_model.py             # cloud → Strix Halo projection
│   ├── hardware_specs.yaml        # H100, MI300X, Strix Halo specs
│   └── tests/                     # unit tests for the projection model
│
├── synthesis/
│   ├── render_report.py           # pandas → jinja2 → markdown
│   ├── templates/
│   │   ├── synthesis.md.j2        # full Phase 0 synthesis report
│   │   └── memo_update.md.j2      # fragment for feasibility-memo v0.4
│   └── charts/
│
└── reports/                       # generated outputs
    ├── synthesis.YYYY-MM-DD.md
    └── memo-fragment.YYYY-MM-DD.md
```

### Structure Rationale

- **`config/` is the only place hardcoded constants live.** Model SHAs, instance SKUs, sample counts, and the $150 ceiling are all data, not code. This makes "rerun with the next-rev model" a config-only change.
- **`assets/` is regenerable but checksummed.** Builders are deterministic; the manifest pins SHAs so a regeneration that drifts is detectable. Generated files are gitignored; the manifest is committed.
- **`substrate/` exists *because* CUDA is pre-flight and ROCm is the real target.** A single `Substrate` interface means gate runners are written once. If Chatterbox-Turbo ROCm is broken on day one, only `substrate/rocm.py` changes — gate runners don't.
- **`gates/` are independent units.** Each gate has its own runner, config, and README so it can be invoked standalone (`make g1`, `make g2`, …). No gate imports from another gate.
- **`orchestration/` is the boundary.** Local code never speaks to a cloud API except through this directory. Cost ledger lives here so the rule "no spin-up without budget check" is structurally enforced.
- **`results/` schema is fixed early.** Synthesis depends on the schema being stable; if you have to break it, bump `schema_version` and don't try to merge old + new in the same query.
- **`derating/` is its own module with its own tests.** The projection from MI300X → Strix Halo is the most contestable artifact Phase 0 produces; isolating it lets the methodology be reviewed independently of measurement code.

---

## Architectural Patterns

### Pattern 1: Substrate Abstraction (CUDA ↔ ROCm parity)

**What:** A Python ABC (`Substrate`) defines the operations gate runners need: `load_stt()`, `load_llm()`, `load_tts(engine)`, `transcribe(audio)`, `generate(prompt)`, `synthesize(text)`. Two implementations exist (`cuda.py`, `rocm.py`). Gate runners import only the ABC.

**When to use:** Whenever the same benchmark must produce comparable numbers across two GPU vendors. Phase 0 is exactly this case — H100 is pre-flight, MI300X is the load-bearing measurement.

**Trade-offs:**
- **Pro:** Gate runners written once. Switching substrates is a single env var. Bugs in one substrate don't pollute the other.
- **Con:** The ABC must be lowest-common-denominator. If ROCm's faster-whisper is materially different in API from CUDA's, the abstraction leaks. Mitigation: keep the ABC narrow (5 methods, audio-in/text-out), push provider quirks behind it.

**Example:**
```python
# substrate/__init__.py
class Substrate(ABC):
    @abstractmethod
    def load_stt(self, model_name: str) -> "STTHandle": ...
    @abstractmethod
    def load_llm(self, model_name: str) -> "LLMHandle": ...
    @abstractmethod
    def load_tts(self, engine: Literal["chatterbox-turbo", "kokoro-82m"]) -> "TTSHandle": ...
    @abstractmethod
    def env_fingerprint(self) -> dict: ...  # driver, runtime, device

def get_substrate() -> Substrate:
    name = os.environ["SUBSTRATE"]  # "cuda" | "rocm"
    return {"cuda": CudaSubstrate, "rocm": RocmSubstrate}[name]()
```

### Pattern 2: Content-Addressed Asset Store

**What:** Every input artifact (audio clip, probe text, reference clip) is stored under a path containing its sha256. A single `manifest.json` maps logical names to (sha, path, schema_version). Builders are deterministic and idempotent — running them twice produces identical SHAs or a loud error.

**When to use:** Any benchmark where inputs must be byte-identical across runs and substrates. G.711 transcoding, in particular, is a place where one minor sox/ffmpeg flag difference silently changes WER by 1–2 points.

**Trade-offs:**
- **Pro:** A result row carrying `asset_sha` is unambiguous about what was measured. Easy to detect "we accidentally ran G2 on the wrong corpus."
- **Con:** Builders must be deterministic, which means seeding RNGs and pinning toolchain versions (sox/ffmpeg/piper). Harder up front; pays back at synthesis time.

**Example:**
```python
# assets/manifest.json (excerpt)
{
  "schema_version": 1,
  "g711_clips": {
    "version": "v1",
    "sha256": "ab1c…",        // sha over the manifest entries themselves
    "items": [
      {"name": "neutral_001", "path": "g711/ab/1c/ab1c…01.wav", "sha256": "ab1c…01"},
      ...
    ]
  }
}
```

### Pattern 3: Cost-Capped Cloud Orchestration

**What:** No GPU instance is ever spun up without a "budget check" against the cost ledger. Each run is preceded by a projected cost (hourly rate × estimated minutes × safety factor). If `budget_remaining - projected_cost < 0`, the orchestrator refuses and prints what would be needed.

**When to use:** Any project with a hard money ceiling and human operators who will, eventually, forget to terminate an instance. The $150 ceiling here is small enough that one forgotten H100 overnight blows it.

**Trade-offs:**
- **Pro:** Cost-cap enforcement is structural, not procedural. The operator can't accidentally exceed budget without explicitly editing `budget.yaml`.
- **Con:** Projection is approximate; a slow run can still overshoot. Mitigation: orchestrator also installs an in-instance watchdog that auto-terminates after `max_minutes` defined per gate.

**Example:**
```python
# orchestration/cost_ledger.py
def check_budget(substrate: str, est_minutes: float) -> None:
    rate = SUBSTRATE_RATES[substrate]  # $/hr from config/budget.yaml
    projected = rate * (est_minutes / 60) * SAFETY_FACTOR  # 1.5x
    remaining = BUDGET_CEILING - sum(actual_cost for r in ledger)
    if projected > remaining:
        raise BudgetExceeded(
            f"{substrate}: projected ${projected:.2f}, remaining ${remaining:.2f}. "
            f"Edit config/budget.yaml to override."
        )
```

### Pattern 4: Schema-Pinned Result Store

**What:** Every gate writes JSONL records conforming to a pydantic schema. The schema carries a `schema_version`. SQLite index ingests JSONL on `make ingest`; synthesis queries the SQLite index. If schema changes mid-Phase-0, version is bumped and old runs are migrated or excluded explicitly.

**When to use:** Whenever multiple runs must be aggregated. Synthesis depends on this stability — without it, every chart in the report becomes a custom join.

**Trade-offs:**
- **Pro:** Synthesis is one pass over `results/index.db`. Trivial to add a new chart or comparison.
- **Con:** Forces schema discipline early, when the temptation is to scribble fields and clean up later.

### Pattern 5: One-Shot `make report`

**What:** A single Make target rebuilds the synthesis report from current SQLite state. Idempotent. No hidden state. Operator doesn't have to remember which scripts to run in what order.

**When to use:** Always, for terminal deliverables. The Phase 0 contract is "produce a synthesis report"; that target should never be a multi-step ritual.

**Trade-offs:**
- **Pro:** Operator can rerun freely as new data arrives. CI can validate the report builds.
- **Con:** Requires upstream pieces (cost ledger, env capture, schema) to have already been done correctly. Failure surfaces here, but the cause is usually upstream.

---

## Data Flow

### End-to-End Phase 0 Flow

```
[config/models.yaml]                        [config/budget.yaml]
        │                                          │
        ▼                                          ▼
[Asset Builders] ──→ [assets/ + manifest.json] ──→ [Cost Ledger]
                                │                       │
                                │                       ▼
                                │              [Cloud Orchestrator]
                                │                       │
                                │                       ▼
                                │              [Provision GPU, rsync code+assets]
                                │                       │
                                ▼                       ▼
                        [Substrate Layer] ←── [Model Cache (SHA-pinned)]
                                │
                                ▼
                        [Gate Runner: G1│G2│G3│G5│G7]
                                │
                                ▼
                        [results/<gate>/<run_id>/{result.jsonl, env.json}]
                                │
                                ▼ (rsync pull + ingest)
                        [results/index.db (SQLite)]
                                │
                                ▼
                        [Derating Model] ──→ [Strix Halo predictions ± band]
                                │
                                ▼
                        [Synthesis Renderer (pandas + jinja2)]
                                │
                                ▼
                        [reports/synthesis.YYYY-MM-DD.md]
                                │
                                ▼
                        [Feasibility Memo v0.4 update]
```

### Per-Gate Inner Flow (G1 latency, illustrative)

```
[manifest: corpus.500_calls (sha)] → [Substrate.load_*()]
                                         │
                                         ▼
For each call in corpus:
    1. timer_start
    2. STT.transcribe(audio_chunks)     ← tracks first_partial_ms, final_ms
    3. LLM.generate(transcript)         ← tracks ttft_ms, total_ms
    4. TTS.synthesize(response)         ← tracks first_audio_ms, total_ms
    5. timer_end → e2e_ms
    6. emit JSONL row {call_id, asset_sha, model_shas, e2e_ms, stage_ms…}

After loop: write summary.parquet (p50, p90, p99 per stage)
            write env.json (driver, runtime, instance SKU, git SHA)
```

### G.711 Transcoding Sub-Flow (input to G2)

```
[16 kHz WAV reference] → sox: 16k mono → 8k μ-law → 8k mono → [G.711 .wav]
                          (pinned sox version + flags, captured in manifest)
                          sha256 over output bytes → asset key
```

### Synthesis Flow

```
[results/index.db] ──→ pandas.read_sql ──→ per-gate DataFrame
                                                │
                                                ▼
                            [Derating Model: cloud → Strix Halo]
                                                │
                                                ▼
                            jinja2(synthesis.md.j2, context={
                                g1: {...}, g2: {...}, ...,
                                cost_total: $X.YZ,
                                strix_predictions: {...},
                                confidence: "MEDIUM, see §derating",
                            })
                                                │
                                                ▼
                            reports/synthesis.YYYY-MM-DD.md
                            reports/memo-fragment.YYYY-MM-DD.md  (insert into memo v0.4)
```

---

## Build Order (Critical Path)

This is the section the roadmap should treat as load-bearing. Phase ordering follows dependency, not gate number.

```
Stage A — Foundation (no GPU spend):
  1. Repo skeleton, Makefile, pyproject.toml, config/ schema
  2. Substrate ABC (substrate/__init__.py) — interface only
  3. Result schema (gates/_common/result_schema.py)
  4. Cost ledger (orchestration/cost_ledger.py) — local-only test first
  5. Asset Builders for ALL gates (corpus, G.711, hesitation, UPL, TTS A/B)
       ← Build all builders before any GPU run; they're CPU-only
  6. Asset manifest committed; assets regeneratable

Stage B — CUDA pre-flight (RunPod H100, ~$10–20):
  7. substrate/cuda.py implementation
  8. orchestration/runpod_h100.py (provision, push, run, pull, destroy)
  9. End-to-end smoke: G1 on 5-call subset, H100 — proves substrate + orchestration
 10. If smoke passes → run G1, G2, G3, G5 on H100 (sanity-check pre-flight numbers)
       ← Goal: "the harness works"; not the final measurement

Stage C — ROCm validation (Vultr/TensorWave MI300X, ~$80–120):
 11. substrate/rocm.py implementation (Chatterbox-Turbo ROCm wheel is the risk)
 12. orchestration/vultr_mi300x.py (or tensorwave_mi300x.py)
 13. Smoke: same G1 5-call subset, MI300X
 14. Full G1, G2, G3, G5, G7 on MI300X
       ← This is the load-bearing measurement Phase 0 derates from

Stage D — Synthesis (no GPU spend):
 15. Ingest results into SQLite
 16. Derating model + tests (unit-test against known H100 ratios)
 17. synthesis/render_report.py + templates
 18. `make report` produces synthesis.md
 19. Feasibility memo v0.4 fragment generated and merged
```

**Hard dependencies:**

- **Asset Builders block all gate runs.** No GPU should be provisioned until the manifest is frozen. Re-running G1 with a regenerated corpus invalidates earlier numbers.
- **Cloud Orchestrator + Cost Ledger block all GPU work.** First spin-up must go through the ledger; never SSH manually for a "quick test" — that's the failure mode that exhausts $150.
- **Substrate ABC blocks gate runners.** Don't write a gate runner that imports `torch` directly. Always go through `Substrate`.
- **Result schema blocks Synthesis.** If schema changes after Stage C results land, every chart breaks. Pin v1 before Stage B and only bump with explicit migration.
- **CUDA pre-flight blocks ROCm.** Per virtual benchmark plan v0.1 and PRD §14, the pipeline must assemble on CUDA first. This catches harness bugs cheaply ($/hr H100 is similar to MI300X but the failure modes are better understood).
- **Derating model can be built in parallel with measurements**, but its outputs aren't trustworthy until Stage C numbers exist. Build + unit-test in Stage A on synthetic data; calibrate in Stage D.

**G7 is special.** TTS A/B is a 5-listener manual blind test. The harness produces the 30 pairs (synth + reference) on MI300X; the listening session is offline and asynchronous. Don't put G7 on the critical path of `make report` — record results separately and merge.

---

## Derating Methodology (Cloud MI300X → Strix Halo)

This is the most contestable artifact in Phase 0; it deserves explicit architectural treatment.

### Inputs (per gate, per measurement)

- Measured value on substrate (e.g., G1 e2e p90 ms on MI300X)
- Substrate hardware spec: peak FP16/BF16 TFLOPS, INT8 TOPS, HBM bandwidth, VRAM
- Strix Halo target spec: ~50 INT8 TOPS NPU + iGPU, ~256 GB/s LPDDR5X bandwidth, unified memory
- Per-stage breakdown (STT compute time, LLM TTFT, TTS first-audio time)

### Projection Formulas (documented in `docs/derating-methodology.md`)

The derating module makes per-stage projections, not a single end-to-end ratio. Each stage has a different bottleneck:

- **STT (compute-bound, INT8):** projected_ms = measured_ms × (substrate_int8_tops / strix_int8_tops). For Whisper-distil INT8, INT8 TOPS dominates.
- **LLM TTFT (memory-bandwidth-bound at 4B params):** projected_ttft = measured_ttft × (substrate_hbm_bw / strix_lpddr5x_bw). Qwen3-4B Q4_K_M at TTFT is bandwidth-bound, not compute-bound.
- **LLM tokens/sec (similarly bandwidth-bound).**
- **TTS first-audio (compute-bound for 350M Chatterbox-Turbo):** projected = measured × (substrate_fp16 / strix_fp16_iGPU).
- **End-to-end p90:** sum of stage projections + measured network/queueing constant. (The constant is small but not zero; capture it explicitly.)

### Uncertainty

Each projection carries an **80% confidence band** built from:
- ±15% for "vendor-published TOPS rarely matches kernel-reality" (well-established for ROCm)
- ±10% for unified-memory vs HBM access patterns (Strix's LPDDR5X behavior is materially different from MI300X HBM3)
- ±20% for Chatterbox-Turbo specifically — published ROCm path is new (PRD §11 risk register flags this)

Bands are added in quadrature for end-to-end. The synthesis report **must** display the band, not just the point estimate. A 900ms point estimate that becomes 700–1100ms with bands is still a meaningful "soft pass with caveats" per DR-28.

### Validation

Strix Halo numbers cannot be ground-truthed in Phase 0 (no dev unit). Two cheap validations:
1. **Cross-substrate consistency:** Measure G1 on both H100 and MI300X. Apply derating *between* them. If H100→MI300X projection misses by > 25%, the methodology has a problem and Strix projection is suspect.
2. **Per-stage sanity vs vendor benchmarks:** Compare measured Whisper INT8 throughput on MI300X to Resemble/distil-whisper published numbers. Outliers signal substrate config issues, not a derating issue.

### Confidence Labels in Output

Synthesis report labels each derated number explicitly:

| Label | Meaning |
|-------|---------|
| HIGH | Bandwidth- or compute-bound stage with a well-understood ratio (LLM TTFT) |
| MEDIUM | Mixed-bottleneck stage (G1 end-to-end) |
| LOW | New-substrate stage (Chatterbox-Turbo ROCm), or where measurement is < 5 samples |

Phase 0 gate decision uses the **lower bound** of the 80% band against PRD targets, not the point estimate. This is the conservative posture DR-28 implies.

---

## Scaling Considerations

Phase 0 is not a production system — "scale" here means "what changes if requirements grow."

| Scale | Architecture Adjustments |
|-------|--------------------------|
| Phase 0 as scoped (5 gates, 1 model set, $150) | This architecture as-is. SQLite is fine. Single operator. |
| Phase 1 hardware benchmarks on actual Strix Halo (G1–G7) | Add `substrate/strix.py` implementing same ABC. No other code changes. Reuse all asset builders and gate runners. Validates the derating model retroactively. |
| Multiple firms / multi-tenant benchmarking | SQLite → Postgres. Add `tenant_id` to result schema (bump version). Cost ledger gains per-tenant quotas. Add CI to lock model SHAs. |
| Continuous regression harness (post-pilot) | Gates run on a schedule against a held-out asset set. Add diff-detection: any metric drifting > X% from baseline opens an alert. SQLite still fine; add `runs.is_baseline` flag. |

### Scaling Priorities

1. **First bottleneck: schema drift.** As soon as a second person edits gate runners, the result schema starts drifting. Pin it now; migrate explicitly. This is *not* premature.
2. **Second bottleneck: substrate proliferation.** If T5 (NVIDIA) ever needs benchmarking, that's a new Substrate impl. The ABC must stay narrow or each new substrate forces refactor.
3. **Third bottleneck: cost-cap arithmetic.** Once spend exceeds Phase 0, per-tenant quotas become real. Today the ledger is one row per run; tomorrow it's per (tenant, gate, month).

---

## Anti-Patterns

### Anti-Pattern 1: Gate runners that import torch directly

**What people do:** Skip the Substrate ABC, "just use PyTorch", figure CUDA/ROCm switching is "a small wrapper later."
**Why it's wrong:** ROCm and CUDA paths diverge in non-obvious ways (model loading, dtypes, kernel selection). Without an ABC, you end up with `if rocm: ... else: ...` scattered across every gate, and your H100 numbers and MI300X numbers stop being comparable at the schema level.
**Do this instead:** Write the ABC first, even if `cuda.py` is the only impl on day one. The discipline matters more than the second impl.

### Anti-Pattern 2: Skipping the manifest, reading files directly

**What people do:** Gate runner reads `assets/g711/clip_001.wav` by path. "It's just a file."
**Why it's wrong:** When the corpus regenerates with a slightly different sox flag, every prior G2 result silently becomes uncomparable. The harness has no way to detect this.
**Do this instead:** Gate runner takes `manifest_entry` as input, asserts SHA, embeds SHA in result row. A drifted asset fails loudly at run time.

### Anti-Pattern 3: SSHing into the GPU box manually for "quick tests"

**What people do:** "I'll just spin up an H100 to check one thing." No ledger update, no env capture, no cleanup hook.
**Why it's wrong:** Forgotten instance overnight = $25–40 = blown Phase 0 budget. Also produces "results" that aren't reproducible because no env.json was written.
**Do this instead:** `make smoke-h100` runs the same orchestration path as a full gate, with `est_minutes=15` and `gate=smoke`. Watchdog auto-terminates. Ledger updates. Env captured. Cleanup runs.

### Anti-Pattern 4: Single end-to-end derating ratio

**What people do:** "MI300X is 3.2× the FLOPS of Strix Halo, so multiply all timings by 3.2."
**Why it's wrong:** STT, LLM TTFT, and TTS have different bottlenecks (compute vs memory bandwidth vs first-token kernel). A single ratio is wrong on at least two of the three. The derated p90 ends up 30–50% off in either direction.
**Do this instead:** Per-stage derating with explicit bottleneck assumptions, summed with quadrature uncertainty bands. Methodology document cites the bottleneck for each stage.

### Anti-Pattern 5: Reporting point estimates without bands

**What people do:** "Strix Halo p90 is projected at 870ms, passes." Synthesis report shows 870ms.
**Why it's wrong:** The lower bound might be 720ms (great) and the upper bound might be 1100ms (fails). DR-28 says Phase 0 is a hard gate; reporting only the point hides the bound that matters.
**Do this instead:** Every projected number in the report is `point [low, high] @ confidence`. Gate decision uses the upper bound vs target.

### Anti-Pattern 6: Hand-curated synthesis report

**What people do:** Operator copy-pastes numbers into a markdown file at the end of Phase 0.
**Why it's wrong:** Re-running a gate (which Phase 0 will do at least twice) means manually re-editing the report. Errors creep in. Memo v0.4 ends up disagreeing with `results/index.db`.
**Do this instead:** `make report` is the only way reports are produced. Templates own the prose; data comes from SQLite.

### Anti-Pattern 7: Building all gates before any single gate runs end-to-end

**What people do:** Implement G1, G2, G3, G5, G7 runners in parallel locally, then try to run them all on MI300X at once.
**Why it's wrong:** The first GPU run will fail in some way (driver, permissions, model SHA mismatch) and you'll be debugging five gates' worth of code at once with the meter running.
**Do this instead:** Stage B's smoke test is one gate (G1) on 5 calls, on H100. Pay $1 to find out the orchestration works. Then expand. Per the build order above.

---

## Integration Points

### External Services

| Service | Integration Pattern | Notes |
|---------|---------------------|-------|
| RunPod (H100) | `runpodctl` CLI from orchestrator wrapper | API key in `.env`; orchestrator handles SSH key injection. Pre-flight only. |
| Vultr (MI300X) | Vultr CLI / API from orchestrator wrapper | ROCm 6.x base image; verify driver before any model load. |
| TensorWave (MI300X) | SSH + provider-specific provisioning script | Backup for Vultr if ROCm path is broken on Vultr; per virtual benchmark plan v0.1, this is the secondary route. |
| Hugging Face Hub | `huggingface_hub` snapshot_download with `revision=<sha>` | Always pin to commit SHA, never tag/branch. Cache on the GPU box's persistent volume to avoid re-downloading per spin-up. |
| Resemble AI (Chatterbox-Turbo weights) | HF Hub or vendor URL, SHA-pinned | Highest risk component (PRD §11). Have Kokoro fallback path ready. |

### Internal Boundaries

| Boundary | Communication | Notes |
|----------|---------------|-------|
| Asset Builders ↔ Gate Runners | Filesystem + `manifest.json` | One-way; gate runners never modify assets. |
| Gate Runners ↔ Substrate | Python ABC | Gate runners depend on `substrate.Substrate` only; never on `torch`/`onnxruntime` directly. |
| Cloud Orchestrator ↔ Gate Runners | rsync code in, run via `make`, rsync results out | Gate runners do not know they're running on a cloud box. Same code runs locally for unit tests. |
| Cost Ledger ↔ Cloud Orchestrator | SQLite read/write | Orchestrator queries before spin-up; updates on state transitions. |
| Result Store ↔ Synthesis | SQLite via pandas | One-way read. Synthesis never mutates results. |
| Derating ↔ Synthesis | Python module call | Synthesis passes measured values + substrate fingerprint, gets `(point, low, high, confidence_label)` back. |

---

## Sources

- `/home/bob/RBOX/.planning/PROJECT.md` — Phase 0 scope, $150 ceiling, 30–40 hour budget, DR-28 gating semantics
- `/home/bob/RBOX/receptionbox-technical-prd-v0_2-2026-05-03 (1).md` §3.5 (dev/test environment), §4.1–4.5 (software architecture, classification router, streaming optimizations), §10 (success metrics SM-66 through SM-72), §11 (risk register — Chatterbox-Turbo ROCm path, latency, WER), §14 (Phase 0 phase plan)
- Companion documents referenced in PRD §15.2: virtual benchmark plan v0.1 (authoritative on Phase 0 procedures) and feasibility memo v0.3 (predecessor to the v0.4 deliverable Phase 0 produces)
- Standard practices for ML reproducibility: SHA-pinned model downloads via Hugging Face Hub `revision=`, content-addressed asset stores, schema-versioned result records
- Per-stage derating rationale: bandwidth-bound (LLM token generation, KV-cache reads) vs compute-bound (Whisper INT8 inference, TTS first-audio) is well-established in published llama.cpp / vLLM / faster-whisper benchmarks; the methodology applies that breakdown to the H100/MI300X/Strix-Halo trio rather than relying on a single TFLOPS ratio

---
*Architecture research for: Phase 0 cloud-GPU voice-AI benchmark harness*
*Researched: 2026-05-04*
