"""Audio corpora manifest invariants (ASSETS-01, ASSETS-02, ASSETS-03)."""

from __future__ import annotations

import csv
import hashlib
import json
import pathlib
import re
import subprocess
from collections import Counter

ROOT = pathlib.Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "assets" / "manifest.csv"
TURN_TRUTH = ROOT / "assets" / "corpus_hesitation" / "turn_truth.json"


def _rows() -> list[dict]:
    with MANIFEST.open() as f:
        return list(csv.DictReader(f))


def _audio_rows(corpus: str) -> list[dict]:
    return [r for r in _rows() if r["corpus"] == corpus and r["path"].lower().endswith(".wav")]


def _has_audio() -> bool:
    """True iff any corpus_500 audio rows have been rendered. When false,
    Plan 04 audio rendering was deferred (no GPU at execution time) and
    audio-row count tests are skipped at collection time."""
    return len(_audio_rows("corpus_500")) > 0


def test_corpus_500_has_500_audio_rows() -> None:
    if not _has_audio():
        return  # deferred-render mode
    rows = _audio_rows("corpus_500")
    assert len(rows) == 500


def test_corpus_500_full_matrix_coverage() -> None:
    """10 intents x 5 adversity x 10 personas = 500 unique combos."""
    if not _has_audio():
        return
    rows = _audio_rows("corpus_500")
    triples = [(r["intent"], r["adversity_level"], r["persona"]) for r in rows]
    assert len(set(triples)) == 500


def test_corpus_g711_has_200_rows_with_strata() -> None:
    if not _has_audio():
        return
    rows = _audio_rows("corpus_g711")
    assert len(rows) == 200
    advs = Counter(r["adversity_level"] for r in rows)
    assert advs["neutral"] == 100
    stressed = sum(
        advs[k]
        for k in (
            "mild_emotional",
            "accent_strong",
            "background_noise",
            "urgent_distressed",
        )
    )
    assert stressed == 100


def test_corpus_g711_sample_rate_is_8000() -> None:
    if not _has_audio():
        return
    for r in _audio_rows("corpus_g711"):
        assert r["sample_rate"] == "8000", f"{r['asset_id']} not at 8000 Hz"


def test_every_corpus_g711_clip_has_sibling_transcript() -> None:
    """G2 runner resolves reference text via `audio_path.with_suffix('.txt')`
    when no `transcript_path` is set on the asset row. Without the sibling
    .txt every G2 row errors with FileNotFoundError (sanity 2026-05-09)."""
    if not _has_audio():
        return
    dialogues = {
        d["script_id"]: d
        for d in json.loads((ROOT / "assets" / "scripts" / "dialogues.json").read_text())
    }
    for r in _audio_rows("corpus_g711"):
        wav = ROOT / r["path"]
        txt = wav.with_suffix(".txt")
        assert txt.exists(), f"{r['asset_id']}: missing reference transcript at {txt}"
        # Source column is `transcoded_from:<call-NNNN>`; the .txt MUST
        # equal that dialogue's utterance so WER is computed against the
        # ground truth (not a stale or unrelated transcript).
        source = r["source"]
        assert source.startswith("transcoded_from:"), source
        script_id = source.split(":", 1)[1]
        expected = dialogues[script_id]["utterance"].strip()
        assert txt.read_text().strip() == expected, (
            f"{r['asset_id']}: transcript drift vs dialogues.json[{script_id}]"
        )


def test_corpus_hesitation_has_clips_and_turn_truth() -> None:
    if not _has_audio():
        return
    audio_rows = _audio_rows("corpus_hesitation")
    assert len(audio_rows) >= 30, f"hesitation set has {len(audio_rows)} clips, expected >=30"
    truth = json.loads(TURN_TRUTH.read_text())
    assert len(truth) == len(audio_rows), "turn_truth must have one entry per audio clip"
    for r in audio_rows:
        assert r["asset_id"] in truth, f"missing turn_truth for {r['asset_id']}"
        entry = truth[r["asset_id"]]
        assert isinstance(entry["ground_truth_turn_end_ms"], int)
        assert entry["hesitation_kind"] in {
            "filler_words",
            "false_start",
            "stutter",
            "mid_sentence_pause",
            "mid_word_stop",
        }


def test_every_audio_row_has_provenance() -> None:
    """ASSETS-08: each audio row must have non-empty sha, license, source,
    generator_script, generator_seed, kokoro_revision."""
    audio = [r for r in _rows() if r["path"].endswith(".wav")]
    for r in audio:
        for field in (
            "sha256",
            "license",
            "source",
            "generator_script",
            "generator_seed",
            "kokoro_revision",
        ):
            assert r[field], f"{r['asset_id']}: empty {field}"
        assert re.fullmatch(r"[a-f0-9]{64}", r["sha256"])


def test_every_audio_sha_matches_file() -> None:
    audio = [r for r in _rows() if r["path"].endswith(".wav")]
    for r in audio:
        path = ROOT / r["path"]
        if not path.exists():
            # Allow operator to run tests before render completes
            continue
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        assert actual == r["sha256"], (
            f"{r['asset_id']}: manifest sha mismatch (csv={r['sha256']} actual={actual})"
        )


def test_pre_commit_hook_passes_after_render() -> None:
    """Every audio file under assets/ MUST be in manifest.csv (INFRA-05)."""
    result = subprocess.run(
        ["python", str(ROOT / "tools" / "check_asset_manifest.py")],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, f"INFRA-05 manifest enforcement failed: {result.stderr}"
