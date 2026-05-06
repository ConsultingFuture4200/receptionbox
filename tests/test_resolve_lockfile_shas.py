"""Unit tests for tools.resolve_lockfile_shas (Plan 02-05 Task 1).

The resolver MUST NOT hit the network during tests — every test passes a
fake `HfApi`-style object and a fake `hf_hub_download` callable. This keeps
CI hermetic and proves the resolver's contract:

  - Pending revisions resolve to the SHA returned by `repo_info(...).sha`.
  - LFS files: take `sibling.lfs.sha256` directly (no download).
  - Non-LFS files under the size cap: download and stream-hash.
  - Non-LFS files over the size cap: refuse with RuntimeError.
  - Already-populated entries: idempotent no-op (no `repo_info` calls).
  - `files: []` entries: populate with the canonical filename set
    (weight extensions + canonical config files).
  - `--dry-run`: do not write back to the lockfile.
"""

from __future__ import annotations

import hashlib
import pathlib
import tempfile
from types import SimpleNamespace
from typing import Any

import pytest
import yaml

from tools import resolve_lockfile_shas as resolver


def _sib(rfilename: str, *, lfs_sha: str | None = None, size: int = 1024) -> SimpleNamespace:
    lfs = SimpleNamespace(sha256=lfs_sha) if lfs_sha else None
    return SimpleNamespace(rfilename=rfilename, size=size, lfs=lfs)


class _FakeApi:
    def __init__(self, sha: str, siblings: list[SimpleNamespace]) -> None:
        self._sha = sha
        self._siblings = siblings
        self.calls: list[dict[str, Any]] = []

    def repo_info(
        self,
        repo_id: str,
        revision: str = "main",
        files_metadata: bool = False,
    ) -> SimpleNamespace:
        self.calls.append(
            {"repo_id": repo_id, "revision": revision, "files_metadata": files_metadata}
        )
        return SimpleNamespace(sha=self._sha, siblings=self._siblings)


def _fake_hf_download_unused(**_kwargs: Any) -> str:
    raise AssertionError("hf_hub_download must not be called in this test")


@pytest.fixture
def lockfile(tmp_path: pathlib.Path) -> pathlib.Path:
    p = tmp_path / "models.lock.yaml"
    p.write_text(
        "# top comment\n"
        "models:\n"
        "  - name: m1\n"
        "    repo_id: org/m1\n"
        "    revision: pending\n"
        "    files:\n"
        "      - filename: model.safetensors\n"
        "        sha256: pending\n"
        "      - filename: config.json\n"
        "        sha256: pending\n"
    )
    return p


def test_resolves_revision_and_lfs_sha(lockfile: pathlib.Path, tmp_path: pathlib.Path) -> None:
    api = _FakeApi(
        sha="a" * 40,
        siblings=[
            _sib("model.safetensors", lfs_sha="b" * 64, size=2_000_000_000),
            _sib("config.json", size=2),
        ],
    )
    cfg_local = tmp_path / "config.json"
    cfg_local.write_bytes(b"{}")

    def _hf_dl(**_kwargs: Any) -> str:
        return str(cfg_local)

    data = resolver.resolve(lockfile=lockfile, api=api, hf_download=_hf_dl)

    m = data["models"][0]
    assert m["revision"] == "a" * 40
    sha_by_name = {f["filename"]: f["sha256"] for f in m["files"]}
    assert sha_by_name["model.safetensors"] == "b" * 64
    assert sha_by_name["config.json"] == hashlib.sha256(b"{}").hexdigest()


def test_refuses_non_lfs_over_cap(lockfile: pathlib.Path) -> None:
    api = _FakeApi(
        sha="a" * 40,
        siblings=[
            _sib("model.safetensors", size=2_000_000_000),  # NO lfs metadata + huge
            _sib("config.json", size=64),
        ],
    )
    with pytest.raises(RuntimeError, match="non-LFS"):
        resolver.resolve(lockfile=lockfile, api=api, hf_download=_fake_hf_download_unused)


def test_idempotent_when_already_populated(tmp_path: pathlib.Path) -> None:
    lf = tmp_path / "lock.yaml"
    lf.write_text(
        "models:\n"
        "  - name: m1\n"
        "    repo_id: org/m1\n"
        "    revision: " + ("a" * 40) + "\n"
        "    files:\n"
        "      - filename: model.safetensors\n"
        "        sha256: " + ("b" * 64) + "\n"
    )
    api = _FakeApi(sha="x" * 40, siblings=[])
    data = resolver.resolve(lockfile=lf, api=api, hf_download=_fake_hf_download_unused)
    # Unchanged; api.repo_info should NOT be called.
    assert api.calls == []
    assert data["models"][0]["revision"] == "a" * 40


def test_populates_empty_files_with_canonical_set(tmp_path: pathlib.Path) -> None:
    lf = tmp_path / "lock.yaml"
    lf.write_text(
        "models:\n  - name: m1\n    repo_id: org/m1\n    revision: pending\n    files: []\n"
    )
    siblings = [
        _sib("model.safetensors", lfs_sha="c" * 64, size=2_000_000_000),
        _sib("config.json", size=2),  # non-LFS, small -> downloaded
        _sib("README.md", size=128),  # NON-canonical -> skipped
    ]
    api = _FakeApi(sha="d" * 40, siblings=siblings)
    cfg_local = tmp_path / "cfg.json"
    cfg_local.write_bytes(b"{}")

    def _hf_dl(**_kwargs: Any) -> str:
        return str(cfg_local)

    data = resolver.resolve(lockfile=lf, api=api, hf_download=_hf_dl)
    names = {f["filename"] for f in data["models"][0]["files"]}
    assert "model.safetensors" in names
    assert "config.json" in names
    assert "README.md" not in names


def test_dry_run_does_not_write(lockfile: pathlib.Path, tmp_path: pathlib.Path) -> None:
    original = lockfile.read_text()
    api = _FakeApi(
        sha="a" * 40,
        siblings=[
            _sib("model.safetensors", lfs_sha="b" * 64, size=2_000_000_000),
            _sib("config.json", size=2),
        ],
    )
    cfg_local = pathlib.Path(tempfile.mkdtemp()) / "config.json"
    cfg_local.write_bytes(b"{}")

    def _hf_dl(**_kwargs: Any) -> str:
        return str(cfg_local)

    resolver.resolve(lockfile=lockfile, dry_run=True, api=api, hf_download=_hf_dl)
    assert lockfile.read_text() == original


def test_preserves_top_of_file_comment(lockfile: pathlib.Path, tmp_path: pathlib.Path) -> None:
    """The `# top comment` line at the head of the lockfile must survive a write."""
    api = _FakeApi(
        sha="a" * 40,
        siblings=[
            _sib("model.safetensors", lfs_sha="b" * 64, size=2_000_000_000),
            _sib("config.json", size=2),
        ],
    )
    cfg_local = tmp_path / "config.json"
    cfg_local.write_bytes(b"{}")
    resolver.resolve(
        lockfile=lockfile,
        api=api,
        hf_download=lambda **_kw: str(cfg_local),
    )
    text = lockfile.read_text()
    assert text.startswith("# top comment"), f"top comment lost: {text[:80]!r}"
    # And the body still parses.
    data = yaml.safe_load(text)
    assert data["models"][0]["revision"] == "a" * 40
