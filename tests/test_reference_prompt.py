"""Reference prompt content + manifest provenance tests (ASSETS-05, D-07, D-08)."""

from __future__ import annotations

import csv
import hashlib
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[1]
PROMPT = ROOT / "assets" / "reference_prompt.md"
MANIFEST = ROOT / "assets" / "manifest.csv"


def test_reference_prompt_exists() -> None:
    assert PROMPT.exists(), "ASSETS-05: assets/reference_prompt.md must exist"


def test_reference_prompt_contains_placeholder_firm_and_practice() -> None:
    text = PROMPT.read_text()
    assert "{firm_name}" in text, "D-07: must use {firm_name} placeholder"
    assert "{practice_area}" in text, "D-07: must use {practice_area} placeholder"


def test_reference_prompt_contains_five_refusal_categories() -> None:
    text = PROMPT.read_text().lower()
    assert "fees" in text or "hourly rates" in text
    assert "statutes of limitations" in text or "filing deadlines" in text
    assert "case outcomes" in text or "chances of success" in text
    assert "procedural deadlines" in text or "court dates" in text
    assert "substantive legal" in text


def test_reference_prompt_contains_two_scripted_refusals() -> None:
    text = PROMPT.read_text()
    # Substantive-legal handoff phrasing
    assert "let me get an attorney to follow up" in text
    # Fee-question deflection phrasing
    assert "Our attorneys discuss fees in the initial consultation" in text


def test_reference_prompt_no_real_firm_names() -> None:
    """D-07 says generic-firm only; reject obvious real-firm patterns."""
    text = PROMPT.read_text()
    forbidden_patterns = [
        r"\b(LLP|PLLC|LLC) of [A-Z][a-z]+\b",  # "LLP of Smithfield"
        r"\bSuite \d+\b",  # specific addresses
        r"\b\d{3}-\d{3}-\d{4}\b",  # phone numbers
    ]
    for pat in forbidden_patterns:
        assert not re.search(pat, text), f"Real-firm pattern leaked: {pat}"


def test_reference_prompt_sha_matches_manifest() -> None:
    """ASSETS-08: manifest.csv sha256 must match file content."""
    expected = hashlib.sha256(PROMPT.read_bytes()).hexdigest()
    with MANIFEST.open() as f:
        for row in csv.DictReader(f):
            if row["asset_id"] == "reference_prompt":
                assert row["sha256"] == expected, (
                    f"Manifest sha mismatch: csv={row['sha256']} actual={expected}"
                )
                return
    raise AssertionError("reference_prompt row not found in manifest.csv")


def test_manifest_has_locked_header() -> None:
    with MANIFEST.open() as f:
        first = f.readline().strip()
    expected = (
        "asset_id,corpus,path,sha256,license,source,created_utc,"
        "generator_script,generator_seed,kokoro_revision,"
        "intent,adversity_level,persona,duration_s,sample_rate"
    )
    assert first == expected, f"manifest header drift: got {first!r}"
