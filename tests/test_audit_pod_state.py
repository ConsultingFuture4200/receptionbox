"""Tests for tools/audit_pod_state.py (CLOUD-06, D-22, D-23).

The audit is the last line of defense against PII / real-audio leakage from a pod
back to the operator workstation. Coverage targets:

- manifest_check: SHA mismatch / extras / dotfile skip
- extension_check: any audio extension under results/ is a violation
- pii_check: SSN / phone / email regexes hit; matches are redacted in the log
- audit log written EVEN on failure (D-23 contract)
- exit code 0 on clean, exit 1 on any violation
"""

from __future__ import annotations

import csv
import hashlib
import json
import pathlib

import pytest

from tools import audit_pod_state as audit


def _write_manifest(path: pathlib.Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = [
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
    with path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in rows:
            full = {k: r.get(k, "") for k in fields}
            w.writerow(full)


def _sha(p: pathlib.Path) -> str:
    h = hashlib.sha256()
    h.update(p.read_bytes())
    return h.hexdigest()


def _make_clean_pod(tmp_path: pathlib.Path) -> pathlib.Path:
    """Build a synthetic pod fs: one matching asset, one clean results JSONL."""
    root = tmp_path / "workspace"
    (root / "assets").mkdir(parents=True)
    asset = root / "assets" / "x.wav"
    asset.write_bytes(b"fake-wav-bytes")
    _write_manifest(
        root / "assets" / "manifest.csv",
        [{"asset_id": "x", "corpus": "c", "path": "assets/x.wav", "sha256": _sha(asset)}],
    )
    (root / "results" / "g1").mkdir(parents=True)
    (root / "results" / "g1" / "run.jsonl").write_text(
        '{"asset_id":"x","status":"ok","metric":1.23}\n'
    )
    return root


def test_audit_clean_run_exits_zero(tmp_path: pathlib.Path) -> None:
    root = _make_clean_pod(tmp_path)
    log = tmp_path / "audit.json"
    rc = audit.main(
        [
            "--root",
            str(root),
            "--manifest",
            "assets/manifest.csv",
            "--results-dir",
            "results",
            "--audit-log",
            str(log),
        ]
    )
    assert rc == 0
    data = json.loads(log.read_text())
    assert data["summary"]["violations"] == 0


def test_audit_extra_asset_file_is_violation(tmp_path: pathlib.Path) -> None:
    root = _make_clean_pod(tmp_path)
    # Add an extra unlisted file under assets/
    (root / "assets" / "rogue.wav").write_bytes(b"surprise")
    log = tmp_path / "audit.json"
    rc = audit.main(
        [
            "--root",
            str(root),
            "--manifest",
            "assets/manifest.csv",
            "--results-dir",
            "results",
            "--audit-log",
            str(log),
        ]
    )
    assert rc == 1
    data = json.loads(log.read_text())
    assert data["manifest_check"]["violations"] >= 1
    assert any("rogue.wav" in p for p in data["manifest_check"]["extras"])


def test_audit_sha_mismatch_is_violation(tmp_path: pathlib.Path) -> None:
    root = _make_clean_pod(tmp_path)
    # Modify the file post-manifest
    (root / "assets" / "x.wav").write_bytes(b"tampered-content")
    log = tmp_path / "audit.json"
    rc = audit.main(
        [
            "--root",
            str(root),
            "--manifest",
            "assets/manifest.csv",
            "--results-dir",
            "results",
            "--audit-log",
            str(log),
        ]
    )
    assert rc == 1
    data = json.loads(log.read_text())
    paths = [m["path"] for m in data["manifest_check"]["mismatches"]]
    assert any("x.wav" in p for p in paths)


def test_audit_audio_extension_under_results_is_violation(tmp_path: pathlib.Path) -> None:
    root = _make_clean_pod(tmp_path)
    (root / "results" / "g1" / "smuggled.wav").write_bytes(b"audio")
    log = tmp_path / "audit.json"
    rc = audit.main(
        [
            "--root",
            str(root),
            "--manifest",
            "assets/manifest.csv",
            "--results-dir",
            "results",
            "--audit-log",
            str(log),
        ]
    )
    assert rc == 1
    data = json.loads(log.read_text())
    assert any("smuggled.wav" in p for p in data["extension_check"]["offending_files"])


def test_audit_pii_ssn_in_jsonl_is_violation(tmp_path: pathlib.Path) -> None:
    root = _make_clean_pod(tmp_path)
    (root / "results" / "g1" / "leak.jsonl").write_text('{"note":"ssn 123-45-6789 leaked"}\n')
    log = tmp_path / "audit.json"
    rc = audit.main(
        [
            "--root",
            str(root),
            "--manifest",
            "assets/manifest.csv",
            "--results-dir",
            "results",
            "--audit-log",
            str(log),
        ]
    )
    assert rc == 1
    data = json.loads(log.read_text())
    hits = data["pii_check"]["hits"]
    assert any(h["kind"] == "ssn" for h in hits)
    # Redacted match must NOT contain the original digits
    for h in hits:
        if h["kind"] == "ssn":
            assert "123-45-6789" not in h["match_redacted"]


def test_audit_pii_phone_and_email(tmp_path: pathlib.Path) -> None:
    root = _make_clean_pod(tmp_path)
    (root / "results" / "g1" / "leak.txt").write_text(
        "call us at (555) 123-4567 or email contact@example.com"
    )
    log = tmp_path / "audit.json"
    rc = audit.main(
        [
            "--root",
            str(root),
            "--manifest",
            "assets/manifest.csv",
            "--results-dir",
            "results",
            "--audit-log",
            str(log),
        ]
    )
    assert rc == 1
    data = json.loads(log.read_text())
    kinds = {h["kind"] for h in data["pii_check"]["hits"]}
    assert "phone" in kinds
    assert "email" in kinds


def test_audit_log_written_even_on_failure(tmp_path: pathlib.Path) -> None:
    """D-23 contract: the audit log itself is the only artifact rsynced on fail."""
    root = _make_clean_pod(tmp_path)
    (root / "results" / "g1" / "leak.txt").write_text("user@host.com")
    log = tmp_path / "deep" / "nested" / "audit.json"
    rc = audit.main(
        [
            "--root",
            str(root),
            "--manifest",
            "assets/manifest.csv",
            "--results-dir",
            "results",
            "--audit-log",
            str(log),
        ]
    )
    assert rc == 1
    assert log.exists(), "audit log MUST exist after failed run"


def test_audit_log_redacts_pii_in_match_field(tmp_path: pathlib.Path) -> None:
    root = _make_clean_pod(tmp_path)
    secret = "555-12-3456"
    (root / "results" / "g1" / "leak.jsonl").write_text(json.dumps({"x": f"ssn={secret}"}) + "\n")
    log = tmp_path / "audit.json"
    audit.main(
        [
            "--root",
            str(root),
            "--manifest",
            "assets/manifest.csv",
            "--results-dir",
            "results",
            "--audit-log",
            str(log),
        ]
    )
    data = json.loads(log.read_text())
    # The full SSN must NOT appear in the match_redacted field
    for h in data["pii_check"]["hits"]:
        assert secret not in h["match_redacted"], (
            f"PII leaked into audit log: {h['match_redacted']}"
        )


def test_audit_skips_dotfiles_under_assets(tmp_path: pathlib.Path) -> None:
    """`.git/` / `.DS_Store` under assets/ are not counted as extras."""
    root = _make_clean_pod(tmp_path)
    (root / "assets" / ".git").mkdir()
    (root / "assets" / ".git" / "HEAD").write_bytes(b"ref: refs/heads/main\n")
    (root / "assets" / ".DS_Store").write_bytes(b"\x00\x00\x00")
    log = tmp_path / "audit.json"
    rc = audit.main(
        [
            "--root",
            str(root),
            "--manifest",
            "assets/manifest.csv",
            "--results-dir",
            "results",
            "--audit-log",
            str(log),
        ]
    )
    assert rc == 0, json.loads(log.read_text())
    data = json.loads(log.read_text())
    assert data["manifest_check"]["violations"] == 0


def test_audit_help_exits_zero() -> None:
    """--help must not raise."""
    with pytest.raises(SystemExit) as ei:
        audit.main(["--help"])
    assert ei.value.code == 0
