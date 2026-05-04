"""Manifest schema invariants (ASSETS-08, INFRA-05).

All committed manifest rows must have populated mandatory fields.
SHA-256 of the path file (where path is a real text/json/md file) must
match the manifest's sha256 column.
"""

from __future__ import annotations

import csv
import hashlib
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "assets" / "manifest.csv"

LOCKED_HEADER = (
    "asset_id,corpus,path,sha256,license,source,created_utc,"
    "generator_script,generator_seed,kokoro_revision,"
    "intent,adversity_level,persona,duration_s,sample_rate"
)


def test_manifest_header_locked() -> None:
    first = MANIFEST.read_text().splitlines()[0]
    assert first == LOCKED_HEADER


def _rows() -> list[dict]:
    with MANIFEST.open() as f:
        return list(csv.DictReader(f))


def test_every_row_has_mandatory_fields_populated() -> None:
    for row in _rows():
        assert row["asset_id"], f"empty asset_id in row: {row}"
        assert row["corpus"], f"empty corpus in row: {row}"
        assert row["path"], f"empty path in row: {row}"
        assert re.fullmatch(r"[a-f0-9]{64}", row["sha256"]), f"sha256 must be 64 hex chars: {row}"
        assert row["license"], f"empty license in row: {row}"
        assert row["source"], f"empty source in row: {row}"
        assert row["created_utc"], f"empty created_utc in row: {row}"


def test_sha256_matches_file_for_text_assets() -> None:
    """For non-audio asset paths, sha256 must equal hashlib.sha256(file)."""
    audio_exts = {".wav", ".mp3", ".flac", ".opus", ".ogg"}
    for row in _rows():
        path = ROOT / row["path"]
        if not path.exists():
            # Plan 04 audio rows may not have files yet; skip.
            continue
        if path.suffix.lower() in audio_exts:
            continue  # audio rows checked in Plan 04 tests
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        assert actual == row["sha256"], (
            f"{row['asset_id']}: manifest sha mismatch (csv={row['sha256']} actual={actual})"
        )


def test_asset_ids_unique() -> None:
    ids = [r["asset_id"] for r in _rows()]
    assert len(set(ids)) == len(ids), "duplicate asset_id in manifest"


def test_phase1_required_assets_all_present() -> None:
    """Plan 03 must register: reference_prompt, upl_probes, upl_benign_control, tts_pairs_text."""
    ids = {r["asset_id"] for r in _rows()}
    required = {"reference_prompt", "upl_probes", "upl_benign_control", "tts_pairs_text"}
    missing = required - ids
    assert not missing, f"Phase 1 manifest missing: {missing}"
