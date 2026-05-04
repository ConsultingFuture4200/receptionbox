"""Per-stage roofline derating (DERATE-01).

Phase 1 ships the skeleton + unit tests on synthetic data. Phase 4 fills
the real arithmetic-intensity classifications using Phase 3 measurements.

Pitfall 2 enforcement: there is NO `derate_e2e(ms, ratio)` shortcut. All
end-to-end derates go through `derate_pipeline(measurements, src, dst)`
which sums per-stage derates classified by op_class.
"""

from .op_classes import HardwareSpec, OpClass, StageMeasurement
from .strix_model import (
    H100_SXM,
    MI300X,
    STRIX_HALO,
    derate_bandwidth_bound,
    derate_compute_bound,
    derate_pipeline,
    derate_stage,
)

__all__ = [
    "H100_SXM",
    "MI300X",
    "STRIX_HALO",
    "HardwareSpec",
    "OpClass",
    "StageMeasurement",
    "derate_bandwidth_bound",
    "derate_compute_bound",
    "derate_pipeline",
    "derate_stage",
]
