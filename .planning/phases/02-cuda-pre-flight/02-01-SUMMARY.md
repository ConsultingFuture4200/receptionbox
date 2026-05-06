---
phase: 02-cuda-pre-flight
plan: 01
subsystem: substrate
tags: [HARNESS-02, D-14, D-15, cuda-substrate, livekit, adapters]
requires:
  - Phase 1 substrate ABC (substrate/__init__.py)
  - bench/models.lock.yaml + bench/images.lock.yaml
  - harness/env_fingerprint.py
provides:
  - substrate.cuda.CUDASubstrate (HARNESS-02)
  - substrate.adapters.{VLLMClient,FasterWhisperEngine,ChatterboxClient,KokoroClient}
  - substrate.livekit_pipeline.{build_session,run_one_call} (D-15)
  - pyproject [project.optional-dependencies] cuda group
affects:
  - Plan 02-02 (gate runners) consumes CUDASubstrate as an opaque ABC
  - Plan 02-03 (orchestration / pod entrypoint) consumes build_session
tech-stack:
  added:
    - vllm>=0.10.0,<0.11.0 (cuda-only optional dep)
    - faster-whisper>=1.0,<2.0 (cuda-only optional dep)
    - livekit-agents>=1.0,<2.0 (cuda-only optional dep)
    - livekit-plugins-silero (cuda-only)
    - livekit-plugins-turn-detector (cuda-only)
    - xgrammar>=0.1 (cuda-only)
    - numpy>=1.26,<3.0 (cuda-only)
    - httpx[http2]>=0.27 (cuda-only)
  patterns:
    - "Adapters MUST NOT raise" (Phase 1 lock-in extended to substrate seam)
    - HTTP-over-OpenAI-protocol for vLLM/Chatterbox/Kokoro (no in-process LLM dep)
    - Lazy heavy-imports inside method bodies (workstation imports cleanly)
    - Shim AgentSession via SimpleNamespace when livekit-agents not installed
key-files:
  created:
    - substrate/cuda.py
    - substrate/adapters/__init__.py
    - substrate/adapters/vllm_client.py
    - substrate/adapters/faster_whisper_engine.py
    - substrate/adapters/chatterbox_client.py
    - substrate/adapters/kokoro_client.py
    - substrate/livekit_pipeline.py
    - tests/test_cuda_substrate.py
    - tests/test_livekit_pipeline.py
  modified:
    - substrate/__init__.py (lazy CUDASubstrate re-export note)
    - pyproject.toml (new [project.optional-dependencies] cuda group)
decisions:
  - "Adapters expose health() returning bool; load_* uses health() not exception"
  - "Default vLLM grammar dispatch: dict -> guided_json, regex-shaped str -> guided_regex, JSON-parseable str -> guided_json, else guided_regex (best-effort)"
  - "FasterWhisperEngine performs deps-free linear resample (np.interp) to 16kHz when sample_rate != 16000; avoids soxr coupling for the harness"
  - "DR-27 fallback wired in synthesize(): Chatterbox health()=False -> Kokoro; logged as WARNING"
  - "env_fingerprint.image_digest preserves 'pending' as a real pre-cloud-resolution value"
  - "LiveKit pipeline rig ships a shim path (SimpleNamespace) so unit tests + workstation dev never need livekit-agents installed"
  - "Heavy backend imports (vllm, faster_whisper, torch, livekit) all deferred inside method bodies — module imports succeed on no-GPU host"
metrics:
  duration_hours: 0.4
  completed: 2026-05-06
---

# Phase 2 Plan 01: CUDA Substrate + LiveKit Pipeline Summary

JWT-of-the-substrate-seam: HARNESS-02 ships CUDASubstrate composing 4 backend adapters per D-14 plus a substrate-agnostic LiveKit AgentSession rig per D-15 — all importable on a no-GPU workstation, all unit-testable with mocked HTTP.

## What Shipped

### `substrate/adapters/` — 4 backend adapters

| Adapter | Wire | Endpoint shape |
|---------|------|----------------|
| `VLLMClient` | HTTP streaming SSE | `POST {base_url}/v1/completions` with `stream: true`, optional `guided_decoding_backend: xgrammar` + `guided_json` / `guided_regex` |
| `FasterWhisperEngine` | In-process CTranslate2 INT8 | `WhisperModel.transcribe(arr, vad_filter=True, beam_size=1, language='en')` in `asyncio.to_thread` |
| `ChatterboxClient` | HTTP streaming bytes | `POST {base_url}/tts` with `{"text", "voice", "stream": true, "format": "pcm_s16le_24000"}`; CUDA path uses upstream `resemble-ai/chatterbox` (NOT devnen ROCm fork) |
| `KokoroClient` | HTTP streaming bytes | `POST {base_url}/v1/audio/speech` (OpenAI-compatible) with `{"input", "voice": "af_bella", "response_format": "pcm", "stream": true}`; upstream `remsky/Kokoro-FastAPI` |

All four adapters honor the Phase 1 lock-in: log WARNING + return / yield-nothing on every error path. Verified by `tests/test_cuda_substrate.py::test_vllm_client_logs_warning_on_500_does_not_raise` and the connect-error swallow tests for each adapter. The T-02-01-02 mitigation (no payload logging) is verified by `test_chatterbox_logs_status_only_no_payload` which sends a sentinel string and asserts it never appears in any caplog record.

### `substrate/cuda.py` — CUDASubstrate

- `class CUDASubstrate(Substrate)` — ABC-conformant; verified by `test_substrate_abc.py` carry-forward + new `test_cuda_substrate_implements_abc`.
- Constructor takes explicit endpoint URLs + model paths (no env-var sniffing): `vllm_url`, `vllm_model`, `whisper_model_dir`, `chatterbox_url`, `kokoro_url`.
- `load_stt/load_llm/load_tts` use `health()` checks; failure logs WARNING and leaves `_loaded[stage] = False` but does not raise.
- DR-27 TTS fallback wired in `synthesize()`: if Chatterbox `health()` returns False, log WARNING and route through Kokoro.
- `env_fingerprint()` returns a fully populated `EnvFingerprint`:
  - `substrate="cuda"`
  - `image_digest` from `bench/images.lock.yaml` lookup (provider=runpod, rail=cuda, image_ref=vllm/vllm-openai); preserves "pending" as a real value
  - `model_shas` from `bench/models.lock.yaml` (4 entries: distil_whisper_large_v3_int8, qwen3_4b_awq_int4, chatterbox_turbo, kokoro_82m)
  - `gpu_sku` / `gpu_count` from `nvidia-smi --query-gpu=name` (5s timeout, returns "unknown"/0 on failure)
  - `cuda_version` / `pytorch_version` from `torch.version.cuda` / `torch.__version__` if importable, else None
  - `vllm_version` from HTTP GET `{vllm_url}/version` (2s timeout), else None

### `substrate/livekit_pipeline.py` — D-15

- `build_session(substrate, *, vad_threshold_ms=800)`:
  - Real path: imports `livekit.agents.AgentSession` + `livekit.plugins.silero` + `livekit.plugins.turn_detector` per CLAUDE.md §8; constructs an AgentSession with `_SubstrateSTTPlugin` / `_SubstrateLLMPlugin` / `_SubstrateTTSPlugin` wrappers around the substrate.
  - Shim path: returns a `SimpleNamespace` with the same `.stt / .llm / .tts` plugin surface — used in unit tests and in any workstation dev that doesn't have livekit-agents installed.
- `run_one_call(session, audio_path)` async drives one E2E call:
  1. Stream the WAV bytes into `session.stt.stream`; record `stt_ttft_ms` on first emitted chunk
  2. Take the final transcript, call `session.llm.chat`; record `llm_ttft_ms` on first chunk; compute `llm_decode_ms_per_tok` from the inter-chunk window divided by chunks-1
  3. Take the response text, call `session.tts.synthesize`; record `tts_first_audio_ms` on first PCM chunk; record `e2e_ms` from start-of-call to first TTS chunk
  4. Return `dict[str, float | None]` with all 5 keys; any stage that yielded nothing → that field is None

## Adapter HTTP Contracts (locked)

```jsonc
// VLLMClient.generate
POST {vllm_url}/v1/completions
{
  "model": "<vllm_model>",
  "prompt": "<text>",
  "max_tokens": 128,
  "stream": true,
  "n": 1,
  "guided_decoding_backend": "xgrammar",      // when grammar provided
  "guided_json": { /* schema */ }              // when grammar is dict / JSON-parseable str
  // OR "guided_regex": "..."                  // when grammar starts with ^
}
// SSE response: data: { "choices": [ { "text": "...", "finish_reason": null|"stop"|"length"|"grammar" } ] }
// Terminator: "data: [DONE]"

// ChatterboxClient.synthesize
POST {chatterbox_url}/tts
{ "text": "...", "voice": "<name>|default", "stream": true, "format": "pcm_s16le_24000" }
// Streaming bytes (aiter_bytes 4096)

// KokoroClient.synthesize
POST {kokoro_url}/v1/audio/speech
{ "input": "...", "voice": "<name>|af_bella", "response_format": "pcm", "stream": true }
// Streaming bytes (aiter_bytes 4096)

// Health checks (all 3 HTTP adapters)
GET {base_url}/health  → 200 OK
```

## Dependency Group Decision

The `cuda` group is **optional**, not in `[project.dependencies]`:

```toml
[project.optional-dependencies]
cuda = [
    "vllm>=0.10.0,<0.11.0",
    "faster-whisper>=1.0,<2.0",
    "livekit-agents>=1.0,<2.0",
    "livekit-plugins-silero",
    "livekit-plugins-turn-detector",
    "httpx[http2]>=0.27",
    "numpy>=1.26,<3.0",
    "xgrammar>=0.1",
]
```

Operator workstation runs `uv sync` (no extras) and gets a clean harness env. The RunPod H100 pod entrypoint runs `uv sync --extra cuda` to pull the GPU stack. Tests verify the workstation path — every adapter module imports without these deps thanks to deferred heavy imports.

## LiveKit Availability Posture

`livekit-agents` is **shim-only on the operator workstation**. The shim path is exercised by 5 tests in `tests/test_livekit_pipeline.py`. The real path will be exercised on the H100 pod in Plan 02-02 (gate runners) once `uv sync --extra cuda` is run there. The shim is structurally identical (SimpleNamespace with the same plugin attributes), so the gate-runner code is the same on both paths.

## Test Count + Coverage

24 new tests across 2 test files (full suite: 137 passing, no regressions).

| File | Tests | Coverage focus |
|------|-------|----------------|
| `tests/test_cuda_substrate.py` | 19 | adapter HTTP contracts, error degradation, ABC conformance, env_fingerprint, no-GPU import |
| `tests/test_livekit_pipeline.py` | 5 | shim fallback, per-stage timings, empty-STT graceful path, no-torch import |

LOC delivered:

| File | LOC |
|------|-----|
| substrate/cuda.py | 225 |
| substrate/livekit_pipeline.py | 265 |
| substrate/adapters/vllm_client.py | 133 |
| substrate/adapters/faster_whisper_engine.py | 149 |
| substrate/adapters/chatterbox_client.py | 65 |
| substrate/adapters/kokoro_client.py | 67 |
| substrate/adapters/__init__.py | 23 |
| tests/test_cuda_substrate.py | 542 |
| tests/test_livekit_pipeline.py | 180 |
| **total** | **1,649** |

## Verification

```bash
$ uv run pytest -q
137 passed in 3.83s

$ uv run python -c "from substrate.cuda import CUDASubstrate; from substrate.livekit_pipeline import build_session, run_one_call"
(no output, exit 0)

$ uv run ruff check substrate/cuda.py substrate/livekit_pipeline.py substrate/adapters/ tests/test_cuda_substrate.py tests/test_livekit_pipeline.py
All checks passed!

$ grep -RnE "^[^#]*\braise\b" substrate/adapters/ substrate/cuda.py | grep -v "MUST NOT raise"
(empty — confirms T-02-01-03 mitigation)
```

## Deviations from Plan

None — plan executed exactly as written. The only minor adaptations:

1. **Pre-commit auto-formatting** rewrote test files for line-length / format compliance during commits; functional content unchanged.
2. **`# noqa: S607` placement** moved to the argument line (vs the call-site line) for ruff to recognize the suppression — cosmetic.

No Rule 1-4 deviations triggered. All 3 tasks fit the plan's `<behavior>` and `<acceptance_criteria>` precisely.

## Threat Model Disposition

| Threat ID | Disposition | Mitigation Verified |
|-----------|-------------|---------------------|
| T-02-01-01 (Tampering, models.lock.yaml) | mitigate | `_lookup_model_shas()` reads directly from lockfile; no runtime override path |
| T-02-01-02 (Information Disclosure, payload logs) | mitigate | `test_chatterbox_logs_status_only_no_payload` asserts secret string never in caplog |
| T-02-01-03 (DoS, adapter raise) | mitigate | grep + per-adapter "swallows error" tests; "MUST NOT raise" pattern enforced |
| T-02-01-04 (Repudiation, missing fp fields) | mitigate | EnvFingerprint pydantic validation rejects partial population; verified by `test_cuda_substrate_env_fingerprint_populated` |
| T-02-01-05 (Spoofing, rogue endpoint) | accept | Pod-internal trust; documented in DR-31; not Phase 2 scope |

## Self-Check: PASSED

Verification:

- substrate/cuda.py: FOUND
- substrate/livekit_pipeline.py: FOUND
- substrate/adapters/__init__.py: FOUND
- substrate/adapters/vllm_client.py: FOUND
- substrate/adapters/faster_whisper_engine.py: FOUND
- substrate/adapters/chatterbox_client.py: FOUND
- substrate/adapters/kokoro_client.py: FOUND
- tests/test_cuda_substrate.py: FOUND
- tests/test_livekit_pipeline.py: FOUND
- pyproject.toml [project.optional-dependencies] cuda: FOUND (8 entries)

Commits (in order):

- c6b560f: test(02-01): add failing tests for CUDA substrate adapters
- 6c5e574: feat(02-01): implement CUDA substrate adapters (HARNESS-02)
- 04ecca3: test(02-01): add failing tests for CUDASubstrate (HARNESS-02)
- fceac51: feat(02-01): implement CUDASubstrate composing 4 adapters (HARNESS-02 D-14)
- c072fc4: test(02-01): add failing tests for LiveKit AgentSession rig (D-15)
- 7d5083c: feat(02-01): implement LiveKit AgentSession pipeline rig (D-15)

All 6 commits present. No deferred items. No blockers introduced.
