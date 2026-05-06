"""LiveKit pipeline rig tests (D-15).

The rig is shimmed when livekit-agents is not installed (workstation case),
so all tests run on bare pytest with no GPU / no LiveKit / no torch.
"""

from __future__ import annotations

import asyncio
import pathlib
import sys
import wave
from collections.abc import AsyncIterator

import pytest

# We use the Phase 1 stub substrate as the test driver.
from substrate._stub import _StubSubstrate
from substrate.types import LLMChunk, STTChunk

# ---------------------------------------------------------------------------
# Fixture: 1 second of silence as a 16 kHz mono int16 WAV.
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def silence_wav(tmp_path_factory: pytest.TempPathFactory) -> pathlib.Path:
    out = tmp_path_factory.mktemp("rig") / "silence_1s.wav"
    with wave.open(str(out), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(16000)
        w.writeframes(b"\x00\x00" * 16000)
    return out


# ---------------------------------------------------------------------------
# build_session — falls back to shim when livekit not importable.
# ---------------------------------------------------------------------------


def test_build_session_returns_shim_when_livekit_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Simulate "livekit not installed".
    monkeypatch.setitem(sys.modules, "livekit", None)
    monkeypatch.setitem(sys.modules, "livekit.agents", None)
    monkeypatch.setitem(sys.modules, "livekit.plugins", None)

    # Re-import to force the shim path.
    for mod in list(sys.modules):
        if mod.startswith("substrate.livekit_pipeline"):
            sys.modules.pop(mod)

    from substrate.livekit_pipeline import build_session

    sub = _StubSubstrate()
    session = build_session(sub)
    assert session is not None
    assert hasattr(session, "stt")
    assert hasattr(session, "llm")
    assert hasattr(session, "tts")


# ---------------------------------------------------------------------------
# run_one_call — emits per-stage timings via the shim.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_one_call_emits_per_stage_timings(
    silence_wav: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Force shim path.
    monkeypatch.setitem(sys.modules, "livekit", None)
    for mod in list(sys.modules):
        if mod.startswith("substrate.livekit_pipeline"):
            sys.modules.pop(mod)

    from substrate.livekit_pipeline import build_session, run_one_call

    sub = _StubSubstrate()
    session = build_session(sub)
    timings = await run_one_call(session, silence_wav)

    expected_keys = {
        "stt_ttft_ms",
        "llm_ttft_ms",
        "llm_decode_ms_per_tok",
        "tts_first_audio_ms",
        "e2e_ms",
    }
    assert expected_keys <= set(timings.keys())
    # Stub yields chunks for all stages, so every timing must be a real float.
    for k in expected_keys:
        assert isinstance(timings[k], float), f"{k} must be float, got {type(timings[k])}"
        assert timings[k] >= 0.0


# ---------------------------------------------------------------------------
# run_one_call — graceful all-None when STT yields nothing.
# ---------------------------------------------------------------------------


class _EmptySTTSubstrate(_StubSubstrate):
    """Substrate whose transcribe yields nothing; downstream stages should
    short-circuit and the run should still produce a valid (all-None) dict."""

    async def transcribe(
        self,
        audio: AsyncIterator[bytes],
        *,
        sample_rate: int,
    ) -> AsyncIterator[STTChunk]:
        async for _ in audio:
            pass
        if False:
            yield STTChunk(text="")

    async def generate(self, prompt, *, grammar=None, max_tokens):  # type: ignore[override]
        if False:
            yield LLMChunk(text="")

    async def synthesize(self, text, *, voice=None):  # type: ignore[override]
        if False:
            yield b""


@pytest.mark.asyncio
async def test_run_one_call_handles_empty_stt_output(
    silence_wav: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setitem(sys.modules, "livekit", None)
    for mod in list(sys.modules):
        if mod.startswith("substrate.livekit_pipeline"):
            sys.modules.pop(mod)

    from substrate.livekit_pipeline import build_session, run_one_call

    sub = _EmptySTTSubstrate()
    session = build_session(sub)
    timings = await run_one_call(session, silence_wav)

    # Empty STT -> all downstream timings should be None.
    assert timings["stt_ttft_ms"] is None
    assert timings["llm_ttft_ms"] is None
    assert timings["tts_first_audio_ms"] is None
    assert timings["e2e_ms"] is None


# ---------------------------------------------------------------------------
# Module must not require torch.
# ---------------------------------------------------------------------------


def test_run_one_call_module_does_not_import_torch(monkeypatch: pytest.MonkeyPatch) -> None:
    # Drop any cached torch reference.
    sys.modules.pop("torch", None)
    for mod in list(sys.modules):
        if mod.startswith("substrate.livekit_pipeline"):
            sys.modules.pop(mod)

    import substrate.livekit_pipeline  # noqa: F401

    assert "torch" not in sys.modules


def test_pipeline_module_imports_without_livekit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(sys.modules, "livekit", None)
    monkeypatch.setitem(sys.modules, "livekit.agents", None)
    monkeypatch.setitem(sys.modules, "livekit.plugins", None)
    for mod in list(sys.modules):
        if mod.startswith("substrate.livekit_pipeline"):
            sys.modules.pop(mod)

    from substrate.livekit_pipeline import build_session, run_one_call

    # Both symbols are exported.
    assert callable(build_session)
    assert asyncio.iscoroutinefunction(run_one_call)
