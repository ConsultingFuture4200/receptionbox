"""Result schema, JSONL writer, SQLite index rebuild (HARNESS-04 + D-10/11/12).

Phase 1 ships the schema + storage path. Phase 2/3 gate runners call
`append_result(...)` for each measurement; `make report` (Phase 4) calls
`rebuild_index()` to repopulate `results/index.sqlite` from JSONL.
"""

from .results import GateResult, append_result
from .store import INDEX_SCHEMA, rebuild_index

__all__ = ["INDEX_SCHEMA", "GateResult", "append_result", "rebuild_index"]
