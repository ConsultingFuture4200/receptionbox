"""Build config/sanity_strata.yaml deterministically from assets/manifest.csv (D-27).

Deterministic, seeded selection of the per-gate asset_id lists used by the
four gate runners during PREFLIGHT-02 sanity. Idempotent given (manifest, seed):
re-running with the same seed produces byte-identical strata content (the only
varying field is the `generated_utc` timestamp).

Selection rules (D-27):
  G1: 10 calls from corpus_500. Group by `intent`; take the top-5 intents by
      frequency (tie-broken alphabetically); from each intent pick 2 calls
      (1 neutral + 1 stressed when both are present, else 2 of whatever exists).
      Final list sorted by asset_id.
  G2: 10 calls from corpus_g711 — 5 with adversity_level == "neutral" and
      5 with adversity_level != "neutral". WARNs if either pool is shy of 5.
  G3: 10 calls from corpus_hesitation — covers the on-disk patterns
      {filler_words, mid_sentence_pause, false_start, stutter}. Plan-spec
      "mid_word_stop" is mapped to the on-disk "stutter" pattern.
  G5: 10 probes from assets/upl_probes — 2 each from refusal categories
      {fee_quote, statute_of_limitations, case_outcome, procedural_deadline}
      = 8, plus 2 benign controls from benign_control.json.

The G5 source is JSON, NOT manifest.csv (UPL probes are text not audio).
"""

from __future__ import annotations

import argparse
import csv
import datetime
import json
import logging
import pathlib
import random
import sys
from collections import defaultdict

import yaml

logger = logging.getLogger(__name__)

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
DEFAULT_PROBES = REPO_ROOT / "assets" / "upl_probes" / "probes.json"
DEFAULT_BENIGN = REPO_ROOT / "assets" / "upl_probes" / "benign_control.json"

# On-disk hesitation patterns (corpus_hesitation rows put the pattern in the
# `adversity_level` column, with `intent` set to "hesitation_adversarial").
HESITATION_PATTERNS = ("filler_words", "mid_sentence_pause", "false_start", "stutter")

# Refusal categories required by D-27.
REFUSAL_CATS = ("fee_quote", "statute_of_limitations", "case_outcome", "procedural_deadline")


def _load_manifest(path: pathlib.Path) -> list[dict]:
    with path.open() as f:
        return list(csv.DictReader(f))


def _seeded_rng(seed: int, salt: str) -> random.Random:
    """Independent RNG per gate so adding a gate doesn't perturb the others.

    `random.Random` accepts int/float/str/bytes only, so we combine seed+salt
    into a deterministic string. Stable across Python versions (no PYTHONHASHSEED
    dependency).
    """
    return random.Random(f"{seed}:{salt}")  # noqa: S311 — non-crypto, deterministic stratification


def _pick_g1(rows: list[dict], rng: random.Random) -> list[str]:
    pool = [r for r in rows if r["corpus"] == "corpus_500"]
    by_intent: dict[str, list[dict]] = defaultdict(list)
    for r in pool:
        by_intent[r.get("intent", "unknown")].append(r)
    # Top-5 intents by frequency. Tie-break alphabetically for stability when
    # the corpus is balanced (50 per intent in our case).
    top5 = sorted(by_intent.items(), key=lambda kv: (-len(kv[1]), kv[0]))[:5]
    picks: list[dict] = []
    for _intent, group in top5:
        neutral = [r for r in group if r.get("adversity_level") == "neutral"]
        stressed = [r for r in group if r.get("adversity_level") not in ("neutral", "")]
        rng.shuffle(neutral)
        rng.shuffle(stressed)
        if neutral and stressed:
            picks.extend([neutral[0], stressed[0]])
        else:
            src = neutral or stressed or group
            picks.extend(src[:2])
    # Pad if any intent had <2 (shouldn't happen on the real corpus).
    pool_ids = {p["asset_id"] for p in picks}
    extras = [r for r in pool if r["asset_id"] not in pool_ids]
    rng.shuffle(extras)
    while len(picks) < 10 and extras:
        picks.append(extras.pop())
    return sorted({p["asset_id"] for p in picks[:10]})


def _pick_g2(rows: list[dict], rng: random.Random) -> list[str]:
    pool = [r for r in rows if r["corpus"] == "corpus_g711"]
    neutral = [r for r in pool if r.get("adversity_level") == "neutral"]
    stressed = [r for r in pool if r.get("adversity_level") not in ("neutral", "")]
    rng.shuffle(neutral)
    rng.shuffle(stressed)
    if len(neutral) < 5:
        logger.warning(f"g2: only {len(neutral)} neutral clips available (wanted 5)")
    if len(stressed) < 5:
        logger.warning(f"g2: only {len(stressed)} stressed clips available (wanted 5)")
    picks = neutral[:5] + stressed[:5]
    return sorted({p["asset_id"] for p in picks})


def _pick_g3(rows: list[dict], rng: random.Random) -> list[str]:
    pool = [r for r in rows if r["corpus"] == "corpus_hesitation"]
    by_pat: dict[str, list[dict]] = defaultdict(list)
    for r in pool:
        # Pattern lives in `adversity_level` for hesitation rows; fall back
        # to `hesitation_pattern` if a future manifest revision adds the column.
        pat = r.get("hesitation_pattern") or r.get("adversity_level") or "unknown"
        by_pat[pat].append(r)
    picks: list[dict] = []
    # Try to seed with up to 3 from each known pattern; trim/pad to 10 below.
    for pat in HESITATION_PATTERNS:
        group = list(by_pat.get(pat, []))
        rng.shuffle(group)
        picks.extend(group[:3])
    if len(picks) < 10:
        # Pad with whatever's left (other patterns / unknowns).
        seen = {p["asset_id"] for p in picks}
        extras = [r for r in pool if r["asset_id"] not in seen]
        rng.shuffle(extras)
        while len(picks) < 10 and extras:
            picks.append(extras.pop())
    rng.shuffle(picks)
    return sorted({p["asset_id"] for p in picks[:10]})


def _pick_g5(probes: list[dict], benign: list[dict], rng: random.Random) -> list[str]:
    by_cat: dict[str, list[dict]] = defaultdict(list)
    for p in probes:
        by_cat[p.get("category", "unknown")].append(p)
    picks: list[str] = []
    for cat in REFUSAL_CATS:
        group = list(by_cat.get(cat, []))
        rng.shuffle(group)
        if len(group) < 2:
            logger.warning(f"g5: only {len(group)} probes available for category {cat} (wanted 2)")
        picks.extend(p["probe_id"] for p in group[:2])
    rng.shuffle(benign)
    if len(benign) < 2:
        logger.warning(f"g5: only {len(benign)} benign controls available (wanted 2)")
    picks.extend(b["probe_id"] for b in benign[:2])
    return sorted(set(picks))


def build(
    *,
    seed: int,
    manifest: pathlib.Path,
    out: pathlib.Path,
    probes_path: pathlib.Path = DEFAULT_PROBES,
    benign_path: pathlib.Path = DEFAULT_BENIGN,
) -> dict:
    """Build a strata dict and write it to `out` as YAML. Returns the dict.

    Idempotent given (manifest contents, seed). Per-gate RNGs are independently
    seeded so adding/removing a gate cannot perturb the existing gates' picks.
    """
    rows = _load_manifest(manifest)
    probes = json.loads(probes_path.read_text()) if probes_path.exists() else []
    benign = json.loads(benign_path.read_text()) if benign_path.exists() else []

    data: dict = {
        "version": "1.0",
        "seed": seed,
        "generated_utc": datetime.datetime.utcnow().isoformat(),
        "manifest_path": str(manifest.relative_to(REPO_ROOT))
        if manifest.is_absolute() and manifest.is_relative_to(REPO_ROOT)
        else str(manifest),
        "strata": {
            "g1": {
                "rule": (
                    "10 calls from corpus_500; top-5 intents by frequency, "
                    "2 picks each (1 neutral + 1 stressed when both available)"
                ),
                "assets": _pick_g1(rows, _seeded_rng(seed, "g1")),
            },
            "g2": {
                "rule": "5 neutral + 5 stressed from corpus_g711",
                "assets": _pick_g2(rows, _seeded_rng(seed, "g2")),
            },
            "g3": {
                "rule": (
                    "10 hesitation clips covering on-disk patterns "
                    "{filler_words, mid_sentence_pause, false_start, stutter}"
                ),
                "assets": _pick_g3(rows, _seeded_rng(seed, "g3")),
            },
            "g5": {
                "rule": ("8 probes (2 each x 4 refusal categories) + 2 benign controls"),
                "assets": _pick_g5(probes, benign, _seeded_rng(seed, "g5")),
            },
        },
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(yaml.safe_dump(data, sort_keys=False, default_flow_style=False))
    return data


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="tools.build_strata")
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--manifest", type=pathlib.Path, default=REPO_ROOT / "assets" / "manifest.csv")
    p.add_argument("--out", type=pathlib.Path, default=REPO_ROOT / "config" / "sanity_strata.yaml")
    p.add_argument("--probes", type=pathlib.Path, default=DEFAULT_PROBES)
    p.add_argument("--benign", type=pathlib.Path, default=DEFAULT_BENIGN)
    args = p.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    data = build(
        seed=args.seed,
        manifest=args.manifest,
        out=args.out,
        probes_path=args.probes,
        benign_path=args.benign,
    )
    for gate, info in data["strata"].items():
        print(f"{gate}: {len(info['assets'])} assets")
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
