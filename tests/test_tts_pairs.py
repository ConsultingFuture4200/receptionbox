"""TTS A/B text pair tests (ASSETS-06)."""

from __future__ import annotations

import csv
import hashlib
import json
import pathlib
import re
import subprocess

ROOT = pathlib.Path(__file__).resolve().parents[1]
PAIRS = ROOT / "assets" / "tts_pairs" / "pairs.json"
MANIFEST = ROOT / "assets" / "manifest.csv"


def test_30_pairs_exist() -> None:
    data = json.loads(PAIRS.read_text())
    assert len(data) == 30


def test_pair_ids_unique_and_formatted() -> None:
    data = json.loads(PAIRS.read_text())
    ids = [p["pair_id"] for p in data]
    assert len(set(ids)) == 30
    for pid in ids:
        assert re.fullmatch(r"tts-\d{4}", pid)


def test_every_pair_has_required_fields() -> None:
    data = json.loads(PAIRS.read_text())
    for p in data:
        assert isinstance(p["text"], str) and p["text"].strip()
        assert isinstance(p["edge_case_kinds"], list) and p["edge_case_kinds"]
        assert "notes" in p


def test_manifest_has_tts_row_with_matching_sha() -> None:
    expected = hashlib.sha256(PAIRS.read_bytes()).hexdigest()
    with MANIFEST.open() as f:
        for row in csv.DictReader(f):
            if row["asset_id"] == "tts_pairs_text":
                assert row["sha256"] == expected
                assert row["corpus"] == "corpus_tts_pairs"
                return
    raise AssertionError("tts_pairs_text row not found in manifest.csv")


def test_authoring_idempotent() -> None:
    sha_before = hashlib.sha256(PAIRS.read_bytes()).hexdigest()
    result = subprocess.run(
        ["uv", "run", "python", "-m", "assets.tts_pairs.author_pairs"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    assert result.returncode == 0
    sha_after = hashlib.sha256(PAIRS.read_bytes()).hexdigest()
    assert sha_before == sha_after
