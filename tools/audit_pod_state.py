"""Pre-teardown audit (CLOUD-06, D-22, D-23). Fail-loud: exit 1 on any violation.

Last line of defense before pod results rsync to operator workstation. Compares
the pod filesystem against assets/manifest.csv (SHA-256 truth set), refuses any
audio extension under results/, and refuses PII regex matches in result text.

D-23: the audit log file is ALWAYS written, even on violation, so the SIGTERM
handler can rsync the audit log without rsyncing result data on a failed audit.
"""

from __future__ import annotations

import argparse
import csv
import datetime
import hashlib
import json
import logging
import pathlib
import re
import sys

AUDIO_EXTS = re.compile(r"\.(wav|mp3|flac|opus|ogg|m4a|aiff|webm)$", re.IGNORECASE)
SSN_RE = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
PHONE_RE = re.compile(r"\b(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b")
EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
TEXT_EXTS = {".json", ".jsonl", ".txt", ".md", ".csv"}

logger = logging.getLogger(__name__)


def _sha256_file(path: pathlib.Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _redact(match: str) -> str:
    if len(match) <= 4:
        return "*" * len(match)
    return f"{match[:2]}{'*' * (len(match) - 4)}{match[-2:]}"


def _is_dotpath(p: pathlib.Path, root: pathlib.Path) -> bool:
    """True if any path segment relative to root starts with '.'."""
    try:
        rel = p.relative_to(root)
    except ValueError:
        return False
    return any(part.startswith(".") for part in rel.parts)


def manifest_check(root: pathlib.Path, manifest_csv: pathlib.Path) -> dict:
    expected: dict[str, str] = {}
    with manifest_csv.open() as f:
        for row in csv.DictReader(f):
            path = (row.get("path") or "").strip()
            sha = (row.get("sha256") or "").strip()
            if path and sha:
                expected[path] = sha
    assets_root = root / "assets"
    found: dict[str, str] = {}
    if assets_root.exists():
        for p in assets_root.rglob("*"):
            if not p.is_file():
                continue
            # Skip dotfiles / dot-directories under assets/.
            if _is_dotpath(p, assets_root):
                continue
            # Skip the asset-rendering venv (Plan 04 Pitfall 1 isolation: deps'
            # bundled WAVs aren't project assets — same rule as
            # tools/check_asset_manifest.py).
            parts = p.relative_to(assets_root).parts
            if any(seg in {".venv", "site-packages"} for seg in parts):
                continue
            # Manifest scope: audio assets only. Source code, JSON probes, and
            # markdown under assets/ are committed-source artifacts, not
            # provenance-tracked audio. The PII regex pass handles them via
            # results/ (no PII probe text leaks into result rows).
            if not AUDIO_EXTS.search(p.name):
                continue
            rel = str(p.relative_to(root))
            found[rel] = _sha256_file(p)
    mismatches: list[dict] = []
    extras: list[str] = []
    for rel, sha in found.items():
        if rel == "assets/manifest.csv":
            # Don't audit the manifest file itself against itself.
            continue
        if rel not in expected:
            extras.append(rel)
        elif expected[rel] != sha:
            mismatches.append({"path": rel, "expected": expected[rel], "actual": sha})
    return {
        "expected_count": len(expected),
        "found_count": len(found),
        "extras": sorted(extras),
        "mismatches": mismatches,
        "violations": len(extras) + len(mismatches),
    }


def extension_check(root: pathlib.Path, results_dir: str) -> dict:
    target = root / results_dir
    offending: list[str] = []
    if target.exists():
        for p in target.rglob("*"):
            if p.is_file() and AUDIO_EXTS.search(p.name):
                offending.append(str(p.relative_to(root)))
    return {"offending_files": sorted(offending), "violations": len(offending)}


def pii_check(root: pathlib.Path, results_dir: str) -> dict:
    target = root / results_dir
    hits: list[dict] = []
    files_checked = 0
    if target.exists():
        for p in target.rglob("*"):
            if not p.is_file() or p.suffix.lower() not in TEXT_EXTS:
                continue
            files_checked += 1
            try:
                with p.open(encoding="utf-8", errors="replace") as fh:
                    for ln, line in enumerate(fh, 1):
                        for kind, rx in (
                            ("ssn", SSN_RE),
                            ("phone", PHONE_RE),
                            ("email", EMAIL_RE),
                        ):
                            for m in rx.finditer(line):
                                hits.append(
                                    {
                                        "file": str(p.relative_to(root)),
                                        "line": ln,
                                        "kind": kind,
                                        "match_redacted": _redact(m.group(0)),
                                    }
                                )
            except OSError as e:
                logger.warning(f"audit: skip {p}: {e}")
    return {"hits": hits, "files_checked": files_checked, "violations": len(hits)}


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description="Pre-teardown audit (CLOUD-06): manifest SHA + extension + PII."
    )
    p.add_argument("--root", type=pathlib.Path, default=pathlib.Path("."))
    p.add_argument("--manifest", type=pathlib.Path, default=pathlib.Path("assets/manifest.csv"))
    p.add_argument("--results-dir", default="results")
    p.add_argument("--audit-log", type=pathlib.Path, required=True)
    args = p.parse_args(argv)

    started = datetime.datetime.utcnow().isoformat()
    manifest_path = args.manifest if args.manifest.is_absolute() else args.root / args.manifest
    manifest_sha = _sha256_file(manifest_path) if manifest_path.exists() else "missing"

    m = manifest_check(args.root, manifest_path)
    e = extension_check(args.root, args.results_dir)
    pi = pii_check(args.root, args.results_dir)
    total = m["violations"] + e["violations"] + pi["violations"]
    finished = datetime.datetime.utcnow().isoformat()

    report = {
        "schema_version": "1.0",
        "summary": {
            "violations": total,
            "files_checked": pi["files_checked"],
            "started_utc": started,
            "finished_utc": finished,
            "manifest_sha": manifest_sha,
        },
        "manifest_check": m,
        "extension_check": e,
        "pii_check": pi,
    }
    args.audit_log.parent.mkdir(parents=True, exist_ok=True)
    args.audit_log.write_text(json.dumps(report, indent=2, sort_keys=True))

    if total > 0:
        logger.error(f"AUDIT FAILED: {total} violation(s); see {args.audit_log}")
        return 1
    logger.info(f"AUDIT OK: 0 violations; {pi['files_checked']} text files checked")
    return 0


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    sys.exit(main())
