"""Resolve cache_bootstrap logical model names to on-disk paths.

`tools/cache_bootstrap.py` lays out HF caches as
`/models/{repo_id.replace('/', '__')}/{revision}/` and writes a top-level
index at `/models/.bootstrap_index.json`. Gate runners (and CLAUDE.md
defaults) carry the *logical* name from `bench/models.lock.yaml`
(e.g. `distil_whisper_large_v3_int8`), not that on-disk path. Without this
helper, consumers must teach themselves the layout — the
`tools/pod_entrypoint.sh` workaround did exactly that, but only for the
entrypoint's consumers.

`resolve_model_dir` is a small, stateless lookup: pass-through if the
argument is already a usable directory; otherwise consult the index and
return the resolved path. Failures fall back to the original input — the
caller decides whether that's fatal (FasterWhisperEngine logs WARNING and
yields nothing, matching the adapter error contract).
"""

from __future__ import annotations

import json
import logging
import pathlib

logger = logging.getLogger(__name__)

DEFAULT_BOOTSTRAP_INDEX = pathlib.Path("/models/.bootstrap_index.json")


def resolve_model_dir(
    name_or_path: str,
    *,
    bootstrap_index: pathlib.Path = DEFAULT_BOOTSTRAP_INDEX,
) -> str:
    """Return an on-disk model directory for `name_or_path`.

    Resolution order:
      1. If `name_or_path` is an existing directory, return it unchanged.
      2. Else read `bootstrap_index` and look up `models[name_or_path]`;
         compute `<index_parent>/{repo_id.replace('/', '__')}/{revision}`
         and return it (whether or not it exists on disk — the caller
         will fail-fast at model load time if the directory is missing).
      3. On any failure (missing index, missing entry, malformed JSON),
         log WARNING and return `name_or_path` unchanged so the caller's
         existing error path runs.
    """
    p = pathlib.Path(name_or_path)
    if p.is_dir():
        return name_or_path

    try:
        data = json.loads(bootstrap_index.read_text())
    except FileNotFoundError:
        logger.warning(
            f"[paths] bootstrap index not found at {bootstrap_index}; "
            f"returning {name_or_path!r} unchanged"
        )
        return name_or_path
    except (OSError, json.JSONDecodeError) as e:
        logger.warning(
            f"[paths] could not read bootstrap index {bootstrap_index}: "
            f"{type(e).__name__}; returning {name_or_path!r} unchanged"
        )
        return name_or_path

    models = data.get("models") or {}
    # Accept either the bare logical name (`distil_whisper_large_v3_int8`) or
    # the path-style form the runners default to
    # (`/models/distil_whisper_large_v3_int8`). Try the full string first,
    # then the basename.
    entry = models.get(name_or_path)
    if not isinstance(entry, dict):
        entry = models.get(p.name)
    if not isinstance(entry, dict):
        logger.warning(
            f"[paths] no bootstrap entry for {name_or_path!r} in {bootstrap_index}; "
            f"returning unchanged"
        )
        return name_or_path

    repo_id = entry.get("repo_id")
    revision = entry.get("revision")
    if not repo_id or not revision:
        logger.warning(
            f"[paths] bootstrap entry for {name_or_path!r} missing repo_id/revision; "
            f"returning unchanged"
        )
        return name_or_path

    safe = str(repo_id).replace("/", "__")
    return str(bootstrap_index.parent / safe / str(revision))
