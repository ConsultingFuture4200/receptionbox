"""UPL probe corpus tests (ASSETS-04 / D-04)."""

from __future__ import annotations

import csv
import hashlib
import json
import pathlib
import re
import subprocess
from collections import Counter

ROOT = pathlib.Path(__file__).resolve().parents[1]
PROBES = ROOT / "assets" / "upl_probes" / "probes.json"
BENIGN = ROOT / "assets" / "upl_probes" / "benign_control.json"
MANIFEST = ROOT / "assets" / "manifest.csv"

REFUSAL_HINTS = {"substantive_legal_handoff", "fee_question_deflection"}
CATEGORIES = {
    "prompt_injection",
    "fee_quote",
    "statute_of_limitations",
    "case_outcome",
    "procedural_deadline",
    "substantive_legal_general",
}


def test_probe_count_is_200() -> None:
    data = json.loads(PROBES.read_text())
    assert len(data) == 200


def test_benign_count_is_50() -> None:
    data = json.loads(BENIGN.read_text())
    assert len(data) == 50


def test_probes_meet_per_category_minimums() -> None:
    """D-04 mandatory minimums."""
    data = json.loads(PROBES.read_text())
    counts = Counter(p["category"] for p in data)
    assert counts["prompt_injection"] >= 30
    assert counts["fee_quote"] >= 20
    assert counts["statute_of_limitations"] >= 20
    assert counts["case_outcome"] >= 20
    assert counts["procedural_deadline"] >= 20
    assert sum(counts.values()) == 200


def test_probe_categories_are_in_taxonomy() -> None:
    data = json.loads(PROBES.read_text())
    for p in data:
        assert p["category"] in CATEGORIES, f"unknown category: {p['category']}"


def test_probe_ids_unique_and_formatted() -> None:
    data = json.loads(PROBES.read_text())
    ids = [p["probe_id"] for p in data]
    assert len(set(ids)) == 200
    for pid in ids:
        assert re.fullmatch(r"upl-\d{4}", pid), f"bad probe_id format: {pid}"


def test_every_probe_has_required_fields() -> None:
    data = json.loads(PROBES.read_text())
    for p in data:
        assert p["expected_label"] == "refuse"
        assert p["refusal_phrasing_hint"] in REFUSAL_HINTS
        assert isinstance(p["prompt"], str) and p["prompt"].strip()


def test_fee_quote_uses_fee_deflection_hint() -> None:
    data = json.loads(PROBES.read_text())
    for p in data:
        if p["category"] == "fee_quote":
            assert p["refusal_phrasing_hint"] == "fee_question_deflection"


def test_benign_probes_all_expect_answer() -> None:
    data = json.loads(BENIGN.read_text())
    for p in data:
        assert p["expected_label"] == "answer"
        assert re.fullmatch(r"benign-\d{4}", p["probe_id"])


def test_no_real_legal_facts_in_probes() -> None:
    """D-04 content-cleanliness lint."""
    data = json.loads(PROBES.read_text())
    forbidden = [
        re.compile(r"\b\d+\s+U\.S\.(C\.)?\s*§?\s*\d+", re.IGNORECASE),
        re.compile(r"\b\d+\s+[A-Z]\.\d+d?\s+\d+"),
        re.compile(r"\bbar\s+#?\s*\d+", re.IGNORECASE),
    ]
    for p in data:
        for pat in forbidden:
            assert not pat.search(p["prompt"]), (
                f"Real-fact pattern leaked in {p['probe_id']}: {p['prompt']!r}"
            )


def test_authoring_is_idempotent() -> None:
    """Running author_probes.py twice produces byte-identical files."""
    sha_before_probes = hashlib.sha256(PROBES.read_bytes()).hexdigest()
    sha_before_benign = hashlib.sha256(BENIGN.read_bytes()).hexdigest()
    result = subprocess.run(
        ["uv", "run", "python", "-m", "assets.upl_probes.author_probes"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    assert result.returncode == 0
    sha_after_probes = hashlib.sha256(PROBES.read_bytes()).hexdigest()
    sha_after_benign = hashlib.sha256(BENIGN.read_bytes()).hexdigest()
    assert sha_before_probes == sha_after_probes, "probes.json not idempotent"
    assert sha_before_benign == sha_after_benign, "benign_control.json not idempotent"


def test_manifest_has_upl_rows_with_matching_sha() -> None:
    expected_probes_sha = hashlib.sha256(PROBES.read_bytes()).hexdigest()
    expected_benign_sha = hashlib.sha256(BENIGN.read_bytes()).hexdigest()
    found = {}
    with MANIFEST.open() as f:
        for row in csv.DictReader(f):
            if row["asset_id"] in {"upl_probes", "upl_benign_control"}:
                found[row["asset_id"]] = row
    assert "upl_probes" in found
    assert "upl_benign_control" in found
    assert found["upl_probes"]["sha256"] == expected_probes_sha
    assert found["upl_benign_control"]["sha256"] == expected_benign_sha
    assert found["upl_probes"]["corpus"] == "corpus_upl"
    assert found["upl_benign_control"]["corpus"] == "corpus_benign"
