"""Real CUDA Substrate composing 4 backend adapters (D-14).

Replaces `substrate/_stub.py` for Phase 2+ gate runners. The class is the
seam between substrate-agnostic gate code and concrete CUDA backends:

- vLLM (Qwen3-4B AWQ-Int4) over OpenAI HTTP — VLLMClient
- faster-whisper (distil-whisper-large-v3 INT8) in-process — FasterWhisperEngine
- Chatterbox-Turbo (resemble-ai upstream) over HTTP — ChatterboxClient
- Kokoro-FastAPI (remsky upstream) over HTTP — KokoroClient

Adapters are private (`self._vllm`, etc.) — gates may not poke through.

Heavy backend imports (vllm, faster_whisper, torch) are NOT performed at
module load. The operator workstation can `from substrate.cuda import
CUDASubstrate` with no CUDA stack installed.
"""

from __future__ import annotations

import logging
import pathlib
import subprocess
from collections.abc import AsyncIterator
from typing import Any

import httpx
import yaml  # type: ignore[import-untyped]

from . import Substrate
from .adapters import ChatterboxClient, FasterWhisperEngine, KokoroClient, VLLMClient
from .types import EnvFingerprint, Grammar, LLMChunk, STTChunk, VoiceRef

logger = logging.getLogger(__name__)

_DEFAULT_IMAGES_LOCK = pathlib.Path("bench/images.lock.yaml")
_DEFAULT_MODELS_LOCK = pathlib.Path("bench/models.lock.yaml")


class CUDASubstrate(Substrate):
    """CUDA-rail Substrate (RunPod H100). Implements the ABC by composition."""

    def __init__(
        self,
        *,
        vllm_url: str,
        vllm_model: str,
        whisper_model_dir: str,
        chatterbox_url: str,
        kokoro_url: str,
        images_lockfile: pathlib.Path = _DEFAULT_IMAGES_LOCK,
        models_lockfile: pathlib.Path = _DEFAULT_MODELS_LOCK,
    ) -> None:
        self._vllm = VLLMClient(base_url=vllm_url, model=vllm_model)
        self._stt = FasterWhisperEngine(model_dir=whisper_model_dir)
        self._chatterbox = ChatterboxClient(base_url=chatterbox_url)
        self._kokoro = KokoroClient(base_url=kokoro_url)
        self._loaded: dict[str, bool] = {"stt": False, "llm": False, "tts": False}
        self._images_lockfile = images_lockfile
        self._models_lockfile = models_lockfile
        self._vllm_url = vllm_url

    # ---- load_* --------------------------------------------------------

    async def load_stt(self) -> None:
        await self._stt.load()
        # FasterWhisperEngine.load() never throws; check via health().
        ok = await self._stt.health()
        self._loaded["stt"] = ok
        if not ok:
            logger.warning("[cuda-substrate] STT load failed; transcribe will yield nothing")

    async def load_llm(self) -> None:
        ok = await self._vllm.health()
        self._loaded["llm"] = ok
        if not ok:
            logger.warning(
                "[cuda-substrate] LLM (vllm) health check failed; generate will yield nothing"
            )

    async def load_tts(self) -> None:
        cb_ok = await self._chatterbox.health()
        kk_ok = await self._kokoro.health()
        ok = cb_ok or kk_ok
        self._loaded["tts"] = ok
        if not ok:
            logger.warning(
                "[cuda-substrate] TTS load failed: both Chatterbox and Kokoro unhealthy "
                "(DR-27 fallback exhausted); synthesize will yield nothing"
            )

    # ---- streaming methods --------------------------------------------

    async def transcribe(
        self,
        audio: AsyncIterator[bytes],
        *,
        sample_rate: int,
    ) -> AsyncIterator[STTChunk]:
        async for chunk in self._stt.transcribe(audio, sample_rate=sample_rate):
            yield chunk

    async def generate(
        self,
        prompt: str,
        *,
        grammar: Grammar | None = None,
        max_tokens: int,
    ) -> AsyncIterator[LLMChunk]:
        async for chunk in self._vllm.generate(prompt, grammar=grammar, max_tokens=max_tokens):
            yield chunk

    async def synthesize(
        self,
        text: str,
        *,
        voice: VoiceRef | None = None,
        engine_hint: str | None = None,
    ) -> AsyncIterator[bytes]:
        """Stream PCM audio.

        engine_hint:
          - "chatterbox" → route to Chatterbox even if its health check fails
            (logs WARNING; no DR-27 fallback). Used by G7 to measure both
            engines explicitly.
          - "kokoro" → same, routed to Kokoro.
          - None → preserve DR-27 behavior (Chatterbox first; Kokoro fallback
            on unhealthy Chatterbox).
        """
        tts: ChatterboxClient | KokoroClient
        if engine_hint == "chatterbox":
            if not await self._chatterbox.health():
                logger.warning(
                    "[cuda-substrate] Chatterbox unhealthy but engine_hint='chatterbox' "
                    "— attempting render anyway (G7 explicit-engine path)"
                )
            tts = self._chatterbox
        elif engine_hint == "kokoro":
            if not await self._kokoro.health():
                logger.warning(
                    "[cuda-substrate] Kokoro unhealthy but engine_hint='kokoro' "
                    "— attempting render anyway (G7 explicit-engine path)"
                )
            tts = self._kokoro
        elif engine_hint is None:
            # DR-27 fallback: prefer Chatterbox; switch to Kokoro if unhealthy.
            if await self._chatterbox.health():
                tts = self._chatterbox
            else:
                logger.warning(
                    "[cuda-substrate] Chatterbox unhealthy; falling back to Kokoro (DR-27)"
                )
                tts = self._kokoro
        else:
            raise ValueError(
                f"engine_hint must be 'chatterbox', 'kokoro', or None; got {engine_hint!r}"
            )
        async for chunk in tts.synthesize(text, voice):
            yield chunk

    # ---- env_fingerprint ----------------------------------------------

    def env_fingerprint(self) -> EnvFingerprint:
        from harness import env_fingerprint as efp

        image_digest = self._lookup_image_digest()
        model_shas = self._lookup_model_shas()
        gpu_sku, gpu_count = self._query_gpu()
        cuda_version, pytorch_version = self._query_torch_versions()
        vllm_version = self._query_vllm_version()

        return efp.capture(
            substrate="cuda",
            image_digest=image_digest,
            model_shas=model_shas,
            gpu_sku=gpu_sku,
            gpu_count=gpu_count,
            cuda_version=cuda_version,
            vllm_version=vllm_version,
            pytorch_version=pytorch_version,
        )

    # ---- env_fingerprint helpers --------------------------------------

    def _lookup_image_digest(self) -> str:
        # DEV-1021 fix: prefer the deployed image digest injected by
        # orchestration.runpod_h100.provision() as RBOX_IMAGE_DIGEST. The
        # lockfile path tracks the *base* vllm/vllm-openai image whose digest
        # we never resolve (we deploy the derived rbox-pod image instead), so
        # the env-var path is the source of truth at runtime. Lockfile read
        # is preserved as fallback for substrates that don't go through
        # provision() (e.g., local dev, future ROCm cohort that keys differently).
        import os

        env_digest = os.environ.get("RBOX_IMAGE_DIGEST")
        if env_digest:
            # Accept either bare "sha256:..." or full "registry/repo@sha256:..."
            if "@" in env_digest:
                return env_digest.split("@", 1)[1]
            return env_digest
        try:
            data = yaml.safe_load(self._images_lockfile.read_text()) or {}
        except Exception as e:
            logger.warning(f"[cuda-substrate] images lockfile read failed: {type(e).__name__}")
            return "unknown"
        for entry in data.get("images") or []:
            if (
                entry.get("provider") == "runpod"
                and entry.get("rail") == "cuda"
                and entry.get("image_ref") == "vllm/vllm-openai"
            ):
                # `pending` is a real, expected value pre-cloud-resolution.
                return str(entry.get("digest") or "unknown")
        return "unknown"

    def _lookup_model_shas(self) -> dict[str, str]:
        try:
            data = yaml.safe_load(self._models_lockfile.read_text()) or {}
        except Exception as e:
            logger.warning(f"[cuda-substrate] models lockfile read failed: {type(e).__name__}")
            return {}
        out: dict[str, str] = {}
        for entry in data.get("models") or []:
            name = entry.get("name")
            rev = entry.get("revision")
            if name:
                out[name] = str(rev or "pending")
        return out

    @staticmethod
    def _query_gpu() -> tuple[str, int]:
        try:
            result = subprocess.run(
                ["nvidia-smi", "--query-gpu=name", "--format=csv,noheader,nounits"],  # noqa: S607
                capture_output=True,
                text=True,
                check=False,
                timeout=5,
            )
            if result.returncode != 0:
                return ("unknown", 0)
            lines = [ln.strip() for ln in result.stdout.splitlines() if ln.strip()]
            if not lines:
                return ("unknown", 0)
            return (lines[0], len(lines))
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return ("unknown", 0)
        except Exception as e:
            logger.warning(f"[cuda-substrate] nvidia-smi probe failed: {type(e).__name__}")
            return ("unknown", 0)

    @staticmethod
    def _query_torch_versions() -> tuple[str | None, str | None]:
        try:
            import torch  # type: ignore[import-not-found]

            return (getattr(torch.version, "cuda", None), getattr(torch, "__version__", None))
        except Exception:
            return (None, None)

    def _query_vllm_version(self) -> str | None:
        url = f"{self._vllm_url.rstrip('/')}/version"
        try:
            with httpx.Client(timeout=2.0) as client:
                resp = client.get(url)
            if resp.status_code != 200:
                return None
            data: Any = resp.json()
            if isinstance(data, dict):
                return str(data.get("version") or data.get("vllm_version") or "")
            return str(data)
        except Exception:
            return None
