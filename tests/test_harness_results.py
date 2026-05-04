"""GateResult schema + JSONL writer + SQLite index rebuild tests.

All tests use tmp_path fixtures; no real results/ pollution.
"""

from __future__ import annotations

import pathlib
import sqlite3
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from harness.results import GateResult, append_result, read_jsonl
from harness.store import rebuild_index


def _make_result(**overrides) -> GateResult:
    base: dict = dict(
        run_id="run-0001",
        gate="smoke",
        asset_id="call-0001",
        asset_manifest_sha="a" * 64,
        substrate="cuda",
        image_digest="sha256:abc",
        model_shas={"whisper": "f" * 40},
        git_commit="0" * 40,
        timestamp_utc=datetime.now(tz=UTC),
        concurrency=1,
        status="ok",
    )
    base.update(overrides)
    return GateResult.model_validate(base)


def test_minimal_ok_result_round_trips() -> None:
    r = _make_result(e2e_ms=850.5)
    j = r.model_dump_json()
    restored = GateResult.model_validate_json(j)
    assert restored == r
    assert restored.schema_version == "1.0"


def test_error_row_keeps_schema_with_null_measurements() -> None:
    r = _make_result(status="error", error_kind="cuda_oom", error_msg="boom")
    assert r.e2e_ms is None
    assert r.stt_ttft_ms is None
    assert r.status == "error"


def test_unknown_schema_version_rejected_pitfall_e() -> None:
    base = _make_result().model_dump()
    base["schema_version"] = "9.9"
    with pytest.raises(ValidationError):
        GateResult.model_validate(base)


def test_unknown_gate_rejected() -> None:
    base = _make_result().model_dump()
    base["gate"] = "g99"
    with pytest.raises(ValidationError):
        GateResult.model_validate(base)


def test_append_result_creates_dir_and_appends_line(tmp_path: pathlib.Path) -> None:
    r = _make_result()
    out = append_result(r, results_dir=tmp_path)
    assert out.exists()
    assert out.parent.name == "smoke"
    # Append again
    append_result(r, results_dir=tmp_path)
    lines = out.read_text().splitlines()
    assert len(lines) == 2


def test_read_jsonl_parses_appended_rows(tmp_path: pathlib.Path) -> None:
    r = _make_result()
    out = append_result(r, results_dir=tmp_path)
    rows = read_jsonl(out)
    assert len(rows) == 1
    assert rows[0] == r


def test_rebuild_index_idempotent(tmp_path: pathlib.Path) -> None:
    r1 = _make_result(run_id="run-A", asset_id="call-1", e2e_ms=800.0)
    r2 = _make_result(run_id="run-A", asset_id="call-2", e2e_ms=900.0)
    append_result(r1, results_dir=tmp_path)
    append_result(r2, results_dir=tmp_path)
    db1 = rebuild_index(tmp_path)
    db2 = rebuild_index(tmp_path)  # second rebuild
    assert db1 == db2
    conn = sqlite3.connect(db2)
    try:
        rows = conn.execute(
            "SELECT run_id, asset_id, e2e_ms FROM results ORDER BY asset_id"
        ).fetchall()
        assert rows == [("run-A", "call-1", 800.0), ("run-A", "call-2", 900.0)]
    finally:
        conn.close()


def test_rebuild_index_picks_up_new_appends(tmp_path: pathlib.Path) -> None:
    append_result(_make_result(run_id="r1", asset_id="a1"), results_dir=tmp_path)
    rebuild_index(tmp_path)
    append_result(_make_result(run_id="r2", asset_id="a2"), results_dir=tmp_path)
    db = rebuild_index(tmp_path)
    conn = sqlite3.connect(db)
    try:
        count = conn.execute("SELECT COUNT(*) FROM results").fetchone()[0]
        assert count == 2
    finally:
        conn.close()
