"""Resolve pending revisions + per-file SHA-256 in bench/models.lock.yaml.

Closes 02-VERIFICATION.md GAP-3 root and genuinely satisfies REPRO-02.

Strategy (do NOT download multi-GB weight files locally):
  - Commit SHA: HfApi().repo_info(repo_id, revision=branch).sha
  - LFS file SHA-256: sibling.lfs.sha256 from repo_info(files_metadata=True)
  - Non-LFS file SHA-256: streamed hash of hf_hub_download() output, capped at
    --max-non-lfs-bytes (default 50 MB) to refuse accidental multi-GB pulls.

Idempotent: re-running with all entries populated logs 'already resolved' and
exits without contacting HF.

When `files: []` is empty for an entry, the resolver populates the canonical
filename set: any sibling with a weight extension (.safetensors, .bin, .gguf,
.pt, .onnx) plus canonical config files (config.json, tokenizer.json,
tokenizer_config.json, special_tokens_map.json, vocab.json, vocabulary.json,
preprocessor_config.json, generation_config.json). README/notebook/example
files are intentionally omitted — Phase 2 only pins what the runtime loads.
"""

from __future__ import annotations

import argparse
import hashlib
import logging
import pathlib
import sys
from typing import Any

import yaml

logger = logging.getLogger(__name__)

_CANONICAL_WEIGHT_PATTERNS = (
    ".safetensors",
    ".bin",
    ".gguf",
    ".pt",
    ".pth",
    ".onnx",
)
_CANONICAL_CONFIG_FILES = (
    "config.json",
    "tokenizer.json",
    "tokenizer_config.json",
    "special_tokens_map.json",
    "vocab.json",
    "vocabulary.json",
    "preprocessor_config.json",
    "generation_config.json",
)


def _is_canonical(filename: str) -> bool:
    if filename in _CANONICAL_CONFIG_FILES:
        return True
    lower = filename.lower()
    return any(lower.endswith(p) for p in _CANONICAL_WEIGHT_PATTERNS)


def _stream_sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _entry_needs_resolve(entry: dict[str, Any]) -> bool:
    """True if any pending markers exist OR files is empty."""
    if entry.get("revision") == "pending":
        return True
    files = entry.get("files") or []
    if not files:
        return True
    return any(f.get("sha256") == "pending" for f in files)


def _resolve_one(
    *,
    entry: dict[str, Any],
    branch: str,
    max_non_lfs_bytes: int,
    api: Any,
    hf_download: Any,
) -> dict[str, Any]:
    """Returns the entry with revision + files filled. Mutates a copy."""
    out = dict(entry)
    repo_id = out["repo_id"]
    rev = out.get("revision", "pending")
    if rev == "pending":
        info = api.repo_info(repo_id=repo_id, revision=branch, files_metadata=True)
        out["revision"] = str(info.sha)
    else:
        info = api.repo_info(repo_id=repo_id, revision=rev, files_metadata=True)
    siblings = list(info.siblings or [])

    by_name: dict[str, Any] = {s.rfilename: s for s in siblings}

    # If files: [] populate canonical set; else preserve existing names + only fill SHAs.
    existing = list(out.get("files") or [])
    if not existing:
        existing = [
            {"filename": s.rfilename, "sha256": "pending"}
            for s in siblings
            if _is_canonical(s.rfilename)
        ]

    filled: list[dict[str, Any]] = []
    for f in existing:
        sib = by_name.get(f["filename"])
        if sib is None:
            logger.warning(
                f"{repo_id}: file {f['filename']} not present at revision "
                f"{out['revision'][:8]}; skipping (lockfile keeps prior value)"
            )
            filled.append(f)
            continue
        if f.get("sha256") and f["sha256"] != "pending":
            filled.append(f)
            continue
        # LFS path - sibling.lfs.sha256 is authoritative; no download.
        lfs = getattr(sib, "lfs", None)
        if lfs is not None and getattr(lfs, "sha256", None):
            filled.append({"filename": f["filename"], "sha256": str(lfs.sha256)})
            continue
        # Non-LFS path - refuse if size exceeds cap.
        size = int(getattr(sib, "size", 0) or 0)
        if size > max_non_lfs_bytes:
            raise RuntimeError(
                f"{repo_id}: {f['filename']} is non-LFS and {size} bytes "
                f"(> cap {max_non_lfs_bytes}); refuse to download. Bump "
                f"--max-non-lfs-bytes if intentional."
            )
        local = hf_download(
            repo_id=repo_id,
            filename=f["filename"],
            revision=out["revision"],
        )
        filled.append({"filename": f["filename"], "sha256": _stream_sha256(local)})
    out["files"] = filled
    return out


def resolve(
    *,
    lockfile: pathlib.Path,
    branch: str = "main",
    max_non_lfs_bytes: int = 50_000_000,
    dry_run: bool = False,
    api: Any = None,
    hf_download: Any = None,
) -> dict[str, Any]:
    """Resolve pending entries; write back unless dry_run. Returns updated dict."""
    if api is None:
        from huggingface_hub import HfApi  # local import — only when really called

        api = HfApi()
    if hf_download is None:
        from huggingface_hub import hf_hub_download as _hub  # local import

        hf_download = _hub

    text = lockfile.read_text()
    data = yaml.safe_load(text) or {}
    models = list(data.get("models", []))
    if not models:
        raise RuntimeError(f"{lockfile}: no `models:` list found")

    if not any(_entry_needs_resolve(m) for m in models):
        logger.info(f"{lockfile}: all entries already resolved; nothing to do")
        return data

    updated: list[dict[str, Any]] = []
    for m in models:
        if not _entry_needs_resolve(m):
            updated.append(m)
            continue
        try:
            updated.append(
                _resolve_one(
                    entry=m,
                    branch=branch,
                    max_non_lfs_bytes=max_non_lfs_bytes,
                    api=api,
                    hf_download=hf_download,
                )
            )
        except Exception as e:
            logger.error(f"{m.get('name')}: resolve failed - {e}")
            raise
    data["models"] = updated

    if dry_run:
        logger.info(f"{lockfile}: DRY RUN - would write {len(updated)} entries")
        return data

    # Preserve top-of-file comment block.
    lead_comment_lines: list[str] = []
    for line in text.splitlines():
        if line.startswith("#") or line.strip() == "":
            lead_comment_lines.append(line)
        else:
            break
    body = yaml.safe_dump(data, sort_keys=False, default_flow_style=False)
    head = "\n".join(lead_comment_lines)
    if head:
        head += "\n"
    lockfile.write_text(head + body)
    logger.info(f"{lockfile}: wrote {len(updated)} resolved entries")
    return data


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="tools.resolve_lockfile_shas")
    p.add_argument(
        "--lockfile",
        type=pathlib.Path,
        default=pathlib.Path("bench/models.lock.yaml"),
    )
    p.add_argument("--branch", default="main")
    p.add_argument("--max-non-lfs-bytes", type=int, default=50_000_000)
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    resolve(
        lockfile=args.lockfile,
        branch=args.branch,
        max_non_lfs_bytes=args.max_non_lfs_bytes,
        dry_run=args.dry_run,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
