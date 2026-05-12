"""G3 turn-detection gate runner.

Feeds hesitation clips through the substrate's streaming `transcribe()` and
captures the final STT chunk's `end_ms` as the detected end-of-turn
timestamp. For each clip, the runner emits ONE result row per VAD
threshold in `threshold_ms_list` (default 12 thresholds spanning 400-1500
ms per SM-69), with `metrics["false_positive"] = (threshold_ms <
gt_endpoint_ms)` — i.e., a detector configured with a silence threshold
shorter than the human-marked true end-of-turn would fire prematurely
mid-utterance (FR-R12).

This is a single-transcription-per-asset sweep: the substrate runs once,
and 12 result rows are materialized from that one pass with different
threshold tags. Phase 4 synthesis can refine the FP semantics
(e.g., simulate detector firing at last_silence + threshold) without
re-spending H100-pod minutes.

NOTE on AgentSession integration: the LiveKit AgentSession path emits a
real semantic end-of-turn timestamp via the turn-detector plugin, but the
shim path (used in tests + workstation dev) does not. We therefore drive
the substrate's transcribe stream directly here and use the last STT
chunk's end_ms as the detected endpoint. A follow-up plan can wire
AgentSession's `on_user_speech_committed` event when running on the H100
pod with livekit-agents installed.
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


# SM-69 sweep: 400-1500 ms in 100 ms steps (12 thresholds).
DEFAULT_THRESHOLDS_MS: tuple[int, ...] = (
    400,
    500,
    600,
    700,
    800,
    900,
    1000,
    1100,
    1200,
    1300,
    1400,
    1500,
)


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
    """G3 turn-detection runner.

    For each (asset, threshold_ms) pair, emits one result row carrying the
    substrate-derived detected_endpoint_ms, gt_endpoint_ms, and a
    threshold-aware false_positive flag. The substrate runs ONCE per
    asset; rows are materialized per threshold from that single pass.
    """

    def __init__(
        self,
        *,
        substrate: Substrate,
        threshold_ms_list: list[int] | tuple[int, ...] | None = None,
        vad_threshold_ms: int = 800,
        **kw,
    ) -> None:
        super().__init__(substrate=substrate, gate="g3", **kw)
        self._vad_threshold_ms = vad_threshold_ms
        thresholds = (
            list(threshold_ms_list)
            if threshold_ms_list is not None
            else list(DEFAULT_THRESHOLDS_MS)
        )
        if not thresholds:
            raise ValueError("threshold_ms_list must contain at least one value")
        self._threshold_ms_list = thresholds

    async def _transcribe_asset(self, asset: dict) -> tuple[float, str | None, str | None]:
        """Return (detected_endpoint_ms, error_kind, error_msg).

        On success, error_kind/error_msg are None. On failure, they're set
        and detected_endpoint_ms is 0.0.
        """
        audio_path = pathlib.Path(asset["path"])
        try:
            audio_iter = _stream_audio_file(audio_path)
            last_end_ms: float | None = None
            async for chunk in self.substrate.transcribe(audio_iter, sample_rate=16000):
                if chunk.end_ms is not None:
                    last_end_ms = float(chunk.end_ms)
            return float(last_end_ms or 0.0), None, None
        except Exception as e:
            return 0.0, type(e).__name__, str(e)[:500]

    async def run_one(self, asset: dict) -> GateResult:
        """Emit ONE base result for a single (asset, first-threshold) pair.

        This method exists for backward-compat with the GateRunner ABC
        (which expects run_one → one GateResult). The actual threshold
        sweep happens in `run_all` below: this base result is expanded
        into N rows there. Tests that call run_one directly get a single
        row at the first configured threshold.
        """
        detected_endpoint_ms, error_kind, error_msg = await self._transcribe_asset(asset)
        if error_kind is not None:
            return self.build_result(
                asset_id=str(asset["asset_id"]),
                status="error",
                error_kind=error_kind,
                error_msg=error_msg,
            )
        threshold_ms = self._threshold_ms_list[0]
        return self._build_threshold_row(
            asset=asset,
            detected_endpoint_ms=detected_endpoint_ms,
            threshold_ms=threshold_ms,
        )

    def _build_threshold_row(
        self,
        *,
        asset: dict,
        detected_endpoint_ms: float,
        threshold_ms: int,
    ) -> GateResult:
        gt_endpoint_ms = float(asset.get("gt_endpoint_ms") or 0.0)
        pattern = asset.get("hesitation_pattern", "unknown")
        # Threshold-aware FP proxy: a VAD configured to fire after `threshold`
        # ms of silence will fire prematurely (false positive) if its threshold
        # is shorter than the human-marked true end-of-turn. Phase 4 synthesis
        # may refine to detected_endpoint+threshold < gt semantics.
        false_positive = bool(threshold_ms < gt_endpoint_ms)
        return self.build_result(
            asset_id=f"{asset['asset_id']}_t{threshold_ms}",
            status="ok",
            metrics={
                "detected_endpoint_ms": detected_endpoint_ms,
                "gt_endpoint_ms": gt_endpoint_ms,
                "threshold_ms": int(threshold_ms),
                "false_positive": false_positive,
                "hesitation_pattern": pattern,
                "vad_threshold_ms": self._vad_threshold_ms,
            },
        )

    async def run_all(self, assets: list) -> list[GateResult]:
        """Override base: one substrate pass per asset → N rows per asset.

        Emits N = len(self._threshold_ms_list) rows per healthy asset.
        Error rows (substrate.transcribe raised) emit a SINGLE error row
        per asset — threshold sweep is meaningless without a detected
        endpoint.
        """
        sem = asyncio.Semaphore(self.concurrency)
        results: list[GateResult] = []
        results_lock = asyncio.Lock()

        async def _wrap(asset: dict) -> None:
            async with sem:
                detected_endpoint_ms, error_kind, error_msg = await self._transcribe_asset(asset)
                rows: list[GateResult]
                if error_kind is not None:
                    rows = [
                        self.build_result(
                            asset_id=str(asset["asset_id"]),
                            status="error",
                            error_kind=error_kind,
                            error_msg=error_msg,
                        )
                    ]
                else:
                    rows = [
                        self._build_threshold_row(
                            asset=asset,
                            detected_endpoint_ms=detected_endpoint_ms,
                            threshold_ms=t,
                        )
                        for t in self._threshold_ms_list
                    ]
                for r in rows:
                    self.emit(r)
                async with results_lock:
                    results.extend(rows)

        await asyncio.gather(*[_wrap(a) for a in assets])
        return results


def _build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="gates.g3.runner")
    p.add_argument("--gate", default="g3", choices=["g3"])
    p.add_argument("--n-calls", type=int, default=None)
    p.add_argument("--strata", default=None)
    p.add_argument("--corpus", default="corpus_hesitation")
    p.add_argument("--vad-threshold-ms", type=int, default=800)
    p.add_argument(
        "--threshold-ms-list",
        default=",".join(str(t) for t in DEFAULT_THRESHOLDS_MS),
        help=(
            "Comma-separated VAD threshold sweep (ms). "
            "Default: SM-69 12-threshold sweep 400..1500 step 100."
        ),
    )
    p.add_argument("--vllm-url", default="http://127.0.0.1:8000")
    p.add_argument("--vllm-model", default="Qwen/Qwen3-4B")
    p.add_argument("--whisper-dir", default="/models/distil_whisper_large_v3_int8")
    p.add_argument("--chatterbox-url", default="http://127.0.0.1:8004")
    p.add_argument("--kokoro-url", default="http://127.0.0.1:8005")
    p.add_argument("--results-dir", type=pathlib.Path, default=pathlib.Path("results"))
    return p


def _select_assets(args: argparse.Namespace, assets: list[dict]) -> list[dict]:
    """Strata-aware selection per D-27. With --strata pointing at a populated
    config/sanity_strata.yaml, picks rows whose `asset_id` appears under
    `strata.g3.assets`. Falls back to first N (default 10) assets when the
    strata file is absent or empty.
    """
    n_default = args.n_calls or 10
    if args.strata:
        strata_path = pathlib.Path(args.strata)
        if not strata_path.exists():
            logger.warning(
                f"[g3] strata file not found at {strata_path}; "
                f"defaulting to first {n_default} assets"
            )
            return assets[:n_default]
        import yaml

        data = yaml.safe_load(strata_path.read_text())
        wanted = set(data.get("strata", {}).get("g3", {}).get("assets", []))
        if not wanted:
            logger.warning(
                f"[g3] strata file {strata_path} has no g3 assets; "
                f"defaulting to first {n_default} assets"
            )
            return assets[:n_default]
        selected = [a for a in assets if a["asset_id"] in wanted]
        missing = wanted - {a["asset_id"] for a in selected}
        if missing:
            logger.warning(f"[g3] strata asset_ids not found in manifest: {sorted(missing)}")
        return selected
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
    threshold_ms_list = [int(x) for x in args.threshold_ms_list.split(",") if x.strip()]
    runner = G3Runner(
        substrate=sub,
        vad_threshold_ms=args.vad_threshold_ms,
        threshold_ms_list=threshold_ms_list,
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
