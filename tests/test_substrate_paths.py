"""Tests for substrate/paths.py — bootstrap-index-aware model dir resolver.

The resolver is the seam that lets gate-runner defaults carry the *logical*
lockfile name (e.g. `/models/distil_whisper_large_v3_int8`) instead of the
on-disk `<repo_safe>/<revision>` path. See substrate/paths.py.
"""

from __future__ import annotations

import json
import logging
import pathlib

import pytest

from substrate.paths import resolve_model_dir


def _write_index(target: pathlib.Path, models: dict[str, dict]) -> pathlib.Path:
    target.mkdir(parents=True, exist_ok=True)
    idx = target / ".bootstrap_index.json"
    idx.write_text(
        json.dumps(
            {"schema_version": "1.0", "models": models},
            indent=2,
            sort_keys=True,
        )
    )
    return idx


def test_resolves_logical_name_via_bootstrap_index(tmp_path: pathlib.Path) -> None:
    rev = "c3058b475261292e64a0412df1d2681c06260fab"
    idx = _write_index(
        tmp_path / "models",
        {
            "distil_whisper_large_v3_int8": {
                "repo_id": "Systran/faster-distil-whisper-large-v3",
                "revision": rev,
            },
        },
    )
    out = resolve_model_dir("/models/distil_whisper_large_v3_int8", bootstrap_index=idx)
    expected = tmp_path / "models" / "Systran__faster-distil-whisper-large-v3" / rev
    assert out == str(expected)


def test_passes_through_existing_directory_unchanged(tmp_path: pathlib.Path) -> None:
    real_dir = tmp_path / "models" / "real" / "abc123"
    real_dir.mkdir(parents=True)
    # No bootstrap index exists — must NOT be consulted because the input is
    # already a usable directory.
    out = resolve_model_dir(str(real_dir), bootstrap_index=tmp_path / "does-not-exist.json")
    assert out == str(real_dir)


def test_missing_index_returns_input_unchanged(
    tmp_path: pathlib.Path, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.WARNING)
    out = resolve_model_dir(
        "/models/distil_whisper_large_v3_int8",
        bootstrap_index=tmp_path / "missing.json",
    )
    assert out == "/models/distil_whisper_large_v3_int8"
    assert any("bootstrap index not found" in rec.message for rec in caplog.records)


def test_missing_entry_returns_input_unchanged(
    tmp_path: pathlib.Path, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.WARNING)
    idx = _write_index(
        tmp_path / "models",
        {"some_other_model": {"repo_id": "a/b", "revision": "x"}},
    )
    out = resolve_model_dir("/models/distil_whisper_large_v3_int8", bootstrap_index=idx)
    assert out == "/models/distil_whisper_large_v3_int8"
    assert any("no bootstrap entry" in rec.message for rec in caplog.records)


def test_malformed_index_returns_input_unchanged(
    tmp_path: pathlib.Path, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.WARNING)
    idx = tmp_path / "models" / ".bootstrap_index.json"
    idx.parent.mkdir(parents=True, exist_ok=True)
    idx.write_text("{not valid json")
    out = resolve_model_dir("/models/distil_whisper_large_v3_int8", bootstrap_index=idx)
    assert out == "/models/distil_whisper_large_v3_int8"
    assert any("could not read bootstrap index" in rec.message for rec in caplog.records)


def test_entry_missing_repo_or_revision_returns_input_unchanged(
    tmp_path: pathlib.Path, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.WARNING)
    idx = _write_index(
        tmp_path / "models",
        {"distil_whisper_large_v3_int8": {"repo_id": "Systran/faster-distil-whisper-large-v3"}},
    )
    out = resolve_model_dir("/models/distil_whisper_large_v3_int8", bootstrap_index=idx)
    assert out == "/models/distil_whisper_large_v3_int8"
    assert any("missing repo_id/revision" in rec.message for rec in caplog.records)


def test_repo_id_slash_replaced_with_double_underscore(tmp_path: pathlib.Path) -> None:
    rev = "deadbeef" * 5
    idx = _write_index(
        tmp_path / "models",
        {"k": {"repo_id": "org/sub/name", "revision": rev}},
    )
    out = resolve_model_dir("k", bootstrap_index=idx)
    # Every '/' in repo_id becomes '__' (matches tools/cache_bootstrap._safe).
    assert out == str(tmp_path / "models" / "org__sub__name" / rev)
