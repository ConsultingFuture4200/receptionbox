"""Render hesitation adversarial corpus (ASSETS-03 / D-03).

50 TTS-generated clips with controlled hesitation patterns: filler words
("uh", "um", "like"), mid-sentence pauses (rendered as silence inserts),
false starts, mid-word stops. Per-clip ground-truth turn-end timestamps
recorded in turn_truth.json.

Synthesis report frames G3 as "soft pass with caveats" per DR-28; the
synthetic-only gap is named in the "What we did not measure" section.
"""

from __future__ import annotations

import csv
import hashlib
import json
import pathlib
import sys
from datetime import UTC, datetime

import numpy as np
import soundfile as sf

ROOT = pathlib.Path(__file__).resolve().parents[2]
TARGET_DIR = ROOT / "assets" / "corpus_hesitation"
TURN_TRUTH = TARGET_DIR / "turn_truth.json"
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

# Each entry is a tuple (utterance_text, hesitation_kind, voice_seed).
# Voices rotate across the persona pool. Texts are short utterances with
# embedded hesitation; turn-end ms is "this is where the speaker is done".

HESITATION_CLIPS: list[tuple[str, str, str]] = [
    ("Um, I just wanted to ask about, uh, scheduling a consultation.", "filler_words", "af_heart"),
    ("So, like, I had a question about, you know, my contract.", "filler_words", "af_alloy"),
    ("I -- I think I need to talk to someone about a, a billing issue.", "false_start", "am_adam"),
    ("Could -- could I -- speak to an attorney please?", "stutter", "af_bella"),
    (
        "I have a question about ... [pause] ... my appointment time.",
        "mid_sentence_pause",
        "am_michael",
    ),
    (
        "Yeah, hi, I'm calling about, um, the paperwork I dropped off last week.",
        "filler_words",
        "af_nicole",
    ),
    ("Just wanted to -- to confirm -- the time for tomorrow.", "stutter", "am_eric"),
    ("Hi, I -- never mind, let me start over. I need to reschedule.", "false_start", "af_sky"),
    (
        "Could you tell me ... [pause] ... what time you close today?",
        "mid_sentence_pause",
        "am_liam",
    ),
    ("Um, hello? Is anyone there?", "filler_words", "af_river"),
    ("So I was wondering, uh, like, is the office open Saturdays?", "filler_words", "af_heart"),
    ("I have a -- I have an appointment -- on Thursday I think?", "false_start", "af_alloy"),
    ("Hi, this is, this is Pat calling about my case.", "stutter", "am_adam"),
    ("Could I get -- [pause] -- a status update on my matter?", "mid_sentence_pause", "af_bella"),
    ("Um, can I -- can I drop something off later today?", "false_start", "am_michael"),
    ("Hey, like, I was hoping to, uh, talk to someone about fees.", "filler_words", "af_nicole"),
    ("So -- so my question is -- when does the consultation start?", "stutter", "am_eric"),
    ("Hi, I, I needed to ask about, hmm, parking.", "filler_words", "af_sky"),
    ("Could you ... [pause] ... transfer me to billing please?", "mid_sentence_pause", "am_liam"),
    ("I -- I have -- a paperwork question.", "stutter", "af_river"),
    ("Like, is there a way to, you know, get my documents back?", "filler_words", "af_heart"),
    ("Um, hello, I, I'm here for my 3 p.m. appointment.", "stutter", "af_alloy"),
    ("Could I -- could I please -- speak with an attorney?", "stutter", "am_adam"),
    ("Hi, I had a -- a question -- about my retainer.", "false_start", "af_bella"),
    (
        "So I called yesterday and ... [pause] ... I wanted to follow up.",
        "mid_sentence_pause",
        "am_michael",
    ),
    ("Yeah, hi -- never mind -- can you transfer me?", "false_start", "af_nicole"),
    ("Um, what time is, uh, the firm open until today?", "filler_words", "am_eric"),
    ("Could you -- could you please -- check on something for me?", "stutter", "af_sky"),
    ("I -- I'd like to schedule -- a consultation.", "stutter", "am_liam"),
    ("Hi I have a quick -- [pause] -- a quick question.", "mid_sentence_pause", "af_river"),
    ("Like, is there, uh, paperwork I should bring?", "filler_words", "af_heart"),
    ("So, um, I was hoping to, like, get a callback today.", "filler_words", "af_alloy"),
    ("I -- I called earlier -- and didn't get -- through.", "stutter", "am_adam"),
    ("Um, hello, can I, can I leave a message?", "stutter", "af_bella"),
    ("Could you ... [pause] ... let me know about parking?", "mid_sentence_pause", "am_michael"),
    ("Hi, I had -- I had a meeting -- yesterday I think?", "false_start", "af_nicole"),
    ("So like, is the -- the office -- open right now?", "stutter", "am_eric"),
    ("Um, just wondering, uh, about hours.", "filler_words", "af_sky"),
    ("Could -- could -- I get -- an attorney callback?", "stutter", "am_liam"),
    ("Hi, this is for, you know, the contract review thing.", "filler_words", "af_river"),
    ("I -- I -- never mind. I'll call back.", "false_start", "af_heart"),
    ("Like, where do I, uh, drop off paperwork?", "filler_words", "af_alloy"),
    ("Could you ... [pause] ... transfer me to the front desk?", "mid_sentence_pause", "am_adam"),
    ("Um, hi, I -- I had a question -- about scheduling.", "stutter", "af_bella"),
    ("So is there -- is there a way -- to confirm the time?", "stutter", "am_michael"),
    ("Hi, I, I'm following up on, uh, an email I sent.", "filler_words", "af_nicole"),
    ("Could -- I -- speak with -- a paralegal?", "stutter", "am_eric"),
    ("Um, just wanted to, uh, see if -- if you got my message.", "filler_words", "af_sky"),
    ("I -- I had -- a couple questions -- about fees.", "false_start", "am_liam"),
    ("So like, what's the, uh, address again?", "filler_words", "af_river"),
]


def _kokoro_revision() -> str:
    try:
        import kokoro  # type: ignore[import-untyped]

        return getattr(kokoro, "__version__", "unknown")
    except Exception:
        return "unknown"


def _render_with_pauses(
    text: str, voice: str, sample_rate: int = 24000
) -> tuple[np.ndarray, float]:
    """Render text via Kokoro, expanding [pause] tokens into 800ms silence inserts.

    Returns (audio, total_duration_s).
    """
    from kokoro import KPipeline  # type: ignore[import-untyped]

    pipeline = KPipeline(lang_code="a")
    parts = text.split("[pause]")
    pause_samples = int(0.8 * sample_rate)
    pause_audio = np.zeros(pause_samples, dtype=np.float32)
    chunks: list[np.ndarray] = []
    for i, part in enumerate(parts):
        for _, _, audio in pipeline(part.strip(), voice=voice, speed=1.0):
            # Kokoro returns torch.Tensor on some versions; convert defensively.
            arr = audio.detach().cpu().numpy() if hasattr(audio, "detach") else np.asarray(audio)
            chunks.append(arr.astype(np.float32))
        if i < len(parts) - 1:
            chunks.append(pause_audio)
    audio = np.concatenate(chunks) if chunks else np.zeros(sample_rate, dtype=np.float32)
    duration = len(audio) / sample_rate
    return audio, duration


def main() -> int:
    TARGET_DIR.mkdir(parents=True, exist_ok=True)
    if MANIFEST.exists():
        with MANIFEST.open() as f:
            by_id = {r["asset_id"]: r for r in csv.DictReader(f)}
    else:
        by_id = {}

    kokoro_rev = _kokoro_revision()
    turn_truth: dict[str, dict] = {}

    for i, (text, kind, voice) in enumerate(HESITATION_CLIPS, start=1):
        clip_id = f"hes-{i:04d}"
        out_wav = TARGET_DIR / f"{clip_id}.wav"
        audio, duration = _render_with_pauses(text, voice)
        sf.write(out_wav, audio, 24000, subtype="PCM_16")
        sha = hashlib.sha256(out_wav.read_bytes()).hexdigest()
        # Ground-truth turn-end = total duration (speaker fully done at end of utterance)
        turn_truth[clip_id] = {
            "ground_truth_turn_end_ms": int(duration * 1000),
            "hesitation_kind": kind,
            "voice_seed": voice,
            "text": text,
        }
        by_id[clip_id] = {
            "asset_id": clip_id,
            "corpus": "corpus_hesitation",
            "path": f"assets/corpus_hesitation/{clip_id}.wav",
            "sha256": sha,
            "license": "synthetic",
            "source": "assets/render_env/render_hesitation.py",
            "created_utc": datetime.now(tz=UTC).replace(microsecond=0).isoformat(),
            "generator_script": "assets/render_env/render_hesitation.py",
            "generator_seed": "42",
            "kokoro_revision": kokoro_rev,
            "intent": "hesitation_adversarial",
            "adversity_level": kind,
            "persona": voice,
            "duration_s": f"{duration:.3f}",
            "sample_rate": "24000",
        }

    TURN_TRUTH.write_text(json.dumps(turn_truth, indent=2, sort_keys=True) + "\n")
    truth_sha = hashlib.sha256(TURN_TRUTH.read_bytes()).hexdigest()
    by_id["hesitation_turn_truth"] = {
        "asset_id": "hesitation_turn_truth",
        "corpus": "corpus_hesitation",
        "path": "assets/corpus_hesitation/turn_truth.json",
        "sha256": truth_sha,
        "license": "synthetic",
        "source": "assets/render_env/render_hesitation.py",
        "created_utc": datetime.now(tz=UTC).replace(microsecond=0).isoformat(),
        "generator_script": "assets/render_env/render_hesitation.py",
        "generator_seed": "42",
        "kokoro_revision": kokoro_rev,
        "intent": "hesitation_ground_truth",
        "adversity_level": "",
        "persona": "",
        "duration_s": "",
        "sample_rate": "",
    }

    with MANIFEST.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        for asset_id in sorted(by_id):
            full = {k: by_id[asset_id].get(k, "") for k in FIELDNAMES}
            writer.writerow(full)
    print(f"Hesitation: rendered {len(HESITATION_CLIPS)} clips + turn_truth.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
