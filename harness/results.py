"""GateResult schema (D-10) + JSONL append-only writer (D-11).

Schema is versioned via `schema_version: Literal["1.0"]`. When schema
evolves (Phase 2+ won't, but Phase 4 might), convert to a discriminated
union — do NOT silently widen the Literal (Pitfall E in RESEARCH.md).

Error rows keep the schema with `status='error'`, populated `error_kind`
/ `error_msg`, and NULL measurements — Liotta-survivable per D-11.
"""

from __future__ import annotations

import json
import pathlib
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

GateName = Literal["g1", "g2", "g3", "g5", "g7", "smoke", "canary", "audit_01", "audit_03"]
Status = Literal["ok", "error", "timeout"]
SubstrateName = Literal["cuda", "rocm"]


class GateResult(BaseModel):
    """Single row in `results/{gate}/{run_id}.jsonl`.

    Versioned via `schema_version`. When schema evolves to 1.1+, convert
    to `GateResultV1 | GateResultV2 = Field(discriminator='schema_version')`
    discriminated union; do NOT widen this Literal.
    """

    schema_version: Literal["1.0"] = "1.0"

    # Identity
    run_id: str
    gate: GateName
    asset_id: str
    asset_manifest_sha: str

    # Substrate fingerprint
    substrate: SubstrateName
    image_digest: str
    model_shas: dict[str, str]
    git_commit: str
    timestamp_utc: datetime

    # Run config
    concurrency: int

    # Outcome (error rows keep schema)
    status: Status
    error_kind: str | None = None
    error_msg: str | None = None

    # Per-stage timings (nullable — single schema serves all gates and error rows)
    stt_ttft_ms: float | None = None
    llm_ttft_ms: float | None = None
    llm_decode_ms_per_tok: float | None = None
    tts_first_audio_ms: float | None = None
    e2e_ms: float | None = None

    # Gate-specific payload
    metrics: dict = Field(default_factory=dict)
    extras: dict = Field(default_factory=dict)


def append_result(
    result: GateResult,
    results_dir: pathlib.Path = pathlib.Path("results"),
) -> pathlib.Path:
    """Append a single JSON line to results/{gate}/{run_id}.jsonl. Returns the path."""
    out = results_dir / result.gate / f"{result.run_id}.jsonl"
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("a") as f:
        f.write(result.model_dump_json() + "\n")
    return out


def read_jsonl(path: pathlib.Path) -> list[GateResult]:
    """Parse a JSONL file into GateResult instances (used by SQLite index rebuild)."""
    out: list[GateResult] = []
    with path.open() as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            out.append(GateResult.model_validate(json.loads(line)))
    return out
