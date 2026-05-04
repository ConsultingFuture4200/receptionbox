"""Pre-commit hook: every audio file under assets/ must be listed in assets/manifest.csv.

Walks assets/ for audio extensions and diffs against the path column of
assets/manifest.csv. Fails the commit if any audio file is unlisted.

Per CONTEXT.md D-06 provenance enforcement and INFRA-05 no-real-audio
assertion. Pitfall F: this hook MUST run on every commit (always_run: true)
so manifest-only edits don't slip past.
"""

from __future__ import annotations

import csv
import pathlib
import sys

ROOT = pathlib.Path(".")
AUDIO_EXTS = {".wav", ".mp3", ".flac", ".opus", ".ogg"}


def main() -> int:
    manifest_path = ROOT / "assets" / "manifest.csv"
    if not manifest_path.exists():
        # Permit pre-manifest state; manifest.csv must exist before audio does
        listed: set[str] = set()
    else:
        with manifest_path.open() as f:
            reader = csv.DictReader(f)
            if reader.fieldnames is None or "path" not in reader.fieldnames:
                print(
                    "assets/manifest.csv exists but has no 'path' column header",
                    file=sys.stderr,
                )
                return 1
            listed = {row["path"] for row in reader}

    found = {
        str(p)
        for p in (ROOT / "assets").rglob("*")
        if p.is_file() and p.suffix.lower() in AUDIO_EXTS
    }
    unlisted = found - listed
    if unlisted:
        print(
            "Audio files present but not listed in assets/manifest.csv (Pitfall 11; INFRA-05):",
            file=sys.stderr,
        )
        for p in sorted(unlisted):
            print(f"  {p}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
