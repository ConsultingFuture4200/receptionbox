"""G7 TTS A/B gate runner — unit tests (Plan 03-04 Task 1).

Covers six behaviors:

1. CUDASubstrate.synthesize(engine_hint="chatterbox") routes to the
   Chatterbox adapter even when Chatterbox.health()=False (no DR-27
   fallback when engine is explicit; logs WARNING but attempts the render).
2. CUDASubstrate.synthesize(engine_hint="kokoro") routes directly to
   the Kokoro adapter.
3. CUDASubstrate.synthesize(engine_hint=None) preserves the existing
   DR-27 behavior (Chatterbox first, Kokoro fallback).
4. G7Runner.run_one(asset) emits one GateResult per render, with
   metrics={engine, path, stimulus_id, first_audio_ms, total_audio_ms,
   audio_path, n_bytes}.
5. G7Runner.run_all(stimuli) over 30 stimuli emits 120 rows
   (4 renders x 30 stimuli = 30 chatterbox-cold + 30 chatterbox-warm
    + 30 kokoro-cold + 30 kokoro-warm).
6. Audio files land at results/g7/audio/{engine}_{path}_{stimulus_id}.wav.

All tests run with mocked adapter substrate (no GPU required).
"""

from __future__ import annotations

import asyncio
import logging
import pathlib
from collections.abc import AsyncIterator
from typing import Any

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _new_substrate(**overrides: Any):
    from substrate.cuda import CUDASubstrate

    kwargs = dict(
        vllm_url="http://fake-vllm:8000",
        vllm_model="qwen3-4b",
        whisper_model_dir="/nonexistent/whisper",
        chatterbox_url="http://fake-chatterbox:8001",
        kokoro_url="http://fake-kokoro:8002",
    )
    kwargs.update(overrides)
    return CUDASubstrate(**kwargs)


# ---------------------------------------------------------------------------
# Behavior 1 + 2 + 3: CUDASubstrate.synthesize honors engine_hint
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_synthesize_engine_hint_chatterbox_routes_directly_even_if_unhealthy(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """Behavior 1: explicit chatterbox routes to Chatterbox even when unhealthy."""
    from substrate.adapters import ChatterboxClient, KokoroClient

    caplog.set_level(logging.WARNING)

    async def cb_health(self):
        return False  # unhealthy — should NOT trigger fallback

    async def kk_health(self):
        return True

    async def cb_synth(self, text, voice):
        yield b"CHATTERBOX_BYTES"

    async def kk_synth(self, text, voice):
        yield b"KOKORO_BYTES"

    monkeypatch.setattr(ChatterboxClient, "health", cb_health, raising=True)
    monkeypatch.setattr(KokoroClient, "health", kk_health, raising=True)
    monkeypatch.setattr(ChatterboxClient, "synthesize", cb_synth, raising=True)
    monkeypatch.setattr(KokoroClient, "synthesize", kk_synth, raising=True)

    sub = _new_substrate()
    out = []
    async for chunk in sub.synthesize("hello", engine_hint="chatterbox"):
        out.append(chunk)

    assert out == [b"CHATTERBOX_BYTES"]
    # Warning emitted because we forced an unhealthy engine.
    assert any(
        "chatterbox" in rec.message.lower() and "unhealthy" in rec.message.lower()
        for rec in caplog.records
    )


@pytest.mark.asyncio
async def test_synthesize_engine_hint_kokoro_routes_directly(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Behavior 2: explicit kokoro routes to Kokoro adapter."""
    from substrate.adapters import ChatterboxClient, KokoroClient

    async def cb_health(self):
        return True  # chatterbox healthy — but we want kokoro

    async def kk_health(self):
        return True

    async def cb_synth(self, text, voice):
        yield b"CHATTERBOX_BYTES"

    async def kk_synth(self, text, voice):
        yield b"KOKORO_BYTES"

    monkeypatch.setattr(ChatterboxClient, "health", cb_health, raising=True)
    monkeypatch.setattr(KokoroClient, "health", kk_health, raising=True)
    monkeypatch.setattr(ChatterboxClient, "synthesize", cb_synth, raising=True)
    monkeypatch.setattr(KokoroClient, "synthesize", kk_synth, raising=True)

    sub = _new_substrate()
    out = []
    async for chunk in sub.synthesize("hello", engine_hint="kokoro"):
        out.append(chunk)

    assert out == [b"KOKORO_BYTES"]


@pytest.mark.asyncio
async def test_synthesize_engine_hint_none_preserves_dr27_behavior(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Behavior 3: None preserves DR-27 (chatterbox first, kokoro fallback when unhealthy)."""
    from substrate.adapters import ChatterboxClient, KokoroClient

    async def cb_health(self):
        return False  # forces fallback

    async def kk_health(self):
        return True

    async def cb_synth(self, text, voice):
        yield b"CHATTERBOX_BYTES"

    async def kk_synth(self, text, voice):
        yield b"KOKORO_BYTES"

    monkeypatch.setattr(ChatterboxClient, "health", cb_health, raising=True)
    monkeypatch.setattr(KokoroClient, "health", kk_health, raising=True)
    monkeypatch.setattr(ChatterboxClient, "synthesize", cb_synth, raising=True)
    monkeypatch.setattr(KokoroClient, "synthesize", kk_synth, raising=True)

    sub = _new_substrate()
    out = []
    async for chunk in sub.synthesize("hello"):
        out.append(chunk)

    assert out == [b"KOKORO_BYTES"]


# ---------------------------------------------------------------------------
# G7Runner: render-asset shape + per-render result
# ---------------------------------------------------------------------------


class _StubSubstrate:
    """Stand-in for a Substrate that yields fixed audio chunks per call.

    Used in place of CUDASubstrate so tests don't need to monkeypatch every
    adapter method individually.
    """

    def __init__(self) -> None:
        from substrate.types import EnvFingerprint

        self._fp = EnvFingerprint(
            substrate="cuda",
            image_digest="sha256:fakefakefakefake",
            model_shas={"chatterbox_turbo": "rev-cb", "kokoro_82m": "rev-kk"},
            gpu_sku="H100-fake",
            gpu_count=1,
            cuda_version="12.4",
            pytorch_version="2.5.0",
            timestamp_utc="2026-05-12T00:00:00Z",
        )
        self.calls: list[tuple[str, str]] = []  # (text, engine_hint)

    async def load_stt(self) -> None:
        return None

    async def load_llm(self) -> None:
        return None

    async def load_tts(self) -> None:
        return None

    async def transcribe(self, audio, *, sample_rate):  # pragma: no cover - unused
        if False:
            yield  # type: ignore[unreachable]

    async def generate(self, prompt, *, grammar=None, max_tokens):  # pragma: no cover - unused
        if False:
            yield  # type: ignore[unreachable]

    async def synthesize(
        self,
        text: str,
        *,
        voice=None,
        engine_hint: str | None = None,
    ) -> AsyncIterator[bytes]:
        self.calls.append((text, engine_hint or "auto"))
        # Two chunks of deterministic bytes to exercise first-audio + total timing.
        await asyncio.sleep(0.001)
        yield b"\x01" * 256
        await asyncio.sleep(0.001)
        yield b"\x02" * 128

    def env_fingerprint(self):
        return self._fp


@pytest.mark.asyncio
async def test_g7_runner_run_one_emits_per_render_metrics(tmp_path: pathlib.Path) -> None:
    """Behavior 4 + 6: one GateResult per render with required metrics + audio path."""
    from gates.g7.runner import G7Runner

    sub = _StubSubstrate()
    audio_dir = tmp_path / "audio"
    runner = G7Runner(
        substrate=sub,
        audio_out_dir=audio_dir,
        results_dir=tmp_path / "results",
        asset_manifest_path=pathlib.Path("assets/manifest.csv"),
    )
    await runner.start()

    asset = {
        "stimulus": {"pair_id": "tts-0001", "text": "hello world"},
        "engine": "chatterbox",
        "path": "cold",
    }
    result = await runner.run_one(asset)

    assert result.status == "ok"
    assert result.gate == "g7"
    m = result.metrics
    assert m["engine"] == "chatterbox"
    assert m["path"] == "cold"
    assert m["stimulus_id"] == "tts-0001"
    assert isinstance(m["first_audio_ms"], float) and m["first_audio_ms"] >= 0.0
    assert isinstance(m["total_audio_ms"], float) and m["total_audio_ms"] >= m["first_audio_ms"]
    assert m["n_bytes"] == 256 + 128
    # Behavior 6: audio path follows the {engine}_{path}_{stimulus_id}.wav convention.
    expected_path = audio_dir / "chatterbox_cold_tts-0001.wav"
    assert m["audio_path"] == str(expected_path)
    assert expected_path.exists()
    assert expected_path.stat().st_size == 256 + 128
    # tts_first_audio_ms also populated on the GateResult itself.
    assert result.tts_first_audio_ms is not None
    assert result.tts_first_audio_ms == m["first_audio_ms"]


@pytest.mark.asyncio
async def test_g7_runner_run_all_emits_120_rows_for_30_stimuli(tmp_path: pathlib.Path) -> None:
    """Behavior 5: 30 stimuli x 2 engines x 2 paths (cold/warm) = 120 rows."""
    from gates.g7.runner import G7Runner

    sub = _StubSubstrate()
    audio_dir = tmp_path / "audio"
    runner = G7Runner(
        substrate=sub,
        audio_out_dir=audio_dir,
        results_dir=tmp_path / "results",
        asset_manifest_path=pathlib.Path("assets/manifest.csv"),
    )
    await runner.start()

    stimuli = [{"pair_id": f"tts-{i:04d}", "text": f"text {i}"} for i in range(1, 31)]
    results = await runner.run_all(stimuli)

    assert len(results) == 120

    # Distribution: 30 per (engine, path) bucket.
    from collections import Counter

    buckets = Counter((r.metrics["engine"], r.metrics["path"]) for r in results)
    assert buckets[("chatterbox", "cold")] == 30
    assert buckets[("chatterbox", "warm")] == 30
    assert buckets[("kokoro", "cold")] == 30
    assert buckets[("kokoro", "warm")] == 30

    # Substrate was called 120 times, all with explicit engine_hint.
    assert len(sub.calls) == 120
    engines_called = Counter(eh for _, eh in sub.calls)
    assert engines_called["chatterbox"] == 60
    assert engines_called["kokoro"] == 60
    assert "auto" not in engines_called  # no implicit fallback path

    # 120 audio files written.
    written = list(audio_dir.glob("*.wav"))
    assert len(written) == 120


@pytest.mark.asyncio
async def test_g7_runner_run_all_uses_cold_then_warm_ordering(tmp_path: pathlib.Path) -> None:
    """Within a single engine, cold renders precede warm renders in submission order.

    Verifies the 'first render of stimulus = cold, second = warm' invariant
    via the runner's internal asset construction (relies on cold listed first).
    """
    from gates.g7.runner import G7Runner, build_render_assets

    stimuli = [{"pair_id": f"tts-{i:04d}", "text": f"t{i}"} for i in range(1, 4)]
    assets = build_render_assets(stimuli)

    # 3 stimuli x 2 engines x 2 paths = 12 render assets.
    assert len(assets) == 12

    # For each (engine, stimulus_id), cold appears at a lower index than warm.
    by_key: dict[tuple[str, str], list[int]] = {}
    for i, a in enumerate(assets):
        key = (a["engine"], a["stimulus"]["pair_id"])
        by_key.setdefault(key, []).append((i, a["path"]))
    for key, entries in by_key.items():
        assert len(entries) == 2, f"{key} should have cold + warm"
        cold_idx = next(i for i, p in entries if p == "cold")
        warm_idx = next(i for i, p in entries if p == "warm")
        assert cold_idx < warm_idx, f"cold must precede warm for {key}"

    # Sanity: all four engines x paths buckets present, 3 stimuli each.
    from collections import Counter

    buckets = Counter((a["engine"], a["path"]) for a in assets)
    assert buckets[("chatterbox", "cold")] == 3
    assert buckets[("chatterbox", "warm")] == 3
    assert buckets[("kokoro", "cold")] == 3
    assert buckets[("kokoro", "warm")] == 3
    # Suppress unused-runner-import lint by referencing the class.
    assert G7Runner is not None
