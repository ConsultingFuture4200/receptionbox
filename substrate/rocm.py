"""Real ROCm Substrate composing 4 backend adapters (D-14, Phase 3 Plan 03-01).

Mirrors substrate/cuda.py:CUDASubstrate line-for-line with the ROCm-specific
deviations called out in 03-01-PLAN.md Task 1:

- env_fingerprint(substrate="rocm")
- _query_gpu() shells out to `rocm-smi --showproductname --json` (NOT nvidia-smi)
- synthesize() reads `tts.primary` from config/sanity_strata.yaml at call time
  (D-37: Day-1 kill-switch flips this row from "chatterbox" to "kokoro")
- _query_torch_versions() returns (rocm_version, pytorch_version) by parsing
  torch.version.hip; on workstation (no torch) returns ("unknown", "unknown")
- _lookup_image_digest() reads RBOX_IMAGE_DIGEST env first (DEV-1021), falls
  back to bench/images.lock.yaml entry where image_ref contains "rbox-pod-rocm"
  (preferred) or "rocm/vllm" (base image)

Adapters are the SAME 4 as CUDASubstrate (VLLMClient, FasterWhisperEngine,
ChatterboxClient, KokoroClient) — vLLM speaks OpenAI HTTP on both rails;
Chatterbox/Kokoro are HTTP servers; faster-whisper is in-process. The ROCm
side runs them in the rocm/vllm pod with onnxruntime-rocm available for
the ONNX-RT production path (Plan 03-04).

Heavy backend imports (torch, faster_whisper, vllm) are NOT performed at
module load. The operator workstation can `from substrate.rocm import
ROCmSubstrate` with no ROCm stack installed.
"""

from __future__ import annotations

import json
import logging
import os
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
_DEFAULT_SANITY_STRATA = pathlib.Path("config/sanity_strata.yaml")


class ROCmSubstrate(Substrate):
    """ROCm-rail Substrate (Vultr/TensorWave MI300X). Implements the ABC by composition."""

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
        sanity_strata_path: pathlib.Path = _DEFAULT_SANITY_STRATA,
    ) -> None:
        self._vllm = VLLMClient(base_url=vllm_url, model=vllm_model)
        self._stt = FasterWhisperEngine(model_dir=whisper_model_dir)
        self._chatterbox = ChatterboxClient(base_url=chatterbox_url)
        self._kokoro = KokoroClient(base_url=kokoro_url)
        self._loaded: dict[str, bool] = {"stt": False, "llm": False, "tts": False}
        self._images_lockfile = images_lockfile
        self._models_lockfile = models_lockfile
        self._sanity_strata_path = sanity_strata_path
        self._vllm_url = vllm_url

    # ---- load_* --------------------------------------------------------

    async def load_stt(self) -> None:
        await self._stt.load()
        ok = await self._stt.health()
        self._loaded["stt"] = ok
        if not ok:
            logger.warning("[rocm-substrate] STT load failed; transcribe will yield nothing")

    async def load_llm(self) -> None:
        ok = await self._vllm.health()
        self._loaded["llm"] = ok
        if not ok:
            logger.warning(
                "[rocm-substrate] LLM (vllm) health check failed; generate will yield nothing"
            )

    async def load_tts(self) -> None:
        cb_ok = await self._chatterbox.health()
        kk_ok = await self._kokoro.health()
        ok = cb_ok or kk_ok
        self._loaded["tts"] = ok
        if not ok:
            logger.warning(
                "[rocm-substrate] TTS load failed: both Chatterbox and Kokoro unhealthy "
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
    ) -> AsyncIterator[bytes]:
        """D-37: read tts.primary from sanity_strata.yaml at call time.

        - primary=chatterbox (default): try Chatterbox first; DR-27 fallback to Kokoro.
        - primary=kokoro: route DIRECTLY to Kokoro; Chatterbox is only contacted
          as a deeper fallback if Kokoro is also unhealthy.
        """
        primary = self._read_tts_primary()
        if primary == "kokoro":
            if await self._kokoro.health():
                async for b in self._kokoro.synthesize(text, voice=voice):
                    yield b
                return
            logger.warning(
                "[rocm-substrate] kokoro primary unhealthy; DR-27 fallback to chatterbox"
            )
            if await self._chatterbox.health():
                async for b in self._chatterbox.synthesize(text, voice=voice):
                    yield b
            return
        # primary == "chatterbox" (default): same shape as cuda.py:synthesize().
        if await self._chatterbox.health():
            async for b in self._chatterbox.synthesize(text, voice=voice):
                yield b
            return
        logger.warning("[rocm-substrate] chatterbox unhealthy; DR-27 fallback to kokoro")
        async for b in self._kokoro.synthesize(text, voice=voice):
            yield b

    def _read_tts_primary(self) -> str:
        """D-37: read `tts.primary` from sanity_strata.yaml. Default = 'chatterbox'."""
        try:
            with open(self._sanity_strata_path) as f:
                data = yaml.safe_load(f) or {}
        except (FileNotFoundError, OSError):
            return "chatterbox"
        except yaml.YAMLError as e:
            logger.warning(f"[rocm-substrate] sanity_strata.yaml parse failed: {type(e).__name__}")
            return "chatterbox"
        tts = data.get("tts") or {}
        primary = tts.get("primary") or "chatterbox"
        return str(primary)

    # ---- env_fingerprint ----------------------------------------------

    def env_fingerprint(self) -> EnvFingerprint:
        from harness import env_fingerprint as efp

        image_digest = self._lookup_image_digest()
        model_shas = self._lookup_model_shas()
        gpu_sku, gpu_count = self._query_gpu()
        rocm_version, pytorch_version = self._query_torch_versions()
        vllm_version = self._query_vllm_version()

        return efp.capture(
            substrate="rocm",
            image_digest=image_digest,
            model_shas=model_shas,
            gpu_sku=gpu_sku,
            gpu_count=gpu_count,
            rocm_version=rocm_version,
            vllm_version=vllm_version,
            pytorch_version=pytorch_version,
        )

    # ---- env_fingerprint helpers --------------------------------------

    def _lookup_image_digest(self) -> str:
        # DEV-1021 (mirror of substrate/cuda.py:_lookup_image_digest):
        # Prefer the deployed image digest injected by
        # orchestration.vultr_mi300x.provision() as RBOX_IMAGE_DIGEST. The
        # lockfile path tracks rbox-pod-rocm whose digest is pinned by Plan
        # 03-01 Task 5 (operator-driven). The env-var path is the source of
        # truth at runtime; lockfile is the fallback for substrates that
        # don't go through provision() (e.g., local dev).
        env_digest = os.environ.get("RBOX_IMAGE_DIGEST")
        if env_digest:
            # Accept either bare "sha256:..." or full "registry/repo@sha256:..."
            if "@" in env_digest:
                return env_digest.split("@", 1)[1]
            return env_digest
        try:
            data = yaml.safe_load(self._images_lockfile.read_text()) or {}
        except Exception as e:
            logger.warning(f"[rocm-substrate] images lockfile read failed: {type(e).__name__}")
            return "unknown"
        # Prefer rbox-pod-rocm entry (the actual deployed image); fall back to
        # the upstream rocm/vllm base.
        for preferred in ("rbox-pod-rocm", "rocm/vllm"):
            for entry in data.get("images") or []:
                if entry.get("rail") != "rocm":
                    continue
                ref = entry.get("image_ref") or ""
                if preferred in ref:
                    return str(entry.get("digest") or "unknown")
        return "unknown"

    def _lookup_model_shas(self) -> dict[str, str]:
        try:
            data = yaml.safe_load(self._models_lockfile.read_text()) or {}
        except Exception as e:
            logger.warning(f"[rocm-substrate] models lockfile read failed: {type(e).__name__}")
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
        """Shell out to `rocm-smi --showproductname --json`. Schema:
            {"card0": {"Card series": "MI300X", "Card model": "MI300X", ...}, ...}

        Returns (model-or-series-string, card_count). On any error → ("unknown", 0).
        """
        try:
            result = subprocess.run(
                ["rocm-smi", "--showproductname", "--json"],  # noqa: S607
                capture_output=True,
                text=True,
                check=False,
                timeout=5,
            )
            if result.returncode != 0:
                return ("unknown", 0)
            data = json.loads(result.stdout)
            if not isinstance(data, dict) or not data:
                return ("unknown", 0)
            cards = [k for k in data if k.startswith("card")]
            if not cards:
                return ("unknown", 0)
            first = data[cards[0]] or {}
            # rocm-smi uses "Card series" + "Card model"; prefer model, fall
            # back to series, then a generic label.
            label = (
                first.get("Card model")
                or first.get("Card series")
                or first.get("Card SKU")
                or "unknown"
            )
            return (str(label), len(cards))
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return ("unknown", 0)
        except json.JSONDecodeError:
            return ("unknown", 0)
        except Exception as e:
            logger.warning(f"[rocm-substrate] rocm-smi probe failed: {type(e).__name__}")
            return ("unknown", 0)

    @staticmethod
    def _query_torch_versions() -> tuple[str | None, str | None]:
        """Shell out to a child Python so a broken torch install on the
        workstation cannot poison the harness process. Returns
        (rocm_version, pytorch_version).
        """
        try:
            argv = [
                "python",
                "-c",
                "import torch; "
                "print(getattr(torch, '__version__', '') or 'unknown'); "
                "print(getattr(torch.version, 'hip', None) or 'unknown')",
            ]
            result = subprocess.run(  # noqa: S603
                argv,
                capture_output=True,
                text=True,
                check=False,
                timeout=5,
            )
            if result.returncode != 0:
                return (None, None)
            lines = [ln.strip() for ln in result.stdout.splitlines() if ln.strip()]
            if len(lines) < 2:
                return (None, None)
            pytorch_version, rocm_version = lines[0], lines[1]
            return (rocm_version, pytorch_version)
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return (None, None)
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
