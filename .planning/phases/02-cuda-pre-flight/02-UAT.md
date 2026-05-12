---
status: partial
phase: 02-cuda-pre-flight
source:
  - .planning/phases/02-cuda-pre-flight/02-01-SUMMARY.md
  - .planning/phases/02-cuda-pre-flight/02-02-SUMMARY.md
  - .planning/phases/02-cuda-pre-flight/02-03-SUMMARY.md
  - .planning/phases/02-cuda-pre-flight/02-04-SUMMARY.md
  - .planning/phases/02-cuda-pre-flight/02-05-SUMMARY.md
  - .planning/phases/02-cuda-pre-flight/02-06-SUMMARY.md
  - .planning/phases/02-cuda-pre-flight/02-07-SUMMARY.md
  - .planning/phases/02-cuda-pre-flight/02-08-SUMMARY.md
started: 2026-05-12T05:55:00Z
updated: 2026-05-12T05:55:00Z
---

## Current Test

[testing complete]

## Tests

### 1. Cold Start Smoke Test
expected: From a clean shell in /home/bob/RBOX, `uv sync && uv run pytest -q` completes without errors. Test suite passes (no failures, no collection errors). No hidden dependency on a running pod, lock files, or warm caches.
result: issue
reported: |
  Suite hangs and never produces final summary. 211 passed, 1 failed, 2 skipped before hang.
  - FAILED: tests/test_orchestration_skeletons.py::test_runpod_provision_authorizes_within_budget — calls runpod_h100.provision() with NO mock; with RUNPOD_API_KEY in operator env, makes real GraphQL call to RunPod; fails with "no instances available" because stock thin (matches STATE.md). Companion tensorwave/vultr tests pass because their keys are UNSET sentinels.
  - HUNG: tests/test_run_preflight.py::test_run_preflight_smoke_honors_runpod_gpu_type — DOES call _install_fake_runpod(monkeypatch) at line 295, so it should be mocked. Hangs anyway. Likely a code path in run_preflight.main(["--mode","smoke"]) not covered by the fake (watchdog/polling loop or runpodctl subprocess).
severity: blocker

### 2. Substrate adapters log+swallow on errors (no raise, no payload leak)
expected: All 4 adapters in `substrate/adapters/` (VLLMClient, FasterWhisperEngine, ChatterboxClient, KokoroClient) log a WARNING and return/yield-nothing on every error path — they never raise. The TTS error path never logs the request payload (verified by `test_chatterbox_logs_status_only_no_payload`). Run `uv run pytest tests/test_cuda_substrate.py -q` and confirm all adapter tests pass.
result: pass
evidence: "22 passed in 0.50s"

### 3. GateRunner auto-stamps all 6 REPRO-03 fields
expected: `gates/_runner_base.py::GateRunner.build_result()` injects `run_id`, `gate`, `asset_manifest_sha`, `substrate`, `image_digest`, `model_shas`, `git_commit`, `timestamp_utc` from `self` — caller cannot forget them. pydantic `GateResult` validation rejects construction if any field missing. Confirm by running `uv run pytest tests/ -k runner -q`.
result: pass

### 4. GateRunner converts per-asset exceptions into error rows (does not abort)
expected: `run_all()` iterates assets under a `Semaphore(concurrency)`; per-asset exceptions become `status='error'` rows with `error_kind` + truncated `error_msg`, and the run continues to completion. Test `test_runner_run_all_converts_exceptions_to_error_rows` proves this.
result: pass

### 5. audit_pod_state.py three checks behave per D-22/D-23
expected: `tools/audit_pod_state.py` runs manifest_check / extension_check / pii_check. Any violation → exit 1. Audit log JSON (`{run_id}.audit.json`) is ALWAYS written (even on violation) so the SIGTERM handler can rsync it without rsyncing result data (D-23 contract).
result: pass

### 6. rbox-pod image digest pin guard intact
expected: `orchestration/runpod_h100.py:_DEFAULT_IMAGE` is pinned to the v18 digest `ghcr.io/consultingfuture4200/rbox-pod@sha256:abcf19f8…ea9d217` (NOT a bare tag like `vllm/vllm-openai:v0.10.0` which caused the prior incident). The constant has a comment block warning future operators not to revert.
result: pass
evidence: |
  orchestration/runpod_h100.py:32-35: _DEFAULT_IMAGE = "ghcr.io/consultingfuture4200/rbox-pod@sha256:abcf19f8d84c165682f615b6e609e209850593b44b67dbec80fb93275ea9d217"
  Full warning comment at lines 23-31 references incident 2026-05-06 + plan 02-06 + CLAUDE.md §2.3.

### 7. REPRO-03 lineage on real result rows (image_digest + git_commit)
expected: Result rows from the v18 diag pod runs (e.g. `results/g2/88de756209e945c9894b963b0e0fdc99.jsonl` or the equivalent under `results/_pulled/`) show non-empty `image_digest` (real sha256, not the "pending" sentinel) and non-empty `git_commit` (real 40-char SHA, not "unknown"). DEV-1021 fix verified on G2 diag pod `jow8x9kugpkgxm`.
result: pass
evidence: |
  results/_pulled/jow8x9kugpkgxm/g2/e9319ce2d8124b1fb5c0ebccae37b551.jsonl row 0:
    image_digest = "sha256:abcf19f8d84c165682f615b6e609e209850593b44b67dbec80fb93275ea9d217" (matches _DEFAULT_IMAGE)
    git_commit   = "f049bb8748678ca935e85b1351a97f4cdcb4fd15" (real 40-char SHA)
    asset_manifest_sha + model_shas (4 models) all populated.
  Pre-DEV-1021 rows (v16 and earlier) under results/_pulled/{4z8jr9...,kom9zjg...,etc.} still show "pending"/"unknown" — expected, those predate the fix.

### 8. G1 smoke verdict pass on real H100 (session 20260509T231720Z)
expected: `results/smoke/` (or `results/_pulled/d6ii16l245t41m/smoke/`) contains the audit + env JSONs for run `2f6b0aa20acb4ebda0302d51b98c6334`. Audit JSON shows verdict pass across all 6 D-25 sub-criteria; pod self-terminated GONE; wall-clock ~185 s; estimated true spend ~$0.14.
result: pass
evidence: |
  results/_pulled/d6ii16l245t41m/smoke/ contains:
    - 2f6b0aa20acb4ebda0302d51b98c6334.jsonl: 5 rows, all status=ok, e2e_ms cold=14s/warm=1.4s
    - 2f6b0aa20acb4ebda0302d51b98c6334.env.json: substrate=cuda, NVIDIA H100 NVL, CUDA 12.8, vllm 0.10.1.dev1, all 4 model_shas pinned
    - 1778368799.audit.json: 0 violations across manifest/extension/pii (D-22 + D-23 checks pass)
  Pod self-terminated cleanly (no orphan in RunPod console per STATE.md notes).
  Pre-DEV-1021 vintage (image_digest=pending, git_commit=unknown) — DEV-1021 fix landed later in v18.

### 9. PREFLIGHT-02/03 sanity baselines (DEV-1019)
expected: G1/G2/G3/G5 sanity runs complete on a real H100 pod and emit per-gate JSONLs with `substrate="cuda"` env fingerprint stamped. STATE.md notes this is operator-driven, not yet executed — likely BLOCKED on operator scheduling a spend session.
result: blocked
blocked_by: prior-phase
reason: "DEV-1019 sanity not run; operator-driven RunPod spend session required. STATE.md PARTIAL on PREFLIGHT-02/03. Likely deferred past DR-39 pivot — Phase 3 retarget may supersede this checkpoint."

## Summary

total: 9
passed: 7
issues: 1
pending: 0
skipped: 0
blocked: 1

## Gaps

- truth: "pytest suite completes cleanly on cold-start (`uv sync && uv run pytest -q`)"
  status: failed
  reason: |
    Suite hangs at ~73% with 1 prior FAIL. Two distinct test defects:
    (a) tests/test_orchestration_skeletons.py::test_runpod_provision_authorizes_within_budget
        calls runpod_h100.provision() without mocking the runpod SDK; with
        RUNPOD_API_KEY set in operator env, makes a real GraphQL call and fails
        when RunPod inventory is thin. Test only passed in the past when stock
        happened to be available — flake by construction.
    (b) tests/test_run_preflight.py::test_run_preflight_smoke_honors_runpod_gpu_type
        installs _install_fake_runpod(monkeypatch) but still hangs. Indicates
        tools/run_preflight.py:main(['--mode','smoke']) has a code path
        (watchdog poll / runpodctl subprocess / non-SDK HTTP) not covered by
        the fake.
  severity: blocker
  test: 1
  artifacts:
    - tests/test_orchestration_skeletons.py:39-49
    - tests/test_run_preflight.py:289-302
    - orchestration/runpod_h100.py:154-157
    - tools/run_preflight.py
  missing:
    - SDK mock fixture for runpod.create_pod in test_orchestration_skeletons.py
    - Coverage of every external-I/O code path in run_preflight smoke-mode by the existing _install_fake_runpod fixture (or a broader fake)
