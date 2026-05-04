"""DR-31 sharing policy validation (DECISION-NC-R14)."""

from __future__ import annotations

import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[1]
DR31 = ROOT / "docs" / "decisions" / "dr-31-sharing-policy.v0.1.0.md"


def test_dr31_v010_exists() -> None:
    assert DR31.exists(), "DECISION-NC-R14 not resolved: dr-31-sharing-policy.v0.1.0.md missing"


def test_dr31_has_status_section() -> None:
    text = DR31.read_text()
    assert re.search(r"^##\s+Status|^\*\*Status:\*\*", text, re.MULTILINE), (
        "DR-31 must have a Status section so operator approval state is explicit"
    )


def test_dr31_locked_stance_present() -> None:
    """The 4 locked stance elements from CONTEXT.md DR-31 Claude's Discretion."""
    text = DR31.read_text().lower()
    assert "methodology" in text and ("prediction range" in text or "predicted" in text)
    assert "raw cloud numbers" in text
    assert "two-tier" in text
    assert "prd" in text and "review" in text


def test_dr31_three_section_structure() -> None:
    """Per RESEARCH Open Q #6: §1 Decision, §2 External rules, §3 Caveats."""
    text = DR31.read_text()
    assert re.search(r"^##\s+§1\s+Decision", text, re.MULTILINE), "missing §1 Decision"
    assert re.search(r"^##\s+§2\s+External", text, re.MULTILINE), (
        "missing §2 External-sharing rules"
    )
    assert re.search(r"^##\s+§3\s+Caveats", text, re.MULTILINE), "missing §3 Caveats"


def test_dr31_cites_authoritative_sources() -> None:
    """Must cite PRD §13 NC-R14 and Pitfall 10 (RESEARCH.md)."""
    text = DR31.read_text()
    assert "NC-R14" in text
    assert "Pitfall 10" in text or "PITFALLS.md" in text


def test_dr31_filename_follows_versioning_convention() -> None:
    """Operator preference: dr-31-sharing-policy.v0.X.Y.md (semver suffix)."""
    assert DR31.name == "dr-31-sharing-policy.v0.1.0.md"
