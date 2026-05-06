"""G3 turn-detection gate runner.

Feeds hesitation clips through the substrate's streaming `transcribe()`,
captures the final STT chunk's `end_ms` as the detected end-of-turn
timestamp, and flags `false_positive = (detected_endpoint_ms < gt_endpoint_ms)`
(early termination is a false positive — FR-R12).

NOTE on AgentSession integration: the LiveKit AgentSession path emits a
real semantic end-of-turn timestamp via the turn-detector plugin, but the
shim path (used in tests + workstation dev) does not. We therefore drive
the substrate's transcribe stream directly here and use the last STT
chunk's end_ms as the detected endpoint. Phase 3 (or a follow-up Plan)
can wire AgentSession's `on_user_speech_committed` event when running on
the H100 pod with livekit-agents installed.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import pathlib
import sys
from collections.abc import AsyncIterator

from gates._runner_base import GateRunner
from harness.results import GateResult
from substrate import Substrate

logger = logging.getLogger(__name__)


async def _stream_audio_file(
    path: pathlib.Path,
    chunk_size: int = 4096,
) -> AsyncIterator[bytes]:
    """Async iterator over `path`'s bytes in `chunk_size`-byte chunks."""
    with path.open("rb") as f:
        while True:
            buf = f.read(chunk_size)
            if not buf:
                return
            yield buf


class G3Runner(GateRunner):
    """G3 turn-detection runner. Records detected vs gt endpoint + FP flag."""

    def __init__(
        self,
        *,
        substrate: Substrate,
        vad_threshold_ms: int = 800,
        **kw,
    ) -> None:
        super().__init__(substrate=substrate, gate="g3", **kw)
        self._vad_threshold_ms = vad_threshold_ms

    async def run_one(self, asset: dict) -> GateResult:
        audio_path = pathlib.Path(asset["path"])
        gt_endpoint_ms = float(asset.get("gt_endpoint_ms") or 0.0)
        pattern = asset.get("hesitation_pattern", "unknown")
        try:
            audio_iter = _stream_audio_file(audio_path)
            last_end_ms: float | None = None
            async for chunk in self.substrate.transcribe(audio_iter, sample_rate=16000):
                if chunk.end_ms is not None:
                    last_end_ms = float(chunk.end_ms)
            detected_endpoint_ms = float(last_end_ms or 0.0)
            false_positive = bool(detected_endpoint_ms < gt_endpoint_ms)
        except Exception as e:
            return self.build_result(
                asset_id=asset["asset_id"],
                status="error",
                error_kind=type(e).__name__,
                error_msg=str(e)[:500],
            )
        return self.build_result(
            asset_id=asset["asset_id"],
            status="ok",
            metrics={
                "detected_endpoint_ms": detected_endpoint_ms,
                "gt_endpoint_ms": gt_endpoint_ms,
                "false_positive": false_positive,
                "hesitation_pattern": pattern,
                "vad_threshold_ms": self._vad_threshold_ms,
            },
        )


def _build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="gates.g3.runner")
    p.add_argument("--gate", default="g3", choices=["g3"])
    p.add_argument("--n-calls", type=int, default=None)
    p.add_argument("--strata", default=None)
    p.add_argument("--corpus", default="corpus_hesitation")
    p.add_argument("--vad-threshold-ms", type=int, default=800)
    p.add_argument("--vllm-url", default="http://127.0.0.1:8000")
    p.add_argument("--vllm-model", default="Qwen/Qwen3-4B")
    p.add_argument("--whisper-dir", default="/models/distil_whisper_large_v3_int8")
    p.add_argument("--chatterbox-url", default="http://127.0.0.1:8004")
    p.add_argument("--kokoro-url", default="http://127.0.0.1:8005")
    p.add_argument("--results-dir", type=pathlib.Path, default=pathlib.Path("results"))
    return p


def _select_assets(args: argparse.Namespace, assets: list[dict]) -> list[dict]:
    """Strata-aware selection. Plan 02-04 fills the strata file."""
    n_default = args.n_calls or 10
    if args.strata:
        strata_path = pathlib.Path(args.strata)
        if not strata_path.exists():
            logger.warning(
                f"[g3] strata file not found at {strata_path}; "
                f"defaulting to first {n_default} assets"
            )
        else:
            logger.info(f"[g3] strata file {strata_path} present; passthrough until Plan 02-04")
    return assets[:n_default]


async def main_async(argv: list[str]) -> int:
    from gates.g1.runner import load_assets
    from substrate.cuda import CUDASubstrate

    args = _build_arg_parser().parse_args(argv)
    sub = CUDASubstrate(
        vllm_url=args.vllm_url,
        vllm_model=args.vllm_model,
        whisper_model_dir=args.whisper_dir,
        chatterbox_url=args.chatterbox_url,
        kokoro_url=args.kokoro_url,
    )
    assets = _select_assets(args, load_assets(args.corpus))
    runner = G3Runner(
        substrate=sub,
        vad_threshold_ms=args.vad_threshold_ms,
        results_dir=args.results_dir,
    )
    await runner.start()
    results = await runner.run_all(assets)
    ok = sum(1 for r in results if r.status == "ok")
    logger.info(f"[g3] {ok}/{len(results)} ok; run_id={runner.run_id}")
    print(f"[g3] {ok}/{len(results)} ok; run_id={runner.run_id}")
    return 0 if ok == len(results) else 1


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    return asyncio.run(main_async(sys.argv[1:]))


if __name__ == "__main__":
    sys.exit(main())
