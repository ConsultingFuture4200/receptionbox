"""Companion docs presence test (D-13 / DECISION-DOCS).

This test is the gate on ROADMAP success criterion #3 — operator must drop
the 6 files into docs/ before Phase 1 closes.
"""

from __future__ import annotations

import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"

REQUIRED = [
    "thumbox-technical-prd-v2_1-2026-04-16.md",
    "thumbox-business-prd-v2_1-2026-04-16.md",
    "addendum-receptionbox-discovery-v0_2-2026-04-22.md",
    "addendum-hardware-pivot-strix-halo-v0_1-2026-04-23.md",
    "receptionbox-technical-feasibility-memo-v0_3-2026-04-23.md",
    "receptionbox-virtual-benchmark-plan-v0_1-2026-05-03.md",
]


def test_all_six_companion_docs_present() -> None:
    missing = [name for name in REQUIRED if not (DOCS / name).exists()]
    assert not missing, (
        f"D-13 / DECISION-DOCS: operator must drop these files into docs/ "
        f"before Phase 1 closes (see docs/COMPANION-DOCS-CHECKLIST.md): {missing}"
    )


def test_companion_docs_checklist_exists() -> None:
    assert (DOCS / "COMPANION-DOCS-CHECKLIST.md").exists(), (
        "docs/COMPANION-DOCS-CHECKLIST.md missing — required for operator handoff"
    )
