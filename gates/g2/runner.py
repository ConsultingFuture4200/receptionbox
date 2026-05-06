"""G2 STT WER gate runner.

Feeds G.711 clips (corpus_g711, sample_rate=8000) through the substrate's
streaming `transcribe()`, accumulates the final hypothesis, and computes
WER vs the hand-curated reference transcript using `jiwer.wer` with the
Whisper basic normalizer applied to both ref + hyp.

Stratum (`neutral` | `stressed`) is recorded per-row so the synthesis
report can split medians per FR-R8 (<12% / <18%) in Phase 4.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import pathlib
import sys
from collections.abc import AsyncIterator

import jiwer
from whisper_normalizer.basic import BasicTextNormalizer

from gates._runner_base import GateRunner
from harness.results import GateResult
from substrate import Substrate

logger = logging.getLogger(__name__)
_NORM = BasicTextNormalizer()


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


class G2Runner(GateRunner):
    """G2 STT WER runner. One GateResult per clip with metrics={wer, stratum, ...}."""

    def __init__(self, *, substrate: Substrate, **kw) -> None:
        super().__init__(substrate=substrate, gate="g2", **kw)

    async def run_one(self, asset: dict) -> GateResult:
        audio_path = pathlib.Path(asset["path"])
        ref_path = pathlib.Path(asset.get("transcript_path") or audio_path.with_suffix(".txt"))
        try:
            ref_text = ref_path.read_text().strip()  # noqa: ASYNC240
            audio_iter = _stream_audio_file(audio_path)
            hyp_parts: list[str] = []
            async for chunk in self.substrate.transcribe(audio_iter, sample_rate=8000):
                if chunk.is_final:
                    hyp_parts.append(chunk.text)
            hyp_text = " ".join(hyp_parts)
            ref_n = _NORM(ref_text)
            hyp_n = _NORM(hyp_text)
            wer = jiwer.wer(ref_n, hyp_n) if ref_n else float("nan")
            stratum = (
                "stressed"
                if asset.get("adversity_level", "neutral") not in ("neutral", "")
                else "neutral"
            )
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
                "wer": wer,
                "ref_text_normalized": ref_n,
                "hyp_text_normalized": hyp_n,
                "stratum": stratum,
            },
        )


def _build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="gates.g2.runner")
    p.add_argument("--gate", default="g2", choices=["g2"])
    p.add_argument("--n-calls", type=int, default=None)
    p.add_argument("--strata", default=None)
    p.add_argument("--corpus", default="corpus_g711")
    p.add_argument("--vllm-url", default="http://127.0.0.1:8000")
    p.add_argument("--vllm-model", default="Qwen/Qwen3-4B")
    p.add_argument("--whisper-dir", default="/models/distil_whisper_large_v3_int8")
    p.add_argument("--chatterbox-url", default="http://127.0.0.1:8004")
    p.add_argument("--kokoro-url", default="http://127.0.0.1:8005")
    p.add_argument("--results-dir", type=pathlib.Path, default=pathlib.Path("results"))
    return p


def _select_assets(args: argparse.Namespace, assets: list[dict]) -> list[dict]:
    """Strata-aware selection. Plan 02-04 fills the strata file; passthrough until then."""
    n_default = args.n_calls or 10
    if args.strata:
        strata_path = pathlib.Path(args.strata)
        if not strata_path.exists():
            logger.warning(
                f"[g2] strata file not found at {strata_path}; "
                f"defaulting to first {n_default} assets"
            )
        else:
            logger.info(f"[g2] strata file {strata_path} present; passthrough until Plan 02-04")
    return assets[:n_default]


async def main_async(argv: list[str]) -> int:
    from gates.g1.runner import load_assets  # reuse manifest loader
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
    runner = G2Runner(substrate=sub, results_dir=args.results_dir)
    await runner.start()
    results = await runner.run_all(assets)
    ok = sum(1 for r in results if r.status == "ok")
    logger.info(f"[g2] {ok}/{len(results)} ok; run_id={runner.run_id}")
    print(f"[g2] {ok}/{len(results)} ok; run_id={runner.run_id}")
    return 0 if ok == len(results) else 1


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    return asyncio.run(main_async(sys.argv[1:]))


if __name__ == "__main__":
    sys.exit(main())
