"""Kokoro-FastAPI HTTP client (CUDA upstream).

CUDA path uses `remsky/Kokoro-FastAPI` (upstream). The ROCm-side
`moritzchow/Kokoro-FastAPI-ROCm` fork is Phase 3 only.

Streams raw PCM bytes from `POST {base_url}/v1/audio/speech` per the
OpenAI-compatible audio endpoint shape Kokoro-FastAPI exposes.
Default voice = `af_bella`.

Errors degrade silently (T-02-01-03): log WARNING + yield nothing.
NEVER log payload (T-02-01-02).
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator

import httpx

from ..types import VoiceRef

logger = logging.getLogger(__name__)


class KokoroClient:
    def __init__(self, base_url: str, *, request_timeout_s: float = 30.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.request_timeout_s = request_timeout_s

    async def health(self) -> bool:
        url = f"{self.base_url}/health"
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(url)
            return getattr(resp, "status_code", 0) == 200
        except Exception as e:
            logger.warning(f"[kokoro] health check failed for {url}: {type(e).__name__}")
            return False

    async def synthesize(
        self,
        text: str,
        voice: VoiceRef | None,
    ) -> AsyncIterator[bytes]:
        """Stream PCM bytes; yield nothing on error."""
        url = f"{self.base_url}/v1/audio/speech"
        body = {
            "input": text,
            "voice": voice.name if voice else "af_bella",
            "response_format": "pcm",
            "stream": True,
        }
        try:
            async with httpx.AsyncClient(timeout=self.request_timeout_s) as client:
                response = client.stream("POST", url, json=body)
                async with response as resp:
                    status = getattr(resp, "status_code", 0)
                    if status != 200:
                        logger.warning(f"[kokoro] {url} returned status {status}")
                        return
                    async for chunk in resp.aiter_bytes(4096):
                        if chunk:
                            yield chunk
        except Exception as e:
            logger.warning(f"[kokoro] stream to {url} failed: {type(e).__name__}")
            return
