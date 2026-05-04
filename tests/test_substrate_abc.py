"""Substrate ABC contract tests. Uses the deterministic _StubSubstrate so
no torch / no GPU is required.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest

from substrate import Grammar, LLMChunk, STTChunk, Substrate
from substrate._stub import _StubSubstrate
from substrate.types import EnvFingerprint, VoiceRef


def test_substrate_is_abstract() -> None:
    with pytest.raises(TypeError):
        Substrate()  # type: ignore[abstract]


def test_grammar_alias_accepts_str_and_dict() -> None:
    g_str: Grammar = '{"type":"object"}'
    g_dict: Grammar = {"type": "object"}
    assert isinstance(g_str, str)
    assert isinstance(g_dict, dict)


@pytest.mark.asyncio
async def test_stub_load_methods_succeed() -> None:
    s = _StubSubstrate()
    await s.load_stt()
    await s.load_llm()
    await s.load_tts()
    assert s._loaded == {"stt": True, "llm": True, "tts": True}


@pytest.mark.asyncio
async def test_stub_transcribe_yields_partial_then_final() -> None:
    s = _StubSubstrate()

    async def empty_audio() -> AsyncIterator[bytes]:
        if False:
            yield b""

    chunks: list[STTChunk] = []
    async for chunk in s.transcribe(empty_audio(), sample_rate=16000):
        chunks.append(chunk)
    assert len(chunks) == 2
    assert chunks[-1].is_final is True
    assert chunks[-1].text == "hello world"


@pytest.mark.asyncio
async def test_stub_generate_yields_tokens_then_stop() -> None:
    s = _StubSubstrate()
    chunks: list[LLMChunk] = []
    async for chunk in s.generate("hi", max_tokens=10):
        chunks.append(chunk)
    assert chunks[-1].finish_reason == "stop"
    assert "ok" in chunks[0].text


@pytest.mark.asyncio
async def test_stub_synthesize_yields_pcm_bytes() -> None:
    s = _StubSubstrate()
    blobs: list[bytes] = []
    async for chunk in s.synthesize("hello", voice=VoiceRef(name="default")):
        blobs.append(chunk)
    assert all(isinstance(b, bytes) for b in blobs)
    assert sum(len(b) for b in blobs) == 480


def test_env_fingerprint_round_trips_through_json() -> None:
    s = _StubSubstrate()
    fp = s.env_fingerprint()
    assert isinstance(fp, EnvFingerprint)
    j = fp.model_dump_json()
    restored = EnvFingerprint.model_validate_json(j)
    assert restored == fp
