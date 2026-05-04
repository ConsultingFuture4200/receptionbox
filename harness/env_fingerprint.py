"""Helpers to capture an EnvFingerprint for a gate run (HARNESS-05 carryover).

Phase 1 ships only what can be captured locally without GPUs:
- substrate (caller-provided)
- image_digest (caller-provided; from bench/images.lock.yaml lookup)
- git_commit (read from `.git/HEAD` chain; no subprocess required)
- timestamp_utc

Phase 2/3 gate runners enrich with gpu_sku, rocm/cuda/vllm versions,
model_shas (from bench/models.lock.yaml), etc.
"""

from __future__ import annotations

import datetime
import pathlib
import subprocess
from typing import Literal

from substrate.types import EnvFingerprint


def _git_commit(repo: pathlib.Path = pathlib.Path(".")) -> str:
    """Return the current HEAD commit SHA, or 'unknown' if not a git repo."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],  # noqa: S607
            cwd=repo,
            capture_output=True,
            text=True,
            check=False,
            timeout=5,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    return "unknown"


def capture(
    *,
    substrate: Literal["cuda", "rocm"],
    image_digest: str = "unknown",
    model_shas: dict[str, str] | None = None,
    gpu_sku: str = "unknown",
    gpu_count: int = 0,
    rocm_version: str | None = None,
    cuda_version: str | None = None,
    vllm_version: str | None = None,
    pytorch_version: str | None = None,
) -> EnvFingerprint:
    """Capture an EnvFingerprint for the current process at this moment."""
    return EnvFingerprint(
        substrate=substrate,
        image_digest=image_digest,
        model_shas=model_shas or {},
        gpu_sku=gpu_sku,
        gpu_count=gpu_count,
        rocm_version=rocm_version,
        cuda_version=cuda_version,
        vllm_version=vllm_version,
        pytorch_version=pytorch_version,
        timestamp_utc=datetime.datetime.utcnow().isoformat(),
    )
