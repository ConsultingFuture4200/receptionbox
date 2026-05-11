"""Unit tests for ROCmSubstrate (Phase 3, Plan 03-01 Task 1).

Mirrors tests/test_cuda_substrate.py structure. ROCmSubstrate composes the
same 4 adapters as CUDASubstrate (VLLMClient, FasterWhisperEngine,
ChatterboxClient, KokoroClient) but adds:

- D-37: tts.primary is read from config/sanity_strata.yaml at synthesize-time.
- DEV-1021: env_fingerprint reads RBOX_IMAGE_DIGEST env first, lockfile fallback.
- _query_gpu() shells out to rocm-smi --showproductname --json.
- env_fingerprint(substrate="rocm").
"""

from __future__ import annotations

import inspect
import logging
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest


def _new_substrate(**overrides: Any):
    from substrate.rocm import ROCmSubstrate

    kwargs = dict(
        vllm_url="http://fake-vllm:8000",
        vllm_model="qwen3-4b",
        whisper_model_dir="/nonexistent/whisper",
        chatterbox_url="http://fake-chatterbox:8001",
        kokoro_url="http://fake-kokoro:8002",
    )
    kwargs.update(overrides)
    return ROCmSubstrate(**kwargs)


# ---------------------------------------------------------------------------
# Test 1: ROCmSubstrate module + class import without torch/vllm/rocm installed
# ---------------------------------------------------------------------------


def test_rocm_substrate_module_importable_without_gpu(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """ROCmSubstrate module + instantiation must not require torch / vllm /
    faster_whisper / rocm-smi (lazy-load discipline; mirrors CUDASubstrate)."""
    monkeypatch.setitem(sys.modules, "torch", None)
    monkeypatch.setitem(sys.modules, "vllm", None)
    monkeypatch.setitem(sys.modules, "faster_whisper", None)

    for mod in list(sys.modules):
        if mod.startswith("substrate.rocm") or mod.startswith("substrate.adapters"):
            sys.modules.pop(mod)

    from substrate.rocm import ROCmSubstrate

    sub = ROCmSubstrate(
        vllm_url="http://x:1",
        vllm_model="qwen",
        whisper_model_dir="/nope",
        chatterbox_url="http://x:2",
        kokoro_url="http://x:3",
    )
    assert sub is not None


def test_rocm_substrate_module_does_not_import_torch_at_module_level() -> None:
    """Pitfall 1 isolation — torch must not be imported at substrate/rocm.py
    module level. The string `import torch` may appear inside a function body
    but never at module level (no top-level `import torch` line)."""
    src = (Path(__file__).resolve().parents[1] / "substrate" / "rocm.py").read_text()
    # Strip docstrings + comments before scanning.
    lines = []
    for ln in src.splitlines():
        stripped = ln.lstrip()
        if stripped.startswith("#"):
            continue
        # Top-level statements are at indent 0.
        if ln.startswith("import torch") or ln.startswith("from torch"):
            lines.append(ln)
    assert lines == [], f"substrate/rocm.py must not import torch at module level (found: {lines})"


# ---------------------------------------------------------------------------
# Test 2: ABC virtual subclass
# ---------------------------------------------------------------------------


def test_rocm_substrate_implements_abc() -> None:
    from substrate import Substrate
    from substrate.rocm import ROCmSubstrate

    assert issubclass(ROCmSubstrate, Substrate)
    sub = _new_substrate()
    for attr in ("load_stt", "load_llm", "load_tts", "transcribe", "generate", "synthesize"):
        assert callable(getattr(sub, attr))


# ---------------------------------------------------------------------------
# Test 3: All async methods are coroutines / async generators
# ---------------------------------------------------------------------------


def test_rocm_substrate_async_method_shapes() -> None:
    sub = _new_substrate()
    # load_* are coroutine functions
    assert inspect.iscoroutinefunction(sub.load_stt)
    assert inspect.iscoroutinefunction(sub.load_llm)
    assert inspect.iscoroutinefunction(sub.load_tts)
    # transcribe/generate/synthesize are async generator functions
    assert inspect.isasyncgenfunction(sub.transcribe)
    assert inspect.isasyncgenfunction(sub.generate)
    assert inspect.isasyncgenfunction(sub.synthesize)


# ---------------------------------------------------------------------------
# Test 4: env_fingerprint reads RBOX_IMAGE_DIGEST env (DEV-1021)
# ---------------------------------------------------------------------------


def test_rocm_substrate_env_fingerprint_reads_RBOX_IMAGE_DIGEST(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    digest = "ghcr.io/consultingfuture4200/rbox-pod-rocm@sha256:" + ("a" * 64)
    monkeypatch.setenv("RBOX_IMAGE_DIGEST", digest)

    from substrate.types import EnvFingerprint

    sub = _new_substrate()
    fp = sub.env_fingerprint()
    assert isinstance(fp, EnvFingerprint)
    assert fp.substrate == "rocm"
    # env wins over lockfile: digest should be the @sha256:... segment.
    assert fp.image_digest == "sha256:" + ("a" * 64)


def test_rocm_substrate_env_fingerprint_falls_back_to_lockfile(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("RBOX_IMAGE_DIGEST", raising=False)
    from substrate.types import EnvFingerprint

    sub = _new_substrate()
    fp = sub.env_fingerprint()
    assert isinstance(fp, EnvFingerprint)
    assert fp.substrate == "rocm"
    # Without the env var, the bench/images.lock.yaml fallback returns
    # "pending" (the rocm/vllm entry hasn't been resolved yet); the
    # exact value is non-empty.
    assert fp.image_digest  # non-empty


# ---------------------------------------------------------------------------
# Test 5: synthesize() with tts.primary=chatterbox + Chatterbox unhealthy →
# falls back to Kokoro (DR-27)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_rocm_substrate_synthesize_falls_back_to_kokoro_when_chatterbox_unhealthy(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from substrate.adapters import ChatterboxClient, KokoroClient

    strata = tmp_path / "sanity_strata.yaml"
    strata.write_text("tts:\n  primary: chatterbox\nstrata: {}\n")

    async def chatterbox_health(self):
        return False

    async def kokoro_health(self):
        return True

    async def chatterbox_synth(self, text, voice):
        yield b"CHATTERBOX"

    async def kokoro_synth(self, text, voice):
        yield b"KOKORO"

    monkeypatch.setattr(ChatterboxClient, "health", chatterbox_health, raising=True)
    monkeypatch.setattr(KokoroClient, "health", kokoro_health, raising=True)
    monkeypatch.setattr(ChatterboxClient, "synthesize", chatterbox_synth, raising=True)
    monkeypatch.setattr(KokoroClient, "synthesize", kokoro_synth, raising=True)

    sub = _new_substrate(sanity_strata_path=strata)
    out = []
    async for chunk in sub.synthesize("hello", voice=None):
        out.append(chunk)
    assert out == [b"KOKORO"]


# ---------------------------------------------------------------------------
# Test 6: synthesize() with tts.primary=kokoro routes DIRECTLY to Kokoro,
# never calling Chatterbox health
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_rocm_substrate_synthesize_kokoro_primary_skips_chatterbox(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from substrate.adapters import ChatterboxClient, KokoroClient

    strata = tmp_path / "sanity_strata.yaml"
    strata.write_text("tts:\n  primary: kokoro\nstrata: {}\n")

    chatterbox_health_called: dict[str, bool] = {"hit": False}

    async def chatterbox_health(self):
        chatterbox_health_called["hit"] = True
        return True  # even healthy — but should NOT be reached

    async def kokoro_health(self):
        return True

    async def kokoro_synth(self, text, voice):
        yield b"KOKORO_DIRECT"

    async def chatterbox_synth(self, text, voice):
        yield b"CHATTERBOX_NOT_REACHED"

    monkeypatch.setattr(ChatterboxClient, "health", chatterbox_health, raising=True)
    monkeypatch.setattr(KokoroClient, "health", kokoro_health, raising=True)
    monkeypatch.setattr(ChatterboxClient, "synthesize", chatterbox_synth, raising=True)
    monkeypatch.setattr(KokoroClient, "synthesize", kokoro_synth, raising=True)

    sub = _new_substrate(sanity_strata_path=strata)
    out = []
    async for chunk in sub.synthesize("hello", voice=None):
        out.append(chunk)
    assert out == [b"KOKORO_DIRECT"]
    assert chatterbox_health_called["hit"] is False, (
        "tts.primary=kokoro must NOT health-check Chatterbox"
    )


# ---------------------------------------------------------------------------
# Test 7: load_* swallows backend failures — log WARNING, _loaded[stage]=False
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_rocm_substrate_load_llm_logs_warning_on_health_fail(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    from substrate.adapters import VLLMClient

    caplog.set_level(logging.WARNING)

    async def fake_health(self):
        return False

    monkeypatch.setattr(VLLMClient, "health", fake_health, raising=True)

    sub = _new_substrate()
    await sub.load_llm()
    assert sub._loaded["llm"] is False
    assert any(
        "llm" in rec.message.lower() or "vllm" in rec.message.lower() for rec in caplog.records
    )


@pytest.mark.asyncio
async def test_rocm_substrate_load_tts_does_not_raise_on_both_unhealthy(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    from substrate.adapters import ChatterboxClient, KokoroClient

    caplog.set_level(logging.WARNING)

    async def fake_health_false(self):
        return False

    monkeypatch.setattr(ChatterboxClient, "health", fake_health_false, raising=True)
    monkeypatch.setattr(KokoroClient, "health", fake_health_false, raising=True)

    sub = _new_substrate()
    # Must not raise.
    await sub.load_tts()
    assert sub._loaded["tts"] is False


# ---------------------------------------------------------------------------
# Test 8: _query_gpu() parses rocm-smi JSON output
# ---------------------------------------------------------------------------


def test_rocm_substrate_query_gpu_parses_rocm_smi_output(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """_query_gpu must shell out to `rocm-smi --showproductname --json` and
    parse the `{"card0": {...}}` schema → (model_or_series, count)."""
    from substrate.rocm import ROCmSubstrate

    captured_argv: dict[str, list] = {"argv": []}

    def fake_run(argv, **kwargs):
        captured_argv["argv"] = list(argv)
        return subprocess.CompletedProcess(
            args=argv,
            returncode=0,
            stdout='{"card0": {"Card series": "MI300X", "Card model": "MI300X"}}',
            stderr="",
        )

    monkeypatch.setattr(subprocess, "run", fake_run)

    sku, count = ROCmSubstrate._query_gpu()
    assert "MI300X" in sku
    assert count == 1
    # Confirms rocm-smi was actually called with --showproductname --json
    assert "rocm-smi" in captured_argv["argv"][0]
    assert "--showproductname" in captured_argv["argv"]
    assert "--json" in captured_argv["argv"]


def test_rocm_substrate_query_gpu_returns_unknown_on_missing_binary(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """rocm-smi absent → ('unknown', 0). Mirrors cuda.py _query_gpu pattern."""
    from substrate.rocm import ROCmSubstrate

    def fake_run(argv, **kwargs):
        raise FileNotFoundError(argv[0])

    monkeypatch.setattr(subprocess, "run", fake_run)

    sku, count = ROCmSubstrate._query_gpu()
    assert sku == "unknown"
    assert count == 0


def test_rocm_substrate_query_gpu_handles_multi_card(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from substrate.rocm import ROCmSubstrate

    def fake_run(argv, **kwargs):
        return subprocess.CompletedProcess(
            args=argv,
            returncode=0,
            stdout=(
                '{"card0": {"Card series": "MI300X", "Card model": "MI300X"}, '
                '"card1": {"Card series": "MI300X", "Card model": "MI300X"}}'
            ),
            stderr="",
        )

    monkeypatch.setattr(subprocess, "run", fake_run)

    sku, count = ROCmSubstrate._query_gpu()
    assert "MI300X" in sku
    assert count == 2


# ---------------------------------------------------------------------------
# Bonus: _read_tts_primary defaults to "chatterbox" if file missing
# ---------------------------------------------------------------------------


def test_rocm_substrate_read_tts_primary_defaults_to_chatterbox(
    tmp_path: Path,
) -> None:
    missing = tmp_path / "does-not-exist.yaml"
    sub = _new_substrate(sanity_strata_path=missing)
    assert sub._read_tts_primary() == "chatterbox"


def test_rocm_substrate_read_tts_primary_reads_kokoro_when_configured(
    tmp_path: Path,
) -> None:
    strata = tmp_path / "sanity_strata.yaml"
    strata.write_text("tts:\n  primary: kokoro\n")
    sub = _new_substrate(sanity_strata_path=strata)
    assert sub._read_tts_primary() == "kokoro"
