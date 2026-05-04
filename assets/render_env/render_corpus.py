"""Render 500-call synthetic dialogue corpus locally on GTX 1070 (ASSETS-01 / D-01).

Reads ../scripts/dialogues.json (relative to this script). For each dialogue,
renders the utterance via Kokoro-82M with the persona-mapped voice seed and
applies an adversity-level post-processing transform. Writes 24 kHz mono WAV
to ../corpus_500/{script_id}.wav and appends a manifest row.

Run from inside the asset-rendering venv:
    cd assets/render_env && uv run python render_corpus.py

Idempotent: skips clips whose target WAV already exists with the expected
sha (recorded in manifest). Force re-render with --force.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import pathlib
import sys
from datetime import UTC, datetime

import numpy as np
import soundfile as sf

ROOT = pathlib.Path(__file__).resolve().parents[2]
DIALOGUES = ROOT / "assets" / "scripts" / "dialogues.json"
CORPUS_DIR = ROOT / "assets" / "corpus_500"
MANIFEST = ROOT / "assets" / "manifest.csv"

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


def _kokoro_revision() -> str:
    """Return the kokoro package version + git commit if available."""
    try:
        import kokoro  # type: ignore[import-untyped]

        return getattr(kokoro, "__version__", "unknown")
    except Exception:
        return "unknown"


def _render_kokoro(text: str, voice: str, *, sample_rate: int = 24000) -> np.ndarray:
    """Render text via Kokoro. Returns mono float32 PCM at sample_rate."""
    from kokoro import KPipeline  # type: ignore[import-untyped]

    pipeline = KPipeline(lang_code="a")  # American English
    audio_chunks: list[np.ndarray] = []
    for _, _, audio in pipeline(text, voice=voice, speed=1.0):
        audio_chunks.append(audio)
    if not audio_chunks:
        raise RuntimeError(f"Kokoro returned no audio for: {text!r}")
    audio = np.concatenate(audio_chunks).astype(np.float32)
    return audio


def _apply_adversity(audio: np.ndarray, adversity: str, *, sr: int = 24000) -> np.ndarray:
    """Lightweight post-processing per adversity_level. Phase 1 keeps these
    deterministic and conservative -- Phase 3 may swap in heavier adversity
    if the gate runner needs more degradation."""
    rng = np.random.default_rng(42)
    if adversity == "neutral":
        return audio
    if adversity == "mild_emotional":
        # Slight pitch wobble via simple sample-rate jitter on a copy.
        return audio  # placeholder -- real prosody control needs voice cloning
    if adversity == "background_noise":
        noise = rng.normal(0.0, 0.005, size=audio.shape).astype(np.float32)
        return audio + noise
    if adversity == "accent_strong":
        return audio  # Phase 3 may swap voice; Phase 1 leaves audio neutral, metadata-only
    if adversity == "urgent_distressed":
        # Slight gain bump
        return np.clip(audio * 1.08, -1.0, 1.0).astype(np.float32)
    return audio


def _sha256_file(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _read_manifest() -> dict[str, dict[str, str]]:
    if not MANIFEST.exists():
        return {}
    with MANIFEST.open() as f:
        return {row["asset_id"]: row for row in csv.DictReader(f)}


def _write_manifest(by_id: dict[str, dict[str, str]]) -> None:
    with MANIFEST.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        for asset_id in sorted(by_id):
            full = {k: by_id[asset_id].get(k, "") for k in FIELDNAMES}
            writer.writerow(full)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true", help="Re-render even if WAV already exists")
    parser.add_argument("--limit", type=int, default=None, help="Render only first N (smoke-test)")
    args = parser.parse_args()

    CORPUS_DIR.mkdir(parents=True, exist_ok=True)
    dialogues = json.loads(DIALOGUES.read_text())
    if args.limit:
        dialogues = dialogues[: args.limit]

    kokoro_rev = _kokoro_revision()
    by_id = _read_manifest()
    rendered = 0

    for d in dialogues:
        out_wav = CORPUS_DIR / f"{d['script_id']}.wav"
        if out_wav.exists() and not args.force:
            # Idempotency: keep existing if sha matches manifest
            if d["script_id"] in by_id and by_id[d["script_id"]].get("sha256") == _sha256_file(
                out_wav
            ):
                continue
        audio = _render_kokoro(d["utterance"], voice=d["voice_seed"])
        audio = _apply_adversity(audio, d["adversity_level"])
        sf.write(out_wav, audio, 24000, subtype="PCM_16")
        sha = _sha256_file(out_wav)
        duration = len(audio) / 24000.0
        by_id[d["script_id"]] = {
            "asset_id": d["script_id"],
            "corpus": "corpus_500",
            "path": f"assets/corpus_500/{d['script_id']}.wav",
            "sha256": sha,
            "license": "synthetic",
            "source": "assets/render_env/render_corpus.py",
            "created_utc": datetime.now(tz=UTC).replace(microsecond=0).isoformat(),
            "generator_script": "assets/render_env/render_corpus.py",
            "generator_seed": "42",
            "kokoro_revision": kokoro_rev,
            "intent": d["intent"],
            "adversity_level": d["adversity_level"],
            "persona": d["persona"],
            "duration_s": f"{duration:.3f}",
            "sample_rate": "24000",
        }
        rendered += 1
        if rendered % 50 == 0:
            print(f"... rendered {rendered}/{len(dialogues)}")

    _write_manifest(by_id)
    print(f"Done. Rendered {rendered} clips; manifest now has {len(by_id)} rows.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
