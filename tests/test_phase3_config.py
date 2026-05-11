"""Phase 3 config validation (Plan 03-01 Task 4).

Asserts that config/budget.yaml's phase3 block + config/sanity_strata.yaml's
tts row are present and structurally correct. These config rows are consumed
by:

- orchestration/vultr_mi300x.py (max_minutes_per_gate, hourly rates)
- substrate/rocm.py:_read_tts_primary() (tts.primary, D-37)
- Plan 03-02 chatterbox_d1 kill-switch (chatterbox_d1_spend_cap_usd)
- Plan 03-04 / 03-05 gate runners (rocm_budget_total_usd ledger init)
"""

from __future__ import annotations

import pathlib

import yaml

ROOT = pathlib.Path(__file__).resolve().parents[1]


def test_budget_yaml_loads_cleanly() -> None:
    data = yaml.safe_load((ROOT / "config" / "budget.yaml").read_text())
    assert isinstance(data, dict)
    assert "phase3" in data
    assert "phase2" in data  # existing block preserved


def test_phase3_max_minutes_per_gate() -> None:
    data = yaml.safe_load((ROOT / "config" / "budget.yaml").read_text())
    mm = data["phase3"]["max_minutes_per_gate"]
    assert mm["chatterbox_d1"] == 120
    assert mm["g1"] == 120
    assert mm["g2"] == 45
    assert mm["g3"] == 20
    assert mm["g5"] == 30
    assert mm["g7"] == 45
    assert mm["audit_co_residency"] == 30
    assert mm["audit_op_coverage"] == 30


def test_phase3_chatterbox_d1_spend_cap() -> None:
    data = yaml.safe_load((ROOT / "config" / "budget.yaml").read_text())
    assert data["phase3"]["chatterbox_d1_spend_cap_usd"] == 4.0


def test_phase3_rocm_budget_total() -> None:
    data = yaml.safe_load((ROOT / "config" / "budget.yaml").read_text())
    assert data["phase3"]["rocm_budget_total_usd"] == 54.0


def test_phase3_hourly_rates() -> None:
    data = yaml.safe_load((ROOT / "config" / "budget.yaml").read_text())
    rates = data["phase3"]["hourly_rate_usd"]
    assert rates["vultr"] == 1.85
    assert rates["tensorwave"] == 1.71


def test_phase3_provider_default() -> None:
    data = yaml.safe_load((ROOT / "config" / "budget.yaml").read_text())
    assert data["phase3"]["provider_default"] == "vultr"


def test_sanity_strata_tts_primary_present() -> None:
    data = yaml.safe_load((ROOT / "config" / "sanity_strata.yaml").read_text())
    assert "tts" in data
    primary = data["tts"]["primary"]
    assert primary in {"chatterbox", "kokoro"}, (
        f"tts.primary must be 'chatterbox' or 'kokoro', got {primary!r}"
    )


def test_sanity_strata_tts_primary_default_is_chatterbox() -> None:
    """Default ships as chatterbox (D-37); Day-1 kill-switch flips to kokoro."""
    data = yaml.safe_load((ROOT / "config" / "sanity_strata.yaml").read_text())
    assert data["tts"]["primary"] == "chatterbox"


def test_substrate_rocm_read_tts_primary_returns_chatterbox() -> None:
    """ROCmSubstrate._read_tts_primary() reads the on-disk file directly."""
    from substrate.rocm import ROCmSubstrate

    sub = ROCmSubstrate(
        vllm_url="http://x:1",
        vllm_model="qwen",
        whisper_model_dir="/nope",
        chatterbox_url="http://x:2",
        kokoro_url="http://x:3",
    )
    # _DEFAULT_SANITY_STRATA points at config/sanity_strata.yaml relative to cwd.
    # Tests run from repo root so this resolves to the real file.
    assert sub._read_tts_primary() == "chatterbox"


def test_phase3_full_strata_present() -> None:
    """Phase 3 gate runners (Plan 03-03/03-04) read these strata entries."""
    data = yaml.safe_load((ROOT / "config" / "sanity_strata.yaml").read_text())
    strata = data["strata"]
    for key in ("g1_full", "g2_full", "g3_full", "g5_full", "g7_full"):
        assert key in strata, f"missing Phase 3 stratum: {key}"
        # Empty assets list signals "iterate full corpus".
        assert isinstance(strata[key].get("assets"), list)
