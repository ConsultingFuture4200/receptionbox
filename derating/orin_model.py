"""Orin-target derate model (DERATE-02, DERATE-05).

Companion to derating/strix_model.py (Strix Halo target, pre-DR-39 pivot;
retained for reference). Numbers and ratios from CLAUDE.md §7 (DR-39 v0.3.0).

Scaffolded ahead of Plan 03-07 execution per the user's W2-prep request;
exercised end-to-end on synthetic fixture data via tests/test_orin_derate.py
+ tests/test_synthesis_scaffold.py so the pipeline shape is locked before
real Phase 3 measurements arrive.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from .op_classes import StageMeasurement


@dataclass(frozen=True)
class OrinSpec:
    """Hardware spec sheet for Orin-target derating.

    Parallel to derating.op_classes.HardwareSpec but carries the FP16/INT8
    compute lines the §7.2 derate logic needs. Kept separate to avoid
    mutating the frozen HardwareSpec dataclass already in use by strix_model.
    """

    name: str
    bandwidth_gb_s: float
    fp16_tflops_sparse: float
    int8_tops_sparse: float
    power_w_max: int


# CLAUDE.md §7.1 spec sheets
H100_PCIE = OrinSpec(
    name="H100 PCIe 80GB",
    bandwidth_gb_s=2000.0,
    fp16_tflops_sparse=756.0,
    int8_tops_sparse=3026.0,
    power_w_max=350,
)

ORIN_AGX_64GB = OrinSpec(
    name="Jetson AGX Orin 64GB",
    bandwidth_gb_s=204.0,
    fp16_tflops_sparse=32.0,
    int8_tops_sparse=275.0,
    power_w_max=60,
)

# CLAUDE.md §7.2 production-runtime overheads
DEFAULT_OLLAMA_OVERHEAD = 1.4  # midpoint of 1.3-1.5
DEFAULT_ARM_PENALTY = 1.15  # midpoint of 10-20%


def derate_compute_bound_fp16(measured_ms: float, src: OrinSpec, dst: OrinSpec) -> float:
    return measured_ms * (src.fp16_tflops_sparse / dst.fp16_tflops_sparse)


def derate_compute_bound_int8(measured_ms: float, src: OrinSpec, dst: OrinSpec) -> float:
    return measured_ms * (src.int8_tops_sparse / dst.int8_tops_sparse)


def derate_bandwidth_bound(measured_ms: float, src: OrinSpec, dst: OrinSpec) -> float:
    return measured_ms * (src.bandwidth_gb_s / dst.bandwidth_gb_s)


# Stage → derate function dispatch. Plan 03-07 Task 1 may refine per-stage classification.
STAGE_DERATE_FUNCS = {
    "stt_ttft": derate_compute_bound_int8,  # faster-whisper INT8 encoder
    "llm_ttft": derate_compute_bound_int8,  # vLLM AWQ-Int4 prefill
    "llm_decode": derate_bandwidth_bound,  # batch=1 decode is bandwidth-bound
    "tts_first_audio": derate_compute_bound_fp16,  # TTS prefill is FP16
}

_LLM_STAGES = ("llm_ttft", "llm_decode")
_META_KEYS = ("_ollama_overhead", "_arm_penalty", "total_ms")


def derate_pipeline(
    measurements: Iterable[StageMeasurement],
    src: OrinSpec = H100_PCIE,
    dst: OrinSpec = ORIN_AGX_64GB,
    ollama_overhead: float | None = None,
    arm_penalty: float | None = None,
) -> dict:
    """Apply per-stage derate to a list of measurements.

    Ollama overhead applied only to LLM stages (llm_ttft, llm_decode).
    ARM penalty applied to every stage. Defaults from CLAUDE.md §7.2 are
    used when the caller passes None; the applied values are returned in
    the dict under `_ollama_overhead` / `_arm_penalty` so downstream
    rendering knows what defaults landed.
    """
    oo = DEFAULT_OLLAMA_OVERHEAD if ollama_overhead is None else ollama_overhead
    ap = DEFAULT_ARM_PENALTY if arm_penalty is None else arm_penalty
    out: dict = {"_ollama_overhead": oo, "_arm_penalty": ap}
    for m in measurements:
        fn = STAGE_DERATE_FUNCS.get(m.stage)
        if fn is None:
            out[m.stage] = None
            continue
        base = fn(m.measured_ms, src, dst)
        if m.stage in _LLM_STAGES:
            base *= oo
        base *= ap
        out[m.stage] = base
    out["total_ms"] = sum(v for k, v in out.items() if k not in _META_KEYS and v is not None)
    return out
