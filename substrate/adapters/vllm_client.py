"""vLLM async streaming HTTP client (CUDA + ROCm both speak the same OpenAI API).

Talks to a vLLM `vllm/vllm-openai` pod over HTTP — does NOT import the `vllm`
Python package. The pod is the model server; the adapter is the wire format.

When `grammar` is provided, request includes `guided_json` (or `guided_regex`
for regex-shaped input) plus `guided_decoding_backend: xgrammar` per
CLAUDE.md §3.1. xgrammar is the default structured-output backend in
vLLM 0.10+.

Error contract (mandatory): on any HTTP / connection / parse failure, log
WARNING (URL + status only — never the payload, T-02-01-02), set
`self.last_error`, and yield NOTHING. The caller's substrate maps an empty
iterator to `status='error'` in GateResult.
"""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator

import httpx

from ..types import Grammar, LLMChunk

logger = logging.getLogger(__name__)


class VLLMClient:
    """Async streaming client for a vLLM `/v1/completions` endpoint."""

    def __init__(
        self,
        base_url: str,
        model: str,
        *,
        request_timeout_s: float = 60.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.request_timeout_s = request_timeout_s
        self.last_error: str | None = None

    async def health(self) -> bool:
        """GET {base_url}/health — True iff 200, False on any error.

        Adapters MUST NOT raise (T-02-01-03).
        """
        url = f"{self.base_url}/health"
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(url)
            return getattr(resp, "status_code", 0) == 200
        except Exception as e:
            logger.warning(f"[vllm] health check failed for {url}: {type(e).__name__}")
            return False

    async def generate(
        self,
        prompt: str,
        *,
        grammar: Grammar | None = None,
        max_tokens: int,
    ) -> AsyncIterator[LLMChunk]:
        """Stream LLMChunks from vLLM /v1/completions.

        Empty iterator on any backend failure; `self.last_error` populated.
        """
        url = f"{self.base_url}/v1/completions"
        body: dict = {
            "model": self.model,
            "prompt": prompt,
            "max_tokens": max_tokens,
            "stream": True,
            "n": 1,
        }
        if grammar is not None:
            body["guided_decoding_backend"] = "xgrammar"
            if isinstance(grammar, dict):
                body["guided_json"] = grammar
            elif isinstance(grammar, str) and grammar.startswith("^"):
                body["guided_regex"] = grammar
            else:
                # JSON Schema string — best interpreted as guided_json.
                try:
                    body["guided_json"] = json.loads(grammar)
                except (ValueError, TypeError):
                    body["guided_regex"] = grammar

        try:
            async with httpx.AsyncClient(timeout=self.request_timeout_s) as client:
                response = client.stream("POST", url, json=body)
                async with response as resp:
                    status = getattr(resp, "status_code", 0)
                    if status != 200:
                        msg = f"[vllm] {url} returned status {status}"
                        logger.warning(msg)
                        self.last_error = msg
                        return
                    async for line in resp.aiter_lines():
                        chunk = self._parse_sse_line(line)
                        if chunk is not None:
                            yield chunk
        except Exception as e:
            msg = f"{type(e).__name__}: {e}"
            logger.warning(f"[vllm] stream to {url} failed: {type(e).__name__}")
            self.last_error = msg
            return

    @staticmethod
    def _parse_sse_line(line: str) -> LLMChunk | None:
        """Parse one OpenAI-style SSE line. Returns None on terminator/blank."""
        if not line:
            return None
        if not line.startswith("data:"):
            return None
        payload = line[len("data:") :].strip()
        if payload == "[DONE]" or not payload:
            return None
        try:
            obj = json.loads(payload)
        except json.JSONDecodeError:
            return None
        choices = obj.get("choices") or []
        if not choices:
            return None
        choice = choices[0]
        text = choice.get("text", "")
        finish = choice.get("finish_reason")
        if finish not in (None, "length", "stop", "grammar"):
            finish = None
        return LLMChunk(text=text, finish_reason=finish)
