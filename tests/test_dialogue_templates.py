"""Dialogue template tests (ASSETS-01 / D-01)."""

from __future__ import annotations

import hashlib
import json
import pathlib
import re
import subprocess
from collections import Counter

ROOT = pathlib.Path(__file__).resolve().parents[1]
DIALOGUES = ROOT / "assets" / "scripts" / "dialogues.json"


def test_500_dialogues_authored() -> None:
    data = json.loads(DIALOGUES.read_text())
    assert len(data) == 500


def test_full_matrix_coverage() -> None:
    """Every (intent, adversity_level, persona) triple appears exactly once."""
    data = json.loads(DIALOGUES.read_text())
    triples = [(d["intent"], d["adversity_level"], d["persona"]) for d in data]
    assert len(set(triples)) == 500
    # 10 intents x 5 adversity x 10 personas = 500
    intents = {t[0] for t in triples}
    advs = {t[1] for t in triples}
    personas = {t[2] for t in triples}
    assert len(intents) == 10
    assert len(advs) == 5
    assert len(personas) == 10


def test_script_ids_unique_and_formatted() -> None:
    data = json.loads(DIALOGUES.read_text())
    ids = [d["script_id"] for d in data]
    assert len(set(ids)) == 500
    for sid in ids:
        assert re.fullmatch(r"call-\d{4}", sid)


def test_every_dialogue_has_required_fields() -> None:
    data = json.loads(DIALOGUES.read_text())
    required = {
        "script_id",
        "intent",
        "adversity_level",
        "persona",
        "utterance",
        "voice_seed",
        "duration_target_s",
    }
    for d in data:
        assert required <= set(d.keys()), f"missing fields in {d['script_id']}"
        assert isinstance(d["utterance"], str) and d["utterance"].strip()
        assert d["duration_target_s"] > 0


def test_utterances_distributed_across_personas() -> None:
    """Each persona should have 50 utterances (10 intents x 5 adversity = 50)."""
    data = json.loads(DIALOGUES.read_text())
    counts = Counter(d["persona"] for d in data)
    for persona, n in counts.items():
        assert n == 50, f"{persona} has {n} utterances, expected 50"


def test_authoring_idempotent() -> None:
    sha_before = hashlib.sha256(DIALOGUES.read_bytes()).hexdigest()
    result = subprocess.run(
        ["uv", "run", "python", "-m", "assets.scripts.templates"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    assert result.returncode == 0
    sha_after = hashlib.sha256(DIALOGUES.read_bytes()).hexdigest()
    assert sha_before == sha_after


def test_render_env_pyproject_pins_torch_le_2_5() -> None:
    """A3 in Assumptions Log: sm_61 wheel availability requires torch <=2.5."""
    pyproject = (ROOT / "assets" / "render_env" / "pyproject.toml").read_text()
    assert "torch<=2.5.1" in pyproject, (
        "asset-rendering venv must pin torch <=2.5 for GTX 1070 sm_61 wheel availability"
    )


def test_render_env_lock_exists() -> None:
    assert (ROOT / "assets" / "render_env" / "uv.lock").exists(), (
        "asset-rendering venv must commit uv.lock (RESEARCH Open Question #3)"
    )
