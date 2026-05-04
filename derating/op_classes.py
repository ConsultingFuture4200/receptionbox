"""Op classification + hardware spec dataclasses for per-stage derating."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class OpClass(Enum):
    """Per-stage classification driving derate strategy.

    - COMPUTE_BOUND: STT prefill (Whisper encoder), TTS first-chunk transformer
      prefill, LLM TTFT (prefill). Use prompt_processing_factor ratio.
    - BANDWIDTH_BOUND: LLM decode tokens/sec (memory-bound at small batch).
      Use bandwidth ratio.
    - UNKNOWN: gfx1151 kernel-coverage gap; widen CI; total_ms becomes None.
      Phase 3 AUDIT-02 produces the kernel-coverage table that resolves UNKNOWN
      back to COMPUTE_BOUND or BANDWIDTH_BOUND for Phase 4.
    """

    COMPUTE_BOUND = "compute_bound"
    BANDWIDTH_BOUND = "bandwidth_bound"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class HardwareSpec:
    """Realized (not peak) bandwidth + prompt-processing factor.

    bandwidth_gb_s: realized memory bandwidth in GB/s (use ~80% of peak).
    prompt_processing_factor: relative compute speed for prefill ops; 1.0
        baseline on MI300X. Strix Halo ~12.5x slower per Phoronix Nov 2025.
    """

    name: str
    bandwidth_gb_s: float
    prompt_processing_factor: float


@dataclass(frozen=True)
class StageMeasurement:
    """Single per-stage measurement consumed by derate_stage / derate_pipeline."""

    stage: str  # 'stt_prefill' | 'llm_ttft' | 'llm_decode_per_tok' | 'tts_first_chunk'
    op_class: OpClass
    measured_ms: float
    n: int  # sample size (used by Phase 4 bootstrap CI; unused in Phase 1)
