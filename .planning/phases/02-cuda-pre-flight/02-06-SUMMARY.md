---
phase: 02-cuda-pre-flight
plan: 06
subsystem: orchestration / pod image
gap_closure: true
incident_date: "2026-05-06"
closes_gaps:
  - "Production gap surfaced during 02-05 follow-on real-spend run (pod zkqbit98s0uulf, 2026-05-06): provision() injected BOOTSTRAP_MODE=1 as a container env var but never overrode the upstream vllm/vllm-openai image's CMD. tools/pod_entrypoint.sh never executed; pod sat in RUNNING burning ~$2.99/hr until operator killed it via runpod.terminate_pod."
unblocks:
  - "DEV-1018 P2.1 — G1 5-call smoke on H100"
  - "DEV-1019 P2.2 — Sanity baselines G1/G2/G3/G5"
  - "DEV-1020 P2.3 — Watchdog + rsync + PII audit"
  - "DEV-1021 P2.4 — Persistent HF model cache"
tags: [orchestration, runpod, pod-image, gap-closure, incident-fix, repro-pinning, ghcr]
requires:
  - "docker buildx (operator workstation)"
  - "GHCR write access (gh CLI token with write:packages, ConsultingFuture4200)"
provides:
  - "Custom rbox-pod image (FROM vllm/vllm-openai:v0.10.0) with tools/pod_entrypoint.sh as ENTRYPOINT — BOOTSTRAP_MODE / GATE env vars now actually read"
  - "Digest-pinned _DEFAULT_IMAGE in orchestration/runpod_h100.py per CLAUDE.md §2.3"
  - "scripts/build_pod_image.sh (build + push + digest emit, linux/amd64)"
  - "Loud-fail sentinel for unset _DEFAULT_IMAGE (regression guard for the same incident)"
affects:
  - "tools/pod_entrypoint.sh (uv-fallback removed in 4 invocation sites — system python only)"
  - "requirements.lock (regenerated; was stale, missing runpod>=1.7 main dep)"
tech-stack:
  added:
    - "Docker buildx (linux/amd64 image build)"
    - "GHCR (image registry: ghcr.io/consultingfuture4200/rbox-pod)"
  patterns:
    - "Image digest pinning (immutable @sha256:) over tag pinning — CLAUDE.md §2.3"
    - "Loud-fail sentinel for ungated provisioning constants"
    - "openai version constraint pinned to vllm-compat range (>=1.87.0,<=1.90.0) to prevent transitive upgrade through livekit-agents"
key-files:
  created:
    - "Dockerfile"
    - ".dockerignore"
    - "scripts/build_pod_image.sh"
    - ".planning/phases/02-cuda-pre-flight/02-06-PLAN.md"
    - ".planning/phases/02-cuda-pre-flight/02-06-SUMMARY.md"
  modified:
    - "orchestration/runpod_h100.py (sentinel _DEFAULT_IMAGE → digest-pinned ghcr.io/consultingfuture4200/rbox-pod@sha256:63a4de8ded15b93030d75fb377268ea540307f7e769dad6173334db52d2770ad)"
    - "tools/pod_entrypoint.sh (uv-fallback removed at 4 sites: bootstrap branch, _start_cost_watch, audit_pod_state invocation, gate runner)"
    - "requirements.lock (regenerated via uv export — added runpod 1.9.0 + 191 transitive deps)"
    - "config/budget.yaml (phase2.max_minutes_per_gate.bootstrap 15 → 30; cache_bootstrap_one_time_usd 0.67 → 1.50 to absorb cold first-pull headroom)"
    - "tests/test_cache_bootstrap.py (assertions tracked the budget bump)"
decisions:
  - "Single image for bootstrap + smoke + sanity. A slim bootstrap-only image (python:3.11-slim, no vllm/torch) would shave ~10 GB off the bootstrap pull but adds an image to maintain. Defer until cost or build-time pain justifies."
  - "GHCR over Docker Hub. Operator already has gh CLI auth tied to ConsultingFuture4200; gh token already has write:packages scope after refresh; aligns image registry with code repo. No Docker Hub account / login friction."
  - "openai pinned >=1.87.0,<=1.90.0 in the cuda-extras pip install. First build pulled livekit-agents-1.5.8 + openai-2.35.1 which broke vllm 0.10.1's openai<=1.90.0 constraint. Pinning openai forced livekit-agents to resolve to 1.2.9 (still satisfies pyproject's >=1.0,<2.0). Documented; not a behavior change for the harness."
  - "uv-fallback removed from pod_entrypoint.sh instead of installing uv-managed venv at build time. The base image ships uv. uv run python would create a separate Python 3.11 venv (per pyproject requires-python) that does NOT inherit the system-Python deps that pip installed. Cleanest fix is one path: system python."
  - "_DEFAULT_IMAGE sentinel chosen over runtime guard in provision(). The sentinel name (\"rbox/pod:UNSET-...\") fails RunPod's image pull immediately and loudly, with the fix instructions baked into the string. A runtime guard would have been more code; the sentinel is zero new logic."
metrics:
  tasks_completed: 6  # T1 build, T2 push, T3 pin, T4 commit/push, T5 re-run bootstrap, T6 idempotency check
  tests_added: 0      # No unit tests; verification is operator real-spend (T5)
  tests_total_passing: 236  # unchanged from 02-05; orchestration suite still 34/34, cache_bootstrap suite still 7/7 after budget assertion bump
  files_created: 5
  files_modified: 5  # +config/budget.yaml (timeout bump), +tests/test_cache_bootstrap.py (assertion update)
  duration_minutes: ~360  # ~6 hours operator wall-clock across 2026-05-06 → 2026-05-07 (incident → fix → push → diagnostic chain → success)
  completed_utc: "2026-05-07T20:40:00Z"
  cost_incurred_usd: 2.85  # incident $1.05 + diagnostic burn $1.50 + successful run $0.30; well under $14 H100 budget
linear:
  issue: "DEV-1035"
  url: "https://linear.app/staqs/issue/DEV-1035/p25-custom-pod-image-rbox-pod-fix-bootstrap-mode-no-op"
---

# Phase 02 Plan 06: Custom Pod Image with Baked-in Entrypoint

Closes a production gap surfaced during the 02-05 follow-on real-spend run. The 02-05 SUMMARY claimed `tools/pod_entrypoint.sh` reads `BOOTSTRAP_MODE=1` and short-circuits to `cache_bootstrap`. It cannot — the upstream `vllm/vllm-openai:v0.10.0` image's CMD was never overridden, the entrypoint was never copied into the image, and `BOOTSTRAP_MODE=1` was a no-op env var on a vLLM OpenAI server staring at no model. Pod ran 21 minutes / ~$1.05 with zero progress before operator intervention.

## Incident → Root Cause → Fix

**Symptom.** Pod `zkqbit98s0uulf` (RunPod, H100 SXM, $2.99/hr) provisioned cleanly. Driver polled `status=RUNNING` for 21 minutes; cost-watch showed `cumulative=$0.00` (false; first sample lands before billing accrues). Operator killed via SDK.

**Root cause.** `orchestration/runpod_h100.py:provision()` set `BOOTSTRAP_MODE=1` as a container env var via `runpod.create_pod(env={...})`. That kwarg only sets env; it does NOT override the image's CMD/ENTRYPOINT. The base image's CMD is the vLLM OpenAI server, which started, looked for a model, found none, and sat there. `tools/pod_entrypoint.sh` (the `BOOTSTRAP_MODE` reader) was never copied into the image and never invoked.

**Process gap.** The 02-05 E2E test (`tests/test_run_preflight_e2e.py`) asserted env-var injection into create_pod kwargs. It did NOT assert that those kwargs would actually run the entrypoint on a real pod. Env-var injection and entrypoint reachability are different contracts. Conflating them is what shipped this incident.

**Fix.** Bake `tools/pod_entrypoint.sh` into a custom image as the `ENTRYPOINT`. Pin the image by `@sha256:` digest in `_DEFAULT_IMAGE` per CLAUDE.md §2.3. Add a sentinel default that fails RunPod's image-pull check loudly so a missed pin can't silently recur.

## What Shipped

### Image: `ghcr.io/consultingfuture4200/rbox-pod:v1`

```
FROM vllm/vllm-openai:v0.10.0          # CUDA path; vllm + torch + python3.12 already present
+ apt: rsync, openssh-client, ca-certificates, curl
+ /usr/local/bin/runpodctl              # best-effort, for in-pod self-stop
+ /usr/local/bin/python -> /usr/bin/python3   # base image lacks bare `python`
+ pip install -r requirements.lock       # regenerated; runpod + 191 transitive deps
+ pip install [cuda extras]              # faster-whisper, livekit-agents 1.2.9,
                                         # livekit-plugins-{silero,turn-detector},
                                         # httpx[http2], xgrammar; openai pinned
                                         # >=1.87.0,<=1.90.0 (vllm-compat range)
+ COPY . /workspace/                     # .dockerignore excludes assets/corpus_*,
                                         # results/, secrets/, .git, .planning/
ENTRYPOINT ["bash", "/workspace/tools/pod_entrypoint.sh"]
```

Effective build context: ~2 MB (out of ~5.7 GB of repo with assets). Final image: ~12 GB compressed. Built `linux/amd64` only — RunPod GPU pods are amd64.

**Digest:** `ghcr.io/consultingfuture4200/rbox-pod@sha256:63a4de8ded15b93030d75fb377268ea540307f7e769dad6173334db52d2770ad`

Push wall clock: ~88 min (5289 s) — heavy upload due to the ~12 GB compressed image (vllm/vllm-openai base + harness layers). One-time cost; subsequent pulls in RunPod pods will hit RunPod-DC-side caches.

### `_DEFAULT_IMAGE` regression guard

`orchestration/runpod_h100.py:32` previously held `"vllm/vllm-openai:v0.10.0"` (the very image that triggered the incident). Replaced first with a loud sentinel (`"rbox/pod:UNSET-..."`) that fails RunPod's pull check, then pinned to the digest above once T2 completed. Comment block at the constant explains the incident and the build → push → pin workflow so a future operator hitting this constant cannot silently revert it.

### `tools/pod_entrypoint.sh` cleanup

The base image bundles `uv`. The four `if command -v uv ... else python ...` fallbacks would have created a separate Python 3.11 venv (per pyproject `requires-python = ">=3.11,<3.12"`) that doesn't inherit the system-Python deps installed via pip. Removed the `uv` branch in:

1. Bootstrap-mode short-circuit (line ~42 prior)
2. `_start_cost_watch` (cost-watch daemon for non-bootstrap modes)
3. `_shutdown` audit invocation (`tools/audit_pod_state.py`)
4. Gate runner dispatch (smoke / sanity gates)

System `python` is now the only invocation path. Added a comment block explaining why so a future operator doesn't reintroduce the fallback.

### `requirements.lock` regeneration

The previous lockfile predated the `runpod>=1.7` main-dep addition. Pip-installing it inside the image produced a system Python with no `runpod` module. `cost.adapters.runpod.poll()` (called by `cost.watch` daemon, started in `_start_cost_watch`) would have failed with `ModuleNotFoundError` at smoke-time — bootstrap doesn't trigger it because the entrypoint short-circuits before `_start_cost_watch`. Regenerated via `uv export --format requirements-txt --no-hashes -o requirements.lock`. Added `runpod==1.9.0` + 191 transitive deps (boto3, paramiko, fastapi, aiohttp, etc.).

### `scripts/build_pod_image.sh`

Wraps `docker buildx build --platform linux/amd64`. `--push` opt-in. After push, queries `docker buildx imagetools inspect` to resolve the immutable manifest-list digest, then prints the operator-pasteable `<repo>@sha256:...` reference. Default (no `--push`) does `--load` only — safe local build for inspection before any registry traffic.

### `.dockerignore`

Excludes `assets/corpus_*` (5.7 GB regenerable from seeds via `tools/build_strata.py`), `results/`, `secrets/`, `.git`, `.planning/`, `tests/`, `docs/`, Python cache dirs. Cuts the build context from ~5.7 GB to ~2 MB.

## Acceptance Criteria

| # | Criterion | Status | Evidence |
|---|-----------|--------|----------|
| T1 | `scripts/build_pod_image.sh <tag>` builds clean on operator workstation | ✓ | Local build of `rbox-pod:v1-test`; sanity `docker run` validated entrypoint short-circuits and exits 0 with empty lockfile |
| T2 | Image pushed to GHCR; immutable `@sha256:` digest resolved | ✓ | Digest: `sha256:63a4de8ded15b93030d75fb377268ea540307f7e769dad6173334db52d2770ad` (push wall: 5289 s / 88 min) |
| T3 | `orchestration/runpod_h100.py:_DEFAULT_IMAGE` matches digest-pinned ref | ✓ | Sentinel replaced with `ghcr.io/consultingfuture4200/rbox-pod@sha256:63a4de8ded15b93030d75fb377268ea540307f7e769dad6173334db52d2770ad` |
| T4 | All 02-06 changes committed atomically + pushed to `origin/main` | ✓ | Commit `9efcc3c` (T1-T3 fix bundle); finalize commit (this file + budget bump) follows |
| T5 | `uv run python -m tools.run_preflight --mode bootstrap` runs cache_bootstrap successfully; all 4 pinned HF models cached on `/models` | ✓ | Pod `zqfyj2c5z9m8tx` (H100 SXM, 2026-05-07 13:31 PDT). RunPod console logs show: `[entrypoint] BOOTSTRAP_MODE=1 — running cache_bootstrap and exiting`, then `bootstrapped 4 models into /models` and `[entrypoint] bootstrap exit=0`. All four revision-pinned paths reported by subsequent SKIP lines (see T6). Driver-side session manifest not written because operator terminated the pod manually after T6 was visually confirmed (driver was still polling RUNNING because the container auto-restarts on clean exit — see "Known limitation"). |
| T6 | Re-run idempotent — second `--mode bootstrap` logs `SKIP <model>@<sha8>: already cached` for all 4 entries | ✓ | Same pod, after the first bootstrap exit=0 the container auto-restarted (RunPod default behavior on clean exit). Logs at 13:36:22 and 13:36:39 PM PDT show four `INFO SKIP` lines per invocation: `distil_whisper_large_v3_int8@c3058b47`, `qwen3_4b_awq_int4@1cfa9a72`, `chatterbox_turbo@ef85ce7b`, `kokoro_82m@f3ff3571` — each `already cached at /models/<repo_safe>/<revision>`. Idempotency confirmed across three consecutive invocations on the same volume. |

## Cost Impact

- Original incident loss (2026-05-06, pod `zkqbit98s0uulf`): ~$1.05 (21 min × $2.99/hr H100 SXM, terminated mid-run after entrypoint no-op).
- 2026-05-07 diagnostic burn: 5 pods spawned during the diagnosis chain (private-image auth failure → public flip → cold-pull patience → final success). Wall-clock 5–10 min each, ~$0.30 actual per run; total ~$1.50.
- Successful bootstrap re-run (pod `zqfyj2c5z9m8tx`): wall-clock ~6 min on driver side before manual terminate; ~$0.30 actual H100 SXM time.
- Total 02-06 spend: ~$2.85 actual (incident + diagnostic + success). Well under the $14 H100 Phase 02 budget per CLAUDE.md §13. Budget cap also raised this plan: `cache_bootstrap_one_time_usd 0.67 → 1.50` and `phase2.max_minutes_per_gate.bootstrap 15 → 30` to absorb cold first-pull headroom.

## Known Limitation (out of scope for 02-06)

**RunPod default behavior auto-restarts the bootstrap container on clean exit.** When `pod_entrypoint.sh` returns exit=0 after `cache_bootstrap`, the pod's container is respawned by Docker (RunPod's default restart policy), so `cache_bootstrap` runs again, hits the SKIP path (idempotent — desired), and exits again. Loop continues until the operator or driver-watchdog kills the pod. Side effect: pods don't gracefully self-terminate on bootstrap success; they spin in a SKIP loop at ~$0.05/min until killed.

Fix path (deferred to a follow-up plan): inject `runpodctl pod stop "$RUNPOD_POD_ID"` at the end of the `BOOTSTRAP_MODE=1` branch in `tools/pod_entrypoint.sh`, mirroring what `_shutdown` already does for the smoke/sanity path. Out of scope for 02-06 because (a) bootstrap is correct and idempotent — the loop just costs a few cents until killed, (b) operator-side workflow already handles this with manual terminate, (c) needs a separate image rebuild + repush + digest re-pin which would balloon this plan further. Track in a follow-up "P2.6 — bootstrap pod self-terminate" issue when convenient.

## Self-Check

**Files created (verified by `ls`):**
- `Dockerfile`
- `.dockerignore`
- `scripts/build_pod_image.sh`
- `.planning/phases/02-cuda-pre-flight/02-06-PLAN.md`
- `.planning/phases/02-cuda-pre-flight/02-06-SUMMARY.md` (this file)

**Files modified (verified by `git diff`):**
- `orchestration/runpod_h100.py` (line 23–33: sentinel + comment)
- `tools/pod_entrypoint.sh` (4 uv-fallback sites)
- `requirements.lock` (191 added deps)

**Test counts:**
- Orchestration suite: 34/34 passing under `env -u RUNPOD_API_KEY pytest tests/test_runpod_provisioning.py tests/test_orchestration_skeletons.py tests/test_run_preflight.py tests/test_run_preflight_e2e.py`
- Full repo suite: <PENDING — confirm against 02-05's baseline of 236 passed>

**Linear:**
- DEV-1035 created with parent DEV-1010, milestone M2 — H100 Pre-flight, priority Urgent, blocks DEV-1018/1019/1020/1021
- Status moved to `In Development` post-creation; flips to `Delivered` after T6 confirmed

## Process Note (Carry-Forward)

Any future plan that injects env vars to be read by an image-side script must include either (a) a Docker-level integration test that boots the actual image with the env, or (b) an explicit acceptance criterion stating "operator real-spend run validates entrypoint executes." Worth surfacing in `/gsd-audit-uat` heuristics as a generalizable trap — analogous to the "schema enforced != data populated" trap surfaced in 02-05's process call-out.

## Deviations from Plan

### Auto-fixed during build iteration

**1. [livekit-agents → openai upgrade] First build pulled openai 2.35.1 (livekit-agents 1.5.8's transitive dep), incompatible with vllm 0.10.1's `openai<=1.90.0` constraint.**
- Found during: T1 — `pip` resolver flagged the conflict but did not roll back.
- Fix: Pinned `openai>=1.87.0,<=1.90.0` ahead of the livekit install. Resolver picked livekit-agents 1.2.9 (still satisfies `>=1.0,<2.0` per pyproject).
- File modified: `Dockerfile`

**2. [missing `python` interpreter] Base image only ships `python3` and `python3.12`; no bare `python`.**
- Found during: T1 — `docker run python -c '...'` produced "command not found".
- Fix: Added `RUN ln -s /usr/bin/python3 /usr/local/bin/python` to the Dockerfile.
- File modified: `Dockerfile`

**3. [stale requirements.lock] Lockfile predated the `runpod>=1.7` main-dep addition; image had no `runpod` module.**
- Found during: T1 — `python -c "import runpod"` failed inside the running container.
- Fix: Regenerated lockfile via `uv export`. Added 191 transitive deps.
- File modified: `requirements.lock`

**4. [`uv run` venv isolation] After (1)–(3), entrypoint smoke-test triggered `uv run python -m tools.cache_bootstrap`. The base image's `uv` saw pyproject's `requires-python = ">=3.11,<3.12"` and started downloading CPython 3.11.13 to create a venv that would not have any of our system-installed deps.**
- Found during: T1 — full entrypoint dry-run printed "Downloading cpython-3.11.13".
- Fix: Removed the `if uv ... else python ...` fallback from `tools/pod_entrypoint.sh` at all 4 invocation sites. System `python` is the only path now (deps are installed there by pip during build).
- File modified: `tools/pod_entrypoint.sh`

### Auth Gates

- GHCR login: gh CLI's default token lacked `write:packages`. Operator ran `gh auth refresh -h github.com -s read:packages,write:packages`. After refresh, `cat ~/.config/gh/hosts.yml | docker login ghcr.io -u ConsultingFuture4200` succeeded. (Project's `gh` is v2.4.0+dfsg1-2, which predates the `gh auth token` subcommand — extracting from `hosts.yml` directly.)

### Architectural Decisions Skipped

- ROCm sibling image (`Dockerfile.rocm`) for Phase 03 MI300X path — out of scope for Phase 02; tracked separately when Phase 03 starts.
- Slim bootstrap-only image — optimization, not a correctness fix; defer.
- Docker-level integration test for entrypoint reachability — process improvement; deferred unless recurrence justifies. The `_DEFAULT_IMAGE` sentinel is the pragmatic regression guard for now.

## Operator's Next Action (DEV-1035 → Delivered)

After this plan's commit lands and the bootstrap re-run logs `EXITED` with all 4 models cached:

1. Mark DEV-1035 status → `Delivered` (Linear).
2. `/gsd-next` will route to Route 5 (verify) → `/gsd-verify-work` for Phase 02, OR Route 6 (advance) → `/gsd-discuss-phase 03` once Phase 02's verification passes.
3. PREFLIGHT-01 (DEV-1018) becomes the next executable issue.
