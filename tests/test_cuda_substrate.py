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
