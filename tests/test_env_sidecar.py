"""env.json sidecar writer tests (HARNESS-05 + D-12).

These tests assert the sidecar:
- round-trips through pydantic on read
- preserves the harness-level reproducibility tuple at the top level
- rejects malformed env blocks via pydantic on read
"""

from __future__ import annotations

import datetime
import json
import pathlib

import pytest
from harness.env_sidecar import read_env_sidecar, write_env_sidecar
from pydantic import ValidationError

from substrate.types import EnvFingerprint


def _make_env_fp(**overrides) -> EnvFingerprint:
    base: dict = dict(
        substrate="cuda",
        image_digest="sha256:deadbeef",
        model_shas={"whisper": "f" * 40, "qwen3": "a" * 40},
        gpu_sku="NVIDIA H100 PCIe",
        gpu_count=1,
        rocm_version=None,
        cuda_version="12.4",
        vllm_version="0.10.1",
        pytorch_version="2.5.1",
        timestamp_utc=datetime.datetime.utcnow().isoformat(),
    )
    base.update(overrides)
    return EnvFingerprint(**base)


def test_write_and_read_roundtrip(tmp_path: pathlib.Path) -> None:
    env_fp = _make_env_fp()
    out = write_env_sidecar(
        env_fp=env_fp,
        run_id="run-test-001",
        gate="smoke",
        git_commit="0" * 40,
        asset_manifest_sha="b" * 64,
        results_dir=tmp_path,
    )
    assert out.exists()
    assert out.parent.name == "smoke"
    assert out.name == "run-test-001.env.json"

    data = read_env_sidecar(out)
    # pydantic re-validation of env block must succeed
    assert data["env"]["substrate"] == "cuda"
    assert data["env"]["image_digest"] == "sha256:deadbeef"


def test_env_sidecar_includes_repro_tuple(tmp_path: pathlib.Path) -> None:
    env_fp = _make_env_fp()
    out = write_env_sidecar(
        env_fp=env_fp,
        run_id="run-test-002",
        gate="g1",
        git_commit="abc1234",
        asset_manifest_sha="c" * 64,
        results_dir=tmp_path,
    )
    payload = json.loads(out.read_text())
    # Top-level harness fields (REPRO-03 tuple support)
    assert payload["run_id"] == "run-test-002"
    assert payload["gate"] == "g1"
    assert payload["git_commit"] == "abc1234"
    assert payload["asset_manifest_sha"] == "c" * 64
    assert payload["schema_version"] == "1.0"
    # env block has all 9 EnvFingerprint fields
    env = payload["env"]
    for key in (
        "substrate",
        "image_digest",
        "model_shas",
        "gpu_sku",
        "gpu_count",
        "rocm_version",
        "cuda_version",
        "vllm_version",
        "pytorch_version",
        "timestamp_utc",
    ):
        assert key in env, f"missing env field: {key}"


def test_env_sidecar_pydantic_rejects_missing_substrate(tmp_path: pathlib.Path) -> None:
    """Write a malformed sidecar (missing env.substrate) and confirm read raises."""
    out = tmp_path / "g1" / "run-malformed.env.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    bad = {
        "schema_version": "1.0",
        "run_id": "run-malformed",
        "gate": "g1",
        "git_commit": "0" * 40,
        "asset_manifest_sha": "0" * 64,
        "env": {
            # substrate intentionally omitted
            "image_digest": "sha256:bad",
            "model_shas": {},
            "gpu_sku": "x",
            "gpu_count": 0,
            "timestamp_utc": "2026-05-06T00:00:00",
        },
    }
    out.write_text(json.dumps(bad))
    with pytest.raises(ValidationError):
        read_env_sidecar(out)
