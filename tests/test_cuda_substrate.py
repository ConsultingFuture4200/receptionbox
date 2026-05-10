"""Unit tests for CUDA substrate adapters (Phase 2, HARNESS-02).

All tests run without GPU drivers, without torch, without faster-whisper,
without vLLM. Heavy imports are deferred inside the adapter implementations
so the workstation can import these modules with no CUDA stack.

Adapters MUST NOT raise on backend failure — they log WARNING and yield
nothing (or yield a degraded chunk). Phase 1 lock-in: the cost-watch loop
mirrors this pattern; we extend it to the substrate seam.
"""

from __future__ import annotations

import asyncio
import json
import logging
import sys
from collections.abc import AsyncIterator
from typing import Any

import httpx
import pytest

# ---------------------------------------------------------------------------
# Helpers: mock httpx without external deps (no respx / no pytest-httpx).
# We monkeypatch httpx.AsyncClient.stream / .get to return a fake response.
# ---------------------------------------------------------------------------


class _FakeResponse:
    """Quacks like an httpx.Response for the small surface we use."""

    def __init__(
        self,
        status_code: int = 200,
        lines: list[str] | None = None,
        chunks: list[bytes] | None = None,
        json_body: dict | None = None,
        capture: dict | None = None,
    ) -> None:
        self.status_code = status_code
        self._lines = lines or []
        self._chunks = chunks or []
        self._json_body = json_body
        self._capture = capture
        self.request = httpx.Request("POST", "http://fake/")

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise httpx.HTTPStatusError(
                f"HTTP {self.status_code}",
                request=self.request,
                response=self,  # type: ignore[arg-type]
            )

    def json(self) -> Any:
        return self._json_body

    async def aiter_lines(self) -> AsyncIterator[str]:
        for line in self._lines:
            yield line

    async def aiter_bytes(self, chunk_size: int | None = None) -> AsyncIterator[bytes]:
        for chunk in self._chunks:
            yield chunk

    async def __aenter__(self) -> _FakeResponse:
        return self

    async def __aexit__(self, *exc_info: Any) -> None:
        return None


def _patch_async_stream(
    monkeypatch: pytest.MonkeyPatch,
    *,
    response: _FakeResponse,
    capture: dict | None = None,
) -> None:
    """Replace httpx.AsyncClient.stream with a thunk returning `response`."""

    def fake_stream(self, method: str, url: str, **kwargs: Any) -> _FakeResponse:
        if capture is not None:
            capture["method"] = method
            capture["url"] = url
            capture["kwargs"] = kwargs
        return response

    monkeypatch.setattr(httpx.AsyncClient, "stream", fake_stream, raising=True)


def _patch_async_get(
    monkeypatch: pytest.MonkeyPatch,
    *,
    status_code: int = 200,
    raise_exc: BaseException | None = None,
) -> None:
    async def fake_get(self, url: str, **kwargs: Any) -> _FakeResponse:
        if raise_exc is not None:
            raise raise_exc
        return _FakeResponse(status_code=status_code, json_body={"ok": True})

    monkeypatch.setattr(httpx.AsyncClient, "get", fake_get, raising=True)


# ---------------------------------------------------------------------------
# VLLMClient
# ---------------------------------------------------------------------------


def _sse(payload: dict) -> str:
    return f"data: {json.dumps(payload)}"


@pytest.mark.asyncio
async def test_vllm_client_yields_chunks_from_stream(monkeypatch: pytest.MonkeyPatch) -> None:
    from substrate.adapters import VLLMClient

    lines = [
        _sse({"choices": [{"text": "hel", "finish_reason": None}]}),
        "",
        _sse({"choices": [{"text": "lo", "finish_reason": None}]}),
        _sse({"choices": [{"text": "", "finish_reason": "stop"}]}),
        "data: [DONE]",
    ]
    _patch_async_stream(monkeypatch, response=_FakeResponse(status_code=200, lines=lines))

    client = VLLMClient(base_url="http://fake", model="qwen3-4b")
    chunks = []
    async for chunk in client.generate("hi", grammar=None, max_tokens=8):
        chunks.append(chunk)

    assert len(chunks) == 3
    assert chunks[0].text == "hel"
    assert chunks[1].text == "lo"
    assert chunks[2].finish_reason == "stop"


@pytest.mark.asyncio
async def test_vllm_client_logs_warning_on_500_does_not_raise(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    from substrate.adapters import VLLMClient

    caplog.set_level(logging.WARNING)
    _patch_async_stream(monkeypatch, response=_FakeResponse(status_code=500, lines=[]))

    client = VLLMClient(base_url="http://fake", model="qwen3-4b")
    chunks = []
    async for chunk in client.generate("hi", grammar=None, max_tokens=8):
        chunks.append(chunk)

    assert chunks == []
    assert client.last_error is not None
    assert any("vllm" in rec.message.lower() or "500" in rec.message for rec in caplog.records)


@pytest.mark.asyncio
async def test_vllm_client_passes_xgrammar_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    from substrate.adapters import VLLMClient

    capture: dict = {}
    _patch_async_stream(
        monkeypatch,
        response=_FakeResponse(status_code=200, lines=["data: [DONE]"]),
        capture=capture,
    )

    client = VLLMClient(base_url="http://fake", model="qwen3-4b")
    grammar = {"type": "object", "properties": {"intent": {"type": "string"}}}
    async for _ in client.generate("hi", grammar=grammar, max_tokens=8):
        pass

    body = capture["kwargs"]["json"]
    assert body["guided_decoding_backend"] == "xgrammar"
    assert body["guided_json"] == grammar
    assert body["stream"] is True
    assert body["model"] == "qwen3-4b"


@pytest.mark.asyncio
async def test_vllm_client_handles_connect_error(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    from substrate.adapters import VLLMClient

    caplog.set_level(logging.WARNING)

    def fake_stream(self, method: str, url: str, **kwargs: Any) -> _FakeResponse:
        raise httpx.ConnectError("connection refused", request=httpx.Request(method, url))

    monkeypatch.setattr(httpx.AsyncClient, "stream", fake_stream, raising=True)

    client = VLLMClient(base_url="http://127.0.0.1:1", model="qwen3-4b")
    chunks = []
    async for chunk in client.generate("hi", grammar=None, max_tokens=8):
        chunks.append(chunk)

    assert chunks == []
    assert client.last_error is not None


@pytest.mark.asyncio
async def test_vllm_client_health_returns_true_on_200(monkeypatch: pytest.MonkeyPatch) -> None:
    from substrate.adapters import VLLMClient

    _patch_async_get(monkeypatch, status_code=200)
    client = VLLMClient(base_url="http://fake", model="qwen3-4b")
    assert await client.health() is True


@pytest.mark.asyncio
async def test_vllm_client_health_returns_false_on_error(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    from substrate.adapters import VLLMClient

    caplog.set_level(logging.WARNING)
    _patch_async_get(
        monkeypatch, raise_exc=httpx.ConnectError("nope", request=httpx.Request("GET", "/"))
    )
    client = VLLMClient(base_url="http://fake", model="qwen3-4b")
    assert await client.health() is False


# ---------------------------------------------------------------------------
# ChatterboxClient
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_chatterbox_client_streams_pcm(monkeypatch: pytest.MonkeyPatch) -> None:
    from substrate.adapters import ChatterboxClient

    chunks_in = [b"\x00" * 1024, b"\x11" * 1024, b"\x22" * 512]
    _patch_async_stream(monkeypatch, response=_FakeResponse(status_code=200, chunks=chunks_in))

    client = ChatterboxClient(base_url="http://fake")
    out = []
    async for c in client.synthesize("hello", voice=None):
        out.append(c)

    assert out == chunks_in


@pytest.mark.asyncio
async def test_chatterbox_client_swallows_connect_error(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    from substrate.adapters import ChatterboxClient

    caplog.set_level(logging.WARNING)

    def fake_stream(self, method: str, url: str, **kwargs: Any) -> _FakeResponse:
        raise httpx.ConnectError("nope", request=httpx.Request(method, url))

    monkeypatch.setattr(httpx.AsyncClient, "stream", fake_stream, raising=True)

    client = ChatterboxClient(base_url="http://127.0.0.1:1")
    out = []
    async for c in client.synthesize("hi", voice=None):
        out.append(c)

    assert out == []
    assert any("chatterbox" in rec.message.lower() for rec in caplog.records)


@pytest.mark.asyncio
async def test_chatterbox_logs_status_only_no_payload(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """T-02-01-02: adapters must NOT log the request payload."""
    from substrate.adapters import ChatterboxClient

    caplog.set_level(logging.WARNING)
    _patch_async_stream(monkeypatch, response=_FakeResponse(status_code=503, chunks=[]))

    client = ChatterboxClient(base_url="http://fake")
    secret_text = "PRIVILEGED_LEGAL_FACT_DO_NOT_LOG"
    out = []
    async for c in client.synthesize(secret_text, voice=None):
        out.append(c)

    for rec in caplog.records:
        assert secret_text not in rec.message


# ---------------------------------------------------------------------------
# KokoroClient
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_kokoro_client_streams_pcm(monkeypatch: pytest.MonkeyPatch) -> None:
    from substrate.adapters import KokoroClient

    chunks_in = [b"\x33" * 1024, b"\x44" * 512]
    capture: dict = {}
    _patch_async_stream(
        monkeypatch,
        response=_FakeResponse(status_code=200, chunks=chunks_in),
        capture=capture,
    )

    client = KokoroClient(base_url="http://fake")
    out = []
    async for c in client.synthesize("hello", voice=None):
        out.append(c)

    assert out == chunks_in
    # Default voice + endpoint shape
    body = capture["kwargs"]["json"]
    assert body["voice"] == "af_bella"
    assert body["response_format"] == "pcm"
    assert "/v1/audio/speech" in capture["url"]


# ---------------------------------------------------------------------------
# FasterWhisperEngine — module import must succeed without faster_whisper.
# ---------------------------------------------------------------------------


def test_faster_whisper_engine_module_imports_without_torch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Pretend faster_whisper is not importable in the env.
    monkeypatch.setitem(sys.modules, "faster_whisper", None)
    monkeypatch.setitem(sys.modules, "torch", None)

    # Drop any cached copy of the engine module so the import re-runs.
    for mod in list(sys.modules):
        if mod.startswith("substrate.adapters.faster_whisper_engine"):
            sys.modules.pop(mod)

    import substrate.adapters.faster_whisper_engine as fw

    assert hasattr(fw, "FasterWhisperEngine")
    eng = fw.FasterWhisperEngine(model_dir="/nonexistent")
    # health should not raise even with no faster_whisper installed.
    healthy = asyncio.new_event_loop().run_until_complete(eng.health())
    assert healthy is False


@pytest.mark.asyncio
async def test_faster_whisper_engine_transcribe_logs_and_yields_nothing_on_failure(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setitem(sys.modules, "faster_whisper", None)
    for mod in list(sys.modules):
        if mod.startswith("substrate.adapters.faster_whisper_engine"):
            sys.modules.pop(mod)

    import substrate.adapters.faster_whisper_engine as fw

    caplog.set_level(logging.WARNING)
    eng = fw.FasterWhisperEngine(model_dir="/nonexistent")

    async def audio() -> AsyncIterator[bytes]:
        yield b"\x00" * 3200

    out = []
    async for chunk in eng.transcribe(audio(), sample_rate=16000):
        out.append(chunk)

    assert out == []


# ---------------------------------------------------------------------------
# DEV-1083: codec-aware audio decode (WAV/RIFF μ-law + PCM int16) regression
#
# Both regressions are tested against the real audio-prep code path, with the
# faster-whisper model itself stubbed so the test runs CPU-side with no GPU /
# no model download. We capture the float32 array the engine *would have
# handed to* WhisperModel.transcribe() and assert it has speech-like
# statistics (RMS in (0.005, 0.5), peak in (0.05, 1.0)) — the broken pre-fix
# code path produces a saturated noise array (peak ~1.0, RMS > 0.5) which
# would fail these bounds.
# ---------------------------------------------------------------------------


def _audio_stats_capture():
    """Return (capture_dict, fake_model_class). The fake model records the
    numpy array passed to transcribe() so the test can inspect it."""
    import numpy as np  # local import; tests/ is unconstrained

    capture: dict = {"arr": None}

    class _FakeWhisperModel:
        def __init__(self, *_a, **_kw) -> None:
            pass

        def transcribe(self, arr, **_kwargs):
            capture["arr"] = np.asarray(arr, dtype=np.float32).copy()
            # Return (segments, info) shape that matches faster_whisper's API.
            return iter(()), object()

    return capture, _FakeWhisperModel


def _make_mulaw_wav_bytes(seconds: float = 0.5, freq_hz: float = 1000.0) -> bytes:
    """Synthesize an 8 kHz mono μ-law WAV in-memory (RIFF + fmt 7 + data)."""
    import io

    import numpy as np
    import soundfile as sf

    sr = 8000
    t = np.linspace(0.0, seconds, int(sr * seconds), endpoint=False, dtype=np.float32)
    tone = 0.3 * np.sin(2 * np.pi * freq_hz * t)
    buf = io.BytesIO()
    # subtype="ULAW" emits WAVE_FORMAT_MULAW (fmt code 7) — matches the G.711
    # corpus produced by ffmpeg's pcm_mulaw codec (assets/g711.py).
    sf.write(buf, tone, sr, format="WAV", subtype="ULAW")
    return buf.getvalue()


def _make_pcm16_wav_bytes(seconds: float = 0.5, freq_hz: float = 1000.0) -> bytes:
    """Synthesize a 16 kHz mono PCM-int16 WAV in-memory."""
    import io

    import numpy as np
    import soundfile as sf

    sr = 16000
    t = np.linspace(0.0, seconds, int(sr * seconds), endpoint=False, dtype=np.float32)
    tone = 0.3 * np.sin(2 * np.pi * freq_hz * t)
    buf = io.BytesIO()
    sf.write(buf, tone, sr, format="WAV", subtype="PCM_16")
    return buf.getvalue()


@pytest.mark.asyncio
async def test_faster_whisper_engine_decodes_g711_mulaw_wav(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """DEV-1083: μ-law WAV bytes must be decompanded, not reinterpreted as int16.

    Pre-fix: `np.frombuffer(wav_file_bytes, dtype=np.int16)` would feed Whisper
    a saturated noise array (peak ≈ 1.0, RMS ≈ 0.6), causing hallucination of
    short coherent English fillers. Post-fix: soundfile decodes μ-law to
    float32 in [-1, 1] with speech-like statistics.
    """
    capture, FakeModel = _audio_stats_capture()
    fake_module = type(sys)("faster_whisper")
    fake_module.WhisperModel = FakeModel  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "faster_whisper", fake_module)
    for mod in list(sys.modules):
        if mod.startswith("substrate.adapters.faster_whisper_engine"):
            sys.modules.pop(mod)

    import substrate.adapters.faster_whisper_engine as fw

    eng = fw.FasterWhisperEngine(model_dir="/nonexistent", device="cpu")
    wav = _make_mulaw_wav_bytes(seconds=0.5, freq_hz=1000.0)

    async def audio() -> AsyncIterator[bytes]:
        # Stream in two chunks to exercise the bytearray drain.
        mid = len(wav) // 2
        yield wav[:mid]
        yield wav[mid:]

    out = []
    async for chunk in eng.transcribe(audio(), sample_rate=8000):
        out.append(chunk)

    arr = capture["arr"]
    assert arr is not None, "fake WhisperModel.transcribe was not called"
    # After 8 kHz → 16 kHz linear resample, a 0.5s tone is ~8000 samples.
    assert 7900 <= arr.size <= 8100, f"unexpected resampled length {arr.size}"
    # Speech-like (or in this case clean-tone) statistics — the broken
    # int16-frombuffer path on a μ-law WAV would produce peak ≈ 1.0 / RMS > 0.5.
    import numpy as np

    peak = float(np.max(np.abs(arr)))
    rms = float(np.sqrt(np.mean(arr.astype(np.float64) ** 2)))
    assert 0.05 < peak < 0.95, f"peak {peak} outside speech-like range"
    assert 0.05 < rms < 0.4, f"rms {rms} outside speech-like range"


@pytest.mark.asyncio
async def test_faster_whisper_engine_decodes_pcm16_wav(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """DEV-1083: PCM-int16 WAV bytes must also go through the soundfile path
    so RIFF header bytes are not interpreted as samples."""
    capture, FakeModel = _audio_stats_capture()
    fake_module = type(sys)("faster_whisper")
    fake_module.WhisperModel = FakeModel  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "faster_whisper", fake_module)
    for mod in list(sys.modules):
        if mod.startswith("substrate.adapters.faster_whisper_engine"):
            sys.modules.pop(mod)

    import substrate.adapters.faster_whisper_engine as fw

    eng = fw.FasterWhisperEngine(model_dir="/nonexistent", device="cpu")
    wav = _make_pcm16_wav_bytes(seconds=0.5, freq_hz=1000.0)

    async def audio() -> AsyncIterator[bytes]:
        yield wav

    out = []
    async for chunk in eng.transcribe(audio(), sample_rate=16000):
        out.append(chunk)

    arr = capture["arr"]
    assert arr is not None
    # 16 kHz x 0.5 s, no resample needed -> ~8000 samples.
    assert 7900 <= arr.size <= 8100
    import numpy as np

    peak = float(np.max(np.abs(arr)))
    assert 0.05 < peak < 0.95


@pytest.mark.asyncio
async def test_faster_whisper_engine_legacy_raw_pcm_path_still_works(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """DEV-1083: The legacy raw-int16-PCM path (no RIFF prefix) must keep
    working unchanged — guards backward compat for non-WAV callers."""
    capture, FakeModel = _audio_stats_capture()
    fake_module = type(sys)("faster_whisper")
    fake_module.WhisperModel = FakeModel  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "faster_whisper", fake_module)
    for mod in list(sys.modules):
        if mod.startswith("substrate.adapters.faster_whisper_engine"):
            sys.modules.pop(mod)

    import numpy as np

    import substrate.adapters.faster_whisper_engine as fw

    eng = fw.FasterWhisperEngine(model_dir="/nonexistent", device="cpu")

    sr = 16000
    t = np.linspace(0.0, 0.5, int(sr * 0.5), endpoint=False, dtype=np.float32)
    tone = (0.3 * np.sin(2 * np.pi * 1000 * t) * 32767).astype(np.int16)
    raw = tone.tobytes()
    assert raw[:4] != b"RIFF"

    async def audio() -> AsyncIterator[bytes]:
        yield raw

    out = []
    async for chunk in eng.transcribe(audio(), sample_rate=sr):
        out.append(chunk)

    arr = capture["arr"]
    assert arr is not None
    assert 7900 <= arr.size <= 8100
    peak = float(np.max(np.abs(arr)))
    assert 0.05 < peak < 0.95


# ---------------------------------------------------------------------------
# CUDASubstrate (composes the 4 adapters per D-14)
# ---------------------------------------------------------------------------


def _new_substrate(**overrides: Any):
    from substrate.cuda import CUDASubstrate

    kwargs = dict(
        vllm_url="http://fake-vllm:8000",
        vllm_model="qwen3-4b",
        whisper_model_dir="/nonexistent/whisper",
        chatterbox_url="http://fake-chatterbox:8001",
        kokoro_url="http://fake-kokoro:8002",
    )
    kwargs.update(overrides)
    return CUDASubstrate(**kwargs)


def test_cuda_substrate_implements_abc() -> None:
    from substrate import Substrate
    from substrate.cuda import CUDASubstrate

    assert issubclass(CUDASubstrate, Substrate)
    sub = _new_substrate()
    # All abstract methods bound and callable.
    for attr in ("load_stt", "load_llm", "load_tts", "transcribe", "generate", "synthesize"):
        assert callable(getattr(sub, attr))


@pytest.mark.asyncio
async def test_cuda_substrate_load_llm_logs_warning_on_health_fail(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    from substrate.adapters import VLLMClient

    caplog.set_level(logging.WARNING)

    async def fake_health(self):
        return False

    monkeypatch.setattr(VLLMClient, "health", fake_health, raising=True)

    sub = _new_substrate()
    # Must not raise.
    await sub.load_llm()
    assert sub._loaded["llm"] is False
    assert any(
        "llm" in rec.message.lower() or "vllm" in rec.message.lower() for rec in caplog.records
    )


@pytest.mark.asyncio
async def test_cuda_substrate_transcribe_delegates_to_engine(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from substrate.adapters import FasterWhisperEngine
    from substrate.types import STTChunk

    async def fake_transcribe(self, audio, *, sample_rate):
        yield STTChunk(text="alpha", is_final=False, start_ms=0.0, end_ms=500.0)
        yield STTChunk(text="alpha bravo", is_final=True, start_ms=0.0, end_ms=1000.0)

    monkeypatch.setattr(FasterWhisperEngine, "transcribe", fake_transcribe, raising=True)

    sub = _new_substrate()

    async def audio() -> AsyncIterator[bytes]:
        yield b"\x00" * 320

    out = []
    async for chunk in sub.transcribe(audio(), sample_rate=16000):
        out.append(chunk)

    assert len(out) == 2
    assert out[-1].text == "alpha bravo"
    assert out[-1].is_final is True


@pytest.mark.asyncio
async def test_cuda_substrate_generate_delegates_to_vllm(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from substrate.adapters import VLLMClient
    from substrate.types import LLMChunk

    async def fake_generate(self, prompt, *, grammar=None, max_tokens):
        yield LLMChunk(text="ok", finish_reason=None)
        yield LLMChunk(text="", finish_reason="stop")

    monkeypatch.setattr(VLLMClient, "generate", fake_generate, raising=True)

    sub = _new_substrate()
    out = []
    async for chunk in sub.generate("hi", max_tokens=8):
        out.append(chunk)

    assert len(out) == 2
    assert out[-1].finish_reason == "stop"


@pytest.mark.asyncio
async def test_cuda_substrate_synthesize_falls_back_to_kokoro_when_chatterbox_unhealthy(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from substrate.adapters import ChatterboxClient, KokoroClient

    async def chatterbox_health(self):
        return False

    async def kokoro_health(self):
        return True

    async def chatterbox_synth(self, text, voice):
        yield b"CHATTERBOX"

    async def kokoro_synth(self, text, voice):
        yield b"KOKORO"

    monkeypatch.setattr(ChatterboxClient, "health", chatterbox_health, raising=True)
    monkeypatch.setattr(KokoroClient, "health", kokoro_health, raising=True)
    monkeypatch.setattr(ChatterboxClient, "synthesize", chatterbox_synth, raising=True)
    monkeypatch.setattr(KokoroClient, "synthesize", kokoro_synth, raising=True)

    sub = _new_substrate()
    out = []
    async for chunk in sub.synthesize("hello", voice=None):
        out.append(chunk)

    assert out == [b"KOKORO"]


def test_cuda_substrate_env_fingerprint_populated() -> None:
    from substrate.types import EnvFingerprint

    sub = _new_substrate()
    fp = sub.env_fingerprint()
    assert isinstance(fp, EnvFingerprint)
    assert fp.substrate == "cuda"
    assert fp.image_digest  # may be "pending" — non-empty string
    # 4 models per bench/models.lock.yaml
    assert len(fp.model_shas) == 4
    expected_models = {
        "distil_whisper_large_v3_int8",
        "qwen3_4b_awq_int4",
        "chatterbox_turbo",
        "kokoro_82m",
    }
    assert set(fp.model_shas.keys()) == expected_models
    assert fp.timestamp_utc  # ISO string


def test_cuda_substrate_module_importable_without_gpu(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """CUDASubstrate module + class instantiation must not require torch / vllm / faster_whisper."""
    monkeypatch.setitem(sys.modules, "torch", None)
    monkeypatch.setitem(sys.modules, "vllm", None)
    monkeypatch.setitem(sys.modules, "faster_whisper", None)

    for mod in list(sys.modules):
        if mod.startswith("substrate.cuda") or mod.startswith("substrate.adapters"):
            sys.modules.pop(mod)

    from substrate.cuda import CUDASubstrate

    sub = CUDASubstrate(
        vllm_url="http://x:1",
        vllm_model="qwen",
        whisper_model_dir="/nope",
        chatterbox_url="http://x:2",
        kokoro_url="http://x:3",
    )
    assert sub is not None
