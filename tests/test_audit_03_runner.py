"""AUDIT-03 engine-swap + Ollama-overhead runner tests (plan 03-05 Task 2).

Drives AUDIT03Runner against a stub substrate that exposes _chatterbox /
_kokoro adapters with deterministic byte streams. The Ollama subprocess
is patched via the `_subprocess_run` seam.
"""

from __future__ import annotations

import asyncio
import pathlib
import subprocess
from collections.abc import AsyncIterator

import pytest

from gates.audit_03.runner import (
    AUDIT03Runner,
    _parse_ollama_tokens_per_sec,
    summarize_ollama_overhead,
)
from substrate._stub import _StubSubstrate
from substrate.types import VoiceRef

# ---------------------------------------------------------------------------
# Fixtures.
# ---------------------------------------------------------------------------


@pytest.fixture()
def manifest_csv(tmp_path: pathlib.Path) -> pathlib.Path:
    p = tmp_path / "manifest.csv"
    p.write_text("asset_id,corpus,path\nfake-1,test,/dev/null\n")
    return p


class _FakeTTSAdapter:
    """Deterministic adapter — yields N PCM chunks, each after a tiny delay."""

    def __init__(self, *, chunks: int = 2, chunk_size: int = 240, delay: float = 0.001) -> None:
        self._chunks = chunks
        self._chunk_size = chunk_size
        self._delay = delay

    async def health(self) -> bool:
        return True

    async def synthesize(self, text: str, voice: VoiceRef | None) -> AsyncIterator[bytes]:
        for _ in range(self._chunks):
            await asyncio.sleep(self._delay)
            yield b"\x00" * self._chunk_size


class _AuditStubSubstrate(_StubSubstrate):
    """StubSubstrate + explicit _chatterbox / _kokoro adapters for AUDIT-03."""

    def __init__(self) -> None:
        super().__init__()
        self._chatterbox = _FakeTTSAdapter()
        self._kokoro = _FakeTTSAdapter()


def _make_runner(
    tmp_path: pathlib.Path,
    manifest_csv: pathlib.Path,
    *,
    substrate: _AuditStubSubstrate | None = None,
) -> AUDIT03Runner:
    return AUDIT03Runner(
        substrate=substrate or _AuditStubSubstrate(),
        asset_manifest_path=manifest_csv,
        results_dir=tmp_path,
    )


def _stimuli(n: int, prefix: str) -> list[dict]:
    return [{"stimulus_id": f"{prefix}_{i}", "text": f"hello {i}"} for i in range(n)]


def _probes(n: int) -> list[dict]:
    return [{"probe_id": f"p_{i}", "prompt": f"What is {i} + {i}?"} for i in range(n)]


# ---------------------------------------------------------------------------
# Test 1: run_all emits 10 swap rows (5 CB + 5 KK) + 40 ollama-vs-vllm rows.
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_run_all_emits_expected_row_counts(
    tmp_path: pathlib.Path,
    manifest_csv: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _ollama_ok(*_args, **_kwargs):
        class _R:
            returncode = 0
            stdout = "answer text"
            stderr = "eval count: 50 token(s)\neval rate: 25.0 tokens/s\n"

        return _R()

    monkeypatch.setattr("gates.audit_03.runner._subprocess_run", _ollama_ok)
    runner = _make_runner(tmp_path, manifest_csv)
    await runner.start()

    cb = _stimuli(5, "cb")
    kk = _stimuli(5, "kk")
    probes = _probes(20)
    results = await runner.run_all({"stimuli_cb": cb, "stimuli_kk": kk, "ollama_probes": probes})

    swap = [r for r in results if (r.metrics or {}).get("path") == "swap"]
    olm_vllm = [r for r in results if (r.metrics or {}).get("engine_kind") == "vllm"]
    olm_ollama = [r for r in results if (r.metrics or {}).get("engine_kind") == "ollama"]

    assert len(swap) == 10
    assert len(olm_vllm) == 20
    assert len(olm_ollama) == 20
    assert len(results) == 50


# ---------------------------------------------------------------------------
# Test 2: engine_swap_ms is populated on the first Kokoro row only.
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_engine_swap_ms_recorded_on_first_kokoro_row_only(
    tmp_path: pathlib.Path,
    manifest_csv: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "gates.audit_03.runner._subprocess_run",
        lambda *_a, **_kw: type("R", (), {"returncode": 0, "stdout": "", "stderr": ""})(),
    )
    runner = _make_runner(tmp_path, manifest_csv)
    await runner.start()

    cb = _stimuli(3, "cb")
    kk = _stimuli(3, "kk")
    results = await runner.run_all({"stimuli_cb": cb, "stimuli_kk": kk, "ollama_probes": []})

    kk_rows = [r for r in results if (r.metrics or {}).get("engine") == "kokoro"]
    assert len(kk_rows) == 3
    swap_ms_values = [r.metrics["engine_swap_ms"] for r in kk_rows]
    # First Kokoro row has a numeric swap-time; subsequent rows are None.
    assert isinstance(swap_ms_values[0], float)
    assert swap_ms_values[0] >= 0.0
    assert swap_ms_values[1] is None
    assert swap_ms_values[2] is None


# ---------------------------------------------------------------------------
# Test 3: Ollama subprocess invoked with --verbose; verbose stderr parsed.
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_ollama_subprocess_called_with_verbose_and_parses_eval_rate(
    tmp_path: pathlib.Path,
    manifest_csv: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    invocations: list[list[str]] = []

    def _capture(cmd, *_args, **_kwargs):
        invocations.append(cmd)

        class _R:
            returncode = 0
            stdout = "the answer is 42 plus one more"
            stderr = "eval count: 99 token(s)\neval rate: 33.3 tokens/s\n"

        return _R()

    monkeypatch.setattr("gates.audit_03.runner._subprocess_run", _capture)
    runner = _make_runner(tmp_path, manifest_csv)
    await runner.start()

    results = await runner.run_all(
        {"stimuli_cb": [], "stimuli_kk": [], "ollama_probes": _probes(1)}
    )

    assert any(cmd[0] == "ollama" and "--verbose" in cmd for cmd in invocations)
    ollama_row = next(r for r in results if (r.metrics or {}).get("engine_kind") == "ollama")
    assert ollama_row.status == "ok"
    assert ollama_row.metrics["tokens"] == 99
    assert ollama_row.metrics["tokens_per_sec"] == pytest.approx(33.3)


# ---------------------------------------------------------------------------
# Test 4: ollama_overhead_factor = median(vllm_tps) / median(ollama_tps).
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_ollama_overhead_factor_computed_from_medians(
    tmp_path: pathlib.Path,
    manifest_csv: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Force Ollama tokens/sec to a deterministic value (eval rate 10).
    def _ollama_stub(*_args, **_kwargs):
        class _R:
            returncode = 0
            stdout = "x x x x x x x x x x"
            stderr = "eval count: 10 token(s)\neval rate: 10.0 tokens/s\n"

        return _R()

    monkeypatch.setattr("gates.audit_03.runner._subprocess_run", _ollama_stub)
    runner = _make_runner(tmp_path, manifest_csv)
    await runner.start()

    probes = _probes(5)
    results = await runner.run_all({"stimuli_cb": [], "stimuli_kk": [], "ollama_probes": probes})
    summary = summarize_ollama_overhead(results)

    assert summary["n_vllm"] == 5
    assert summary["n_ollama"] == 5
    assert summary["ollama_tps_median"] == pytest.approx(10.0)
    assert summary["vllm_tps_median"] > 0
    # vLLM stub yields "ok thanks" (~2 tokens) in well under a second, so its
    # tokens/sec is far above 10 — overhead factor must therefore be > 1.0.
    assert summary["ollama_overhead_factor"] is not None
    assert summary["ollama_overhead_factor"] > 0


# ---------------------------------------------------------------------------
# Test 5: ollama_not_installed → error row, AUDIT-01 portion unaffected.
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_ollama_not_installed_emits_error_row_but_continues(
    tmp_path: pathlib.Path,
    manifest_csv: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _boom(*_args, **_kwargs):
        raise FileNotFoundError("[Errno 2] No such file or directory: 'ollama'")

    monkeypatch.setattr("gates.audit_03.runner._subprocess_run", _boom)
    runner = _make_runner(tmp_path, manifest_csv)
    await runner.start()

    cb = _stimuli(2, "cb")
    kk = _stimuli(2, "kk")
    probes = _probes(3)
    results = await runner.run_all({"stimuli_cb": cb, "stimuli_kk": kk, "ollama_probes": probes})

    # Swap pass landed cleanly.
    swap = [r for r in results if (r.metrics or {}).get("path") == "swap"]
    assert len(swap) == 4
    for r in swap:
        assert r.status == "ok"

    # Each Ollama row is an error row with explicit ollama_not_installed marker.
    ollama_rows = [r for r in results if (r.metrics or {}).get("engine_kind") == "ollama"]
    assert len(ollama_rows) == 3
    for r in ollama_rows:
        assert r.status == "error"
        assert r.error_kind == "FileNotFoundError"
        assert r.error_msg and "ollama_not_installed" in r.error_msg


# ---------------------------------------------------------------------------
# Ollama timeout → status=timeout, run continues.
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_ollama_timeout_marks_row_timeout_and_keeps_running(
    tmp_path: pathlib.Path,
    manifest_csv: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _timeout(*_args, **_kwargs):
        raise subprocess.TimeoutExpired(cmd=["ollama"], timeout=120)

    monkeypatch.setattr("gates.audit_03.runner._subprocess_run", _timeout)
    runner = _make_runner(tmp_path, manifest_csv)
    await runner.start()
    results = await runner.run_all(
        {"stimuli_cb": [], "stimuli_kk": [], "ollama_probes": _probes(2)}
    )
    olm = [r for r in results if (r.metrics or {}).get("engine_kind") == "ollama"]
    assert len(olm) == 2
    for r in olm:
        assert r.status == "timeout"
        assert r.error_kind == "TimeoutExpired"


# ---------------------------------------------------------------------------
# Parser unit tests.
# ---------------------------------------------------------------------------
def test_parse_ollama_tokens_per_sec_prefers_verbose_block() -> None:
    tokens, tps = _parse_ollama_tokens_per_sec(
        "eval count: 123 token(s)\neval rate: 45.67 tokens/s",
        fallback_tokens=5,
        duration_s=2.0,
    )
    assert tokens == 123
    assert tps == pytest.approx(45.67)


def test_parse_ollama_tokens_per_sec_falls_back_to_wallclock() -> None:
    tokens, tps = _parse_ollama_tokens_per_sec(
        "no timing block",
        fallback_tokens=20,
        duration_s=4.0,
    )
    assert tokens == 20
    assert tps == pytest.approx(5.0)


def test_summarize_ollama_overhead_returns_nulls_when_one_side_empty() -> None:
    # Build a fake results list with only vLLM rows.
    class _F:
        def __init__(self, kind: str, tps: float) -> None:
            self.status = "ok"
            self.metrics = {"engine_kind": kind, "tokens_per_sec": tps}

    summary = summarize_ollama_overhead([_F("vllm", 100.0), _F("vllm", 110.0)])
    assert summary["n_vllm"] == 2
    assert summary["n_ollama"] == 0
    assert summary["ollama_overhead_factor"] is None
