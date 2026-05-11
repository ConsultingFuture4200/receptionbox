"""Tests for tools/build_strata.py + config/sanity_strata.yaml (D-27).

Drives the deterministic stratification config used by the four gate runners
during PREFLIGHT-02 sanity. The actual manifest is the source of truth —
these tests run against the real assets/manifest.csv so the asserted shape
matches what the runners will see on the H100 pod.
"""

from __future__ import annotations

import csv
import pathlib

import yaml

from tools import build_strata

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
MANIFEST = REPO_ROOT / "assets" / "manifest.csv"
STRATA_FILE = REPO_ROOT / "config" / "sanity_strata.yaml"


def _manifest_rows() -> list[dict]:
    with MANIFEST.open() as f:
        return list(csv.DictReader(f))


def test_build_strata_seed_42_is_deterministic(tmp_path: pathlib.Path) -> None:
    """Two builds with same seed produce byte-identical YAML (modulo timestamps)."""
    out1 = tmp_path / "a.yaml"
    out2 = tmp_path / "b.yaml"
    d1 = build_strata.build(seed=42, manifest=MANIFEST, out=out1)
    d2 = build_strata.build(seed=42, manifest=MANIFEST, out=out2)
    # Strip the only nondeterministic field (generated_utc) before comparing.
    d1.pop("generated_utc", None)
    d2.pop("generated_utc", None)
    assert d1 == d2, "build is not deterministic at fixed seed"


def test_strata_g1_has_10_assets_from_corpus_500() -> None:
    data = build_strata.build(seed=42, manifest=MANIFEST, out=pathlib.Path("/tmp/_strata_g1.yaml"))
    g1 = data["strata"]["g1"]["assets"]
    assert len(g1) == 10, f"g1 expected 10 picks, got {len(g1)}"
    rows = _manifest_rows()
    corpus_500_ids = {r["asset_id"] for r in rows if r["corpus"] == "corpus_500"}
    assert all(a in corpus_500_ids for a in g1), "g1 picks must all be corpus_500"


def test_strata_g2_has_5_neutral_and_5_stressed() -> None:
    data = build_strata.build(seed=42, manifest=MANIFEST, out=pathlib.Path("/tmp/_strata_g2.yaml"))
    g2 = data["strata"]["g2"]["assets"]
    assert len(g2) == 10
    rows = {r["asset_id"]: r for r in _manifest_rows() if r["corpus"] == "corpus_g711"}
    neutral = sum(1 for a in g2 if rows[a].get("adversity_level") == "neutral")
    stressed = sum(1 for a in g2 if rows[a].get("adversity_level") not in ("neutral", ""))
    # Strict: corpus_g711 has 100 neutral + 100 non-neutral, so 5/5 is achievable.
    assert neutral == 5, f"g2 expected 5 neutral, got {neutral}"
    assert stressed == 5, f"g2 expected 5 stressed, got {stressed}"


def test_strata_g3_covers_at_least_3_hesitation_patterns() -> None:
    data = build_strata.build(seed=42, manifest=MANIFEST, out=pathlib.Path("/tmp/_strata_g3.yaml"))
    g3 = data["strata"]["g3"]["assets"]
    assert len(g3) == 10
    rows = {r["asset_id"]: r for r in _manifest_rows() if r["corpus"] == "corpus_hesitation"}
    # On-disk manifest uses adversity_level for the pattern: filler_words /
    # mid_sentence_pause / false_start / stutter. Plan-spec mid_word_stop maps
    # to stutter. Allow either field name; require >=3 distinct patterns.
    patterns = {rows[a].get("adversity_level") for a in g3}
    assert len(patterns) >= 3, f"g3 expected >=3 distinct hesitation patterns, got {patterns}"


def test_strata_g5_has_2_per_refusal_category_and_2_controls() -> None:
    data = build_strata.build(seed=42, manifest=MANIFEST, out=pathlib.Path("/tmp/_strata_g5.yaml"))
    g5 = data["strata"]["g5"]["assets"]
    assert len(g5) == 10
    # Build a probe-id -> category map by re-reading the source JSON files
    # because UPL probes do NOT live in manifest.csv.
    import json

    probes = json.loads((REPO_ROOT / "assets" / "upl_probes" / "probes.json").read_text())
    benign = json.loads((REPO_ROOT / "assets" / "upl_probes" / "benign_control.json").read_text())
    pid_to_cat = {p["probe_id"]: p.get("category", "") for p in probes}
    benign_ids = {p["probe_id"] for p in benign}

    refusal_cats = ("fee_quote", "statute_of_limitations", "case_outcome", "procedural_deadline")
    counts: dict[str, int] = {c: 0 for c in refusal_cats}
    controls = 0
    for pid in g5:
        if pid in benign_ids:
            controls += 1
        elif pid in pid_to_cat and pid_to_cat[pid] in refusal_cats:
            counts[pid_to_cat[pid]] += 1
    assert all(counts[c] == 2 for c in refusal_cats), f"refusal counts: {counts}"
    assert controls == 2, f"controls: {controls}"


def test_strata_yaml_round_trips() -> None:
    """The committed strata file is valid YAML with the expected shape."""
    assert STRATA_FILE.exists(), f"missing {STRATA_FILE}"
    data = yaml.safe_load(STRATA_FILE.read_text())
    assert data["seed"] == 42
    assert data["version"] == "1.0"
    for g in ("g1", "g2", "g3", "g5"):
        assert g in data["strata"], f"missing gate {g}"
        assert "assets" in data["strata"][g]
        assert "rule" in data["strata"][g]


def test_strata_changing_seed_changes_assets(tmp_path: pathlib.Path) -> None:
    """Different seed → different assets in at least one gate."""
    out_a = tmp_path / "a.yaml"
    out_b = tmp_path / "b.yaml"
    d_a = build_strata.build(seed=42, manifest=MANIFEST, out=out_a)
    d_b = build_strata.build(seed=43, manifest=MANIFEST, out=out_b)
    diff = any(
        d_a["strata"][g]["assets"] != d_b["strata"][g]["assets"] for g in ("g1", "g2", "g3", "g5")
    )
    assert diff, "seed change had zero effect on any gate's selection"


def test_committed_strata_matches_seed_42_build(tmp_path: pathlib.Path) -> None:
    """Idempotency: running the builder reproduces the committed file's strata
    for the seed-42-built keys (g1, g2, g3, g5).

    Plan 03-01 Task 4 added Phase 3 placeholder strata (g1_full..g7_full) that
    are not produced by build_strata.py (operator iterates the full corpus
    directly). The equality check is scoped to the seed-42 keys only; the
    builder's output must be a subset of the committed strata.
    """
    out = tmp_path / "fresh.yaml"
    fresh = build_strata.build(seed=42, manifest=MANIFEST, out=out)
    committed = yaml.safe_load(STRATA_FILE.read_text())
    for key in fresh["strata"]:
        assert key in committed["strata"], f"committed file missing seed-42 key: {key}"
        assert fresh["strata"][key] == committed["strata"][key], (
            f"committed config/sanity_strata.yaml drifted from build_strata.py output for {key}"
        )


def test_runner_loads_strata_via_helper() -> None:
    """The G1 runner's _select_assets honors a strata file by selecting matching ids."""
    from gates.g1 import runner as g1_runner

    # Load the committed strata file's g1 list.
    data = yaml.safe_load(STRATA_FILE.read_text())
    wanted = set(data["strata"]["g1"]["assets"])

    rows = [r for r in _manifest_rows() if r["corpus"] == "corpus_500"]
    import argparse

    args = argparse.Namespace(gate="g1", n_calls=None, strata=str(STRATA_FILE), corpus="corpus_500")
    selected = g1_runner._select_assets(args, rows)
    selected_ids = {r["asset_id"] for r in selected}
    assert selected_ids == wanted, f"runner picks {selected_ids - wanted} not in strata"
