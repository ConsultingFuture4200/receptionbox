"""Tests for tools/pod_entrypoint.sh and tools/rsync_results.sh (CLOUD-04, D-16/D-17/D-18).

These tests are *static analysis* on the shell scripts: syntax check, presence
of required idioms, source ordering of audit→rsync, and the assets/-never-rsynced
invariant. Live invocation requires a RunPod pod environment so is out of scope.

Hard contracts:
- assets/ is NEVER the rsync source — only results/ (T1 mitigation)
- Audit runs BEFORE rsync; audit-fail → audit-only rsync (D-23)
- SSH key value is never echoed to stdout/stderr (T2 mitigation)
"""

from __future__ import annotations

import os
import pathlib
import shutil
import subprocess

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
ENTRY = ROOT / "tools" / "pod_entrypoint.sh"
RSYNC = ROOT / "tools" / "rsync_results.sh"


def test_entrypoint_script_exists_and_is_executable() -> None:
    assert ENTRY.exists(), f"missing: {ENTRY}"
    assert os.access(ENTRY, os.X_OK), f"not executable: {ENTRY}"


def test_rsync_script_exists_and_is_executable() -> None:
    assert RSYNC.exists(), f"missing: {RSYNC}"
    assert os.access(RSYNC, os.X_OK), f"not executable: {RSYNC}"


def test_entrypoint_has_set_euo_pipefail() -> None:
    src = ENTRY.read_text()
    assert "set -euo pipefail" in src, "entrypoint must use set -euo pipefail"


def test_rsync_has_set_euo_pipefail() -> None:
    src = RSYNC.read_text()
    assert "set -euo pipefail" in src


def test_entrypoint_traps_term_and_int() -> None:
    src = ENTRY.read_text()
    # SIGTERM trap is the watchdog/operator-stop entry point (D-16, D-17).
    assert "trap " in src and ("TERM" in src), "missing TERM trap"
    assert "INT" in src, "missing INT trap"


def test_entrypoint_invokes_audit_before_rsync() -> None:
    """In _shutdown(), audit_pod_state must be called before rsync_results.sh."""
    src = ENTRY.read_text()
    audit_idx = src.find("audit_pod_state")
    rsync_idx = src.find("rsync_results.sh")
    assert audit_idx != -1, "audit_pod_state.py not invoked"
    assert rsync_idx != -1, "rsync_results.sh not invoked"
    assert audit_idx < rsync_idx, (
        "audit must run BEFORE rsync (D-22 fail-loud → D-23 audit-only rsync)"
    )


def test_entrypoint_audit_failure_invokes_audit_only_rsync() -> None:
    """If audit returns non-zero, rsync_results.sh --audit-only must run."""
    src = ENTRY.read_text()
    assert "AUDIT_RC" in src
    assert "--audit-only" in src


def test_entrypoint_self_stops_via_runpodctl() -> None:
    src = ENTRY.read_text()
    assert "runpodctl pod stop" in src, "missing self-stop via runpodctl"


def test_entrypoint_does_not_rsync_assets() -> None:
    """assets/ MUST NEVER be the rsync source. Only results/ may cross the wire."""
    for f in (ENTRY, RSYNC):
        src = f.read_text()
        for line in src.splitlines():
            stripped = line.lstrip()
            if stripped.startswith("#"):
                # Comments are documentation, not invocations.
                continue
            if "rsync " in stripped and "assets" in stripped:
                pytest.fail(f"{f.name} appears to rsync assets/: {stripped!r}")


def test_rsync_full_mode_uses_results_as_source() -> None:
    src = RSYNC.read_text()
    # results/ must appear as the source argument (followed by remote target)
    assert "results/" in src
    # And the remote target must be ~/RBOX/results/ (not ~/RBOX/ which would
    # accept assets pushed by mistake on the operator side).
    assert "~/RBOX/results/" in src or ":~/RBOX/results/" in src


def test_rsync_audit_only_mode_includes_only_audit_json() -> None:
    src = RSYNC.read_text()
    assert "--audit-only" in src
    assert "*.audit.json" in src
    assert "--exclude='*'" in src or '--exclude="*"' in src


def test_entrypoint_smoke_uses_g1_runner_with_5_calls() -> None:
    """D-24 smoke profile: gates.g1.runner --gate=smoke --n-calls=5."""
    src = ENTRY.read_text()
    assert "gates.g1.runner" in src
    assert "--gate=smoke" in src
    assert "--n-calls=5" in src


def test_entrypoint_does_not_log_ssh_key_value() -> None:
    """T2 mitigation: SSH_PRIVATE_KEY value must never be printed to stdout/stderr.

    Reject any echo/printf line that expands SSH_PRIVATE_KEY without an output
    redirection (`>`). Existence tests (`[[ -n "${SSH_PRIVATE_KEY:-}" ]]`) and
    comments are fine — those don't emit the value.
    """
    src = ENTRY.read_text()
    for ln, line in enumerate(src.splitlines(), 1):
        stripped = line.lstrip()
        if stripped.startswith("#"):
            continue
        if "$SSH_PRIVATE_KEY" not in line and "${SSH_PRIVATE_KEY" not in line:
            continue
        # Only flag print-like operators (echo/printf) without a file redirect.
        is_print = stripped.startswith("echo ") or stripped.startswith("printf ")
        has_redirect = ">" in stripped
        if is_print and not has_redirect:
            pytest.fail(f"line {ln}: SSH_PRIVATE_KEY printed without file redirect: {stripped!r}")


def test_entrypoint_watchdog_uses_max_minutes_sleep_and_kill() -> None:
    """D-16: watchdog mechanism is `sleep $((MAX_MINUTES*60)); kill -TERM`."""
    src = ENTRY.read_text()
    assert "MAX_MINUTES" in src
    assert "sleep" in src
    assert "kill -TERM" in src


@pytest.mark.skipif(shutil.which("bash") is None, reason="bash not available")
def test_entrypoint_bash_syntax_valid() -> None:
    r = subprocess.run(["bash", "-n", str(ENTRY)], capture_output=True, text=True)
    assert r.returncode == 0, f"bash -n failed:\n{r.stderr}"


@pytest.mark.skipif(shutil.which("bash") is None, reason="bash not available")
def test_rsync_bash_syntax_valid() -> None:
    r = subprocess.run(["bash", "-n", str(RSYNC)], capture_output=True, text=True)
    assert r.returncode == 0, f"bash -n failed:\n{r.stderr}"


@pytest.mark.skipif(shutil.which("shellcheck") is None, reason="shellcheck not installed")
def test_entrypoint_shellcheck_clean() -> None:
    r = subprocess.run(["shellcheck", str(ENTRY)], capture_output=True, text=True)
    assert r.returncode == 0, f"shellcheck:\n{r.stdout}\n{r.stderr}"


@pytest.mark.skipif(shutil.which("shellcheck") is None, reason="shellcheck not installed")
def test_rsync_shellcheck_clean() -> None:
    r = subprocess.run(["shellcheck", str(RSYNC)], capture_output=True, text=True)
    assert r.returncode == 0, f"shellcheck:\n{r.stdout}\n{r.stderr}"
