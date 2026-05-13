"""G7 TTS A/B gate runner.

For each of 30 stimulus text pairs (assets/tts_pairs/pairs.json), renders
FOUR audio outputs:

  (Chatterbox-cold, Chatterbox-warm, Kokoro-cold, Kokoro-warm) = 120 total

Cold path = first render of that stimulus on that engine in this run.
Warm path = second render (cache hit). Per-render result rows record
first_audio_ms and total_audio_ms; the cold-vs-warm gap is the
operator-visible sanity check that the engine's cache distinction is
real.

Listener A/B preference test (SM-72 target ≥60% prefer cloned) is the
Phase 4 synthesis follow-on — this runner produces the RAW AUDIO + the
first-byte timings; the verdict is computed downstream.

DR-27 note: G7 measures BOTH engines deliberately; we do NOT fall back
on adapter unhealth — instead the per-render row carries status="error"
with the adapter exception. The runner uses
CUDASubstrate.synthesize(..., engine_hint=engine) which bypasses the
DR-27 fallback when an engine is explicitly requested.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import pathlib
import sys
import time
from typing import Any

from gates._runner_base import GateRunner
from harness.results import GateResult
from substrate import Substrate
from substrate.types import VoiceRef

logger = logging.getLogger(__name__)

# Per-engine voice references. Chatterbox uses a cloned voice ref;
# Kokoro uses a neutral default voice from its built-in voice pack.
# These are knob-able via CLI but defaulted here so the runner is
# self-contained when invoked from `make g7`.
_DEFAULT_VOICE_NAMES = {
    "chatterbox": "default",
    "kokoro": "af_bella",
}


def default_voice_ref(engine: str) -> VoiceRef:
    """Return the default VoiceRef for the named engine.

    Voice tuning is deferred to Phase 4 — for G7 we just need a stable,
    repeatable identifier per engine so cold-vs-warm is comparable.
    """
    return VoiceRef(name=_DEFAULT_VOICE_NAMES.get(engine, "default"))


def build_render_assets(stimuli: list[dict]) -> list[dict]:
    """Expand N stimuli into 4N render assets (2 engines x 2 paths).

    Order is deterministic: per engine, ALL stimuli's cold render first,
    then ALL stimuli's warm render. This guarantees the cache is warm by
    the time the warm renders execute, regardless of concurrency=1
    semantics inside `GateRunner.run_all`.
    """
    out: list[dict] = []
    for engine in ("chatterbox", "kokoro"):
        for stim in stimuli:
            out.append({"stimulus": stim, "engine": engine, "path": "cold"})
        for stim in stimuli:
            out.append({"stimulus": stim, "engine": engine, "path": "warm"})
    return out


class G7Runner(GateRunner):
    """G7 TTS A/B runner. One GateResult per render."""

    def __init__(
        self,
        *,
        substrate: Substrate,
        audio_out_dir: pathlib.Path,
        **kw: Any,
    ) -> None:
        super().__init__(substrate=substrate, gate="g7", **kw)
        self.audio_out_dir = pathlib.Path(audio_out_dir)
        self.audio_out_dir.mkdir(parents=True, exist_ok=True)

    async def _render_one(
        self,
        stimulus: dict,
        engine: str,
        path: str,
    ) -> GateResult:
        stimulus_id = stimulus.get("pair_id") or stimulus.get("stimulus_id") or "unknown"
        text = stimulus["text"]
        voice = default_voice_ref(engine)
        audio_path = self.audio_out_dir / f"{engine}_{path}_{stimulus_id}.wav"
        # Truncate any prior bytes so re-runs of the same (engine, path,
        # stimulus_id) produce a clean file.
        audio_path.write_bytes(b"")

        t_start = time.perf_counter()
        first_audio_ms: float | None = None
        n_bytes = 0
        try:
            async for chunk in self.substrate.synthesize(text, voice=voice, engine_hint=engine):
                if first_audio_ms is None:
                    first_audio_ms = (time.perf_counter() - t_start) * 1000.0
                n_bytes += len(chunk)
                with audio_path.open("ab") as f:
                    f.write(chunk)
            total_ms = (time.perf_counter() - t_start) * 1000.0
        except Exception as e:
            return self.build_result(
                asset_id=f"{stimulus_id}_{engine}_{path}",
                status="error",
                error_kind=type(e).__name__,
                error_msg=str(e)[:500],
                metrics={
                    "engine": engine,
                    "path": path,
                    "stimulus_id": stimulus_id,
                    "audio_path": str(audio_path),
                    "n_bytes": n_bytes,
                },
            )
        return self.build_result(
            asset_id=f"{stimulus_id}_{engine}_{path}",
            status="ok",
            tts_first_audio_ms=first_audio_ms,
            metrics={
                "engine": engine,
                "path": path,
                "stimulus_id": stimulus_id,
                "first_audio_ms": first_audio_ms,
                "total_audio_ms": total_ms,
                "audio_path": str(audio_path),
                "n_bytes": n_bytes,
            },
        )

    async def run_one(self, asset: dict) -> GateResult:
        """Drive one render asset (= one stimulus x engine x path) through synthesize()."""
        return await self._render_one(asset["stimulus"], asset["engine"], asset["path"])

    async def run_all(self, stimuli: list[dict]) -> list[GateResult]:
        """Expand `stimuli` into 4N render assets and drive them all.

        Accepts the natural input shape (N stimuli) and handles the
        cold/warm + dual-engine fanout internally. Forces concurrency=1
        irrespective of the constructor setting so cold-then-warm
        ordering is preserved (concurrent execution would race the
        warm-after-cold invariant).
        """
        original_concurrency = self.concurrency
        self.concurrency = 1
        try:
            render_assets = build_render_assets(stimuli)
            return await super().run_all(render_assets)
        finally:
            self.concurrency = original_concurrency


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def load_stimuli(
    pairs_path: pathlib.Path = pathlib.Path("assets/tts_pairs/pairs.json"),
) -> list[dict]:
    """Load the 30 G7 stimulus pairs from `assets/tts_pairs/pairs.json`."""
    with pairs_path.open() as f:
        data = json.load(f)
    if not isinstance(data, list):
        raise ValueError(f"expected list at {pairs_path}, got {type(data).__name__}")
    return data


def _build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="gates.g7.runner")
    p.add_argument("--gate", default="g7", choices=["g7"])
    p.add_argument("--corpus", default="tts_pairs", help="(reserved; only tts_pairs supported)")
    p.add_argument(
        "--pairs-path",
        type=pathlib.Path,
        default=pathlib.Path("assets/tts_pairs/pairs.json"),
    )
    p.add_argument("--vllm-url", default="http://127.0.0.1:8000")
    p.add_argument("--vllm-model", default="Qwen/Qwen3-4B")
    p.add_argument("--whisper-dir", default="/models/distil_whisper_large_v3_int8")
    p.add_argument("--chatterbox-url", default="http://127.0.0.1:8004")
    p.add_argument("--kokoro-url", default="http://127.0.0.1:8005")
    p.add_argument("--results-dir", type=pathlib.Path, default=pathlib.Path("results"))
    p.add_argument(
        "--audio-out-dir",
        type=pathlib.Path,
        default=pathlib.Path("results/g7/audio"),
    )
    p.add_argument(
        "--n-stimuli",
        type=int,
        default=None,
        help="Cap stimulus count (default: all 30 pairs)",
    )
    return p


async def main_async(argv: list[str]) -> int:
    from substrate.cuda import CUDASubstrate

    args = _build_arg_parser().parse_args(argv)
    sub = CUDASubstrate(
        vllm_url=args.vllm_url,
        vllm_model=args.vllm_model,
        whisper_model_dir=args.whisper_dir,
        chatterbox_url=args.chatterbox_url,
        kokoro_url=args.kokoro_url,
    )
    stimuli = load_stimuli(args.pairs_path)
    if args.n_stimuli is not None:
        stimuli = stimuli[: args.n_stimuli]
    runner = G7Runner(
        substrate=sub,
        audio_out_dir=args.audio_out_dir,
        results_dir=args.results_dir,
    )
    await runner.start()
    results = await runner.run_all(stimuli)
    ok = sum(1 for r in results if r.status == "ok")
    expected = len(stimuli) * 4
    logger.info(
        f"[g7] {ok}/{len(results)} ok (expected {expected} renders); run_id={runner.run_id}"
    )
    print(f"[g7] {ok}/{len(results)} ok (expected {expected} renders); run_id={runner.run_id}")
    return 0 if ok == len(results) == expected else 1


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    return asyncio.run(main_async(sys.argv[1:]))


if __name__ == "__main__":
    sys.exit(main())
