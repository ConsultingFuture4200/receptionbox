"""Render the standalone Derating Methodology section for Phase 4 synthesis.

Reads `results/synthesis/orin_derate_table.csv` (from synthesis.derate_pipeline)
+ `results/synthesis/nvidia_crosscheck.json` (from synthesis.cross_check_nvidia).
Emits `results/synthesis/derate_methodology.md` — a Phase-4-ready methodology
prose block that captures: spec-sheet ratios used, Ollama overhead measured-or-
defaulted, ARM penalty assumption, NVIDIA cross-check status + flags, and the
post-Phase-0 dev-kit validation plan (CLAUDE.md §7.3).

Gracefully handles missing inputs by emitting a methodology document with
clearly-marked "AWAITING" sections rather than failing — this is the Phase 4
author's reference document, not a gate.
"""

from __future__ import annotations

import json
import pathlib

import pandas as pd

from derating.orin_model import (
    DEFAULT_ARM_PENALTY,
    DEFAULT_OLLAMA_OVERHEAD,
    H100_PCIE,
    ORIN_AGX_64GB,
)


def _ratio(num: float, den: float) -> float:
    return num / den if den else float("nan")


def _load_derate_table(path: pathlib.Path) -> pd.DataFrame | None:
    if not path.exists():
        return None
    df = pd.read_csv(path)
    return df if not df.empty else None


def _load_crosscheck(path: pathlib.Path) -> dict:
    if not path.exists():
        return {"status": "missing", "comparisons": [], "flags": []}
    return json.loads(path.read_text())


def _format_overheads(derate: pd.DataFrame | None) -> tuple[str, str]:
    if derate is None:
        oo = f"{DEFAULT_OLLAMA_OVERHEAD:.2f}x (default — no Phase 3 measurements yet)"
        ap = f"{DEFAULT_ARM_PENALTY:.2f}x (CLAUDE.md §7.2 midpoint)"
        return oo, ap
    # Pull the highest non-1.0 ollama_overhead_applied seen in the table
    llm_rows = derate[derate["ollama_overhead_applied"] != 1.0]
    if llm_rows.empty:
        oo_val = DEFAULT_OLLAMA_OVERHEAD
        oo_note = "default — no LLM rows in derate table"
    else:
        oo_val = float(llm_rows["ollama_overhead_applied"].iloc[0])
        oo_note = (
            "measured from AUDIT-03"
            if abs(oo_val - DEFAULT_OLLAMA_OVERHEAD) > 1e-6
            else "default (AUDIT-03 absent or non-discriminating)"
        )
    ap_val = float(derate["arm_penalty_applied"].iloc[0])
    return f"{oo_val:.3f}x ({oo_note})", f"{ap_val:.2f}x (CLAUDE.md §7.2 midpoint of 10-20%)"


def render(derate_path: pathlib.Path, crosscheck_path: pathlib.Path) -> str:
    derate = _load_derate_table(derate_path)
    crosscheck = _load_crosscheck(crosscheck_path)
    oo_line, ap_line = _format_overheads(derate)

    int8_src = H100_PCIE.int8_tops_sparse
    int8_dst = ORIN_AGX_64GB.int8_tops_sparse
    bw_src = H100_PCIE.bandwidth_gb_s
    bw_dst = ORIN_AGX_64GB.bandwidth_gb_s
    fp16_src = H100_PCIE.fp16_tflops_sparse
    fp16_dst = ORIN_AGX_64GB.fp16_tflops_sparse
    stt_int8 = _ratio(int8_src, int8_dst)
    llm_int8 = _ratio(int8_src, int8_dst)
    decode_bw = _ratio(bw_src, bw_dst)
    tts_fp16 = _ratio(fp16_src, fp16_dst)

    n_buckets = 0 if derate is None else len(derate)
    cc_status = crosscheck.get("status", "missing")
    n_comparisons = len(crosscheck.get("comparisons", []))
    n_flags = len(crosscheck.get("flags", []))
    awaiting_derate = (
        ""
        if derate is not None
        else (
            "\n_Note: `orin_derate_table.csv` not present at render time — populate by "
            "running `python -m synthesis.derate_pipeline` after Wave 2/3 measurements land._\n"
        )
    )

    md = f"""# Derating Methodology (Phase 0 / Phase 3)

## Substrate Chain

- **Measurement:** RunPod H100 PCIe 80GB (CUDA 12.x, vLLM 0.10+)
- **Target:** NVIDIA Jetson AGX Orin 64GB (JetPack 6 / CUDA 12.x)
- Same-vendor, same-stack derate — single hop, no cross-vendor risk surface.

## Per-Stage Derate Ratios (CLAUDE.md §7)

| Stage | Op class | H100 PCIe | Orin 64GB | Ratio |
|-------|----------|-----------|-----------|-------|
| STT encoder | INT8 TOPS sparse | {int8_src:.0f} | {int8_dst:.0f} | {stt_int8:.1f}x |
| LLM prefill | INT8 TOPS sparse | {int8_src:.0f} | {int8_dst:.0f} | {llm_int8:.1f}x |
| LLM decode | LPDDR5 vs HBM3 | {bw_src:.0f} GB/s | {bw_dst:.0f} GB/s | {decode_bw:.1f}x |
| TTS prefill | FP16 TFLOPS sparse | {fp16_src:.0f} | {fp16_dst:.0f} | {tts_fp16:.1f}x |

## Production-Runtime Overheads

- **Ollama-overhead factor** (LLM stages only): {oo_line}
- **ARM-penalty** (universal): {ap_line}

## Bootstrap Confidence Intervals

All Orin predictions report 95% CIs via `scipy.stats.bootstrap` (percentile
method, `n_resamples=10000`) on the derated sample distribution. CI columns:

- `derated_orin_ci_lo_ms`
- `derated_orin_point_ms` (median of derated samples)
- `derated_orin_ci_hi_ms`

## NVIDIA Published-Benchmark Cross-Check

- **Status:** `{cc_status}`
- **Comparisons performed:** {n_comparisons}
- **Flags (divergence > 50%):** {n_flags}

When `status == "awaiting_operator_curation"`, the operator must populate
`data/nvidia_orin_published_benchmarks.json` with NVIDIA-published Jetson AGX
Orin 64GB numbers (`developer.nvidia.com/embedded/jetson-orin-benchmarks`) and
re-run `python -m synthesis.cross_check_nvidia`.

## Coverage

Derate buckets in this run: **{n_buckets}** (gate x stage x concurrency).{awaiting_derate}

## What We Do NOT Know

- Real PSTN audio vs synthetic mu-law behavior (Phase 0 measures only synthetic)
- Sustained Ollama-vs-vLLM behavior on actual Orin hardware under load
- Orin MAXN power-mode sustained-load thermal behavior
- TensorRT-LLM Orin port speedup over Ollama (likely 1.5-2x; unmeasured here)
- Exact CPU/ARM integration penalty on Orin's Cortex-A78AE (10-20% is a
  first-principles estimate; midpoint 1.15x applied)

## Post-Phase-0 Validation Plan

After Phase 0 passes the gate decision, procure 1x Jetson AGX Orin 64GB
Developer Kit (~$2k, ~1 week ship). Run the same harness against the same
pinned model weights. Confirm predicted ratios within +/-20%. Re-issue the
synthesis report as v0.2 with measured-vs-predicted comparison **before** SOW
execution per CLAUDE.md §7.3.
"""
    return md


def main() -> int:
    derate_path = pathlib.Path("results/synthesis/orin_derate_table.csv")
    crosscheck_path = pathlib.Path("results/synthesis/nvidia_crosscheck.json")
    out_path = pathlib.Path("results/synthesis/derate_methodology.md")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(render(derate_path, crosscheck_path))
    print(f"[methodology] -> {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
