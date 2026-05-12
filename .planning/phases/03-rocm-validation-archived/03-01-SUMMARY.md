---
phase: 03-rocm-validation
plan: 01
subsystem: substrate / orchestration / image-pinning
tags: [rocm, substrate, image-pin, vultr, tensorwave, dev-1021, harness-03, amendment]

requires:
  - phase: 02-cuda-pre-flight
    provides: "substrate/cuda.py composition pattern, GateResult schema (REPRO-03), DEV-1021 RBOX_IMAGE_DIGEST env contract, runpod_h100.provision() reference shape"
provides:
  - "substrate/rocm.py — Substrate ABC implementation by composition (mirrors CUDASubstrate); ABC-conformant; D-37 tts.primary plumbing; DEV-1021 env injection"
  - "dockerfiles/rocm/Dockerfile + scripts/build_pod_image_rocm.sh — rbox-pod-rocm pod-image recipe with baked ENTRYPOINT (Pitfall 10); base image digest-pinned per CLAUDE.md §2.3"
  - "orchestration/vultr_mi300x.py — real provision() with AST-asserted authorize_spend-first + DEV-1021 env + dry-run path + UNSET sentinel guard (Phase 2 02-06 pattern mirrored)"
  - "config/budget.yaml phase3 block (D-33, D-34) + config/sanity_strata.yaml tts.primary row (D-37)"
  - "bench/images.lock.yaml rbox-pod-rocm row with base_image_digest pinned (D-32-A1)"
  - "Plan 03-01 AMENDMENTS.md — D-31-A4 substrate pivot + D-32-A1 image migration"
affects: [03-02-chatterbox-killswitch, 03-03-gate-runners, 03-04-g7, 03-05-audits, 04-synthesis-derating]

tech-stack:
  added:
    - "rocm/vllm:rocm7.12.0_gfx94X-dcgpu base image (sha256:997f858b…2a8f7) — primary ROCm 7.12 / PyTorch 2.9.1 / vLLM 0.16 base for MI300X"
    - "Vultr /v2/instances client (httpx) in orchestration/vultr_mi300x.py — present but parked under D-31-A4 (Vultr is backup-only)"
  patterns:
    - "Sentinel-guard-after-authorize_spend: loud-fail on _DEFAULT_IMAGE_ROCM='...UNSET...' AFTER ledger authorization but BEFORE any network call (Hard Constraint #1 preserved)"
    - "Substrate composition by lazy adapter wiring (mirrors CUDASubstrate): 4 private adapters (vLLM, faster-whisper, Chatterbox, Kokoro), no torch at module level"
    - "tts.primary as config-row (D-37): substrate/rocm.py:synthesize() reads sanity_strata.yaml at session start; DR-27 fallback chain still applies on top of whichever is primary"
    - "Amendment-via-AMENDMENTS.md (instead of rewriting CLAUDE.md): operator-approved deviations recorded in plan dir for traceability, original CLAUDE.md left untouched"

key-files:
  created:
    - "substrate/rocm.py"
    - "tests/test_rocm_substrate.py"
    - "dockerfiles/rocm/Dockerfile"
    - "dockerfiles/rocm/README.md"
    - "scripts/build_pod_image_rocm.sh"
    - "tests/test_vultr_provisioning.py"
    - "tests/test_phase3_config.py"
    - ".planning/phases/03-rocm-validation/03-01-AMENDMENTS.md"
    - ".planning/phases/03-rocm-validation/03-01-SUMMARY.md"
  modified:
    - "substrate/__init__.py (lazy ROCmSubstrate export)"
    - "orchestration/vultr_mi300x.py (real provision body replacing Phase 1 stub)"
    - "tests/test_orchestration_skeletons.py (AST assertion extended to vultr_mi300x; ProvisionResult-shape test)"
    - "bench/images.lock.yaml (rbox-pod-rocm row + base_image_digest D-32-A1)"
    - "dockerfiles/rocm/Dockerfile (FROM line: digest-pinned ROCm 7.12 per D-32-A1)"
    - "config/budget.yaml (phase3 block: D-33 max_minutes_per_gate, D-34 hourly rates, D-36 spend cap)"
    - "config/sanity_strata.yaml (tts.primary row + g{1,2,3,5,7}_full strata stubs)"
    - ".planning/STATE.md (D-31-A4 + D-32-A1 decisions; Plan 03-01 follow-ups blocker)"

key-decisions:
  - "D-32-A1 amendment: migrate ROCm base from CLAUDE.md §2.1's (non-existent) rocm/vllm:rocm6.4_mi300_ubuntu22.04_py3.11_vllm_0.10.x to AMD's current stable rocm/vllm:rocm7.12.0_gfx94X-dcgpu_* @ sha256:997f858b…2a8f7"
  - "D-31-A4 amendment: pivot Day-1 MI300X substrate from Vultr to TensorWave; Vultr is backup-only (sole MI300X SKU is 8-GPU bare-metal preemptible-only at $14.80/hr — breaks $54 Phase 3 budget)"
  - "Vultr orchestration code stays in repo with UNSET sentinel intact — explicit-failure-on-provisioning is correct posture while Vultr is backup-only"
  - "TensorWave orchestration module deferred to a separate research plan: TensorWave provisioning surface (dashboard? CLI? partner API?) is unknown and must be characterized before scaffolding orchestration/tensorwave_mi300x.py"
  - "rbox-pod-rocm derived-image build + push deferred: operator builds once a TensorWave-validated dev pod confirms the new ROCm 7.12 base runs faster-whisper / Kokoro / Chatterbox cleanly"
  - "Phase 4 opportunity flagged: matching gfx1151 base image now published (sha256:8a09c886…5a1) — same ROCm/PyTorch/vLLM as MI300X tightens DERATE-03 cross-substrate consistency check by eliminating version-skew as a confounding variable"

patterns-established:
  - "Amendment files (XX-YY-AMENDMENTS.md) in the plan directory close human-verify checkpoints whose findings invalidate plan assumptions, without rewriting the plan or CLAUDE.md"
  - "When a checkpoint surfaces a stale CLAUDE.md fact, record the amendment in .planning/, leave CLAUDE.md untouched (it's user-owned), and update only the in-repo files the amendment actually changes (images.lock.yaml, Dockerfile, STATE.md)"
  - "Substrate pivot under economic constraint: orchestration code for the demoted-to-backup substrate stays in repo with sentinel intact — zero rework cost when/if the substrate becomes viable again"

requirements-completed:
  - HARNESS-03

duration: "~120 min (Tasks 1-4) + ~25 min (Task 5 checkpoint closure)"
completed: 2026-05-11
---

# Phase 03 Plan 01: ROCm Substrate + Image + Provisioning Summary

**Plan 03-01 builds the ROCm rail's substrate composition, pod-image recipe, Vultr provisioning code, and Phase 3 config blocks WITHOUT spending a dollar on MI300X. The Task 5 operator checkpoint surfaced two invalidated CLAUDE.md assumptions; both were resolved by amendment (D-32-A1 base-image migration to ROCm 7.12, D-31-A4 substrate pivot to TensorWave-primary) without re-executing or rewriting any of the four committed build tasks.**

## Performance

- **Duration:** ~145 min total (~120 min Tasks 1-4 + ~25 min Task 5 checkpoint closure)
- **Started:** 2026-05-11 (Tasks 1-4 prior session)
- **Completed:** 2026-05-11T17:52Z
- **Tasks:** 5 of 5 (4 auto + 1 checkpoint closed via amendment)
- **Files modified:** 13 (8 created, 5 modified)
- **Spend:** $0 on MI300X (zero cloud-GPU provisioning across the entire plan; only operator-side `docker pull` of the base image to resolve its digest)

## Accomplishments

- **HARNESS-03 closed.** `substrate/rocm.py` implements the Substrate ABC by composition mirroring `substrate/cuda.py`, with the D-37 `tts.primary` mechanism wired and DEV-1021 `RBOX_IMAGE_DIGEST` env-first lookup preserved. 15 unit tests pass with no torch/ROCm installed locally.
- **Pod-image recipe + build script + lockfile entry on disk.** `dockerfiles/rocm/Dockerfile` bakes `tools/pod_entrypoint.sh` as ENTRYPOINT (Pitfall 10 mitigation); `scripts/build_pod_image_rocm.sh` mirrors the Phase 2 build pattern with `--build-arg GIT_COMMIT` for DEV-1021 lineage.
- **Real Vultr `provision()` with sentinel guard.** `orchestration/vultr_mi300x.py` replaces the Phase 1 stub: `authorize_spend` is the AST-asserted first call (Hard Constraint #1), `_DEFAULT_IMAGE_ROCM` is a loud-fail UNSET sentinel that raises `VultrProvisionError` before any network call until a real `@sha256` digest is pinned, dry-run path commits the ledger row even with no API key. 10 unit tests pass.
- **Phase 3 config blocks.** `config/budget.yaml` phase3 (D-33 per-gate max_minutes, D-34 hourly rates, D-36 $4 Chatterbox D-1 spend cap, D-37 $54 ROCm-rail total). `config/sanity_strata.yaml` adds `tts.primary: chatterbox` row + `g{1,2,3,5,7}_full` strata stubs for Plans 03-03/03-04 gate runners.
- **Task 5 checkpoint closed via amendments, not blockers.** Two operator findings turned what could have been a wave-blocker into two amendment entries that preserve all committed work, leave the substrate-agnostic design intact, and flag the one new follow-up (TensorWave orchestration module) that needs its own research plan.

## Task Commits

Each task committed atomically:

1. **Task 1 — ROCmSubstrate composition** — `5a00169` (`feat(03-01): add ROCmSubstrate composition + tests (Task 1)`)
2. **Task 2 — Dockerfile + build script + lockfile entry** — `b2dd730` (`feat(03-01): add rbox-pod-rocm Dockerfile + build script + lockfile entry (Task 2)`)
3. **Task 3 — Real vultr_mi300x.provision() + sentinel guard** — `e110a9f` (`feat(03-01): real vultr_mi300x.provision() with sentinel guard + tests (Task 3)`)
4. **Task 4 — Phase 3 budget + sanity_strata config** — `f6297e4` (`feat(03-01): Phase 3 budget + sanity_strata config + tests (Task 4)`)
5. **Task 5 — Operator checkpoint closure (amendments)** — new commit this session (`docs(03-01): amendments D-31-A4 and D-32-A1 from Task 5 checkpoint results`)

**Plan-complete metadata commit:** new commit this session (`docs(03-01): plan complete — SUMMARY.md and ROADMAP/requirements update`)

## Files Created / Modified

### Created
- `substrate/rocm.py` — `ROCmSubstrate(Substrate)`; composes 4 adapters; D-37 `_read_tts_primary()`; DEV-1021 env-first `_lookup_image_digest()`; `_query_gpu()` via `rocm-smi`
- `tests/test_rocm_substrate.py` — 15 unit tests (ABC conformance, isinstance, async-generator shape, env_fingerprint, DR-27 fallback with both tts.primary settings, GPU query parsing, lazy-load discipline)
- `dockerfiles/rocm/Dockerfile` — `FROM rocm/vllm@sha256:997f858b…2a8f7` (D-32-A1 pinned); apt deps; harness pip deps including `livekit-agents==1.2.9`, `jiwer>=4.0`, `whisper-normalizer`, `pyloudnorm`, `runpod`; ENTRYPOINT baked
- `dockerfiles/rocm/README.md` — version-verification probes for the first pod
- `scripts/build_pod_image_rocm.sh` — `docker buildx build --platform linux/amd64` + `--build-arg GIT_COMMIT=$(git rev-parse HEAD)` + `--push` + emits resolved `@sha256` digest
- `tests/test_vultr_provisioning.py` — 10 unit tests covering dry-run path, real-path POST, BudgetExhausted preventing httpx, UNSET sentinel guard, HTTP failure handling, `terminate()` safety, env-injection completeness
- `tests/test_phase3_config.py` — 10 unit tests asserting budget.yaml phase3 fields + sanity_strata.yaml tts.primary + `_read_tts_primary()` default
- `.planning/phases/03-rocm-validation/03-01-AMENDMENTS.md` — Task 5 checkpoint closure document (this plan's primary deliverable from the checkpoint session)

### Modified
- `substrate/__init__.py` — lazy ROCmSubstrate export (Pitfall 1: no torch at module level)
- `orchestration/vultr_mi300x.py` — Phase 1 stub replaced with real `provision()` body + `terminate()` + `_build_cloud_init()`; `_DEFAULT_IMAGE_ROCM` UNSET sentinel; `_DEFAULT_GPU = "vcg-MI300X"` placeholder; `VultrProvisionError` exception class; `ProvisionResult` dataclass
- `tests/test_orchestration_skeletons.py` — AST first-call assertion extended to `vultr_mi300x`; `test_vultr_provision_authorizes` test added returning `ProvisionResult` with `pod_id="dry-run"`; vultr ledger initialized in fixture
- `bench/images.lock.yaml` — `rbox-pod-rocm` row gains `base_image_ref` / `base_image_digest` / `base_image_captured_utc` fields per D-32-A1; notes updated to describe substrate-pivot (D-31-A4) and gfx1151 Phase-4 opportunity
- `dockerfiles/rocm/Dockerfile` — `FROM` migrated from non-existent `rocm/vllm:rocm6.4_mi300_*` tag to digest-pinned `rocm/vllm@sha256:997f858b…2a8f7` per D-32-A1; amendment block in comments
- `config/budget.yaml` — `phase3` block per D-33/D-34
- `config/sanity_strata.yaml` — `tts:` block per D-37 + 5 `g*_full` strata stubs
- `.planning/STATE.md` — two D-31-A4 / D-32-A1 decision entries appended; CLOUD-02 blocker note expanded with TensorWave follow-up; Plan 03-01 deferred follow-ups added

## Decisions Made

### Plan-level (Tasks 1-4)
- **D-37 plumbing wired in substrate, not gate runner.** `synthesize()` reads `tts.primary` at session start so gate runners stay engine-agnostic.
- **Sentinel-guard-after-authorize_spend order:** the loud-fail check for `_DEFAULT_IMAGE_ROCM='...UNSET...'` comes AFTER `authorize_spend()` but BEFORE any network call. This preserves Hard Constraint #1 (AST-asserted first call) while still preventing real provisioning against an unpinned image. Operator pays for the authorization row even on sentinel failure — by design, so they see what the spend would have been.
- **Vultr dry-run path commits the ledger row.** Operators get the same visibility as a real provisioning would produce, just without the actual pod.

### Amendment-level (Task 5 checkpoint)
- **D-32-A1**: Migrate ROCm base image to current AMD-published `rocm/vllm:rocm7.12.0_gfx94X-dcgpu_*` (digest-pinned). Original CLAUDE.md §2.1 tag does not exist on Docker Hub. Bonus: vLLM 0.16 has xgrammar as the default structured-output backend (required by GATE-G5).
- **D-31-A4**: Pivot Day-1 MI300X substrate from Vultr to TensorWave. Vultr's only MI300X SKU is `vbm-256c-2048gb-8-mi300x-gpu` — an 8-GPU bare-metal node, `deploy_ondemand=false`, preemptible-only at $14.80/hr for the whole node. Breaks Phase 3's $54 budget 4× over. TensorWave at ~$1.71/GPU-hr on-demand fits. Vultr orchestration code stays as backup.

See `03-01-AMENDMENTS.md` for full rationale on both.

## Deviations from Plan

### Auto-fixed Issues
None on Tasks 1-4 (plan executed exactly as written).

### Operator-Approved Amendments (from Task 5 checkpoint)

**1. D-32-A1 — Base image migration (ROCm 6.4 → ROCm 7.12)**
- **Found during:** Task 5 (operator-side `docker pull` of base image)
- **Issue:** CLAUDE.md §2.1's specified tag (`rocm/vllm:rocm6.4_mi300_ubuntu22.04_py3.11_vllm_0.10.x`) does not exist on Docker Hub — extrapolated pattern that never matched AMD's actual tag schema
- **Fix:** Migrated to `rocm/vllm:rocm7.12.0_gfx94X-dcgpu_ubuntu24.04_py3.12_pytorch_2.9.1_vllm_0.16.0` @ `sha256:997f858b973cb4e9566653a180c79bc27170bd87585a6930f9257346869a28f7`; pinned by digest in `dockerfiles/rocm/Dockerfile` and recorded in `bench/images.lock.yaml`
- **Files modified:** `bench/images.lock.yaml`, `dockerfiles/rocm/Dockerfile`
- **Verification:** Operator confirmed digest resolves; image is 14.1 GB, last updated 2026-03-27, architecture gfx94X-dcgpu (covers MI300X)
- **Committed in:** (this session — first amendment commit)
- **Note:** Pod-image (`rbox-pod-rocm`) derived-image digest still `pending`; operator builds + pushes once TensorWave-validated dev pod confirms harness deps run on the new base

**2. D-31-A4 — Substrate pivot (Vultr primary → TensorWave primary)**
- **Found during:** Task 5 (operator-side Vultr API exploration)
- **Issue:** Plan named Vultr as Day-1 substrate, but the only MI300X SKU on Vultr is an 8-GPU bare-metal preemptible-only node at $14.80/hr — breaks Phase 3 $54 budget and GATE-CHATTERBOX-D1 $4 spend cap (D-36)
- **Fix:** Demote Vultr to backup; promote TensorWave to Day-1 primary (per CLAUDE.md §1.2's original ordering, which the plan had inverted). `orchestration/vultr_mi300x.py` stays as backup code with UNSET sentinel intact; new follow-up: a TensorWave orchestration module
- **Files modified:** `.planning/STATE.md` (decisions + blocker), `03-01-AMENDMENTS.md` (full rationale)
- **Verification:** Vultr sentinel guard confirmed intact (`grep "UNSET" orchestration/vultr_mi300x.py` returns 5 lines); all 10 vultr-provisioning tests pass; AST first-call assertion passes
- **Committed in:** (this session — first amendment commit)

## Deferred Work

1. **`orchestration/tensorwave_mi300x.py` real provision body** — required before Wave 2 spend (Plan 03-02 Chatterbox kill-switch). Blocker: TensorWave does not appear to publish a public REST API; provisioning surface needs research. **Do NOT scaffold speculatively** — spawn a separate research plan first.
2. **`rbox-pod-rocm` derived-image build + push to GHCR + digest pin** — operator-side work; done once a TensorWave-validated dev pod confirms the new base runs `faster-whisper` / Kokoro / Chatterbox cleanly. Then paste `@sha256:...` into `bench/images.lock.yaml` (`digest: pending` → real) and the future TensorWave module's `_DEFAULT_IMAGE_ROCM`.
3. **CLAUDE.md sync** — not done by this agent (CLAUDE.md is the user's global config). Amendments live in `.planning/phases/03-rocm-validation/03-01-AMENDMENTS.md` and STATE.md; operator may choose to fold these back into a future CLAUDE.md revision.

## Test Summary

| Test file | Tests | Status |
| --------- | ----- | ------ |
| `tests/test_rocm_substrate.py` | 15 | passed |
| `tests/test_vultr_provisioning.py` | 10 | passed |
| `tests/test_phase3_config.py` | 10 | passed |
| `tests/test_orchestration_skeletons.py::*vultr*` + `*first*` | 2 | passed |
| **Plan 03-01 owned total** | **37** | **all passed** |

Pre-existing unrelated test failures (`tests/test_orchestration_skeletons.py::test_runpod_provision_authorizes_within_budget`, `test_tensorwave_provision_authorizes`) require real provider APIs and are out of scope for this plan — neither is affected by Plan 03-01 changes.

## Phase 4 Opportunity Flag

AMD now publishes a matching `rocm/vllm:rocm7.12.0_gfx1151_*` base image for Strix Halo:

- **gfx1151 digest:** `sha256:8a09c886e1bab993f5e12faec669579c8455e5ca1ab31553350f87c3e26ca5a1`

Using this image for local Strix Halo validation in Phase 4 gives same-ROCm / same-PyTorch / same-vLLM measurements vs MI300X, eliminating version-skew as a confounding variable in the DERATE-03 cross-substrate consistency check. Should be incorporated into `04-CONTEXT.md` when Phase 4 planning begins.

## Self-Check

- [x] `substrate/rocm.py` exists — confirmed pre-existing from Task 1 (`5a00169`)
- [x] `dockerfiles/rocm/Dockerfile` exists with new digest-pinned FROM — modified this session
- [x] `bench/images.lock.yaml` `rbox-pod-rocm` row has `base_image_digest: sha256:997f858b…2a8f7` — modified this session
- [x] `orchestration/vultr_mi300x.py` UNSET sentinel intact — 5 grep hits confirmed
- [x] `.planning/phases/03-rocm-validation/03-01-AMENDMENTS.md` exists — created this session
- [x] `.planning/STATE.md` decisions appended with D-31-A4 and D-32-A1 — modified this session
- [x] Commits `5a00169`, `b2dd730`, `e110a9f`, `f6297e4` exist — confirmed via `git log --oneline`
- [x] All 37 Plan 03-01 unit tests still pass after edits

## Self-Check: PASSED
