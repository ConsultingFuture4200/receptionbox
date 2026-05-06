"""LiveKit AgentSession pipeline rig (D-15).

Wraps a Substrate (the ABC, not a concrete impl) into an AgentSession with:
  - silero-vad v5 for frame-level VAD
  - LiveKit `turn-detector` plugin for semantic end-of-turn
  - Custom STT/LLM/TTS plugins delegating to the Substrate methods

Per-stage timing comes from AgentSession's native instrumentation when
livekit-agents is available; the shim path (used for unit tests AND for
operator-workstation development) implements the same surface using
`time.perf_counter()` between stage transitions.

Heavy LiveKit imports are deferred inside `build_session()` so this
module imports cleanly on a no-GPU / no-LiveKit workstation. Torch is
NEVER imported at module load.
"""

from __future__ import annotations

import logging
import pathlib
import time
import wave
from collections.abc import AsyncIterator
from types import SimpleNamespace
from typing import Any

from . import Substrate
from .types import VoiceRef

logger = logging.getLogger(__name__)

# Audio chunking parameters for the shim path. 16 kHz mono int16 → 320 samples
# per 20 ms frame → 640 bytes/frame. We feed 4096-byte chunks (≈128 ms each).
_AUDIO_CHUNK_BYTES = 4096


# ---------------------------------------------------------------------------
# Substrate-backed plugin wrappers.
#
# These are duck-typed so they work both with the real LiveKit AgentSession
# and the shim path. LiveKit Agents 1.x uses Protocol-based plugin
# registration, so concrete subclassing is not required.
# ---------------------------------------------------------------------------


class _SubstrateSTTPlugin:
    def __init__(self, substrate: Substrate) -> None:
        self._sub = substrate

    async def stream(
        self,
        audio: AsyncIterator[bytes],
        *,
        sample_rate: int = 16000,
    ) -> AsyncIterator[Any]:
        async for chunk in self._sub.transcribe(audio, sample_rate=sample_rate):
            yield chunk


class _SubstrateLLMPlugin:
    def __init__(self, substrate: Substrate) -> None:
        self._sub = substrate

    async def chat(
        self,
        prompt: str,
        *,
        grammar: Any = None,
        max_tokens: int = 512,
    ) -> AsyncIterator[Any]:
        async for chunk in self._sub.generate(prompt, grammar=grammar, max_tokens=max_tokens):
            yield chunk


class _SubstrateTTSPlugin:
    def __init__(self, substrate: Substrate) -> None:
        self._sub = substrate

    async def synthesize(
        self,
        text: str,
        *,
        voice: VoiceRef | None = None,
    ) -> AsyncIterator[bytes]:
        async for chunk in self._sub.synthesize(text, voice=voice):
            yield chunk


# ---------------------------------------------------------------------------
# Shim AgentSession (used when livekit-agents is unavailable).
#
# The shim exposes `.stt`, `.llm`, `.tts` plugin attributes — same surface
# the real AgentSession exposes — so `run_one_call()` is substrate-agnostic.
# ---------------------------------------------------------------------------


def _build_shim_session(substrate: Substrate, *, vad_threshold_ms: int = 800) -> SimpleNamespace:
    return SimpleNamespace(
        stt=_SubstrateSTTPlugin(substrate),
        llm=_SubstrateLLMPlugin(substrate),
        tts=_SubstrateTTSPlugin(substrate),
        vad=None,
        turn_detection=None,
        min_endpointing_delay=vad_threshold_ms / 1000.0,
        _is_shim=True,
    )


# ---------------------------------------------------------------------------
# build_session — public entry point.
# ---------------------------------------------------------------------------


def build_session(substrate: Substrate, *, vad_threshold_ms: int = 800) -> Any:
    """Build a configured AgentSession (or shim) wrapping the given Substrate.

    Real path: imports `livekit.agents.AgentSession` + silero VAD + turn
    detector per CLAUDE.md §8. Shim path: returns a SimpleNamespace with the
    same plugin surface so unit tests and offline dev work.
    """
    try:
        from livekit.agents import AgentSession  # type: ignore[import-not-found]
        from livekit.plugins import silero, turn_detector  # type: ignore[import-not-found]
    except Exception as e:
        logger.warning(
            f"[livekit-rig] livekit-agents not installed ({type(e).__name__}); "
            "falling back to shim session"
        )
        return _build_shim_session(substrate, vad_threshold_ms=vad_threshold_ms)

    try:
        vad = silero.VAD.load()
        td = turn_detector.EOUModel()
        session = AgentSession(
            stt=_SubstrateSTTPlugin(substrate),
            llm=_SubstrateLLMPlugin(substrate),
            tts=_SubstrateTTSPlugin(substrate),
            vad=vad,
            turn_detection=td,
            min_endpointing_delay=vad_threshold_ms / 1000.0,
        )
    except Exception as e:
        logger.warning(
            f"[livekit-rig] AgentSession construction failed ({type(e).__name__}); "
            "falling back to shim session"
        )
        return _build_shim_session(substrate, vad_threshold_ms=vad_threshold_ms)

    return session


# ---------------------------------------------------------------------------
# run_one_call — drives the session through a single audio file end-to-end.
# ---------------------------------------------------------------------------


async def _stream_wav(
    path: pathlib.Path, chunk_bytes: int = _AUDIO_CHUNK_BYTES
) -> AsyncIterator[bytes]:
    with wave.open(str(path), "rb") as w:
        while True:
            data = w.readframes(chunk_bytes // (w.getsampwidth() * w.getnchannels()))
            if not data:
                return
            yield data


def _now_ms() -> float:
    return time.perf_counter() * 1000.0


async def run_one_call(session: Any, audio_path: pathlib.Path) -> dict[str, float | None]:
    """Run one E2E call through the session; return per-stage timings.

    Keys: stt_ttft_ms, llm_ttft_ms, llm_decode_ms_per_tok, tts_first_audio_ms,
    e2e_ms. Any stage that yielded nothing → that field is None.
    """
    timings: dict[str, float | None] = {
        "stt_ttft_ms": None,
        "llm_ttft_ms": None,
        "llm_decode_ms_per_tok": None,
        "tts_first_audio_ms": None,
        "e2e_ms": None,
    }

    t_start = _now_ms()

    # ---- STT --------------------------------------------------------------
    transcript_parts: list[str] = []
    final_text: str | None = None
    t_first_stt: float | None = None
    try:
        async for stt_chunk in session.stt.stream(_stream_wav(audio_path)):
            if t_first_stt is None:
                t_first_stt = _now_ms()
            text = getattr(stt_chunk, "text", "") or ""
            transcript_parts.append(text)
            if getattr(stt_chunk, "is_final", False):
                final_text = text
    except Exception as e:
        logger.warning(f"[livekit-rig] STT stage failed: {type(e).__name__}: {e}")

    if t_first_stt is not None:
        timings["stt_ttft_ms"] = float(t_first_stt - t_start)
    else:
        # No STT output → downstream stages cannot run meaningfully.
        return timings

    if final_text is None and transcript_parts:
        final_text = transcript_parts[-1]
    if not final_text:
        final_text = " ".join(transcript_parts).strip()
    if not final_text:
        return timings

    # ---- LLM --------------------------------------------------------------
    t_llm_start = _now_ms()
    t_first_llm: float | None = None
    llm_chunks_received = 0
    response_text_parts: list[str] = []
    try:
        async for llm_chunk in session.llm.chat(final_text, max_tokens=128):
            now = _now_ms()
            if t_first_llm is None:
                t_first_llm = now
            llm_chunks_received += 1
            response_text_parts.append(getattr(llm_chunk, "text", "") or "")
        t_llm_end = _now_ms()
    except Exception as e:
        logger.warning(f"[livekit-rig] LLM stage failed: {type(e).__name__}: {e}")
        return timings

    if t_first_llm is None:
        return timings

    timings["llm_ttft_ms"] = float(t_first_llm - t_llm_start)
    decode_window = max(t_llm_end - t_first_llm, 0.0)
    if llm_chunks_received > 1:
        timings["llm_decode_ms_per_tok"] = float(decode_window / max(llm_chunks_received - 1, 1))
    else:
        timings["llm_decode_ms_per_tok"] = 0.0

    response_text = "".join(response_text_parts).strip()
    if not response_text:
        return timings

    # ---- TTS --------------------------------------------------------------
    t_tts_start = _now_ms()
    t_first_tts: float | None = None
    try:
        async for _audio_chunk in session.tts.synthesize(response_text):
            if t_first_tts is None:
                t_first_tts = _now_ms()
                break
    except Exception as e:
        logger.warning(f"[livekit-rig] TTS stage failed: {type(e).__name__}: {e}")
        return timings

    if t_first_tts is None:
        return timings

    timings["tts_first_audio_ms"] = float(t_first_tts - t_tts_start)
    timings["e2e_ms"] = float(t_first_tts - t_start)
    return timings
