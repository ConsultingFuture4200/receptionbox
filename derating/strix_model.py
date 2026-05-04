"""Per-stage roofline derating model (DERATE-01).

Hardware specs (verified from CLAUDE.md §7.1 + STACK.md §7.1; May 2026):
- MI300X: 5.3 TB/s HBM3 peak; ~80% realized = 4.24 TB/s
- H100 SXM: 3.35 TB/s HBM3
- Strix Halo (Ryzen AI Max+ 395): 256 GB/s LPDDR5X-8000 spec; ~212 GB/s realized
  (rocm_bandwidth_test); prompt-processing penalty 10-15x vs MI300X (Phoronix
  Nov 2025); midpoint 12.5x used here, refined in Phase 4.
"""

from __future__ import annotations

from collections.abc import Iterable

from .op_classes import HardwareSpec, OpClass, StageMeasurement

MI300X = HardwareSpec(
    name="MI300X",
    bandwidth_gb_s=4240.0,  # 80% of 5.3 TB/s peak
    prompt_processing_factor=1.0,
)

H100_SXM = HardwareSpec(
    name="H100 SXM",
    bandwidth_gb_s=3350.0,
    prompt_processing_factor=1.0,
)

STRIX_HALO = HardwareSpec(
    name="Strix Halo",
    bandwidth_gb_s=212.0,  # realized via rocm_bandwidth_test
    prompt_processing_factor=12.5,  # 10-15x midpoint per Phoronix Nov 2025
)


def derate_compute_bound(measured_ms: float, src: HardwareSpec, dst: HardwareSpec) -> float:
    """Compute-bound stages: STT prefill, TTS first-chunk, LLM TTFT.

    Uses prompt_processing_factor ratio. dst slower -> larger output.
    """
    return measured_ms * (dst.prompt_processing_factor / src.prompt_processing_factor)


def derate_bandwidth_bound(measured_ms: float, src: HardwareSpec, dst: HardwareSpec) -> float:
    """Bandwidth-bound stages: LLM decode tokens/sec.

    Uses bandwidth ratio. dst slower (lower bandwidth_gb_s) -> larger output.
    """
    return measured_ms * (src.bandwidth_gb_s / dst.bandwidth_gb_s)


def derate_stage(
    measurement: StageMeasurement,
    src: HardwareSpec,
    dst: HardwareSpec,
) -> float | None:
    """Dispatch on op_class. UNKNOWN returns None — caller must widen CI."""
    if measurement.op_class is OpClass.COMPUTE_BOUND:
        return derate_compute_bound(measurement.measured_ms, src, dst)
    if measurement.op_class is OpClass.BANDWIDTH_BOUND:
        return derate_bandwidth_bound(measurement.measured_ms, src, dst)
    if measurement.op_class is OpClass.UNKNOWN:
        return None
    raise ValueError(f"Unknown OpClass: {measurement.op_class}")


def derate_pipeline(
    measurements: Iterable[StageMeasurement],
    src: HardwareSpec,
    dst: HardwareSpec,
) -> dict[str, float | None]:
    """Sum per-stage derates -> end-to-end estimate.

    Returns dict mapping each stage name to its derated ms, plus
    `total_ms` = sum or None if any stage is UNKNOWN.

    Pitfall 2 enforcement: caller cannot bypass per-stage classification.
    """
    out: dict[str, float | None] = {}
    total: float | None = 0.0
    for m in measurements:
        derated = derate_stage(m, src, dst)
        out[m.stage] = derated
        if derated is None:
            total = None
        elif total is not None:
            total += derated
    out["total_ms"] = total
    return out
