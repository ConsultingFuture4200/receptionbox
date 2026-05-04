"""Idempotent authoring of 30 TTS A/B text pairs (ASSETS-06 / D-05).

Phase 1 ships text only -- actual A/B audio renders happen on MI300X in
Phase 3 (Chatterbox vs Kokoro). Each pair targets edge-case prosody:
numbers, money formats, time formats, proper nouns (uncommon names),
legal terminology, abbreviations.
"""

from __future__ import annotations

import csv
import hashlib
import json
import pathlib
from datetime import UTC, datetime

ROOT = pathlib.Path(__file__).resolve().parents[2]
PAIRS_PATH = ROOT / "assets" / "tts_pairs" / "pairs.json"
MANIFEST_PATH = ROOT / "assets" / "manifest.csv"

PAIRS: list[tuple[str, list[str], str]] = [
    (
        "Schedule a 30-minute consultation for $250 with Mr. Petrenko at 14:30 on October 12th.",
        ["numbers", "money_format", "time_format", "proper_nouns", "abbreviations"],
        "Numerics + uncommon name + 24-hour time",
    ),
    (
        "The retainer is two thousand five hundred dollars, payable in three installments.",
        ["numbers_spelled_out", "money_format"],
        "Spelled-out numerics",
    ),
    (
        "Filed under Civil Procedure section 425.16, the anti-SLAPP motion is due Tuesday.",
        ["legal_terminology", "proper_nouns", "weekday"],
        "Statutory cite without real number; weekday",
    ),
    (
        "Please call back at 555-0142 between 9 a.m. and 5 p.m. Pacific.",
        ["phone_number", "time_format", "timezone"],
        "Faux phone number; AM/PM; timezone",
    ),
    (
        "Confirm receipt of the subpoena duces tecum by November 3rd.",
        ["legal_terminology", "date_format"],
        "Latin legal phrase; ordinal date",
    ),
    (
        "The address is 1842 Esperanza Boulevard, Suite 7B, in Pasadena.",
        ["address", "proper_nouns", "alphanumeric"],
        "Address with alphanumeric suite",
    ),
    (
        "Court is set for Wednesday at 10:15 a.m. in courtroom 4.",
        ["weekday", "time_format", "ordinal"],
        "Weekday + AM/PM",
    ),
    (
        "Attorney Wojciechowska is unavailable until Q1 of next year.",
        ["proper_nouns_difficult", "abbreviations"],
        "Hard-to-pronounce surname; quarter abbreviation",
    ),
    (
        "Please bring two copies of the W-2, the 1099-MISC, and the 1040.",
        ["form_numbers", "alphanumeric"],
        "Tax-form alphanumerics",
    ),
    (
        "The deposition is scheduled for the 22nd at half past three.",
        ["ordinal", "informal_time"],
        "Ordinal + colloquial time",
    ),
    (
        "Mr. and Mrs. Nguyen-Vasquez confirmed their 4 p.m. appointment.",
        ["proper_nouns_difficult", "time_format", "hyphenated_names"],
        "Compound surname + AM/PM",
    ),
    (
        "The settlement offer is $137,250.50.",
        ["money_format_complex"],
        "Money with cents",
    ),
    (
        "File the brief by the close of business on Friday the 13th.",
        ["weekday", "ordinal", "idiom"],
        "Common phrase; ordinal date",
    ),
    (
        "Subparagraph (b)(3)(ii) of the lease addresses noise complaints.",
        ["legal_alphanumeric"],
        "Statute-style nested numbering",
    ),
    (
        "She'll be in trial from June 4th through June 17th.",
        ["date_range", "month"],
        "Date range across days of same month",
    ),
    (
        "Confirm the Zoom ID 873 4519 0226 and passcode is 'rocketship'.",
        ["spaced_digits", "literal_quoted"],
        "Spaced numeric + quoted token",
    ),
    (
        "The 2026-05-04 hearing was continued to 2026-08-19.",
        ["iso_date"],
        "ISO date format",
    ),
    (
        "Please send the .docx to intake at our domain.",
        ["file_extension", "domain_word"],
        "File extension + 'at our domain'",
    ),
    (
        "The judgment was upheld 5 to 2 by the appellate panel.",
        ["score_format", "legal_terminology"],
        "Vote count style",
    ),
    (
        "Pro se litigants must file in forma pauperis if requesting fee waivers.",
        ["latin_phrase", "legal_terminology"],
        "Multiple Latin phrases",
    ),
    (
        "The premiums increased 12.5% year over year, effective January 1st.",
        ["percent", "date"],
        "Decimal percent + ordinal",
    ),
    (
        "Park in lot C, level 2, near elevators 3 and 4.",
        ["alphanumeric", "spatial"],
        "Alphanumerics + spatial",
    ),
    (
        "Email the redline of the NDA back by EOD tomorrow.",
        ["abbreviations", "abbreviation_eod"],
        "EOD; NDA",
    ),
    (
        "Mr. McAllister-Quinones is in conflicts review.",
        ["proper_nouns_difficult", "hyphenated_names"],
        "Difficult compound surname",
    ),
    (
        "The check arrives on or about the third of the month.",
        ["informal_date", "idiom"],
        "Vague date phrase",
    ),
    (
        "She authored Smith v. State, decided in the Eastern District last year.",
        ["case_caption_generic", "geographic"],
        "Generic case-caption pattern",
    ),
    (
        "Twenty-seven thousand four hundred fifty dollars and zero cents.",
        ["spelled_money", "spelled_numbers"],
        "Fully spelled money",
    ),
    (
        "Reschedule from 11:45 to noon on the same day.",
        ["time_format", "noon_keyword"],
        "Time + 'noon' keyword",
    ),
    (
        "The complaint cites breach of fiduciary duty and tortious interference.",
        ["legal_terminology"],
        "Two legal terms back-to-back",
    ),
    (
        "Please confirm whether the address is 1 N. Broadway or 1 South Broadway.",
        ["abbreviations_directional", "proper_nouns"],
        "Directional abbreviations",
    ),
]


def _build_pairs() -> list[dict]:
    out: list[dict] = []
    for i, (text, kinds, notes) in enumerate(PAIRS, start=1):
        out.append(
            {
                "pair_id": f"tts-{i:04d}",
                "text": text,
                "edge_case_kinds": kinds,
                "notes": notes,
            }
        )
    return out


def _update_manifest(sha: str, now_utc: str) -> None:
    fieldnames = [
        "asset_id",
        "corpus",
        "path",
        "sha256",
        "license",
        "source",
        "created_utc",
        "generator_script",
        "generator_seed",
        "kokoro_revision",
        "intent",
        "adversity_level",
        "persona",
        "duration_s",
        "sample_rate",
    ]
    existing: list[dict[str, str]] = []
    if MANIFEST_PATH.exists():
        with MANIFEST_PATH.open() as f:
            existing = list(csv.DictReader(f))
    by_id = {r["asset_id"]: r for r in existing}
    # Preserve created_utc when sha unchanged so idempotent re-runs do not drift.
    existing_row = by_id.get("tts_pairs_text")
    created = (
        existing_row["created_utc"] if existing_row and existing_row["sha256"] == sha else now_utc
    )
    by_id["tts_pairs_text"] = {
        "asset_id": "tts_pairs_text",
        "corpus": "corpus_tts_pairs",
        "path": "assets/tts_pairs/pairs.json",
        "sha256": sha,
        "license": "synthetic",
        "source": "assets/tts_pairs/author_pairs.py",
        "created_utc": created,
        "generator_script": "assets/tts_pairs/author_pairs.py",
        "generator_seed": "0",
        "kokoro_revision": "",
        "intent": "",
        "adversity_level": "",
        "persona": "",
        "duration_s": "",
        "sample_rate": "",
    }
    with MANIFEST_PATH.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for asset_id in sorted(by_id):
            full = {k: by_id[asset_id].get(k, "") for k in fieldnames}
            writer.writerow(full)


def main() -> int:
    pairs = _build_pairs()
    assert len(pairs) == 30, f"expected 30, got {len(pairs)}"
    payload = json.dumps(pairs, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    PAIRS_PATH.write_text(payload)
    sha = hashlib.sha256(payload.encode()).hexdigest()
    now_utc = datetime.now(tz=UTC).replace(microsecond=0).isoformat()
    _update_manifest(sha, now_utc)
    print(f"Wrote {len(pairs)} TTS A/B text pairs.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
