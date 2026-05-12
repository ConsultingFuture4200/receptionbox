---
phase: 02-cuda-pre-flight
plan: 09
subsystem: test-suite hygiene / cloud-key isolation
gap_closure: true
closes_gaps:
  - "test-1-cold-start-pytest (02-UAT.md, severity=blocker)"
tags: [test-mocks, gap-closure, runpod, conftest, pytest-hangs]
files_modified:
  - tests/test_run_preflight.py
  - tests/test_orchestration_skeletons.py
  - tests/conftest.py
commits:
  - 97919eb test(02-09): stub tools.fetch_results.fetch in run_preflight smoke fixture
  - a7e368d test(02-09): force dry-run path in runpod budget-authorization test
  - ee684bc test(02-09): autouse conftest fixture scrubs cloud API keys per test
---

# Phase 02 Plan 09 — Summary

## Outcome

Closes the single blocker gap in 02-UAT.md (2026-05-12). Phase 02 cold-start
`uv run pytest -q` is now clean: **288 passed, 2 skipped, 0 failed in ~7.5s**,
both with the operator's real `RUNPOD_API_KEY` exported AND with the env
clean. Two distinct test-side defects fixed, and one belt-and-suspenders
conftest fixture added so future tests cannot regress into making real
RunPod GraphQL calls.

No production code changed — `orchestration/runpod_h100.py`,
`tools/run_preflight.py`, `tools/fetch_results.py` untouched. Pure mock
surface widening + per-test env discipline + a session-wide policy fixture.

## What shipped

Three atomic commits, 3 files changed, +63/-2 LOC.

| Commit | File | Change |
|---|---|---|
| `97919eb` | `tests/test_run_preflight.py` | `_install_fake_runpod()` now `monkeypatch.setattr`s `tools.fetch_results.fetch -> rc=0`, eliminating the real subprocess+SDK hang in the smoke-mode pull-back path (`tools/run_preflight.py:238-260`). |
| `a7e368d` | `tests/test_orchestration_skeletons.py` | `test_runpod_provision_authorizes_within_budget` now `monkeypatch.delenv("RUNPOD_API_KEY")` to force the dry-run branch + positively asserts `result.pod_id == "dry-run"`. Matches the existing vultr/tensorwave pattern in the same file. |
| `ee684bc` | `tests/conftest.py` (new) | Autouse fixture `_scrub_cloud_keys` deletes `RUNPOD_API_KEY` / `TENSORWAVE_API_KEY` / `VULTR_API_KEY` from `os.environ` before every test. Function-scope, overridable via `monkeypatch.setenv(...)` in any test that needs the key SET. |

## Root cause (matches 02-UAT.md Test 1 diagnosis)

1. **Flake-by-construction.** `test_runpod_provision_authorizes_within_budget`
   called `runpod_h100.provision()` with no SDK mock and no env scrub. With
   `RUNPOD_API_KEY` set in operator env (the normal state post
   `secrets/rboxkey.md`), `provision()` hit the real RunPod GraphQL endpoint
   and failed with "no instances available" whenever H100 stock was thin.

2. **Incomplete fake fixture.** `_install_fake_runpod` in
   `test_run_preflight.py` patched `runpod.create_pod`, `runpod.get_pods`,
   `runpod.terminate_pod`, `_wait_for_pod_exit`, and `_final_spend` — but
   NOT `tools.fetch_results.fetch`. The smoke-mode path in
   `tools/run_preflight.py:_run_gate` (lines 238-260) imports `fetch` at call
   time and invokes it whenever `final_state in ("EXITED", "GONE") and
   network_volume_id` (always true under the existing fake, which returned
   "EXITED"). The unmocked `fetch_results.fetch` then spawned a real
   subprocess + RunPod SDK call that hung the test indefinitely.

3. **No global env policy.** The lack of an autouse `delenv` for cloud
   provider keys meant every contributor had to remember to scrub the env
   per-test. The pattern was inconsistent across the suite.

## Verification

### Per-task acceptance (all green)

```text
$ timeout 30 uv run pytest tests/test_run_preflight.py -v --tb=short -x
18 passed in 0.93s

$ RUNPOD_API_KEY=bogus_value_xyz timeout 30 uv run pytest tests/test_orchestration_skeletons.py -v
5 passed in 0.36s

$ uv run ruff check tests/conftest.py
All checks passed!
$ uv run ruff format --check tests/conftest.py
1 file already formatted
```

### Phase-level gap-closure check (both env variants)

```text
$ unset RUNPOD_API_KEY TENSORWAVE_API_KEY VULTR_API_KEY
$ timeout 120 uv run pytest -q
288 passed, 2 skipped in 7.45s
exit=0

$ export RUNPOD_API_KEY="$(cat secrets/rboxkey.md | tr -d '[:space:]')"   # length=55
$ timeout 120 uv run pytest -q
288 passed, 2 skipped in 7.41s
exit=0
```

Compared to 02-UAT.md Test 1 baseline (`211 passed, 1 failed, 2 skipped before
hang`), the suite is now `288 passed, 0 failed, 2 skipped, 0 hangs`. The
pass-count delta (211 → 288) reflects intervening commits across Phase 02
since the 2026-05-12 verify; the binding criterion is **0 failed, 0 hangs,
completes in <120s**.

### Defense-in-depth

`RUNPOD_API_KEY=bogus_xyz` exported still passes the entire suite, proving
no test depends on RunPod inventory state.

## 02-UAT.md status flip

02-UAT.md Test 1 will flip from `result: issue / severity: blocker` to
`result: pass` on next `/gsd-verify-work 2` run. The two test commands cited
in the UAT (the orchestration-skeletons FAIL and the run_preflight HANG) now
both exit 0 in <5s each.

## Self-Check: PASSED

- `tests/test_run_preflight.py` — FOUND, `_install_fake_runpod` contains
  `tools.fetch_results` (grep-confirmed).
- `tests/test_orchestration_skeletons.py` — FOUND, contains
  `monkeypatch.delenv("RUNPOD_API_KEY", raising=False)` and
  `assert result.pod_id == "dry-run"` (grep-confirmed).
- `tests/conftest.py` — FOUND, contains autouse fixture deleting
  `RUNPOD_API_KEY`, `TENSORWAVE_API_KEY`, `VULTR_API_KEY`.
- Commits `97919eb`, `a7e368d`, `ee684bc` — all FOUND in `git log`.
- Pre-commit hooks (ruff legacy + ruff format + manifest hook) passed on
  every commit. No `--no-verify` used.
- Final `uv run pytest -q` line: `288 passed, 2 skipped in 7.41s` (exit 0).
