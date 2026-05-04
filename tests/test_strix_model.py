"""Per-stage derating tests on synthetic data (DERATE-01)."""

from __future__ import annotations

import pytest

from derating.op_classes import OpClass, StageMeasurement
from derating.strix_model import (
    H100_SXM,
    MI300X,
    STRIX_HALO,
    derate_bandwidth_bound,
    derate_compute_bound,
    derate_pipeline,
    derate_stage,
)


def test_compute_bound_strix_12_5x_slower_than_mi300x() -> None:
    assert derate_compute_bound(100.0, MI300X, STRIX_HALO) == 1250.0


def test_bandwidth_bound_uses_bandwidth_ratio() -> None:
    # MI300X 4240 GB/s realized -> Strix Halo 212 GB/s = 20x slower
    assert derate_bandwidth_bound(10.0, MI300X, STRIX_HALO) == pytest.approx(200.0)


def test_h100_to_strix_compute_bound_uses_factor() -> None:
    # Both H100 and MI300X have prompt_processing_factor=1.0; same ratio applies
    assert derate_compute_bound(50.0, H100_SXM, STRIX_HALO) == 625.0


def test_unknown_op_returns_none_widens_ci() -> None:
    m = StageMeasurement("stt_prefill", OpClass.UNKNOWN, 100.0, n=500)
    assert derate_stage(m, MI300X, STRIX_HALO) is None


def test_pipeline_sums_per_stage() -> None:
    measurements = [
        StageMeasurement("stt_prefill", OpClass.COMPUTE_BOUND, 50.0, n=500),
        StageMeasurement("llm_ttft", OpClass.COMPUTE_BOUND, 100.0, n=500),
        StageMeasurement("llm_decode_per_tok", OpClass.BANDWIDTH_BOUND, 5.0, n=500),
    ]
    out = derate_pipeline(measurements, MI300X, STRIX_HALO)
    # 50*12.5 + 100*12.5 + 5*20 = 625 + 1250 + 100 = 1975
    assert out["stt_prefill"] == 625.0
    assert out["llm_ttft"] == 1250.0
    assert out["llm_decode_per_tok"] == pytest.approx(100.0)
    assert out["total_ms"] == pytest.approx(1975.0)


def test_pipeline_total_none_if_any_unknown_pitfall_2() -> None:
    measurements = [
        StageMeasurement("stt_prefill", OpClass.COMPUTE_BOUND, 100.0, n=500),
        StageMeasurement("llm_decode_per_tok", OpClass.UNKNOWN, 5.0, n=500),
    ]
    out = derate_pipeline(measurements, MI300X, STRIX_HALO)
    assert out["total_ms"] is None
    assert out["stt_prefill"] == 1250.0
    assert out["llm_decode_per_tok"] is None


def test_no_e2e_shortcut_exists() -> None:
    """Pitfall 2 — there must be no `derate_e2e(ms, ratio)` function."""
    import derating.strix_model as m

    assert not hasattr(m, "derate_e2e"), "Pitfall 2 violation: derate_e2e shortcut must not exist"
