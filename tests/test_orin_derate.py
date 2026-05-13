"""Unit tests for derating/orin_model.py (DERATE-02, DERATE-05).

Mirrors the test stanzas in Plan 03-07 Task 1; scaffolded ahead of
plan execution per the W2-prep request.
"""

from __future__ import annotations

import pytest

from derating.op_classes import OpClass, StageMeasurement
from derating.orin_model import (
    DEFAULT_ARM_PENALTY,
    DEFAULT_OLLAMA_OVERHEAD,
    H100_PCIE,
    ORIN_AGX_64GB,
    derate_bandwidth_bound,
    derate_compute_bound_fp16,
    derate_compute_bound_int8,
    derate_pipeline,
)


def test_compute_bound_fp16_uses_fp16_tflops_ratio() -> None:
    expected = 100.0 * (756.0 / 32.0)
    actual = derate_compute_bound_fp16(100.0, H100_PCIE, ORIN_AGX_64GB)
    assert actual == pytest.approx(expected, rel=1e-9)
    assert actual == pytest.approx(2362.5, rel=0.01)


def test_compute_bound_int8_uses_int8_tops_ratio() -> None:
    expected = 100.0 * (3026.0 / 275.0)
    actual = derate_compute_bound_int8(100.0, H100_PCIE, ORIN_AGX_64GB)
    assert actual == pytest.approx(expected, rel=1e-9)
    assert actual == pytest.approx(1100.36, rel=0.01)


def test_bandwidth_bound_uses_bandwidth_ratio() -> None:
    expected = 10.0 * (2000.0 / 204.0)
    actual = derate_bandwidth_bound(10.0, H100_PCIE, ORIN_AGX_64GB)
    assert actual == pytest.approx(expected, rel=1e-9)
    assert actual == pytest.approx(98.04, rel=0.01)


def test_pipeline_applies_ollama_overhead_only_to_llm_stages() -> None:
    measurements = [
        StageMeasurement("stt_ttft", OpClass.COMPUTE_BOUND, 100.0, n=500),
        StageMeasurement("llm_ttft", OpClass.COMPUTE_BOUND, 100.0, n=500),
        StageMeasurement("llm_decode", OpClass.BANDWIDTH_BOUND, 10.0, n=500),
        StageMeasurement("tts_first_audio", OpClass.COMPUTE_BOUND, 50.0, n=500),
    ]
    out = derate_pipeline(
        measurements,
        H100_PCIE,
        ORIN_AGX_64GB,
        ollama_overhead=1.4,
        arm_penalty=1.15,
    )
    # llm_ttft should have ollama factor applied; stt_ttft should not.
    stt = 100.0 * (3026.0 / 275.0) * 1.15
    llm_ttft = 100.0 * (3026.0 / 275.0) * 1.4 * 1.15
    llm_decode = 10.0 * (2000.0 / 204.0) * 1.4 * 1.15
    tts = 50.0 * (756.0 / 32.0) * 1.15
    assert out["stt_ttft"] == pytest.approx(stt, rel=1e-6)
    assert out["llm_ttft"] == pytest.approx(llm_ttft, rel=1e-6)
    assert out["llm_decode"] == pytest.approx(llm_decode, rel=1e-6)
    assert out["tts_first_audio"] == pytest.approx(tts, rel=1e-6)
    assert out["total_ms"] == pytest.approx(stt + llm_ttft + llm_decode + tts, rel=1e-6)


def test_pipeline_defaults_emitted_when_none() -> None:
    measurements = [
        StageMeasurement("llm_ttft", OpClass.COMPUTE_BOUND, 100.0, n=500),
    ]
    out = derate_pipeline(measurements, H100_PCIE, ORIN_AGX_64GB)
    assert out["_ollama_overhead"] == DEFAULT_OLLAMA_OVERHEAD
    assert out["_arm_penalty"] == DEFAULT_ARM_PENALTY


def test_unknown_stage_lands_as_none() -> None:
    measurements = [
        StageMeasurement("some_unmapped_stage", OpClass.UNKNOWN, 100.0, n=500),
    ]
    out = derate_pipeline(measurements, H100_PCIE, ORIN_AGX_64GB)
    assert out["some_unmapped_stage"] is None
    assert out["total_ms"] == 0.0
