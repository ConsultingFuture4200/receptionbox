"""env.json sidecar writer (HARNESS-05 + D-12).

Each gate run emits ONE sidecar per run_id at `results/{gate}/{run_id}.env.json`.
Layout:

    {
      "schema_version": "1.0",
      "run_id": "<ULID-or-uuid>",
      "gate": "smoke|g1|g2|g3|g5|...",
      "git_commit": "<sha>",
      "asset_manifest_sha": "<sha256-of-manifest.csv>",
      "env": { ...EnvFingerprint... }
    }

The `env` block is a pydantic-dumped EnvFingerprint. `read_env_sidecar`
re-validates it via pydantic, which is how the tampering check from
T-02-02-01 is realized in practice.
"""

from __future__ import annotations

import json
import pathlib

from substrate.types import EnvFingerprint

SCHEMA_VERSION = "1.0"


def write_env_sidecar(
    *,
    env_fp: EnvFingerprint,
    run_id: str,
    gate: str,
    git_commit: str,
    asset_manifest_sha: str,
    results_dir: pathlib.Path = pathlib.Path("results"),
) -> pathlib.Path:
    """Write `results/{gate}/{run_id}.env.json` and return the path."""
    out = results_dir / gate / f"{run_id}.env.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": SCHEMA_VERSION,
        "run_id": run_id,
        "gate": gate,
        "git_commit": git_commit,
        "asset_manifest_sha": asset_manifest_sha,
        "env": env_fp.model_dump(mode="json"),
    }
    out.write_text(json.dumps(payload, indent=2, sort_keys=True))
    return out


def read_env_sidecar(path: pathlib.Path) -> dict:
    """Read + pydantic-revalidate an env.json sidecar. Raises on malformed env block."""
    data = json.loads(path.read_text())
    # Re-validate the env block via pydantic on read (raises ValidationError on bad data).
    EnvFingerprint.model_validate(data["env"])
    return data
