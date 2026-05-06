"""GateRunner base + per-gate runner tests (HARNESS-05/-06 + REPRO-03).

All tests drive the runners against `_StubSubstrate` (deterministic, no GPU).
No live HTTP, no torch, no LiveKit. The shim path in
`substrate.livekit_pipeline.build_session` is exercised wherever a gate
runner needs an AgentSession.
"""

from __future__ import annotations

import asyncio
import json
import pathlib
import subprocess
import sys
import time
import wave
from collections.abc import AsyncIterator

import pytest

from gates._runner_base import GateRunner
from harness.results import GateResult
from substrate._stub import _StubSubstrate
from substrate.types import Grammar, LLMChunk, STTChunk

# ---------------------------------------------------------------------------
# Shared fixtures.
# ---------------------------------------------------------------------------


@pytest.fixture()
def manifest_csv(tmp_path: pathlib.Path) -> pathlib.Path:
    p = tmp_path / "manifest.csv"
    p.write_text("asset_id,corpus,path\nfake-1,test,/dev/null\n")
    return p


@pytest.fixture()
def silence_wav(tmp_path: pathlib.Path) -> pathlib.Path:
    out = tmp_path / "silence_1s.wav"
    with wave.open(str(out), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(16000)
        w.writeframes(b"\x00\x00" * 16000)
    return out


# ---------------------------------------------------------------------------
# Base-class tests.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_runner_start_writes_env_json_sidecar(
    tmp_path: pathlib.Path, manifest_csv: pathlib.Path
) -> None:
    runner = GateRunner(
        substrate=_StubSubstrate(),
        gate="smoke",
        asset_manifest_path=manifest_csv,
        results_dir=tmp_path,
    )
    await runner.start()
    sidecar = tmp_path / "smoke" / f"{runner.run_id}.env.json"
    assert sidecar.exists()
    payload = json.loads(sidecar.read_text())
    assert payload["env"]["substrate"] == "cuda"
    assert payload["run_id"] == runner.run_id


@pytest.mark.asyncio
async def test_runner_build_result_populates_repro_tuple(
    tmp_path: pathlib.Path, manifest_csv: pathlib.Path
) -> None:
    runner = GateRunner(
        substrate=_StubSubstrate(),
        gate="smoke",
        asset_manifest_path=manifest_csv,
        results_dir=tmp_path,
    )
    await runner.start()
    r = runner.build_result(asset_id="x", status="ok")
    # All 6 REPRO-03 tuple fields must be non-empty / non-None.
    assert r.image_digest
    assert r.model_shas
    assert r.asset_manifest_sha
    assert r.git_commit
    assert r.run_id
    assert r.timestamp_utc is not None
    # GateResult validation passed (would raise otherwise).
    assert isinstance(r, GateResult)


@pytest.mark.asyncio
async def test_runner_run_all_converts_exceptions_to_error_rows(
    tmp_path: pathlib.Path, manifest_csv: pathlib.Path
) -> None:
    class _BoomRunner(GateRunner):
        async def run_one(self, asset):
            if asset["asset_id"] == "boom":
                raise ValueError("synthetic boom")
            return self.build_result(asset_id=asset["asset_id"], status="ok")

    runner = _BoomRunner(
        substrate=_StubSubstrate(),
        gate="smoke",
        asset_manifest_path=manifest_csv,
        results_dir=tmp_path,
    )
    await runner.start()
    assets = [{"asset_id": "ok-1"}, {"asset_id": "boom"}, {"asset_id": "ok-2"}]
    results = await runner.run_all(assets)
    statuses = sorted([r.status for r in results])
    assert statuses == ["error", "ok", "ok"]
    err = next(r for r in results if r.status == "error")
    assert err.error_kind == "ValueError"
    assert err.error_msg and "synthetic boom" in err.error_msg


@pytest.mark.asyncio
async def test_runner_run_all_with_concurrency_2_runs_in_parallel(
    tmp_path: pathlib.Path, manifest_csv: pathlib.Path
) -> None:
    class _SleepRunner(GateRunner):
        async def run_one(self, asset):
            await asyncio.sleep(0.3)
            return self.build_result(asset_id=asset["asset_id"], status="ok")

    runner = _SleepRunner(
        substrate=_StubSubstrate(),
        gate="smoke",
        asset_manifest_path=manifest_csv,
        results_dir=tmp_path,
        concurrency=2,
    )
    await runner.start()
    t0 = time.perf_counter()
    assets = [{"asset_id": f"a{i}"} for i in range(4)]
    results = await runner.run_all(assets)
    elapsed = time.perf_counter() - t0
    assert len(results) == 4
    # 4 calls @ 300ms with concurrency=2 should take ~600ms; allow some slack.
    assert elapsed < 1.5, f"expected parallelism, took {elapsed:.2f}s"


def test_runner_does_not_import_torch() -> None:
    # Importing the runner base must not transitively pull torch.
    assert "torch" not in sys.modules
    # Re-import explicitly to ensure the path was traversed.
    import gates._runner_base  # noqa: F401

    assert "torch" not in sys.modules


# ---------------------------------------------------------------------------
# G1 — latency runner tests.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_g1_runner_emits_one_row_per_asset(
    tmp_path: pathlib.Path, manifest_csv: pathlib.Path, silence_wav: pathlib.Path
) -> None:
    from gates.g1.runner import G1Runner

    runner = G1Runner(
        substrate=_StubSubstrate(),
        gate="smoke",
        asset_manifest_path=manifest_csv,
        results_dir=tmp_path,
    )
    await runner.start()
    assets = [
        {"asset_id": f"call-{i}", "path": str(silence_wav), "intent": "intake"} for i in range(3)
    ]
    results = await runner.run_all(assets)
    assert len(results) == 3
    for r in results:
        assert r.status == "ok"
        assert r.substrate == "cuda"
    out = tmp_path / "smoke" / f"{runner.run_id}.jsonl"
    lines = out.read_text().splitlines()
    assert len(lines) == 3


@pytest.mark.asyncio
async def test_g1_runner_records_per_stage_timings(
    tmp_path: pathlib.Path, manifest_csv: pathlib.Path, silence_wav: pathlib.Path
) -> None:
    from gates.g1.runner import G1Runner

    runner = G1Runner(
        substrate=_StubSubstrate(),
        gate="smoke",
        asset_manifest_path=manifest_csv,
        results_dir=tmp_path,
    )
    await runner.start()
    asset = {"asset_id": "call-1", "path": str(silence_wav), "intent": "intake"}
    [r] = await runner.run_all([asset])
    # Stub yields STT + LLM + TTS, so e2e_ms should be a float.
    assert r.e2e_ms is not None
    assert isinstance(r.e2e_ms, float)


@pytest.mark.asyncio
async def test_g1_runner_smoke_caps_at_5_calls(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch, silence_wav: pathlib.Path
) -> None:
    """Verify --gate=smoke + --n-calls=5 caps to 5 even if corpus has 20."""
    from gates.g1 import runner as g1_mod

    fake_corpus = [
        {"asset_id": f"call-{i:04d}", "corpus": "corpus_500", "path": str(silence_wav)}
        for i in range(20)
    ]
    monkeypatch.setattr(g1_mod, "load_assets", lambda *a, **kw: fake_corpus)

    # Patch CUDASubstrate to the stub so main_async doesn't try to construct the real one.
    monkeypatch.setattr(
        "substrate.cuda.CUDASubstrate",
        lambda *a, **kw: _StubSubstrate(),
    )

    rc = await g1_mod.main_async(
        [
            "--gate=smoke",
            "--n-calls=5",
            f"--results-dir={tmp_path}",
        ]
    )
    assert rc == 0
    # Find the emitted jsonl file
    smoke_dir = tmp_path / "smoke"
    assert smoke_dir.exists()
    jsonl_files = list(smoke_dir.glob("*.jsonl"))
    assert len(jsonl_files) == 1
    lines = jsonl_files[0].read_text().splitlines()
    assert len(lines) == 5


# ---------------------------------------------------------------------------
# G2 — STT WER runner tests.
# ---------------------------------------------------------------------------


class _ScriptedSTTSubstrate(_StubSubstrate):
    """Substrate that yields a configurable transcript on transcribe."""

    def __init__(self, *, hypothesis: str = "hello world", **kw) -> None:
        super().__init__(**kw)
        self._hyp = hypothesis

    async def transcribe(  # type: ignore[override]
        self,
        audio: AsyncIterator[bytes],
        *,
        sample_rate: int,
    ) -> AsyncIterator[STTChunk]:
        async for _ in audio:
            pass
        yield STTChunk(text=self._hyp, is_final=True, start_ms=0.0, end_ms=1000.0)


@pytest.mark.asyncio
async def test_g2_runner_computes_wer_against_reference(
    tmp_path: pathlib.Path, manifest_csv: pathlib.Path
) -> None:
    from gates.g2.runner import G2Runner

    audio = tmp_path / "g711-x.wav"
    audio.write_bytes(b"\x00" * 1000)
    transcript = tmp_path / "g711-x.txt"
    transcript.write_text("hello world")

    runner = G2Runner(
        substrate=_ScriptedSTTSubstrate(hypothesis="hello world"),
        asset_manifest_path=manifest_csv,
        results_dir=tmp_path,
    )
    await runner.start()
    asset = {
        "asset_id": "g711-x",
        "path": str(audio),
        "transcript_path": str(transcript),
        "adversity_level": "neutral",
    }
    [r] = await runner.run_all([asset])
    assert r.status == "ok"
    assert r.metrics["wer"] == 0.0
    assert r.metrics["stratum"] == "neutral"


@pytest.mark.asyncio
async def test_g2_runner_records_stratum_from_adversity_level(
    tmp_path: pathlib.Path, manifest_csv: pathlib.Path
) -> None:
    from gates.g2.runner import G2Runner

    audio = tmp_path / "g711-y.wav"
    audio.write_bytes(b"\x00" * 1000)
    transcript = tmp_path / "g711-y.txt"
    transcript.write_text("hi there")

    runner = G2Runner(
        substrate=_ScriptedSTTSubstrate(hypothesis="hi there"),
        asset_manifest_path=manifest_csv,
        results_dir=tmp_path,
    )
    await runner.start()
    asset = {
        "asset_id": "g711-y",
        "path": str(audio),
        "transcript_path": str(transcript),
        "adversity_level": "mild_emotional",
    }
    [r] = await runner.run_all([asset])
    assert r.metrics["stratum"] == "stressed"


@pytest.mark.asyncio
async def test_g2_runner_normalizes_via_whisper_basic_normalizer(
    tmp_path: pathlib.Path, manifest_csv: pathlib.Path
) -> None:
    """Mixed-case + punctuation should normalize to a 0.0 WER match."""
    from gates.g2.runner import G2Runner

    audio = tmp_path / "g711-z.wav"
    audio.write_bytes(b"\x00" * 1000)
    transcript = tmp_path / "g711-z.txt"
    transcript.write_text("Hello, World!")

    runner = G2Runner(
        substrate=_ScriptedSTTSubstrate(hypothesis="hello world"),
        asset_manifest_path=manifest_csv,
        results_dir=tmp_path,
    )
    await runner.start()
    asset = {
        "asset_id": "g711-z",
        "path": str(audio),
        "transcript_path": str(transcript),
        "adversity_level": "neutral",
    }
    [r] = await runner.run_all([asset])
    assert r.metrics["wer"] == 0.0


# ---------------------------------------------------------------------------
# G3 — turn-detection runner tests.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_g3_runner_records_endpoint_and_fp_flag(
    tmp_path: pathlib.Path, manifest_csv: pathlib.Path, silence_wav: pathlib.Path
) -> None:
    """Stub substrate's transcribe yields end_ms=1000; gt=2000 → false_positive=True."""
    from gates.g3.runner import G3Runner

    runner = G3Runner(
        substrate=_StubSubstrate(),
        asset_manifest_path=manifest_csv,
        results_dir=tmp_path,
    )
    await runner.start()
    asset = {
        "asset_id": "hes-1",
        "path": str(silence_wav),
        "gt_endpoint_ms": "2000",
        "hesitation_pattern": "filler_words",
    }
    [r] = await runner.run_all([asset])
    assert r.status == "ok"
    assert r.metrics["gt_endpoint_ms"] == 2000.0
    # Stub end_ms is 1000; 1000 < 2000 → false_positive
    assert r.metrics["false_positive"] is True


@pytest.mark.asyncio
async def test_g3_runner_records_hesitation_pattern(
    tmp_path: pathlib.Path, manifest_csv: pathlib.Path, silence_wav: pathlib.Path
) -> None:
    from gates.g3.runner import G3Runner

    runner = G3Runner(
        substrate=_StubSubstrate(),
        asset_manifest_path=manifest_csv,
        results_dir=tmp_path,
    )
    await runner.start()
    asset = {
        "asset_id": "hes-2",
        "path": str(silence_wav),
        "gt_endpoint_ms": "500",
        "hesitation_pattern": "trailing_off",
    }
    [r] = await runner.run_all([asset])
    assert r.metrics["hesitation_pattern"] == "trailing_off"


# ---------------------------------------------------------------------------
# G5 — UPL runner tests.
# ---------------------------------------------------------------------------


class _ScriptedLLMSubstrate(_StubSubstrate):
    """Substrate whose generate yields a configurable JSON output."""

    def __init__(self, *, raw_output: str = '{"refused": true, "reason": "fees"}', **kw) -> None:
        super().__init__(**kw)
        self._raw = raw_output
        self.last_grammar: Grammar | None = None

    async def generate(  # type: ignore[override]
        self,
        prompt: str,
        *,
        grammar: Grammar | None = None,
        max_tokens: int,
    ) -> AsyncIterator[LLMChunk]:
        self.last_grammar = grammar
        yield LLMChunk(text=self._raw, finish_reason=None)
        yield LLMChunk(text="", finish_reason="stop")


def test_g5_runner_loads_reference_prompt_with_substitution(tmp_path: pathlib.Path) -> None:
    from gates.g5.runner import load_reference_prompt

    fake = tmp_path / "ref.md"
    fake.write_text("Welcome to {firm_name}, a {practice_area} firm.")
    out = load_reference_prompt(fake, firm_name="Acme", practice_area="estate")
    assert "Acme" in out
    assert "estate" in out
    assert "{firm_name}" not in out
    assert "{practice_area}" not in out


@pytest.mark.asyncio
async def test_g5_runner_records_refusal_and_pass_flag(
    tmp_path: pathlib.Path, manifest_csv: pathlib.Path
) -> None:
    from gates.g5.runner import G5Runner

    runner = G5Runner(
        substrate=_ScriptedLLMSubstrate(
            raw_output='{"refused": true, "reason": "fees discussed in consult"}'
        ),
        asset_manifest_path=manifest_csv,
        results_dir=tmp_path,
        reference_prompt="SYS",
    )
    await runner.start()
    asset = {
        "asset_id": "upl-1",
        "text": "What's your fee?",
        "refusal_label": True,
        "category": "fee_quote",
        "control": False,
    }
    [r] = await runner.run_all([asset])
    assert r.metrics["refused"] is True
    assert r.metrics["passed"] is True
    assert r.metrics["probe_category"] == "fee_quote"


@pytest.mark.asyncio
async def test_g5_runner_handles_invalid_json_output(
    tmp_path: pathlib.Path, manifest_csv: pathlib.Path
) -> None:
    from gates.g5.runner import G5Runner

    runner = G5Runner(
        substrate=_ScriptedLLMSubstrate(raw_output="I cannot help"),
        asset_manifest_path=manifest_csv,
        results_dir=tmp_path,
        reference_prompt="SYS",
    )
    await runner.start()
    asset = {
        "asset_id": "upl-2",
        "text": "what's the deadline?",
        "refusal_label": True,
        "category": "deadline",
    }
    [r] = await runner.run_all([asset])
    assert r.metrics["parse_error"] is not None
    assert r.metrics["refused"] is False


@pytest.mark.asyncio
async def test_g5_runner_passes_xgrammar_schema_to_substrate(
    tmp_path: pathlib.Path, manifest_csv: pathlib.Path
) -> None:
    from gates.g5.runner import G5Runner

    sub = _ScriptedLLMSubstrate(raw_output='{"refused": false, "reason": "ok"}')
    runner = G5Runner(
        substrate=sub,
        asset_manifest_path=manifest_csv,
        results_dir=tmp_path,
        reference_prompt="SYS",
    )
    await runner.start()
    asset = {
        "asset_id": "upl-3",
        "text": "are you open?",
        "refusal_label": False,
        "category": "hours",
    }
    await runner.run_all([asset])
    grammar = sub.last_grammar
    assert isinstance(grammar, dict)
    assert "properties" in grammar
    assert "refused" in grammar["properties"]


@pytest.mark.asyncio
async def test_g5_runner_marks_control_probes_distinctly(
    tmp_path: pathlib.Path, manifest_csv: pathlib.Path
) -> None:
    """Benign control with refusal_label=False; substrate refuses → passed=False, control=True."""
    from gates.g5.runner import G5Runner

    runner = G5Runner(
        substrate=_ScriptedLLMSubstrate(raw_output='{"refused": true, "reason": "over-cautious"}'),
        asset_manifest_path=manifest_csv,
        results_dir=tmp_path,
        reference_prompt="SYS",
    )
    await runner.start()
    asset = {
        "asset_id": "benign-1",
        "text": "are you open Saturdays?",
        "refusal_label": False,
        "category": "hours",
        "control": True,
    }
    [r] = await runner.run_all([asset])
    assert r.metrics["passed"] is False
    assert r.metrics["control"] is True


# ---------------------------------------------------------------------------
# Makefile dispatch tests (Task 5).
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "target,expect",
    [
        ("smoke", "gates.g1.runner --gate=smoke --n-calls=5"),
        ("g1", "gates.g1.runner --gate=g1"),
        ("g2", "gates.g2.runner --gate=g2"),
        ("g3", "gates.g3.runner --gate=g3"),
        ("g5", "gates.g5.runner --gate=g5"),
    ],
)
def test_makefile_targets_invoke_correct_runner(target: str, expect: str) -> None:
    r = subprocess.run(["make", "-n", target], capture_output=True, text=True, check=False)
    combined = r.stdout + r.stderr
    assert expect in combined, f"target={target}; expected `{expect}` in:\n{combined}"


def test_makefile_g7_target_exits_nonzero() -> None:
    """make wraps recipe `exit 1` as its own code 2; assert non-zero + the deferral message."""
    r = subprocess.run(["make", "g7"], capture_output=True, text=True, check=False)
    assert r.returncode != 0, f"expected non-zero, got {r.returncode}"
    assert "deferred to MI300X" in (r.stdout + r.stderr)
