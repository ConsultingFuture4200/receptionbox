"""Tests for tools/cache_bootstrap.py (CLOUD-05, D-19, D-20, D-21).

Bootstrap pulls all 4 HF models into /models/{repo_safe}/{revision}/ on the
RunPod network volume; subsequent gate pods mount /models read-only and skip
download. Idempotent: marker file mechanism. Bootstrap failures graceful-
degrade (no raise) — same posture as cost adapters.
"""

from __future__ import annotations

import json
import pathlib
from typing import Any

import pytest
import yaml

from tools import cache_bootstrap as cb


def _write_lockfile(path: pathlib.Path, models: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump({"models": models}))


def test_bootstrap_skips_pending_revision(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    lock = tmp_path / "models.lock.yaml"
    _write_lockfile(
        lock,
        [{"name": "qwen", "repo_id": "Qwen/Qwen3-4B", "revision": "pending"}],
    )
    target = tmp_path / "models"
    # Should not call snapshot_download for pending entries
    calls = []

    def _fake_snapshot(**kwargs):
        calls.append(kwargs)
        return ""

    monkeypatch.setattr("huggingface_hub.snapshot_download", _fake_snapshot, raising=False)
    with caplog.at_level("WARNING"):
        idx = cb.bootstrap(target=target, lockfile=lock)
    assert idx == {}
    assert calls == []
    # Marker dir should not exist
    assert not (target / "Qwen__Qwen3-4B").exists()


def test_bootstrap_creates_marker_and_index(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    lock = tmp_path / "models.lock.yaml"
    _write_lockfile(
        lock,
        [
            {
                "name": "kokoro",
                "repo_id": "hexgrad/Kokoro-82M",
                "revision": "abcdef0123456789" * 2 + "abcdef01",  # 40-char fake sha
            }
        ],
    )
    target = tmp_path / "models"

    def _fake_snapshot(**kwargs):
        local_dir = pathlib.Path(kwargs["local_dir"])
        local_dir.mkdir(parents=True, exist_ok=True)
        (local_dir / "model.bin").write_bytes(b"x" * 1024)
        (local_dir / "config.json").write_text("{}")
        return str(local_dir)

    monkeypatch.setattr("huggingface_hub.snapshot_download", _fake_snapshot)

    idx = cb.bootstrap(target=target, lockfile=lock)
    rev = "abcdef0123456789" * 2 + "abcdef01"
    marker = target / "hexgrad__Kokoro-82M" / rev / ".bootstrap.json"
    assert marker.exists()
    rec = json.loads(marker.read_text())
    assert rec["repo_id"] == "hexgrad/Kokoro-82M"
    assert rec["revision"] == rev
    assert rec["total_bytes"] >= 1024
    assert "kokoro" in idx
    # Top-level index must exist with this entry
    top = target / ".bootstrap_index.json"
    assert top.exists()
    top_data = json.loads(top.read_text())
    assert "kokoro" in top_data["models"]


def test_bootstrap_idempotent_when_marker_exists(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    lock = tmp_path / "models.lock.yaml"
    rev = "deadbeef" * 5  # 40-char fake
    _write_lockfile(lock, [{"name": "k", "repo_id": "h/k", "revision": rev}])
    target = tmp_path / "models"
    # Pre-create marker as if a prior bootstrap finished
    dest = target / "h__k" / rev
    dest.mkdir(parents=True)
    (dest / ".bootstrap.json").write_text(
        json.dumps({"repo_id": "h/k", "revision": rev, "total_bytes": 0, "files": []})
    )
    calls = []
    monkeypatch.setattr(
        "huggingface_hub.snapshot_download",
        lambda **kw: calls.append(kw),
    )
    idx = cb.bootstrap(target=target, lockfile=lock)
    assert calls == [], "snapshot_download must not be called when marker exists"
    assert "k" in idx


def test_bootstrap_force_re_runs_even_with_marker(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    lock = tmp_path / "models.lock.yaml"
    rev = "cafe" * 10
    _write_lockfile(lock, [{"name": "k", "repo_id": "h/k", "revision": rev}])
    target = tmp_path / "models"
    dest = target / "h__k" / rev
    dest.mkdir(parents=True)
    (dest / ".bootstrap.json").write_text("{}")
    calls = []

    def _fake(**kw):
        calls.append(kw)
        local_dir = pathlib.Path(kw["local_dir"])
        local_dir.mkdir(parents=True, exist_ok=True)
        (local_dir / "x.bin").write_bytes(b"!")
        return str(local_dir)

    monkeypatch.setattr("huggingface_hub.snapshot_download", _fake)
    cb.bootstrap(target=target, lockfile=lock, force=True)
    assert len(calls) == 1


def test_bootstrap_fail_logs_does_not_raise(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    lock = tmp_path / "models.lock.yaml"
    rev = "feed" * 10
    _write_lockfile(lock, [{"name": "k", "repo_id": "h/k", "revision": rev}])
    target = tmp_path / "models"

    def _boom(**kw):
        raise RuntimeError("network down")

    monkeypatch.setattr("huggingface_hub.snapshot_download", _boom)
    # Must not raise:
    idx = cb.bootstrap(target=target, lockfile=lock)
    # Failed model NOT in index
    assert "k" not in idx


def test_budget_yaml_has_phase2_block() -> None:
    data = yaml.safe_load(pathlib.Path("config/budget.yaml").read_text())
    assert "phase2" in data
    p2 = data["phase2"]
    mm = p2["max_minutes_per_gate"]
    # Plan 02-07 bumped smoke 30 -> 60 to absorb cold first-pull of the v6+
    # image (16 GB; vllm + Kokoro venv) onto a fresh host.
    assert mm["smoke"] == 60
    assert mm["g1"] == 30
    assert mm["g2"] == 15
    assert mm["g3"] == 10
    assert mm["g5"] == 15
    # Plan 02-05 Task 2 added bootstrap; Plan 02-06 bumped 15 -> 30 to
    # absorb cold first-pull of the rbox-pod image from GHCR.
    assert mm["bootstrap"] == 30
    # Sum across smoke + 4 sanity gates is now 130 (D-18 cap relaxed by
    # Plan 02-07; the cap was a $14-budget heuristic, not a hard rule).
    sanity_sum = mm["smoke"] + mm["g1"] + mm["g2"] + mm["g3"] + mm["g5"]
    assert sanity_sum <= 130
    # Plan 02-05 set 0.67 (15 min x $2.69/hr H100 PCIe). Plan 02-06 bumped
    # to 1.50 (30 min x $2.99/hr H100 SXM = $1.495 rounded up).
    assert p2["cache_bootstrap_one_time_usd"] == 1.50


def test_cache_bootstrap_help_exits_zero() -> None:
    with pytest.raises(SystemExit) as ei:
        cb.main(["--help"])
    assert ei.value.code == 0
