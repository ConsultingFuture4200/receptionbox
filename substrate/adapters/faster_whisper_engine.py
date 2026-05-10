"""faster-whisper INT8 wrapper for CUDA + ROCm STT.

faster-whisper is the in-process CTranslate2 backend (CLAUDE.md §4.1).
Heavy imports (`faster_whisper`, `numpy`) are deferred inside method
bodies so this module imports cleanly on the operator workstation with
no CUDA / no torch / no faster_whisper installed.

Error contract (T-02-01-03): on any failure, log WARNING + yield nothing.
NEVER log audio bytes or transcripts (T-02-01-02).
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator

from ..paths import resolve_model_dir
from ..types import STTChunk

logger = logging.getLogger(__name__)


class FasterWhisperEngine:
    def __init__(
        self,
        model_dir: str,
        *,
        compute_type: str = "int8",
        device: str = "cuda",
    ) -> None:
        # `model_dir` may be either an on-disk path (the entrypoint pre-resolves
        # via `/models/.bootstrap_index.json` and passes the real path) OR the
        # logical lockfile name (gate-runner defaults; e.g.
        # `/models/distil_whisper_large_v3_int8`). resolve_model_dir is a
        # no-op for real directories and consults the bootstrap index
        # otherwise. See substrate/paths.py.
        self.model_dir = resolve_model_dir(model_dir)
        self.compute_type = compute_type
        self.device = device
        self._model = None  # populated by load()

    async def health(self) -> bool:
        """Try to instantiate the model in a thread; False on any error."""
        try:
            await self.load()
        except Exception as e:
            logger.warning(f"[faster-whisper] health check failed: {type(e).__name__}: {e}")
            return False
        return self._model is not None

    async def load(self) -> None:
        """Instantiate faster-whisper WhisperModel. Idempotent."""
        if self._model is not None:
            return

        def _instantiate():
            try:
                from faster_whisper import WhisperModel  # type: ignore[import-not-found]
            except Exception as e:
                logger.warning(
                    f"[faster-whisper] import failed (engine unavailable on this host): "
                    f"{type(e).__name__}"
                )
                return None
            try:
                return WhisperModel(
                    self.model_dir,
                    device=self.device,
                    compute_type=self.compute_type,
                )
            except Exception as e:
                logger.warning(
                    f"[faster-whisper] model load failed for {self.model_dir!r}: {type(e).__name__}"
                )
                return None

        self._model = await asyncio.to_thread(_instantiate)

    async def transcribe(
        self,
        audio: AsyncIterator[bytes],
        *,
        sample_rate: int,
    ) -> AsyncIterator[STTChunk]:
        """Drain `audio` to a numpy float32 array, run model.transcribe, yield STTChunks."""
        # Lazy-load on first transcribe.
        if self._model is None:
            await self.load()
        if self._model is None:
            logger.warning("[faster-whisper] model unavailable; yielding nothing")
            return

        # Drain bytes.
        try:
            buf = bytearray()
            async for chunk in audio:
                if chunk:
                    buf.extend(chunk)
        except Exception as e:
            logger.warning(f"[faster-whisper] audio iterator failed: {type(e).__name__}")
            return

        try:
            import numpy as np  # type: ignore[import-not-found]
        except Exception as e:
            logger.warning(f"[faster-whisper] numpy unavailable: {type(e).__name__}")
            return

        if len(buf) < 2:
            logger.warning("[faster-whisper] empty audio buffer")
            return

        # Codec-aware decode (DEV-1083). Two byte-stream shapes are supported:
        #
        #  1. Raw int16 mono PCM at the caller-declared `sample_rate`. Legacy
        #     path; preserved for backward compatibility (unit-test paths and
        #     any future raw-PCM caller).
        #  2. A complete WAV file (RIFF container) — what gates/g2/runner.py
        #     and substrate/livekit_pipeline.py actually stream today. Both
        #     PCM-int16 (fmt code 1) and G.711 μ-law (fmt code 7) are handled
        #     via soundfile, which transparently decompands μ-law to int16
        #     and exposes the authoritative header sample rate. The
        #     caller-declared `sample_rate` is overridden by the WAV header
        #     because the header is the source of truth for what's in the
        #     bytes; mismatched declarations are logged at INFO once.
        #
        # Without this branch, μ-law codewords are reinterpreted as int16
        # samples, the resampler upsamples noise to 16 kHz, and Whisper
        # hallucinates short coherent English fillers ("thank you", "i don't
        # know") on what it perceives as near-silent or noisy input — the
        # exact failure mode reported in DEV-1083.
        try:
            wav_bytes = bytes(buf)
            is_riff = (
                len(wav_bytes) >= 12 and wav_bytes[:4] == b"RIFF" and wav_bytes[8:12] == b"WAVE"
            )
            if is_riff:
                try:
                    import io

                    import soundfile as sf  # type: ignore[import-not-found]
                except Exception as e:
                    logger.warning(
                        f"[faster-whisper] soundfile unavailable for WAV decode: {type(e).__name__}"
                    )
                    return
                try:
                    samples, file_sr = sf.read(
                        io.BytesIO(wav_bytes),
                        dtype="float32",
                        always_2d=False,
                    )
                except Exception as e:
                    logger.warning(f"[faster-whisper] WAV decode failed: {type(e).__name__}")
                    return
                # Force mono.
                if samples.ndim == 2:
                    samples = samples.mean(axis=1)
                arr = np.ascontiguousarray(samples, dtype=np.float32)
                if file_sr != sample_rate:
                    logger.info(
                        f"[faster-whisper] WAV header sample_rate={file_sr} overrides "
                        f"caller-declared sample_rate={sample_rate}"
                    )
                effective_sr = int(file_sr)
            else:
                arr = np.frombuffer(wav_bytes, dtype=np.int16).astype(np.float32) / 32768.0
                effective_sr = int(sample_rate)

            if effective_sr != 16000 and arr.size > 0:
                # Linear resample to 16 kHz (deps-free; deterministic).
                target_n = round(arr.size * 16000 / effective_sr)
                if target_n > 0:
                    src_x = np.linspace(0.0, 1.0, num=arr.size, endpoint=False)
                    dst_x = np.linspace(0.0, 1.0, num=target_n, endpoint=False)
                    arr = np.interp(dst_x, src_x, arr).astype(np.float32)
        except Exception as e:
            logger.warning(f"[faster-whisper] audio prep failed: {type(e).__name__}")
            return

        def _transcribe():
            try:
                segments, _info = self._model.transcribe(  # type: ignore[union-attr]
                    arr,
                    vad_filter=True,
                    beam_size=1,
                    language="en",
                )
                # Materialize generator inside the thread.
                return list(segments)
            except Exception as e:
                logger.warning(f"[faster-whisper] transcribe failed: {type(e).__name__}")
                return None

        segments = await asyncio.to_thread(_transcribe)
        if not segments:
            return

        for seg in segments:
            try:
                yield STTChunk(
                    text=getattr(seg, "text", ""),
                    is_final=True,
                    start_ms=float(getattr(seg, "start", 0.0)) * 1000.0,
                    end_ms=float(getattr(seg, "end", 0.0)) * 1000.0,
                    confidence=getattr(seg, "avg_logprob", None),
                )
            except Exception as e:
                logger.warning(f"[faster-whisper] segment marshal failed: {type(e).__name__}")
                continue
