"""One-time HF cache bootstrap (CLOUD-05, D-19, D-20, D-21).

Pulls every model from bench/models.lock.yaml into /models/{repo_safe}/{revision}/
on the RunPod network volume. Idempotent — re-runs skip already-bootstrapped
models via a marker file (`.bootstrap.json`) at each repo+revision dir.

Operator runs this ONCE on a small bootstrap pod (D-20: ~$0.50 amortized
storage). Subsequent gate pods mount /models read-only and skip download.

D-21: cache paths keyed by HF revision SHA — bumping a SHA in the lockfile
triggers a fresh pull on next pod start. No automatic cleanup of old SHAs.
"""

from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import logging
import pathlib
import sys

import yaml

logger = logging.getLogger(__name__)


def _safe(repo_id: str) -> str:
    """Convert 'org/repo' -> 'org__repo' for safe filesystem paths."""
    return repo_id.replace("/", "__")


def _sha(path: pathlib.Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def bootstrap(
    *,
    target: pathlib.Path,
    lockfile: pathlib.Path,
    force: bool = False,
) -> dict:
    """Pull every lockfile model into target/{repo_safe}/{revision}/.

    Returns a dict mapping logical model name -> bootstrap record. Models with
    revision == 'pending' are skipped with a WARNING. Per-model failures are
    logged and the model is omitted from the returned index — never raises.
    """
    target.mkdir(parents=True, exist_ok=True)
    data = yaml.safe_load(lockfile.read_text()) or {}
    index: dict[str, dict] = {}
    for entry in data.get("models", []):
        name = entry["name"]
        repo = entry["repo_id"]
        rev = entry["revision"]
        if rev == "pending":
            logger.warning(f"SKIP {name}: revision still 'pending'; resolve in lockfile first")
            continue
        dest = target / _safe(repo) / rev
        marker = dest / ".bootstrap.json"
        if marker.exists() and not force:
            logger.info(f"SKIP {name}@{rev[:8]}: already cached at {dest}")
            try:
                index[name] = json.loads(marker.read_text())
            except (OSError, json.JSONDecodeError) as e:
                logger.warning(f"could not read existing marker for {name}: {e}")
            continue
        dest.mkdir(parents=True, exist_ok=True)
        started = datetime.datetime.utcnow().isoformat()
        try:
            from huggingface_hub import snapshot_download

            snapshot_download(
                repo_id=repo,
                revision=rev,
                local_dir=str(dest),
            )
        except Exception as e:
            logger.error(f"FAIL {name}@{rev[:8]}: {e}")
            continue
        files = sorted(str(p.relative_to(dest)) for p in dest.rglob("*") if p.is_file())
        total_bytes = sum((dest / f).stat().st_size for f in files if (dest / f).is_file())
        record = {
            "repo_id": repo,
            "revision": rev,
            "name": name,
            "started_utc": started,
            "finished_utc": datetime.datetime.utcnow().isoformat(),
            "total_bytes": total_bytes,
            "files": files,
        }
        marker.write_text(json.dumps(record, indent=2, sort_keys=True))
        index[name] = record
        logger.info(f"OK {name}@{rev[:8]}: {total_bytes / 1e9:.2f} GB at {dest}")

    idx_path = target / ".bootstrap_index.json"
    idx_path.write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "captured_utc": datetime.datetime.utcnow().isoformat(),
                "lockfile_sha": _sha(lockfile),
                "models": index,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return index


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="One-time HF cache bootstrap (CLOUD-05, D-19/D-21).")
    p.add_argument("--target", type=pathlib.Path, default=pathlib.Path("/models"))
    p.add_argument(
        "--lockfile",
        type=pathlib.Path,
        default=pathlib.Path("bench/models.lock.yaml"),
    )
    p.add_argument(
        "--force",
        action="store_true",
        help="Re-pull even when a .bootstrap.json marker exists.",
    )
    args = p.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    idx = bootstrap(target=args.target, lockfile=args.lockfile, force=args.force)
    print(f"bootstrapped {len(idx)} models into {args.target}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
