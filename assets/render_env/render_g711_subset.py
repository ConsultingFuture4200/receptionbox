"""Render 200-clip G.711 stratified subset (ASSETS-02 / D-02).

Selects 100 neutral + 100 stressed clips deterministically from
corpus_500 using RNG seed 42. Transcodes each via ffmpeg with the locked
flags from ../g711.py: aresample=resampler=soxr:precision=28, pcm_mulaw,
8 kHz mono.

Run after render_corpus.py:
    cd assets/render_env && uv run python render_g711_subset.py
"""

from __future__ import annotations

import csv
import hashlib
import pathlib
import random
import subprocess
import sys
from datetime import UTC, datetime

ROOT = pathlib.Path(__file__).resolve().parents[2]
SOURCE_DIR = ROOT / "assets" / "corpus_500"
TARGET_DIR = ROOT / "assets" / "corpus_g711"
MANIFEST = ROOT / "assets" / "manifest.csv"

NEUTRAL_TARGET = 100
STRESSED_TARGET = 100
STRESSED_LEVELS = {
    "mild_emotional",
    "accent_strong",
    "background_noise",
    "urgent_distressed",
}

FIELDNAMES = [
    "asset_id",
    "corpus",
    "path",
    "sha256",
    "license",
    "source",
    "created_utc",
    "generator_script",
    "generator_seed",
    "kokoro_revision",
    "intent",
    "adversity_level",
    "persona",
    "duration_s",
    "sample_rate",
]


def _read_manifest_by_id() -> dict[str, dict[str, str]]:
    with MANIFEST.open() as f:
        return {row["asset_id"]: row for row in csv.DictReader(f)}


def _ffmpeg_transcode(in_wav: pathlib.Path, out_wav: pathlib.Path) -> None:
    cmd = [
        "ffmpeg",
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        str(in_wav),
        "-ac",
        "1",
        "-ar",
        "8000",
        "-af",
        "aresample=resampler=soxr:precision=28",
        "-c:a",
        "pcm_mulaw",
        str(out_wav),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg failed for {in_wav.name}: {result.stderr}")


def _sha256_file(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    by_id = _read_manifest_by_id()
    candidates = [r for r in by_id.values() if r["corpus"] == "corpus_500"]
    if len(candidates) < 500:
        print(
            f"FATAL: corpus_500 has only {len(candidates)} clips; need 500",
            file=sys.stderr,
        )
        return 1

    rng = random.Random(42)
    neutral_pool = sorted(
        [r for r in candidates if r["adversity_level"] == "neutral"],
        key=lambda r: r["asset_id"],
    )
    stressed_pool = sorted(
        [r for r in candidates if r["adversity_level"] in STRESSED_LEVELS],
        key=lambda r: r["asset_id"],
    )
    rng.shuffle(neutral_pool)
    rng.shuffle(stressed_pool)
    selected = neutral_pool[:NEUTRAL_TARGET] + stressed_pool[:STRESSED_TARGET]
    if len(selected) != 200:
        print(
            f"FATAL: stratified selection yielded {len(selected)}, expected 200",
            file=sys.stderr,
        )
        return 1

    TARGET_DIR.mkdir(parents=True, exist_ok=True)
    for i, src_row in enumerate(selected, start=1):
        src = ROOT / src_row["path"]
        out = TARGET_DIR / f"g711-{i:04d}.wav"
        _ffmpeg_transcode(src, out)
        sha = _sha256_file(out)
        by_id[f"g711-{i:04d}"] = {
            "asset_id": f"g711-{i:04d}",
            "corpus": "corpus_g711",
            "path": f"assets/corpus_g711/g711-{i:04d}.wav",
            "sha256": sha,
            "license": "synthetic_transcoded",
            "source": f"transcoded_from:{src_row['asset_id']}",
            "created_utc": datetime.now(tz=UTC).replace(microsecond=0).isoformat(),
            "generator_script": "assets/render_env/render_g711_subset.py",
            "generator_seed": "42",
            "kokoro_revision": src_row.get("kokoro_revision", ""),
            "intent": src_row["intent"],
            "adversity_level": src_row["adversity_level"],
            "persona": src_row["persona"],
            "duration_s": src_row["duration_s"],
            "sample_rate": "8000",
        }
    with MANIFEST.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        for asset_id in sorted(by_id):
            full = {k: by_id[asset_id].get(k, "") for k in FIELDNAMES}
            writer.writerow(full)
    print("G.711 subset: 100 neutral + 100 stressed -> assets/corpus_g711/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
