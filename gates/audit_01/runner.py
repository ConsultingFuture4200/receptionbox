"""AUDIT-01 co-residency stack-load runner.

Load all 4 models (STT + LLM + Chatterbox + Kokoro) on one pod, then hold
the substrate alive for `duration_s` while sampling VRAM every
`sample_interval_s` via nvidia-smi. One result row per VRAM sample.

The "all 4 models resident" check goes deeper than substrate._loaded
(which OR's the two TTS engines per DR-27 fallback): AUDIT-01 needs each
of {stt, llm, chatterbox, kokoro} verified independently to prove the
appliance can hold the entire stack simultaneously on 64 GB Orin.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import pathlib
import subprocess
import sys

from gates._runner_base import GateRunner
from harness.results import GateResult
from substrate import Substrate

logger = logging.getLogger(__name__)

# Module-local seam so tests can patch nvidia-smi invocation without mutating
# the global `subprocess.run` (which `_runner_base._git_commit` also relies on).
_subprocess_run = subprocess.run


def _parse_nvidia_smi_csv(text: str) -> dict:
    """Parse `nvidia-smi --query-gpu=... --format=csv,noheader,nounits` output.

    Expected: a single line of three comma-separated integers, e.g.
    `"22000, 81920, 35"` → (memory.used_MiB, memory.total_MiB, util.gpu_pct).
    """
    parts = [p.strip() for p in text.strip().split(",")]
    if len(parts) < 3:
        raise ValueError(f"nvidia-smi CSV malformed: {text!r}")
    return {
        "vram_mb": int(parts[0]),
        "vram_total_mb": int(parts[1]),
        "gpu_util_pct": int(parts[2]),
    }


class AUDIT01Runner(GateRunner):
    """AUDIT-01 co-residency runner. One GateResult per VRAM sample."""

    def __init__(self, *, substrate: Substrate, **kw) -> None:
        super().__init__(substrate=substrate, gate="audit_01", **kw)

    def _sample_nvidia_smi(self) -> dict:
        """Run `nvidia-smi` once and return memory/util numbers, or null on failure."""
        try:
            r = _subprocess_run(
                [
                    "nvidia-smi",
                    "--query-gpu=memory.used,memory.total,utilization.gpu",
                    "--format=csv,noheader,nounits",
                ],
                capture_output=True,
                text=True,
                check=True,
                timeout=5,
            )
            parsed = _parse_nvidia_smi_csv(r.stdout)
            parsed["error"] = None
            return parsed
        except (
            FileNotFoundError,
            subprocess.CalledProcessError,
            subprocess.TimeoutExpired,
            ValueError,
        ) as e:
            return {
                "vram_mb": None,
                "vram_total_mb": None,
                "gpu_util_pct": None,
                "error": f"nvidia-smi unavailable: {type(e).__name__}",
            }

    async def _all_four_models_resident(self) -> bool:
        """True iff stt + llm + chatterbox + kokoro all report healthy.

        substrate._loaded["tts"] is OR'd (DR-27), so we peek directly at
        the two TTS adapters to enforce strict simultaneous residency.
        """
        sub = self.substrate
        if not (sub._loaded.get("stt") and sub._loaded.get("llm")):
            return False
        cb = getattr(sub, "_chatterbox", None)
        kk = getattr(sub, "_kokoro", None)
        if cb is None or kk is None:
            # _StubSubstrate or future ROCm: fall back to substrate._loaded.tts.
            return bool(sub._loaded.get("tts"))
        try:
            cb_ok = await cb.health()
            kk_ok = await kk.health()
        except Exception:
            return False
        return bool(cb_ok and kk_ok)

    async def run_one(self, asset: dict) -> GateResult:
        """asset = {"sample_idx": int, "duration_s": int}."""
        sample = self._sample_nvidia_smi()
        all_four = await self._all_four_models_resident()
        return self.build_result(
            asset_id=f"sample_{asset['sample_idx']:03d}",
            status="ok",
            metrics={
                **sample,
                "all_4_models_resident": all_four,
                "sample_idx": asset["sample_idx"],
            },
        )

    async def run_all(self, params: list[dict]) -> list[GateResult]:  # type: ignore[override]
        """params = [{"duration_s": int, "sample_interval_s": int}].

        Single-config list to match the GateRunner.run_all contract while
        keeping the audit's own loop semantics: emit one row per sample,
        sleep `interval` seconds between samples for the full `duration`.
        """
        cfg = params[0]
        duration = int(cfg["duration_s"])
        interval = int(cfg["sample_interval_s"])
        if interval <= 0:
            raise ValueError(f"sample_interval_s must be > 0, got {interval}")
        n_samples = max(1, duration // interval)
        results: list[GateResult] = []
        for i in range(n_samples):
            r = await self.run_one({"sample_idx": i, "duration_s": duration})
            self.emit(r)
            results.append(r)
            if i < n_samples - 1:
                await asyncio.sleep(interval)
        return results


def _build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="AUDIT-01 co-residency stack-load runner")
    # Dispatch-contract args from tools/pod_entrypoint.sh — accepted but
    # not load-bearing for this audit (no corpus, no strata).
    p.add_argument("--gate", default="audit_01", choices=["audit_01"])
    p.add_argument("--strata", default=None, help="ignored; audits have no corpus strata")
    p.add_argument("--vllm-url", default="http://127.0.0.1:8000/v1")
    p.add_argument("--vllm-model", default="Qwen/Qwen3-4B-AWQ")
    p.add_argument("--whisper-dir", default="/models/distil-whisper-large-v3-int8")
    p.add_argument("--chatterbox-url", default="http://127.0.0.1:8004")
    p.add_argument("--kokoro-url", default="http://127.0.0.1:8880")
    p.add_argument("--duration-s", type=int, default=300, help="total run time")
    p.add_argument("--sample-interval-s", type=int, default=10, help="VRAM sample period")
    p.add_argument("--results-dir", type=pathlib.Path, default=pathlib.Path("results"))
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
    runner = AUDIT01Runner(substrate=sub, results_dir=args.results_dir)
    await runner.start()
    results = await runner.run_all(
        [{"duration_s": args.duration_s, "sample_interval_s": args.sample_interval_s}]
    )
    ok = sum(1 for r in results if r.status == "ok")
    msg = f"[audit_01] {ok}/{len(results)} samples ok; run_id={runner.run_id}"
    logger.info(msg)
    print(msg)
    return 0 if ok == len(results) else 1


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    return asyncio.run(main_async(sys.argv[1:]))


if __name__ == "__main__":
    sys.exit(main())
