"""Per-stage Orin derate + scipy.stats.bootstrap 95% CIs.

Reads an ingested DataFrame (from synthesis.ingest_gate_jsonls.load_all),
buckets by (gate, stage, concurrency), and emits one derate row per bucket
with the measured H100 median plus the bootstrap-derived Orin point + CI.

Scaffolded ahead of Plan 03-07 Task 2; fixture exercise lives at
tests/test_synthesis_scaffold.py.
"""

from __future__ import annotations

import json
import pathlib

import numpy as np
import pandas as pd
from scipy import stats

from derating.orin_model import (
    DEFAULT_ARM_PENALTY,
    DEFAULT_OLLAMA_OVERHEAD,
    H100_PCIE,
    ORIN_AGX_64GB,
    STAGE_DERATE_FUNCS,
    OrinSpec,
)

# DataFrame column per stage (matches harness.results.GateResult field names).
STAGE_COLS: dict[str, str] = {
    "stt_ttft": "stt_ttft_ms",
    "llm_ttft": "llm_ttft_ms",
    "llm_decode": "llm_decode_ms_per_tok",
    "tts_first_audio": "tts_first_audio_ms",
}

_LLM_STAGES = ("llm_ttft", "llm_decode")
BOOTSTRAP_N_RESAMPLES = 10_000
BOOTSTRAP_CONFIDENCE = 0.95


def _measure_ollama_overhead(audit_03_root: pathlib.Path) -> float | None:
    """Derive the Ollama-overhead factor from AUDIT-03 throughput logs.

    Returns the median(vllm_tps) / median(ollama_tps) ratio across rows
    that carry an `engine_kind` discriminator. Returns None when AUDIT-03
    data is absent or doesn't contain both engines.
    """
    if not audit_03_root.exists():
        return None
    files = list(audit_03_root.glob("*.jsonl"))
    if not files:
        return None
    rows: list[dict] = []
    for f in files:
        for line in f.read_text().splitlines():
            if line.strip():
                rows.append(json.loads(line))
    vllm_tps = [
        r["metrics"]["tokens_per_sec"]
        for r in rows
        if r.get("metrics", {}).get("engine_kind") == "vllm"
        and r.get("metrics", {}).get("tokens_per_sec")
    ]
    olm_tps = [
        r["metrics"]["tokens_per_sec"]
        for r in rows
        if r.get("metrics", {}).get("engine_kind") == "ollama"
        and r.get("metrics", {}).get("tokens_per_sec")
    ]
    if not vllm_tps or not olm_tps:
        return None
    return float(np.median(vllm_tps) / np.median(olm_tps))


def _bootstrap_ci(samples: np.ndarray) -> tuple[float, float, float]:
    """Return (point=median, ci_lo, ci_hi). Falls back to (mean, min, max) for n<2."""
    if len(samples) < 2:
        v = float(samples[0]) if len(samples) else float("nan")
        return (v, v, v)
    r = stats.bootstrap(
        (samples,),
        np.median,
        n_resamples=BOOTSTRAP_N_RESAMPLES,
        confidence_level=BOOTSTRAP_CONFIDENCE,
        method="percentile",
    )
    return (
        float(np.median(samples)),
        float(r.confidence_interval.low),
        float(r.confidence_interval.high),
    )


def run(
    df: pd.DataFrame,
    src: OrinSpec = H100_PCIE,
    dst: OrinSpec = ORIN_AGX_64GB,
    ollama_overhead: float | None = None,
    arm_penalty: float | None = None,
) -> pd.DataFrame:
    """Bucket `df` by (gate, stage, concurrency); emit one derate row per bucket."""
    oo = DEFAULT_OLLAMA_OVERHEAD if ollama_overhead is None else ollama_overhead
    ap = DEFAULT_ARM_PENALTY if arm_penalty is None else arm_penalty

    if df.empty:
        return pd.DataFrame(
            columns=[
                "gate",
                "stage",
                "concurrency",
                "n_samples",
                "measured_h100_p50_ms",
                "derated_orin_point_ms",
                "derated_orin_ci_lo_ms",
                "derated_orin_ci_hi_ms",
                "ollama_overhead_applied",
                "arm_penalty_applied",
            ]
        )

    out_rows: list[dict] = []
    group_keys = [k for k in ("gate", "concurrency") if k in df.columns]
    for stage, col in STAGE_COLS.items():
        if col not in df.columns:
            continue
        derate_fn = STAGE_DERATE_FUNCS.get(stage)
        if derate_fn is None:
            continue
        for keys, grp in df.groupby(group_keys, dropna=False) if group_keys else [((), df)]:
            samples = grp[col].dropna().to_numpy()
            if len(samples) == 0:
                continue
            h100_p50, _, _ = _bootstrap_ci(samples)
            derated = np.array([derate_fn(float(s), src, dst) for s in samples])
            if stage in _LLM_STAGES:
                derated *= oo
            derated *= ap
            orin_p50, orin_lo, orin_hi = _bootstrap_ci(derated)
            keys_t = keys if isinstance(keys, tuple) else (keys,)
            row = {
                "gate": keys_t[0] if "gate" in group_keys else None,
                "stage": stage,
                "concurrency": (
                    keys_t[group_keys.index("concurrency")] if "concurrency" in group_keys else None
                ),
                "n_samples": len(samples),
                "measured_h100_p50_ms": h100_p50,
                "derated_orin_point_ms": orin_p50,
                "derated_orin_ci_lo_ms": orin_lo,
                "derated_orin_ci_hi_ms": orin_hi,
                "ollama_overhead_applied": oo if stage in _LLM_STAGES else 1.0,
                "arm_penalty_applied": ap,
            }
            out_rows.append(row)
    return pd.DataFrame(out_rows)


def main() -> int:
    from synthesis.ingest_gate_jsonls import load_all

    df = load_all()
    audit_03 = pathlib.Path("results/audit_03")
    oo = _measure_ollama_overhead(audit_03)
    out = run(df, ollama_overhead=oo)
    out_path = pathlib.Path("results/synthesis/orin_derate_table.csv")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(out_path, index=False)
    print(f"[derate] {len(out)} rows -> {out_path} (ollama_overhead={oo})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
