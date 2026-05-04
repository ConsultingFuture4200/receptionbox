"""Deterministic in-memory Substrate for Phase 1 unit tests.

Not a "fake" — a real Substrate whose load_* are no-ops and whose
streaming methods yield deterministic synthetic chunks. Lives under a
private (_stub) module so gate runners can never accidentally use it.
"""

from __future__ import annotations

import datetime
from collections.abc import AsyncIterator

from . import Substrate
from .types import EnvFingerprint, Grammar, LLMChunk, STTChunk, VoiceRef


class _StubSubstrate(Substrate):
    """In-memory deterministic Substrate. Tests only."""

    def __init__(self, *, fingerprint_substrate: str = "cuda") -> None:
        self._loaded = {"stt": False, "llm": False, "tts": False}
        self._fingerprint_substrate = fingerprint_substrate

    async def load_stt(self) -> None:
        self._loaded["stt"] = True

    async def load_llm(self) -> None:
        self._loaded["llm"] = True

    async def load_tts(self) -> None:
        self._loaded["tts"] = True

    async def transcribe(
        self,
        audio: AsyncIterator[bytes],
        *,
        sample_rate: int,
    ) -> AsyncIterator[STTChunk]:
        # Drain the audio iterator deterministically; emit two partials + final.
        n_chunks = 0
        async for _ in audio:
            n_chunks += 1
        yield STTChunk(text="hello", is_final=False, start_ms=0.0, end_ms=500.0)
        yield STTChunk(text="hello world", is_final=True, start_ms=0.0, end_ms=1000.0)

    async def generate(
        self,
        prompt: str,
        *,
        grammar: Grammar | None = None,
        max_tokens: int,
    ) -> AsyncIterator[LLMChunk]:
        for word in ("ok", " thanks"):
            yield LLMChunk(text=word, finish_reason=None)
        yield LLMChunk(text="", finish_reason="stop")

    async def synthesize(
        self,
        text: str,
        *,
        voice: VoiceRef | None = None,
    ) -> AsyncIterator[bytes]:
        # Deterministic 240-byte PCM chunks (10ms @ 24kHz mono int16).
        yield b"\x00" * 240
        yield b"\x00" * 240

    def env_fingerprint(self) -> EnvFingerprint:
        return EnvFingerprint(
            substrate=self._fingerprint_substrate,  # type: ignore[arg-type]
            image_digest="sha256:stub",
            model_shas={"stub": "0" * 40},
            gpu_sku="stub-gpu",
            gpu_count=1,
            rocm_version=None,
            cuda_version=None,
            vllm_version=None,
            pytorch_version=None,
            timestamp_utc=datetime.datetime.utcnow().isoformat(),
        )
