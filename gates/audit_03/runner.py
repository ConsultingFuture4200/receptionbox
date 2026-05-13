"""AUDIT-03 engine-swap + Ollama-vs-vLLM overhead measurement runner.

Two passes on one pod session:

1. **Engine swap (DR-27 viability)** — render N stimuli on Chatterbox,
   then render N stimuli on Kokoro. Measure `engine_swap_ms` =
   first_kokoro_first_audio_t - last_chatterbox_last_byte_t. Validates
   the pluggable-TTS architecture survives mid-session flips.

2. **Ollama-vs-vLLM overhead** - run the same prompt set through both
   the vLLM AWQ-Int4 path (via `substrate.generate`) and the Ollama
   llama.cpp Q4_K_M path (via `ollama run` subprocess). Compute the
   median tokens/sec ratio. Grounds the 1.3-1.5x scalar from
   CLAUDE.md §3.1 (currently extrapolated from community benchmarks).

If Ollama is not installed on the pod, the Ollama rows record
`error="ollama_not_installed"` and the audit continues — never aborts.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import pathlib
import re
import statistics
import subprocess
import sys
import time

from gates._runner_base import GateRunner
from harness.results import GateResult
from substrate import Substrate

logger = logging.getLogger(__name__)

# Module-local seam (same pattern as AUDIT-01) so tests can patch the Ollama
# subprocess invocation without leaking onto _runner_base._git_commit's
# subprocess.run.
_subprocess_run = subprocess.run

# Ollama `--verbose` reports a trailing block like:
#   total duration:       2.345s
#   eval count:           123 token(s)
#   eval rate:            45.67 tokens/s
# We parse `eval rate` when available and fall back to count/duration.
_OLLAMA_EVAL_RATE_RE = re.compile(r"eval rate:\s*([0-9.]+)\s*tokens/s")
_OLLAMA_EVAL_COUNT_RE = re.compile(r"eval count:\s*([0-9]+)\s*token")


def _parse_ollama_tokens_per_sec(
    stderr: str, fallback_tokens: int, duration_s: float
) -> tuple[int, float]:
    """Return (tokens, tokens_per_sec) from Ollama's --verbose stderr.

    Ollama writes the timing block to stderr (not stdout) — stdout is the
    generated text. The verbose block is only present when `--verbose` is
    passed; otherwise we fall back to a word-count rough estimate over the
    wall-clock duration.
    """
    rate_match = _OLLAMA_EVAL_RATE_RE.search(stderr or "")
    count_match = _OLLAMA_EVAL_COUNT_RE.search(stderr or "")
    if rate_match and count_match:
        return int(count_match.group(1)), float(rate_match.group(1))
    if duration_s <= 0:
        return fallback_tokens, 0.0
    return fallback_tokens, fallback_tokens / duration_s


class AUDIT03Runner(GateRunner):
    """AUDIT-03 swap + Ollama-overhead runner.

    Emits 2N swap rows (`metrics.path="swap"`) + 2M Ollama-vs-vLLM rows
    (`metrics.engine_kind ∈ {"vllm","ollama"}`).
    """

    def __init__(
        self,
        *,
        substrate: Substrate,
        ollama_model: str = "qwen3:4b-q4_K_M",
        ollama_max_tokens: int = 200,
        **kw,
    ) -> None:
        super().__init__(substrate=substrate, gate="audit_03", **kw)
        self.ollama_model = ollama_model
        self.ollama_max_tokens = ollama_max_tokens

    # ------------------------------------------------------------------
    # Pass 1: engine swap (Chatterbox → Kokoro).
    # ------------------------------------------------------------------
    def _tts_engine(self, kind: str):
        """Return the Chatterbox/Kokoro adapter from the substrate.

        AUDIT-03 needs to drive each TTS engine directly (the substrate's
        public `synthesize` runs DR-27 fallback logic, which masks the
        explicit swap we're trying to measure).
        """
        attr = "_chatterbox" if kind == "chatterbox" else "_kokoro"
        adapter = getattr(self.substrate, attr, None)
        if adapter is None:
            raise RuntimeError(f"substrate has no '{attr}' adapter; AUDIT-03 needs both")
        return adapter

    async def _render_one(self, kind: str, stim: dict) -> tuple[float, float, int]:
        """Render one stimulus on a specific TTS engine.

        Returns (first_byte_t, last_byte_t, total_bytes) measured against
        a wall-clock baseline so the caller can compute the swap gap.
        """
        engine = self._tts_engine(kind)
        text = stim.get("text") or stim.get("prompt") or ""
        first_byte_t: float | None = None
        last_byte_t: float | None = None
        total_bytes = 0
        async for chunk in engine.synthesize(text, None):
            now = time.perf_counter()
            if first_byte_t is None:
                first_byte_t = now
            last_byte_t = now
            total_bytes += len(chunk) if chunk else 0
        if first_byte_t is None:
            # Engine yielded nothing — error path; surface zero-byte first/last.
            first_byte_t = time.perf_counter()
            last_byte_t = first_byte_t
        return first_byte_t, last_byte_t, total_bytes

    async def _run_swap_pass(
        self, stimuli_cb: list[dict], stimuli_kk: list[dict]
    ) -> list[GateResult]:
        results: list[GateResult] = []
        last_cb_last_byte_t: float | None = None

        for s in stimuli_cb:
            t0 = time.perf_counter()
            first_byte, last_byte, n_bytes = await self._render_one("chatterbox", s)
            last_cb_last_byte_t = last_byte
            results.append(
                self.build_result(
                    asset_id=f"cb_{s.get('stimulus_id', s.get('asset_id', 'x'))}",
                    status="ok",
                    metrics={
                        "engine": "chatterbox",
                        "path": "swap",
                        "first_byte_ms": (first_byte - t0) * 1000.0,
                        "duration_ms": (last_byte - t0) * 1000.0,
                        "bytes": n_bytes,
                        "engine_swap_ms": None,
                    },
                )
            )

        for i, s in enumerate(stimuli_kk):
            t0 = time.perf_counter()
            first_byte, last_byte, n_bytes = await self._render_one("kokoro", s)
            engine_swap_ms: float | None = None
            if i == 0 and last_cb_last_byte_t is not None:
                engine_swap_ms = (first_byte - last_cb_last_byte_t) * 1000.0
            results.append(
                self.build_result(
                    asset_id=f"kk_{s.get('stimulus_id', s.get('asset_id', 'x'))}",
                    status="ok",
                    metrics={
                        "engine": "kokoro",
                        "path": "swap",
                        "first_byte_ms": (first_byte - t0) * 1000.0,
                        "duration_ms": (last_byte - t0) * 1000.0,
                        "bytes": n_bytes,
                        "engine_swap_ms": engine_swap_ms,
                    },
                )
            )
        return results

    # ------------------------------------------------------------------
    # Pass 2: Ollama vs vLLM overhead.
    # ------------------------------------------------------------------
    async def _measure_vllm_one(self, probe: dict) -> GateResult:
        prompt = probe.get("prompt") or probe.get("text") or ""
        t0 = time.perf_counter()
        tokens = 0
        async for chunk in self.substrate.generate(
            prompt, grammar=None, max_tokens=self.ollama_max_tokens
        ):
            text = getattr(chunk, "text", "") or ""
            # Rough token count: split on whitespace. Replace with proper
            # token accounting once vLLM adapter surfaces token counts.
            if text.strip():
                tokens += max(1, len(text.split()))
        duration_ms = (time.perf_counter() - t0) * 1000.0
        tps = (tokens / (duration_ms / 1000.0)) if duration_ms > 0 else 0.0
        return self.build_result(
            asset_id=f"olm_vllm_{probe.get('probe_id', probe.get('asset_id', 'x'))}",
            status="ok",
            metrics={
                "engine_kind": "vllm",
                "tokens": tokens,
                "duration_ms": duration_ms,
                "tokens_per_sec": tps,
            },
        )

    def _measure_ollama_one(self, probe: dict) -> GateResult:
        prompt = probe.get("prompt") or probe.get("text") or ""
        asset_id = f"olm_ollama_{probe.get('probe_id', probe.get('asset_id', 'x'))}"
        try:
            t0 = time.perf_counter()
            r = _subprocess_run(
                ["ollama", "run", "--verbose", self.ollama_model, prompt],
                capture_output=True,
                text=True,
                timeout=120,
                check=False,
            )
            duration_ms = (time.perf_counter() - t0) * 1000.0
        except FileNotFoundError as e:
            return self.build_result(
                asset_id=asset_id,
                status="error",
                error_kind="FileNotFoundError",
                error_msg=f"ollama_not_installed: {e}"[:500],
                metrics={"engine_kind": "ollama"},
            )
        except subprocess.TimeoutExpired as e:
            return self.build_result(
                asset_id=asset_id,
                status="timeout",
                error_kind="TimeoutExpired",
                error_msg=f"ollama timeout: {e}"[:500],
                metrics={"engine_kind": "ollama"},
            )

        # Estimate tokens from --verbose stderr; fall back to word count.
        fallback_tokens = len((r.stdout or "").split())
        tokens, tps = _parse_ollama_tokens_per_sec(
            r.stderr or "", fallback_tokens, duration_ms / 1000.0
        )
        return self.build_result(
            asset_id=asset_id,
            status="ok" if r.returncode == 0 else "error",
            error_kind=None if r.returncode == 0 else "OllamaNonZeroExit",
            error_msg=None if r.returncode == 0 else (r.stderr or "")[:500],
            metrics={
                "engine_kind": "ollama",
                "tokens": tokens,
                "duration_ms": duration_ms,
                "tokens_per_sec": tps,
                "returncode": r.returncode,
            },
        )

    async def _run_ollama_overhead_pass(self, probes: list[dict]) -> list[GateResult]:
        results: list[GateResult] = []
        for probe in probes:
            results.append(await self._measure_vllm_one(probe))
            results.append(self._measure_ollama_one(probe))
        return results

    # ------------------------------------------------------------------
    # Orchestration.
    # ------------------------------------------------------------------
    async def run_all(self, params: dict) -> list[GateResult]:  # type: ignore[override]
        """params = {"stimuli_cb": [...], "stimuli_kk": [...], "ollama_probes": [...]}.

        AUDIT-01 conventions: emit rows incrementally so a partial pod
        crash still leaves a useful JSONL on disk.
        """
        cb = params.get("stimuli_cb", [])
        kk = params.get("stimuli_kk", [])
        probes = params.get("ollama_probes", [])

        swap_results = await self._run_swap_pass(cb, kk)
        for r in swap_results:
            self.emit(r)

        olm_results = await self._run_ollama_overhead_pass(probes)
        for r in olm_results:
            self.emit(r)

        return swap_results + olm_results


def summarize_ollama_overhead(results: list[GateResult]) -> dict:
    """Compute `ollama_overhead_factor = median(vllm_tps) / median(ollama_tps)`.

    Skips rows where tokens_per_sec is null/zero or status != "ok". The
    factor is null if either side has no usable samples; the caller (pod
    real-spend run) records the gap explicitly rather than emitting a
    fabricated number.
    """
    vllm_tps: list[float] = []
    ollama_tps: list[float] = []
    for r in results:
        m = getattr(r, "metrics", {}) or {}
        tps = m.get("tokens_per_sec")
        if not tps or r.status != "ok":
            continue
        kind = m.get("engine_kind")
        if kind == "vllm":
            vllm_tps.append(float(tps))
        elif kind == "ollama":
            ollama_tps.append(float(tps))
    if not vllm_tps or not ollama_tps:
        return {
            "vllm_tps_median": statistics.median(vllm_tps) if vllm_tps else None,
            "ollama_tps_median": statistics.median(ollama_tps) if ollama_tps else None,
            "ollama_overhead_factor": None,
            "n_vllm": len(vllm_tps),
            "n_ollama": len(ollama_tps),
        }
    vllm_med = statistics.median(vllm_tps)
    olm_med = statistics.median(ollama_tps)
    factor = (vllm_med / olm_med) if olm_med > 0 else None
    return {
        "vllm_tps_median": vllm_med,
        "ollama_tps_median": olm_med,
        "ollama_overhead_factor": factor,
        "n_vllm": len(vllm_tps),
        "n_ollama": len(ollama_tps),
    }


def _build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="AUDIT-03 swap + Ollama-overhead runner")
    # Dispatch-contract args from tools/pod_entrypoint.sh.
    p.add_argument("--gate", default="audit_03", choices=["audit_03"])
    p.add_argument("--strata", default=None, help="ignored; audits have no corpus strata")
    p.add_argument("--vllm-url", default="http://127.0.0.1:8000/v1")
    p.add_argument("--vllm-model", default="Qwen/Qwen3-4B-AWQ")
    p.add_argument("--whisper-dir", default="/models/distil-whisper-large-v3-int8")
    p.add_argument("--chatterbox-url", default="http://127.0.0.1:8004")
    p.add_argument("--kokoro-url", default="http://127.0.0.1:8880")
    p.add_argument("--ollama-model", default="qwen3:4b-q4_K_M")
    p.add_argument("--ollama-max-tokens", type=int, default=200)
    p.add_argument(
        "--tts-pairs-path",
        type=pathlib.Path,
        default=pathlib.Path("assets/tts_pairs/pairs.json"),
    )
    p.add_argument(
        "--upl-probes-path",
        type=pathlib.Path,
        default=pathlib.Path("assets/upl_probes/probes.json"),
    )
    p.add_argument("--n-swap", type=int, default=5)
    p.add_argument("--n-probes", type=int, default=20)
    p.add_argument("--results-dir", type=pathlib.Path, default=pathlib.Path("results"))
    return p


def _load_json_list(path: pathlib.Path, n: int) -> list[dict]:
    import json

    if not path.exists():
        return []
    data = json.loads(path.read_text())
    items = data if isinstance(data, list) else data.get("items", [])
    return items[:n]


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
    runner = AUDIT03Runner(
        substrate=sub,
        ollama_model=args.ollama_model,
        ollama_max_tokens=args.ollama_max_tokens,
        results_dir=args.results_dir,
    )
    await runner.start()
    pairs = _load_json_list(args.tts_pairs_path, args.n_swap)
    probes = _load_json_list(args.upl_probes_path, args.n_probes)
    results = await runner.run_all(
        {
            "stimuli_cb": pairs,
            "stimuli_kk": pairs,
            "ollama_probes": probes,
        }
    )
    summary = summarize_ollama_overhead(results)
    ok = sum(1 for r in results if r.status == "ok")
    msg = (
        f"[audit_03] {ok}/{len(results)} ok; run_id={runner.run_id}; "
        f"ollama_overhead_factor={summary['ollama_overhead_factor']}"
    )
    logger.info(msg)
    print(msg)
    return 0 if ok > 0 else 1


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    return asyncio.run(main_async(sys.argv[1:]))


if __name__ == "__main__":
    sys.exit(main())
