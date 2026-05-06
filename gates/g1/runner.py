"""G1 latency gate runner (PREFLIGHT-01 smoke + PREFLIGHT-02 sanity).

Drives N calls through the LiveKit pipeline (substrate.livekit_pipeline)
at concurrency=1, recording per-stage timings on each GateResult row.

Substrate-agnostic by construction — types against the Substrate ABC.
The CLI entry point wires CUDASubstrate concretely; tests substitute the
stub via monkeypatch.
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import logging
import pathlib
import sys

from gates._runner_base import GateRunner
from harness.results import GateName, GateResult
from substrate import Substrate
from substrate.livekit_pipeline import build_session, run_one_call

logger = logging.getLogger(__name__)


class G1Runner(GateRunner):
    """G1 latency runner. Each asset is one E2E call; emits per-stage timings."""

    def __init__(
        self,
        *,
        substrate: Substrate,
        gate: GateName = "g1",
        **kw,
    ) -> None:
        super().__init__(substrate=substrate, gate=gate, **kw)
        self._session = None

    async def start(self) -> None:
        await super().start()
        self._session = build_session(self.substrate)

    async def run_one(self, asset: dict) -> GateResult:
        audio_path = pathlib.Path(asset["path"])
        try:
            timings = await run_one_call(self._session, audio_path)
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
            stt_ttft_ms=timings.get("stt_ttft_ms"),
            llm_ttft_ms=timings.get("llm_ttft_ms"),
            llm_decode_ms_per_tok=timings.get("llm_decode_ms_per_tok"),
            tts_first_audio_ms=timings.get("tts_first_audio_ms"),
            e2e_ms=timings.get("e2e_ms"),
            metrics={
                "intent": asset.get("intent"),
                "adversity": asset.get("adversity_level"),
            },
        )


def load_assets(
    corpus: str,
    manifest: pathlib.Path = pathlib.Path("assets/manifest.csv"),
) -> list[dict]:
    """Load rows from `assets/manifest.csv` filtered by `corpus`."""
    rows: list[dict] = []
    with manifest.open() as f:
        for r in csv.DictReader(f):
            if r["corpus"] == corpus:
                rows.append(r)
    return rows


def _select_assets(args: argparse.Namespace, assets: list[dict]) -> list[dict]:
    """Apply --gate / --strata / --n-calls selection rules (D-27).

    - smoke: first N assets (default 5).
    - g1 sanity with --strata: filter manifest rows to the asset_ids listed
      under `strata.g1.assets` in config/sanity_strata.yaml.
    - g1 sanity without --strata or strata file missing: fall back to first
      N assets and WARN.
    """
    if args.gate == "smoke":
        n = args.n_calls or 5
        return assets[:n]
    n_default = args.n_calls or 10
    if args.strata:
        strata_path = pathlib.Path(args.strata)
        if not strata_path.exists():
            logger.warning(
                f"[g1] strata file not found at {strata_path}; "
                f"defaulting to first {n_default} assets"
            )
            return assets[:n_default]
        import yaml

        data = yaml.safe_load(strata_path.read_text())
        wanted = set(data.get("strata", {}).get("g1", {}).get("assets", []))
        if not wanted:
            logger.warning(
                f"[g1] strata file {strata_path} has no g1 assets; "
                f"defaulting to first {n_default} assets"
            )
            return assets[:n_default]
        selected = [a for a in assets if a["asset_id"] in wanted]
        missing = wanted - {a["asset_id"] for a in selected}
        if missing:
            logger.warning(f"[g1] strata asset_ids not found in manifest: {sorted(missing)}")
        return selected
    return assets[:n_default]


def _build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="gates.g1.runner")
    p.add_argument("--gate", default="g1", choices=["g1", "smoke"])
    p.add_argument(
        "--n-calls",
        type=int,
        default=None,
        help="Cap call count (smoke=5; g1 sanity=10 via Plan 02-04 strata)",
    )
    p.add_argument(
        "--strata",
        default=None,
        help="Path to config/sanity_strata.yaml entry to drive selection",
    )
    p.add_argument("--corpus", default="corpus_500")
    p.add_argument("--vllm-url", default="http://127.0.0.1:8000")
    p.add_argument("--vllm-model", default="Qwen/Qwen3-4B")
    p.add_argument("--whisper-dir", default="/models/distil_whisper_large_v3_int8")
    p.add_argument("--chatterbox-url", default="http://127.0.0.1:8004")
    p.add_argument("--kokoro-url", default="http://127.0.0.1:8005")
    p.add_argument("--results-dir", type=pathlib.Path, default=pathlib.Path("results"))
    return p


async def main_async(argv: list[str]) -> int:
    args = _build_arg_parser().parse_args(argv)

    # Late import — keeps the CLI helptext printable on a no-CUDA workstation.
    from substrate.cuda import CUDASubstrate

    sub = CUDASubstrate(
        vllm_url=args.vllm_url,
        vllm_model=args.vllm_model,
        whisper_model_dir=args.whisper_dir,
        chatterbox_url=args.chatterbox_url,
        kokoro_url=args.kokoro_url,
    )
    assets = load_assets(args.corpus)
    selected = _select_assets(args, assets)
    runner = G1Runner(
        substrate=sub,
        gate="smoke" if args.gate == "smoke" else "g1",
        results_dir=args.results_dir,
    )
    await runner.start()
    results = await runner.run_all(selected)
    ok = sum(1 for r in results if r.status == "ok")
    logger.info(f"[g1] {ok}/{len(results)} ok; run_id={runner.run_id}")
    print(f"[g1] {ok}/{len(results)} ok; run_id={runner.run_id}")
    return 0 if ok == len(results) else 1


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    return asyncio.run(main_async(sys.argv[1:]))


if __name__ == "__main__":
    sys.exit(main())
