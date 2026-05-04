"""Tests for config/loader.py. Exercise each loader against the committed
YAMLs and against malformed YAML (must raise ValidationError, not KeyError).
"""

from __future__ import annotations

import pathlib

import pytest
import yaml
from pydantic import ValidationError

from config import loader


def test_load_models() -> None:
    cfg = loader.load_models()
    assert cfg.stt.repo_id == "Systran/faster-distil-whisper-large-v3"
    assert cfg.llm.quantization == "awq-int4"
    assert cfg.tts_primary.format == "chatterbox"
    assert cfg.tts_fallback.repo_id == "hexgrad/Kokoro-82M"


def test_load_substrates() -> None:
    cfg = loader.load_substrates()
    assert cfg.cuda.provider == "runpod"
    assert cfg.cuda.gpu == "H100_PCIe"
    assert cfg.rocm.provider == "tensorwave"
    assert cfg.rocm.fallback_provider == "vultr"


def test_load_gates() -> None:
    cfg = loader.load_gates()
    assert cfg.g1.asset_corpus == "corpus_500"
    assert cfg.g1.concurrency == [1, 2, 4]
    assert cfg.g3.threshold_sweep_ms is not None
    assert 800 in cfg.g3.threshold_sweep_ms  # default endpoint per SM-69
    assert cfg.g5.reference_prompt_path == "assets/reference_prompt.md"


def test_gates_concurrency_must_be_positive(tmp_path: pathlib.Path) -> None:
    bad = tmp_path / "gates.yaml"
    bad.write_text(
        yaml.safe_dump(
            {
                "g1": {"asset_corpus": "x", "concurrency": [0], "max_minutes": 1},
                "g2": {"asset_corpus": "x", "concurrency": [1], "max_minutes": 1},
                "g3": {"asset_corpus": "x", "concurrency": [1], "max_minutes": 1},
                "g5": {"asset_corpus": "x", "concurrency": [1], "max_minutes": 1},
                "g7": {"asset_corpus": "x", "concurrency": [1], "max_minutes": 1},
                "smoke": {"asset_corpus": "x", "concurrency": [1], "max_minutes": 1},
                "canary": {"asset_corpus": "x", "concurrency": [1], "max_minutes": 1},
            }
        )
    )
    with pytest.raises(ValidationError):
        loader.load_gates(bad)


def test_load_budget_and_projected_total() -> None:
    cfg = loader.load_budget()
    assert cfg.safety_factor == 1.5
    assert cfg.provider_caps["runpod"] == 75.0
    assert cfg.provider_caps["tensorwave"] == 75.0
    assert cfg.provider_caps["vultr"] == 75.0
    # smoke: 1.0 * 1 * 1.5 = 1.5
    assert cfg.projected_total("smoke") == pytest.approx(1.5)
    # g1: 2.0 * 5 * 1.5 = 15.0
    assert cfg.projected_total("g1") == pytest.approx(15.0)


def test_budget_unknown_gate_raises() -> None:
    cfg = loader.load_budget()
    with pytest.raises(KeyError):
        cfg.projected_total("g999")


def test_budget_safety_factor_below_one_rejected(tmp_path: pathlib.Path) -> None:
    bad = tmp_path / "budget.yaml"
    bad.write_text(
        yaml.safe_dump(
            {
                "safety_factor": 0.5,  # invalid
                "provider_caps": {"runpod": 75.0, "tensorwave": 75.0, "vultr": 75.0},
                "gates": {"smoke": {"projected_cost_per_run_usd": 1.0, "expected_runs": 1}},
            }
        )
    )
    with pytest.raises(ValidationError):
        loader.load_budget(bad)
