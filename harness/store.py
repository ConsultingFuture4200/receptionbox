"""SQLite index rebuild from JSONL primary store (D-11).

Idempotent: each call rebuilds `results/index.sqlite` from scratch by
walking `results/**/*.jsonl`. Run by `make report` (Phase 4).
"""

from __future__ import annotations

import json
import pathlib
import sqlite3

INDEX_SCHEMA = """
CREATE TABLE IF NOT EXISTS results (
    run_id TEXT,
    gate TEXT,
    asset_id TEXT,
    substrate TEXT,
    image_digest TEXT,
    git_commit TEXT,
    timestamp_utc TEXT,
    concurrency INTEGER,
    status TEXT,
    e2e_ms REAL,
    stt_ttft_ms REAL,
    llm_ttft_ms REAL,
    llm_decode_ms_per_tok REAL,
    tts_first_audio_ms REAL,
    metrics_json TEXT,
    schema_version TEXT,
    PRIMARY KEY (run_id, asset_id, gate)
);
CREATE INDEX IF NOT EXISTS idx_gate ON results(gate);
CREATE INDEX IF NOT EXISTS idx_substrate ON results(substrate);
CREATE INDEX IF NOT EXISTS idx_status ON results(status);
"""


def rebuild_index(results_dir: pathlib.Path = pathlib.Path("results")) -> pathlib.Path:
    """Drop and rebuild results/index.sqlite from JSONL files. Idempotent."""
    db_path = results_dir / "index.sqlite"
    db_path.unlink(missing_ok=True)
    results_dir.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    try:
        conn.executescript(INDEX_SCHEMA)
        for jsonl in sorted(results_dir.rglob("*.jsonl")):
            with jsonl.open() as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    row = json.loads(line)
                    conn.execute(
                        "INSERT OR REPLACE INTO results VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                        (
                            row["run_id"],
                            row["gate"],
                            row["asset_id"],
                            row["substrate"],
                            row["image_digest"],
                            row["git_commit"],
                            row["timestamp_utc"],
                            row["concurrency"],
                            row["status"],
                            row.get("e2e_ms"),
                            row.get("stt_ttft_ms"),
                            row.get("llm_ttft_ms"),
                            row.get("llm_decode_ms_per_tok"),
                            row.get("tts_first_audio_ms"),
                            json.dumps(row.get("metrics", {})),
                            row["schema_version"],
                        ),
                    )
        conn.commit()
    finally:
        conn.close()
    return db_path
