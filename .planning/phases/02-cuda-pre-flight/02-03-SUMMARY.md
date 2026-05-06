---
phase: 02-cuda-pre-flight
plan: 03
subsystem: orchestration
tags: [CLOUD-04, CLOUD-05, CLOUD-06, D-16, D-17, D-18, D-19, D-20, D-21, D-22, D-23, watchdog, audit, cache-bootstrap, runpod-provisioning]
requires:
  - Plan 02-01 (substrate/cuda.py — referenced by entrypoint via gate runner)
  - Plan 02-02 (gates/g{1,2,3,5}/runner.py — execed from entrypoint)
  - cost/ledger.py:authorize_spend (Hard Constraint #1 gate, AST-asserted)
  - assets/manifest.csv (audit truth set)
  - bench/models.lock.yaml (cache bootstrap source)
  - tests/test_orchestration_skeletons.py (Phase 1 AST lock-in must remain green)
provides:
  - tools/audit_pod_state.py (CLOUD-06: manifest SHA + extension blocklist + PII regex; fail-loud)
  - tools/cache_bootstrap.py (CLOUD-05: SHA-keyed /models/{repo}/{rev}/ pulls; idempotent)
  - tools/pod_entrypoint.sh (CLOUD-04: watchdog + audit + rsync + self-stop trap)
  - tools/rsync_results.sh (D-17 results push; --audit-only mode for D-23)
  - orchestration/runpod_h100.py:{provision,terminate,ProvisionResult,RunPodProvisionError}
  - config/budget.yaml phase2 block (D-18 max_minutes_per_gate; D-20 cache cost line item)
affects:
  - Plan 02-04 (sanity strata) feeds config/sanity_strata.yaml that the entrypoint passes to runners
  - Phase 3 reuses pod_entrypoint.sh + audit + rsync_results.sh verbatim — same trap pattern on MI300X
  - Phase 1 AST lock-in (test_orchestration_modules_call_authorize_spend_first) remains green
tech-stack:
  added: []  # All new modules use existing Phase 1/2 deps (huggingface_hub, pyyaml, pydantic). No new wheels.
  patterns:
    - "First AST Call in provision() is authorize_spend(...) — Hard Constraint #1 preserved across stub-to-real swap"
    - "Audit fails LOUD with non-zero exit (D-22); audit log written even on failure (D-23)"
    - "PII matches redacted to first-2 + last-2 chars in audit log (T-02-03-07)"
    - "rsync source is ALWAYS results/ — never assets/ (T1 mitigation, grep-asserted by test)"
    - "Cache bootstrap is idempotent via .bootstrap.json marker file"
    - "Bootstrap failures graceful-degrade (per-model log + omit from index, never raise)"
    - "Provision dry-runs when RUNPOD_API_KEY unset — operator iterates offline without spend"
    - "SSH key value written to file via printf > file; never echoed (T2 mitigation, source-grep test)"
    - "_shutdown() is idempotent — trap and normal-exit can both fire it without double-running"
key-files:
  created:
    - tools/audit_pod_state.py
    - tools/cache_bootstrap.py
    - tools/pod_entrypoint.sh
    - tools/rsync_results.sh
    - tests/test_audit_pod_state.py
    - tests/test_cache_bootstrap.py
    - tests/test_runpod_provisioning.py
    - tests/test_pod_entrypoint.py
  modified:
    - orchestration/runpod_h100.py (Phase 1 stub replaced by real provisioning; ProvisionResult dataclass)
    - config/budget.yaml (added phase2 block per D-18, D-20)
    - tests/test_orchestration_skeletons.py (test_runpod_provision_authorizes_within_budget reads result.authorization.provider — return type changed to ProvisionResult)
decisions:
  - "Audit manifest_check scope: AUDIO files only under assets/ (matches tools/check_asset_manifest.py pattern). Source code / scripts / probes / markdown under assets/ are committed code, not provenance-tracked audio. Without this scope filter, the audit would fail-loud on every dev tree (23 extras: __init__.py, render scripts, JSON probes, etc.)"
  - "SSH-key-leak test only flags echo/printf lines without file redirect — existence checks like [[ -n \"${SSH_PRIVATE_KEY:-}\" ]] are safe and required by the script"
  - "_shutdown() idempotency guard added: trap on TERM/INT and normal exit at end of script can both fire it; without the guard the audit + rsync would run twice"
  - "ProvisionResult is the new return type for provision(); Authorization remains reachable via .authorization for the Phase 1 ledger contract test"
  - "RunPodProvisionError is thrown when SDK fails AFTER ledger commit, so callers can record/refund the spend (the Authorization row is already committed)"
  - "Audit log is sorted via sort_keys=True for byte-stable output (D-23 audit log is THE artifact rsynced on fail; stability matters for diffing)"
metrics:
  duration_hours: 0.5
  completed: 2026-05-06
  tasks: 4
  tests_added: 41
  total_tests_passing: 205
---

# Phase 2 Plan 03: Cleanup Posture + Real RunPod Provisioning Summary

CLOUD-04/05/06 + Phase 1-stub-to-real swap. The most security-load-bearing plan in Phase 2: pre-teardown audit is fail-LOUD; on failure the audit log is rsynced but result data is NOT (bias to losing the run > leaking PII). Hard Constraint #1 preserved: `authorize_spend` is still the first AST Call in `provision()`.

## What Shipped

### `tools/audit_pod_state.py` — Pre-teardown audit (CLOUD-06, D-22, D-23) — 191 LOC

Three checks; any violation → exit 1 (fail-loud) but audit log is ALWAYS written so the SIGTERM handler can rsync the log without rsyncing result data on a failed audit (D-23 contract).

| Check | Behavior | Violation criteria |
|-------|----------|--------------------|
| `manifest_check` | Walks `{root}/assets/`, hashes every audio file, compares to `assets/manifest.csv` | extras (unlisted audio file) OR mismatches (sha256 differs) |
| `extension_check` | Walks `{root}/results/` recursively | any file matching `\.(wav\|mp3\|flac\|opus\|ogg\|m4a\|aiff\|webm)$` |
| `pii_check` | Walks `{root}/results/**/*.{json,jsonl,txt,md,csv}` | any line matching SSN / phone / email regex |

Audit log JSON shape (`{run_id}.audit.json`):

```jsonc
{
  "schema_version": "1.0",
  "summary": {"violations": 0, "files_checked": 12, "started_utc": "...", "finished_utc": "...", "manifest_sha": "..."},
  "manifest_check": {"expected_count": 200, "found_count": 200, "extras": [], "mismatches": [], "violations": 0},
  "extension_check": {"offending_files": [], "violations": 0},
  "pii_check": {"hits": [], "files_checked": 12, "violations": 0}
}
```

**PII regex catalog** (3 patterns, deferred-ideas slot for richer catalog):

```python
SSN_RE   = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
PHONE_RE = re.compile(r"\b(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b")
EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
```

Richer catalog (NPI, MRN, credit-card BIN ranges, IBAN, IPv4, etc.) is deferred to a backlog item; the 3 patterns above cover the most likely receptionBOX leak classes (phone numbers from intake forms, email from caller bookkeeping, SSN from any "verify identity" template that slipped through DR-31).

**Match redaction** (T-02-03-07 mitigation): every PII hit's `match_redacted` field shows only the first 2 + last 2 chars (`12*****89` for `123-45-6789`). The original match string never enters the audit log. Verified by `test_audit_log_redacts_pii_in_match_field`.

### `tools/cache_bootstrap.py` — One-time HF cache (CLOUD-05, D-19/D-20/D-21) — 138 LOC

`bootstrap(target=/models, lockfile=bench/models.lock.yaml, force=False)` walks every entry in `models.lock.yaml` and pulls into `/models/{repo_safe}/{revision}/` where `repo_safe = repo_id.replace("/", "__")`. Per D-21, paths are keyed by HF revision SHA — bumping a SHA triggers a fresh pull.

Per-model `.bootstrap.json` marker:
```jsonc
{"repo_id": "...", "revision": "...", "name": "...", "started_utc": "...", "finished_utc": "...", "total_bytes": 12345, "files": ["..."]}
```

Top-level `/models/.bootstrap_index.json` lists every cached model + the lockfile SHA at bootstrap time. Idempotent: pre-existing markers cause the model to be skipped (loaded from disk into the returned index). `--force` flag re-pulls anyway.

Failures (network down, revision moved) log `error` and omit the model from the returned index — never raise. Mirrors the cost-adapter "MUST NOT raise" pattern.

### `orchestration/runpod_h100.py` — Real provisioning replacing Phase 1 stub — 147 LOC

```python
def provision(*, gate, projected_cost, max_minutes=None, network_volume_id=None,
              ssh_pubkey=None, operator_host=None, image_ref="vllm/vllm-openai:v0.10.0",
              gpu_type="NVIDIA H100 PCIe") -> ProvisionResult:
    auth = authorize_spend(provider="runpod", gate=gate, projected_cost=projected_cost)  # FIRST stmt
    api_key = os.environ.get("RUNPOD_API_KEY")
    if not api_key:
        # DRY RUN: ledger row committed; return ProvisionResult(pod_id="dry-run", ...)
        return ProvisionResult(authorization=auth, pod_id="dry-run", ...)
    try:
        import runpod
        runpod.api_key = api_key
        pod = runpod.create_pod(name=..., image_name=image_ref, gpu_type_id=gpu_type,
                                gpu_count=1, volume_in_gb=50, container_disk_in_gb=50,
                                env={GATE, MAX_MINUTES, RUN_ID_PREFIX, [SSH_PUBKEY], [OPERATOR_HOST]},
                                ports="8000/http,22/tcp",
                                [network_volume_id=..., volume_mount_path="/models"])
    except Exception as e:
        raise RunPodProvisionError(str(e)) from e  # auth already committed
    return ProvisionResult(authorization=auth, pod_id=pod["id"], pod_url=..., ...)
```

| Knob | Value | Source |
|------|-------|--------|
| Image | `vllm/vllm-openai:v0.10.0` (CUDA 12.4) | bench/images.lock.yaml + CLAUDE.md §2.2 |
| GPU | `NVIDIA H100 PCIe` | substrates.yaml cuda.gpu |
| Volume | 50 GB container_disk + optional 50 GB network volume mounted at `/models` | D-19 cache headroom |
| Env vars | GATE, MAX_MINUTES, RUN_ID_PREFIX, SSH_PUBKEY (opt), OPERATOR_HOST (opt) | Entrypoint contract |
| Ports | `8000/http,22/tcp` | vLLM serve + ssh for rsync target debug |

When `RUNPOD_API_KEY` is unset, `provision()` returns `ProvisionResult(pod_id="dry-run", pod_url=None, ...)` so the operator can iterate offline. The ledger row is still committed (operator sees the row in `cost/ledger.sqlite`).

`terminate(pod_id)` is the watchdog SIGTERM handler companion: dry-runs when no API key, swallows SDK errors (consistent with cost adapter pattern — terminate must not raise inside a SIGTERM trap).

### `tools/pod_entrypoint.sh` — Pod CMD (CLOUD-04, D-16/D-17/D-18) — 151 LOC

Lifecycle:

```
_setup_ssh        → printf '%s\n' "$SSH_PRIVATE_KEY" > ~/.ssh/id_ed25519; chmod 600
_start_cost_watch → uv run python -m cost.watch --providers runpod --interval 300 &
_start_watchdog   → ( sleep $((MAX_MINUTES * 60)); kill -TERM $ENTRY_PID ) &
exec runner       → uv run python -m gates.g1.runner --gate=smoke --n-calls=5  (smoke)
                  → uv run python -m gates.${GATE}.runner --strata=...           (sanity)
wait $RUNNER_PID  → SIGTERM trap intercepts on watchdog timeout / runpodctl pod stop
```

`trap _shutdown TERM INT` runs:

1. `kill -TERM $RUNNER_PID`; wait up to 60s for graceful drain; `kill -KILL` if needed
2. `python tools/audit_pod_state.py --audit-log results/${GATE}/${ts}.audit.json` → captures `AUDIT_RC`
3. If `AUDIT_RC == 0`: `bash tools/rsync_results.sh` (full results push)
   If `AUDIT_RC != 0`: `bash tools/rsync_results.sh --audit-only` (D-23: only audit log crosses the wire)
4. `runpodctl pod stop $RUNPOD_POD_ID` (self-terminate)

`_SHUTDOWN_DONE` idempotency guard prevents double-firing when both the trap and the post-`wait` path call `_shutdown` (Rule 3 fix during Task 4).

### `tools/rsync_results.sh` — Results push helper — 49 LOC

Two modes:
- **default**: `rsync -avz --partial --append-verify -e "ssh ..." results/ ${USER}@${HOST}:~/RBOX/results/`
- **`--audit-only`**: same but with `--include='*/' --include='*.audit.json' --exclude='*'` so only audit logs cross the wire (D-23 fail-loud egress posture)

**Critical invariant (T1 mitigation):** the rsync source is ALWAYS `results/` — never `assets/`, never workspace root. Verified by `test_entrypoint_does_not_rsync_assets` (greps non-comment lines for `rsync.*assets`; fails if any match). Non-comment grep output:

```
$ grep -RE "rsync.*assets" tools/pod_entrypoint.sh tools/rsync_results.sh \
    | grep -v "^[^:]*:[[:space:]]*#"
(no matches)
```

### `config/budget.yaml` phase2 block — D-18, D-20

```yaml
phase2:
  max_minutes_per_gate:
    smoke: 30
    g1: 30
    g2: 15
    g3: 10
    g5: 15  # sum = 100 minutes per session, well under $14 budget at $2.69/hr SXM
  cache_bootstrap_one_time_usd: 0.50
```

## Hard Constraint #1 — Cost Ledger Gate Preserved

The Phase 1 AST test (`test_orchestration_modules_call_authorize_spend_first`) walks `provision()` in `runpod_h100.py` / `tensorwave_mi300x.py` / `vultr_mi300x.py`, finds the first `ast.Call` in the function body, and asserts the call target is `authorize_spend`. The new `runpod_h100.py:provision()` body's first executable statement is:

```python
auth = authorize_spend(provider="runpod", gate=gate, projected_cost=projected_cost)
```

`os.environ.get(...)` and `datetime.utcnow().isoformat()` come AFTER, so the AST test stays green. Verified:

```bash
$ uv run pytest tests/test_orchestration_skeletons.py::test_orchestration_modules_call_authorize_spend_first -q
1 passed
```

Behavior-level proof: `test_provision_calls_authorize_spend_first` (in test_runpod_provisioning.py) installs a fake `runpod` SDK, sets `RUNPOD_API_KEY=fake-key`, calls `provision(projected_cost=60.0)` (which violates the $75 cap with safety_factor 1.5 = $90 needed), asserts `BudgetExhausted` is raised AND `runpod.create_pod` was never called.

## Test Count

41 new tests across 4 test files (full suite: 205 passing, +41 vs Plan 02-02's 164).

| File | Tests | Coverage focus |
|------|-------|----------------|
| `tests/test_audit_pod_state.py` | 10 | manifest SHA / extras / dotfile-skip; audio-extension blocklist; SSN/phone/email regex hits; PII redaction (T-02-03-07 mitigation); audit log written on failure (D-23) |
| `tests/test_cache_bootstrap.py` | 7 | pending-skip; marker creation; idempotency; --force; failure no-raise; budget.yaml phase2 contract; --help |
| `tests/test_runpod_provisioning.py` | 8 | dry-run path; AST ordering preserved (BudgetExhausted → no SDK call); volume_mount_path=/models; env-var injection; SDK-failure → RunPodProvisionError; terminate dry-run + SDK-failure swallow |
| `tests/test_pod_entrypoint.py` | 16 (2 skipped) | existence + executability; set -euo pipefail; TERM/INT trap; audit-before-rsync ordering; --audit-only path; runpodctl self-stop; assets/ never rsynced; rsync target ~/RBOX/results/; smoke = g1.runner --n-calls=5 (D-24); SSH key never echoed (T2 mitigation); watchdog sleep+kill; bash -n syntax; shellcheck (skipped: not installed) |

## LOC

| File | LOC |
|------|-----|
| tools/audit_pod_state.py | 191 |
| tools/cache_bootstrap.py | 138 |
| tools/pod_entrypoint.sh | 151 |
| tools/rsync_results.sh | 49 |
| orchestration/runpod_h100.py | 147 |
| tests/test_audit_pod_state.py | 287 |
| tests/test_cache_bootstrap.py | 174 |
| tests/test_runpod_provisioning.py | 179 |
| tests/test_pod_entrypoint.py | 165 |
| **total** | **1,481** |

## Verification

```bash
$ uv run pytest -q
205 passed, 2 skipped in 4.86s

$ uv run ruff check tools/audit_pod_state.py tools/cache_bootstrap.py orchestration/runpod_h100.py
All checks passed!

$ bash -n tools/pod_entrypoint.sh && bash -n tools/rsync_results.sh && echo OK
OK

$ test -x tools/pod_entrypoint.sh && test -x tools/rsync_results.sh && echo executable
executable

$ ! grep -RE "rsync.*assets" tools/pod_entrypoint.sh tools/rsync_results.sh \
    | grep -v "^[^:]*:[[:space:]]*#" && echo "no non-comment matches"
no non-comment matches

$ uv run python tools/audit_pod_state.py --root . --audit-log /tmp/rbox_audit.json
2026-05-06 09:52:02 INFO AUDIT OK: 0 violations; 0 text files checked
$ python -c "import json; d=json.load(open('/tmp/rbox_audit.json')); print(d['summary']['violations'])"
0

$ uv run pytest tests/test_orchestration_skeletons.py::test_orchestration_modules_call_authorize_spend_first -q
1 passed
```

## Operator's Current State — Audit Self-Test

`uv run python tools/audit_pod_state.py --root . --audit-log /tmp/rbox_audit.json` against the actual `~/RBOX` dev tree exits 0 with 0 violations:

- `manifest_check`: 760 audio files in manifest, 760 found in `assets/corpus_500/`, `assets/corpus_g711/`, `assets/corpus_hesitation/`, `assets/tts_pairs/`. SHA-256 match across all entries.
- `extension_check`: 0 audio files under `results/` (results dir is empty pre-flight)
- `pii_check`: 0 text files checked (results dir empty); no PII hits possible

Operator can run this command at any time during dev to validate posture before pushing changes.

## Dry-Run pod_id

When `RUNPOD_API_KEY` is unset, `provision()` returns `ProvisionResult(pod_id="dry-run", pod_url=None, ...)`. Verified by `test_provision_dry_run_when_no_api_key`:

```python
result = runpod_h100.provision(gate="smoke", projected_cost=1.0)
assert result.pod_id == "dry-run"
assert result.authorization.provider == "runpod"  # ledger row IS committed
```

The operator's local dev workflow:

```bash
$ unset RUNPOD_API_KEY
$ uv run python -c "from orchestration.runpod_h100 import provision; r = provision(gate='smoke', projected_cost=1.0); print(r.pod_id)"
dry-run  # plus a WARNING log showing what WOULD be created
$ sqlite3 cost/ledger.sqlite "SELECT * FROM authorizations ORDER BY id DESC LIMIT 1"
# row exists — ledger committed even on dry-run
```

## Deviations from Plan

### [Rule 3 — Blocking] Audit manifest scope filter

- **Found during:** Task 1 verification (acceptance criterion: dev tree must audit clean)
- **Issue:** D-22 wording says "every file under assets/" but the manifest only lists audio files. Without a scope filter, the audit found 23 extras on the dev tree (`__init__.py`, `g711.py`, render scripts, JSON probes, `.pyc` files, etc.) — non-audio source code that's committed to the repo and not provenance-tracked.
- **Fix:** `manifest_check` walks only files matching `AUDIO_EXTS` regex under `assets/`. Aligns with the existing `tools/check_asset_manifest.py` pattern (which uses the same audio-only scope) and CLOUD-06's actual security concern (real-audio / PII leakage, not source-code drift).
- **Files modified:** `tools/audit_pod_state.py`
- **Commit:** 2982c42

### [Rule 1 — Bug] assets-rsync test caught a comment, not an invocation

- **Found during:** Task 4 verification
- **Issue:** `test_entrypoint_does_not_rsync_assets` fired on `# Strict: assets/ is NEVER copied back. The rsync source is results/ only.` because the comment contained both `rsync ` and `assets`.
- **Fix:** test now skips lines starting with `#` so it only flags actual rsync invocations.
- **Files modified:** `tests/test_pod_entrypoint.py`
- **Commit:** 9196bf7

### [Rule 1 — Bug] SSH key leak test fired on existence check

- **Found during:** Task 4 verification
- **Issue:** `test_entrypoint_does_not_log_ssh_key_value` flagged `if [[ -n "${SSH_PRIVATE_KEY:-}" ]]; then` as "SSH_PRIVATE_KEY appears without file redirect" — but that line is an existence check, not a value-emission. The original test was over-broad.
- **Fix:** test now only flags `echo`/`printf` lines that expand `SSH_PRIVATE_KEY` without an output redirect.
- **Files modified:** `tests/test_pod_entrypoint.py`
- **Commit:** 9196bf7

### [Rule 3 — Blocking] _shutdown() idempotency guard

- **Found during:** Task 4 implementation
- **Issue:** entrypoint script ends with `wait "$RUNNER_PID"; _shutdown` (normal exit path). If a watchdog SIGTERM fires, the trap runs `_shutdown` AND the post-wait line runs `_shutdown` again, causing the audit + rsync to run twice (double-rsync wastes bandwidth + double-audit log file races on path).
- **Fix:** added `_SHUTDOWN_DONE=0` guard at top of `_shutdown`; sets to 1 on first invocation, returns early on subsequent calls.
- **Files modified:** `tools/pod_entrypoint.sh`
- **Commit:** 9196bf7

### [Rule 1 — Bug] Phase 1 test on return type

- **Found during:** Task 3 verification
- **Issue:** `tests/test_orchestration_skeletons.py::test_runpod_provision_authorizes_within_budget` accessed `auth.provider` on the return value. The new `provision()` returns `ProvisionResult`, not `Authorization`, so this attribute access broke.
- **Fix:** test reads `result.authorization.provider` (the `Authorization` is now a member of `ProvisionResult`). The plan's interfaces section anticipated this — `ProvisionResult` is the documented return type.
- **Files modified:** `tests/test_orchestration_skeletons.py`
- **Commit:** c09519b

No Rule 4 architectural decisions required. No checkpoints hit. No real RunPod spend incurred (mocks only).

## Threat Model Disposition

| Threat ID | Disposition | Mitigation Verified |
|-----------|-------------|---------------------|
| T1 — PII / real-audio leak via rsync | mitigate | rsync source is ALWAYS `results/` — never `assets/`. Verified by `test_entrypoint_does_not_rsync_assets` (non-comment grep across both shell scripts). Audit-fail → `--audit-only` mode (results data never crosses the wire). Verified by `test_entrypoint_audit_failure_invokes_audit_only_rsync`. |
| T2 — SSH key exposure in pod env | mitigate | Key value reaches the pod via the SSH_PRIVATE_KEY env var, written via `printf '%s\n' "$SSH_PRIVATE_KEY" > ~/.ssh/id_ed25519` (file redirect, never stdout/stderr). Mode 0600 set. Verified by `test_entrypoint_does_not_log_ssh_key_value` (source grep across `tools/pod_entrypoint.sh`). |
| T3 — cost-cap bypass | mitigate | `authorize_spend(...)` is the FIRST AST `Call` in `provision()` body — Phase 1 AST test still green (`test_orchestration_modules_call_authorize_spend_first`). Behavior-level proof: `test_provision_calls_authorize_spend_first` mocks the SDK and asserts `runpod.create_pod` is NEVER called when `BudgetExhausted` raises. |
| T4 — HF model substitution / SHA mismatch | mitigate | Cache paths keyed by HF revision SHA per D-21 (`/models/{repo_safe}/{revision}/`). Different SHA → different cache directory → cannot collide. Marker file (`.bootstrap.json`) records `repo_id + revision + total_bytes + files[]` for read-time integrity. Top-level `.bootstrap_index.json` records `lockfile_sha` so a swap of the lockfile is detectable. |
| T5 — audit-tool tampering | mitigate | Audit script is committed to git (`tools/audit_pod_state.py`); the entrypoint invokes it by file path inside the pod workspace, NOT downloaded at runtime. If the file is missing/unreadable, `python tools/audit_pod_state.py` exits non-zero, the entrypoint catches that as `AUDIT_RC != 0`, the audit-only rsync path runs (operator gets the missing-script error in the rsync output). The audit cannot be silently disabled. |
| T-02-03-06 — watchdog hangs (single-mechanism risk) | accept | D-16 explicitly accepts the single-mechanism watchdog (`sleep N; kill -TERM` cannot fail at the kernel level). Operator-side cost-watch hard-stop (Phase 1) is the secondary layer. External poller deferred to backlog. |
| T-02-03-07 — audit log itself contains PII | mitigate | PII matches in audit log are redacted via `_redact()` (first-2 + last-2 chars only). Verified by `test_audit_log_redacts_pii_in_match_field` — asserts the original full match never appears in the `match_redacted` field. |

## Self-Check: PASSED

Files (all created):

- tools/audit_pod_state.py: FOUND
- tools/cache_bootstrap.py: FOUND
- tools/pod_entrypoint.sh: FOUND
- tools/rsync_results.sh: FOUND
- tests/test_audit_pod_state.py: FOUND
- tests/test_cache_bootstrap.py: FOUND
- tests/test_runpod_provisioning.py: FOUND
- tests/test_pod_entrypoint.py: FOUND

Files modified:

- orchestration/runpod_h100.py: MODIFIED (Phase 1 stub → real provisioning + ProvisionResult dataclass + RunPodProvisionError + terminate())
- config/budget.yaml: MODIFIED (added phase2 block per D-18, D-20)
- tests/test_orchestration_skeletons.py: MODIFIED (test_runpod_provision_authorizes_within_budget reads result.authorization.provider)

Commits (in order):

- baadd80: test(02-03): add failing tests for pre-teardown audit (CLOUD-06, D-22, D-23)
- 2982c42: feat(02-03): implement pre-teardown audit (CLOUD-06, D-22, D-23)
- faf5c5f: test(02-03): add failing tests for HF cache bootstrap (CLOUD-05, D-19/D-20/D-21)
- 774a152: feat(02-03): implement HF cache bootstrap + budget phase2 block (CLOUD-05)
- 5e1224c: test(02-03): add failing tests for real RunPod provisioning
- c09519b: feat(02-03): implement real RunPod provisioning replacing Phase 1 stub
- 81a6393: test(02-03): add failing tests for pod entrypoint + rsync (CLOUD-04)
- 9196bf7: feat(02-03): pod entrypoint + rsync helper (CLOUD-04, D-16/D-17/D-18)

All 8 commits present. No deferred items. No blockers introduced. Phase 1 AST lock-in (`test_orchestration_modules_call_authorize_spend_first`) remains green. No real RunPod spend in this plan — all unit tests use mocks.
