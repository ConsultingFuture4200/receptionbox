"""Synthetic gate-row generator for Plan 03-07 scaffolding exercise.

Produces realistic-shape JSONL files under a chosen results root so the
synthesis pipeline can be dry-run end-to-end before W2/W3 land real
Phase 3 measurements. Row shape matches harness.results.GateResult.
"""

from __future__ import annotations

import json
import pathlib
import random
from typing import Final

# Realistic H100 PCIe median latencies (ms) for a CPG-reception-bot pipeline.
# Tuned to roughly match expected smoke-run distribution; not load-bearing.
_STAGE_MEAN_MS: Final[dict[str, float]] = {
    "stt_ttft_ms": 120.0,
    "llm_ttft_ms": 90.0,
    "llm_decode_ms_per_tok": 8.0,
    "tts_first_audio_ms": 60.0,
}
_STAGE_NOISE_SD: Final[dict[str, float]] = {
    "stt_ttft_ms": 18.0,
    "llm_ttft_ms": 12.0,
    "llm_decode_ms_per_tok": 1.0,
    "tts_first_audio_ms": 9.0,
}


def _concurrency_scale(concurrency: int) -> float:
    """Per-row latency multiplier as concurrency rises (queueing)."""
    return 1.0 + 0.18 * (concurrency - 1)


def make_gate_rows(
    gate: str,
    concurrency: int,
    n_rows: int,
    run_id: str,
    seed: int = 0,
) -> list[dict]:
    """Generate `n_rows` synthetic GateResult-shaped dicts."""
    rng = random.Random(seed)
    scale = _concurrency_scale(concurrency)
    rows: list[dict] = []
    for i in range(n_rows):
        row: dict = {
            "gate": gate,
            "run_id": run_id,
            "asset_id": f"call-{i + 1:04d}",
            "asset_manifest_sha": "fixture-manifest-sha-0001",
            "image_digest": "sha256:fixture-v19a-digest",
            "git_commit": "fixturecommit01",
            "substrate": "cuda-fixture",
            "concurrency": concurrency,
            "status": "ok",
        }
        for col, mean in _STAGE_MEAN_MS.items():
            sd = _STAGE_NOISE_SD[col]
            v = max(0.1, rng.gauss(mean * scale, sd * scale))
            row[col] = round(v, 3)
        row["e2e_ms"] = round(
            row["stt_ttft_ms"]
            + row["llm_ttft_ms"]
            + 30 * row["llm_decode_ms_per_tok"]
            + row["tts_first_audio_ms"],
            3,
        )
        rows.append(row)
    return rows


def seed_results_dir(
    target_root: pathlib.Path,
    gates: tuple[str, ...] = ("g1", "g2", "g3", "g5"),
    concurrencies: tuple[int, ...] = (1, 2, 4),
    rows_per_run: int = 25,
    seed: int = 0,
) -> dict[str, list[pathlib.Path]]:
    """Materialize ``gates * concurrencies`` JSONL files under target_root.

    Returns a {gate: [jsonl_path, ...]} map for caller inspection.
    """
    target_root.mkdir(parents=True, exist_ok=True)
    written: dict[str, list[pathlib.Path]] = {}
    for g in gates:
        gate_dir = target_root / g
        gate_dir.mkdir(parents=True, exist_ok=True)
        written[g] = []
        for c in concurrencies:
            run_id = f"fixture-{g}-c{c}"
            rows = make_gate_rows(g, c, rows_per_run, run_id, seed=seed + c)
            path = gate_dir / f"{run_id}.jsonl"
            with path.open("w") as fh:
                for r in rows:
                    fh.write(json.dumps(r) + "\n")
            written[g].append(path)
    return written
