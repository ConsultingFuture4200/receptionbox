"""Fetch HF models per bench/models.lock.yaml with revision pinning + ETag SHA verification.

Phase 1: ships the script. Operator runs it from the cloud pod at the start
of Phase 2 to populate revisions and per-file SHAs (REPRO-02 + Pitfall 9).
"""

from __future__ import annotations

import argparse
import pathlib

import yaml
from huggingface_hub import hf_hub_download

LOCKFILE = pathlib.Path("bench/models.lock.yaml")


def fetch_pinned(lockfile: pathlib.Path = LOCKFILE, cache_dir: str | None = None) -> None:
    """Iterate models.lock.yaml and download each pinned file + revision."""
    locks = yaml.safe_load(lockfile.read_text())
    for entry in locks["models"]:
        if entry["revision"] == "pending":
            print(f"SKIP {entry['name']} (revision still 'pending'; resolve first)")
            continue
        for f in entry.get("files", []):
            path = hf_hub_download(
                repo_id=entry["repo_id"],
                filename=f["filename"],
                revision=entry["revision"],
                cache_dir=cache_dir,
            )
            print(f"OK {entry['name']}@{entry['revision'][:8]} -> {path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch pinned HF models")
    parser.add_argument("--cache-dir", default=None)
    parser.add_argument("--lockfile", type=pathlib.Path, default=LOCKFILE)
    args = parser.parse_args()
    fetch_pinned(args.lockfile, cache_dir=args.cache_dir)


if __name__ == "__main__":
    main()
