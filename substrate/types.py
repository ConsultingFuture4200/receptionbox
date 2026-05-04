"""Type definitions consumed by the Substrate ABC.

These are pydantic v2 models (not raw dataclasses) so they JSON-serialize
cleanly into env.json sidecars (HARNESS-05) and gate result `extras`.

Grammar is a plain type alias because xgrammar's JSON Schema input is
either a string or a dict — no richer wrapper required for Phase 1
(see RESEARCH.md Open Question #5).
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

# xgrammar accepts JSON Schema strings or dicts; no dedicated wrapper in Phase 1.
Grammar = str | dict[str, Any]


class STTChunk(BaseModel):
    """Streaming partial hypothesis from STT (faster-whisper or ONNX-RT path)."""

    text: str
    is_final: bool = False
    start_ms: float | None = None
    end_ms: float | None = None
    confidence: float | None = None


class LLMChunk(BaseModel):
    """Streaming token / text fragment from the LLM (Qwen3-4B via vLLM)."""

    text: str
    token_id: int | None = None
    logprob: float | None = None
    finish_reason: Literal["length", "stop", "grammar", None] = None


class VoiceRef(BaseModel):
    """Reference voice identifier or clone-reference clip path for TTS."""

    name: str
    clone_ref_path: str | None = None
    sample_rate: int = 24000


class EnvFingerprint(BaseModel):
    """Captured at the start of every gate run (HARNESS-05)."""

    substrate: Literal["cuda", "rocm"]
    image_digest: str
    model_shas: dict[str, str] = Field(default_factory=dict)
    gpu_sku: str
    gpu_count: int
    rocm_version: str | None = None
    cuda_version: str | None = None
    vllm_version: str | None = None
    pytorch_version: str | None = None
    timestamp_utc: str
