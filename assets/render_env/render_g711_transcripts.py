"""Materialise reference transcripts for the corpus_g711 stratified subset.

For every `corpus_g711` row in `assets/manifest.csv`, write a sibling
`.txt` file containing the source dialogue's `utterance` text. The
g711 row's `source` column is `transcoded_from:<call-NNNN>`; the
matching utterance is in `assets/scripts/dialogues.json` keyed by
`script_id`.

These transcripts are gates/g2/runner.py's reference text. The runner
resolves them via `audio_path.with_suffix(".txt")` when no
`transcript_path` is set on the asset row. Without these files G2
errors with FileNotFoundError on every row (sanity run 2026-05-09).

Pure-stdlib (csv + json + pathlib) so it can run in any Python without
the render_env venv. Idempotent: rewrites are byte-identical when
dialogues.json hasn't changed.

Run from the repo root:
    python assets/render_env/render_g711_transcripts.py
"""

from __future__ import annotations

import csv
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
DIALOGUES = ROOT / "assets" / "scripts" / "dialogues.json"
MANIFEST = ROOT / "assets" / "manifest.csv"
TARGET_DIR = ROOT / "assets" / "corpus_g711"

_SOURCE_PREFIX = "transcoded_from:"


def main() -> int:
    dialogues = {d["script_id"]: d for d in json.loads(DIALOGUES.read_text())}
    with MANIFEST.open() as f:
        rows = [r for r in csv.DictReader(f) if r["corpus"] == "corpus_g711"]
    if not rows:
        print("FATAL: no corpus_g711 rows in manifest.csv", file=sys.stderr)
        return 1

    TARGET_DIR.mkdir(parents=True, exist_ok=True)
    written = 0
    for r in rows:
        source = r.get("source", "")
        if not source.startswith(_SOURCE_PREFIX):
            print(
                f"FATAL: {r['asset_id']} source={source!r} not '{_SOURCE_PREFIX}<script_id>'",
                file=sys.stderr,
            )
            return 1
        script_id = source[len(_SOURCE_PREFIX) :]
        dialogue = dialogues.get(script_id)
        if dialogue is None:
            print(
                f"FATAL: {r['asset_id']}: source script_id {script_id!r} not in dialogues.json",
                file=sys.stderr,
            )
            return 1
        out = TARGET_DIR / f"{r['asset_id']}.txt"
        out.write_text(dialogue["utterance"].strip() + "\n")
        written += 1
    print(f"Wrote {written} transcripts -> assets/corpus_g711/*.txt")
    return 0


if __name__ == "__main__":
    sys.exit(main())
