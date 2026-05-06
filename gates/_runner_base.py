"""Substrate-agnostic GateRunner base (HARNESS-06).

Concrete runners under `gates/g{1,2,3,5}/runner.py` subclass `GateRunner`
and implement `run_one(asset)`. Everything substrate-agnostic — env.json
sidecar emission, REPRO-03 tuple population, exception → error-row
conversion — lives here.

The runner types against the Substrate ABC, NOT a concrete CUDASubstrate.
Phase 3's ROCmSubstrate drops in without touching gate code.
"""

from __future__ import annotations

import asyncio
import datetime
import hashlib
import logging
import pathlib
import subprocess
from typing import Any

from harness.env_sidecar import write_env_sidecar
from harness.results import GateName, GateResult, Status, append_result
from substrate import Substrate
from substrate.types import EnvFingerprint

logger = logging.getLogger(__name__)


def _gen_run_id() -> str:
    """ULID if `python-ulid` is installed; else uuid4 hex (still monotonic-ish)."""
    try:
        from ulid import ULID  # type: ignore[import-not-found]

        return str(ULID())
    except ImportError:
        import uuid

        return uuid.uuid4().hex


def _git_commit() -> str:
    """`git rev-parse HEAD`, or 'unknown' on failure (no exceptions escape)."""
    try:
        r = subprocess.run(
            ["git", "rev-parse", "HEAD"],  # noqa: S607
            capture_output=True,
            text=True,
            check=False,
            timeout=5,
        )
        if r.returncode == 0:
            return r.stdout.strip()
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    return "unknown"


def _sha256_file(path: pathlib.Path) -> str:
    """sha256 of `path`'s contents, streamed in 64 KiB chunks."""
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


class GateRunner:
    """Substrate-agnostic gate runner. Subclasses implement `run_one`.

    Constructor computes the reproducibility tuple ONCE at instantiation:
    run_id (ULID/uuid), git_commit, asset_manifest_sha. `start()` then
    loads the substrate, captures its env_fingerprint, and writes the
    env.json sidecar. From that point on every result row carries the
    full REPRO-03 tuple via `build_result()`.
    """

    def __init__(
        self,
        *,
        substrate: Substrate,
        gate: GateName,
        asset_manifest_path: pathlib.Path = pathlib.Path("assets/manifest.csv"),
        results_dir: pathlib.Path = pathlib.Path("results"),
        concurrency: int = 1,
    ) -> None:
        self.substrate = substrate
        self.gate: GateName = gate
        self.results_dir = results_dir
        self.concurrency = concurrency
        self.run_id = _gen_run_id()
        self.git_commit = _git_commit()
        self.asset_manifest_sha = _sha256_file(asset_manifest_path)
        self._env_fp: EnvFingerprint | None = None

    async def start(self) -> None:
        """Load substrate stages in parallel, capture fingerprint, emit sidecar."""
        await asyncio.gather(
            self.substrate.load_stt(),
            self.substrate.load_llm(),
            self.substrate.load_tts(),
            return_exceptions=False,  # adapters MUST NOT raise (Phase 1 lock-in).
        )
        self._env_fp = self.substrate.env_fingerprint()
        write_env_sidecar(
            env_fp=self._env_fp,
            run_id=self.run_id,
            gate=self.gate,
            git_commit=self.git_commit,
            asset_manifest_sha=self.asset_manifest_sha,
            results_dir=self.results_dir,
        )
        logger.info(
            f"[{self.gate}] run_id={self.run_id} substrate={self._env_fp.substrate} "
            f"image={self._env_fp.image_digest[:12]}... commit={self.git_commit[:8]}"
        )

    def build_result(
        self,
        *,
        asset_id: str,
        status: Status,
        error_kind: str | None = None,
        error_msg: str | None = None,
        stt_ttft_ms: float | None = None,
        llm_ttft_ms: float | None = None,
        llm_decode_ms_per_tok: float | None = None,
        tts_first_audio_ms: float | None = None,
        e2e_ms: float | None = None,
        metrics: dict | None = None,
        extras: dict | None = None,
    ) -> GateResult:
        """Build a GateResult with the full REPRO-03 tuple auto-populated.

        Pydantic raises if any required field is missing — REPRO-03 enforced
        at write-time, impossible to forget.
        """
        if self._env_fp is None:
            raise RuntimeError("Call start() before build_result()")
        return GateResult(
            run_id=self.run_id,
            gate=self.gate,
            asset_id=asset_id,
            asset_manifest_sha=self.asset_manifest_sha,
            substrate=self._env_fp.substrate,
            image_digest=self._env_fp.image_digest,
            model_shas=self._env_fp.model_shas,
            git_commit=self.git_commit,
            timestamp_utc=datetime.datetime.utcnow(),
            concurrency=self.concurrency,
            status=status,
            error_kind=error_kind,
            error_msg=error_msg,
            stt_ttft_ms=stt_ttft_ms,
            llm_ttft_ms=llm_ttft_ms,
            llm_decode_ms_per_tok=llm_decode_ms_per_tok,
            tts_first_audio_ms=tts_first_audio_ms,
            e2e_ms=e2e_ms,
            metrics=metrics or {},
            extras=extras or {},
        )

    def emit(self, result: GateResult) -> pathlib.Path:
        """Append one JSONL row to `results/{gate}/{run_id}.jsonl`."""
        return append_result(result, self.results_dir)

    async def run_one(self, asset: Any) -> GateResult:
        """Subclass hook — drive ONE asset through the substrate; return one GateResult."""
        raise NotImplementedError

    async def run_all(self, assets: list) -> list[GateResult]:
        """Iterate `assets` with `Semaphore(concurrency)`. Exceptions → error rows.

        T-02-02-04 mitigation: per-asset failures emit error rows but never
        abort the run. The error row carries error_kind + truncated error_msg;
        run_id / asset_manifest_sha / git_commit / image_digest / model_shas
        / substrate are still populated (REPRO-03 holds for error rows too).
        """
        sem = asyncio.Semaphore(self.concurrency)
        results: list[GateResult] = []
        results_lock = asyncio.Lock()

        async def _wrap(a: Any) -> None:
            async with sem:
                try:
                    r = await self.run_one(a)
                except Exception as e:
                    asset_id = (
                        a.get("asset_id") if isinstance(a, dict) else getattr(a, "asset_id", str(a))
                    )
                    r = self.build_result(
                        asset_id=str(asset_id),
                        status="error",
                        error_kind=type(e).__name__,
                        error_msg=str(e)[:500],
                    )
                self.emit(r)
                async with results_lock:
                    results.append(r)

        await asyncio.gather(*[_wrap(a) for a in assets])
        return results
