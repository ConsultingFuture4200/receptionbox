"""Tests for tools/check_asset_manifest.py (INFRA-05 hook script).

Each test runs the hook with a CWD pointed at a tmp_path that mimics the
repo layout so we don't pollute the real assets/ directory.
"""

from __future__ import annotations

import pathlib
import subprocess

HOOK = pathlib.Path(__file__).resolve().parents[1] / "tools" / "check_asset_manifest.py"


def _run(cwd: pathlib.Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["python", str(HOOK)],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
    )


def test_empty_repo_state_passes(tmp_path: pathlib.Path) -> None:
    (tmp_path / "assets").mkdir()
    result = _run(tmp_path)
    assert result.returncode == 0, result.stderr


def test_audio_listed_in_manifest_passes(tmp_path: pathlib.Path) -> None:
    assets = tmp_path / "assets"
    assets.mkdir()
    (assets / "foo.wav").write_bytes(b"RIFF")
    (assets / "manifest.csv").write_text(
        "asset_id,corpus,path,sha256,license,source,created_utc\n"
        "foo,corpus_test,assets/foo.wav,abc123,synthetic,test,2026-05-04\n"
    )
    result = _run(tmp_path)
    assert result.returncode == 0, result.stderr


def test_audio_unlisted_fails(tmp_path: pathlib.Path) -> None:
    assets = tmp_path / "assets"
    assets.mkdir()
    (assets / "rogue.wav").write_bytes(b"RIFF")
    (assets / "manifest.csv").write_text("asset_id,corpus,path,sha256,license,source,created_utc\n")
    result = _run(tmp_path)
    assert result.returncode == 1
    assert "rogue.wav" in result.stderr


def test_manifest_missing_path_column_fails(tmp_path: pathlib.Path) -> None:
    assets = tmp_path / "assets"
    assets.mkdir()
    (assets / "manifest.csv").write_text("asset_id,corpus\nfoo,test\n")
    result = _run(tmp_path)
    assert result.returncode == 1
    assert "no 'path' column" in result.stderr
