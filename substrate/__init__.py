"""Substrate ABC — gate-runner contract for STT/LLM/TTS.

Concrete implementations land in Phase 2 (substrate/cuda.py for RunPod H100)
and Phase 3 (substrate/rocm.py for TensorWave MI300X). Phase 1 ships only
the ABC + a deterministic in-memory stub for unit tests.

The async-streaming method shape is locked by D-09 in CONTEXT.md and matches
LiveKit Agents 1.x natively — when Phase 3 wires LiveKit AgentSession,
no rework is needed.

HARNESS-01 enforcement: gate runners under gates/ MUST NOT import torch,
onnxruntime, vllm, transformers, ctranslate2, or faster_whisper directly.
This is checked by tests/test_harness_isolation.py.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator

from .types import EnvFingerprint, Grammar, LLMChunk, STTChunk, VoiceRef

__all__ = [
    "EnvFingerprint",
    "Grammar",
    "LLMChunk",
    "STTChunk",
    "Substrate",
    "VoiceRef",
]


class Substrate(ABC):
    """Cloud-GPU substrate for receptionBOX Phase 0 benchmarking."""

    @abstractmethod
    async def load_stt(self) -> None: ...

    @abstractmethod
    async def load_llm(self) -> None: ...

    @abstractmethod
    async def load_tts(self) -> None: ...

    @abstractmethod
    async def transcribe(
        self,
        audio: AsyncIterator[bytes],
        *,
        sample_rate: int,
    ) -> AsyncIterator[STTChunk]:
        """Stream partial hypotheses from streaming audio bytes."""
        ...

    @abstractmethod
    async def generate(
        self,
        prompt: str,
        *,
        grammar: Grammar | None = None,
        max_tokens: int,
    ) -> AsyncIterator[LLMChunk]:
        """Stream LLM tokens. `grammar` carries the xgrammar constraint for G5."""
        ...

    @abstractmethod
    async def synthesize(
        self,
        text: str,
        *,
        voice: VoiceRef | None = None,
    ) -> AsyncIterator[bytes]:
        """Stream PCM audio chunks."""
        ...

    @abstractmethod
    def env_fingerprint(self) -> EnvFingerprint:
        """Return image digest, model SHAs, ROCm/CUDA version, GPU SKU.

        Sync — env capture is point-in-time and shouldn't suspend.
        """
        ...
