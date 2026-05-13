---
gsd_state_version: 1.0
milestone: v0.4
milestone_name: milestone
status: executing
stopped_at: "Phase 02 plans 02-04 / 02-07 / 02-08 summaries written; PREFLIGHT-01 closed; REQUIREMENTS / ROADMAP advanced. Phase 3 context (gathered separately at 16:18Z) preserved at .planning/phases/03-rocm-validation-archived/03-CONTEXT.md and DISCUSSION-LOG.md — ready for /gsd-plan-phase 3."
last_updated: "2026-05-13T07:58:04.118Z"
last_activity: 2026-05-13
progress:
  total_phases: 4
  completed_phases: 2
  total_plans: 29
  completed_plans: 19
  percent: 66
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-05-04)

**Core value:** Produce trustworthy go/no-go evidence on receptionBOX feasibility — derated Strix Halo predictions for latency/WER/turn-detection/UPL/TTS — before any sales commitment is made to the firm.
**Current focus:** Phase 03 — cloud-derate

## Current Position

Phase: 03 (cloud-derate) — EXECUTING
Plan: 3 of 8
Status: Ready to execute
Last activity: 2026-05-13

Progress: Phase 2 complete; Phase 3 path now unblocked. New plan set draft is the immediate next step (`/gsd-plan-phase 3 --gaps`).

## Performance Metrics

**Velocity:**

- Total plans completed: 0
- Average duration: —
- Total execution time: 0.0 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| - | - | - | - |

**Recent Trend:**

- Last 5 plans: —
- Trend: —

*Updated after each plan completion*
| Phase 01 P01 | 0.4 | 3 tasks | 33 files |
| Phase 01 P02 | 0.1 | 3 tasks | 18 files |
| Phase 01 P03 | 0.15 | 3 tasks | 18 files |
| Phase 01 P04 | 0.83 | 3 tasks | 760 files |
| Phase 01 P05 | 0.2 | 2 tasks | 15 files |
| Phase 02 P01 | 0.4 | 3 tasks | 9 files |
| Phase 02 P02 | 0.5 | 5 tasks | 14 files |
| Phase 02 P03 | 0.5 | 4 tasks | 11 files |
| Phase 02 P04 | 0.4 | 3/4 tasks (PARTIAL) | 6 files |
| Phase 02 P05 | 0.5 | 3 tasks | 13 files |
| Phase 02 P06 | 6.0 | 6 tasks (T1-T6 ✓) | 8 files |
| Phase 03 P07 | 30min | 3 tasks | 14 files |
| Phase 03 P07b | 15min | 2 tasks | 4 files |

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table. Recent:

- Phase 0 scope is cloud-only (no local Strix Halo dev unit available)
- Operator drives Phase 0 locally on Ubuntu 22.04 from `~/RBOX`
- Parent thUMBox PRDs and addenda to be dropped into `docs/` (gates Phase 1 completion)
- receptionBOX PRD v0.2 is authoritative input
- All evaluation assets curated in Phase 0 (no pre-existing corpora)
- RunPod H100 + TensorWave MI300X (Vultr backup) — no alternatives evaluated
- [Phase 01]: Use uv project mode (pyproject.toml + uv.lock) as canonical; emit requirements.lock as pip-compat export via make export-requirements
- [Phase 01]: Pin jiwer >=4.0,<5.0 + whisper-normalizer as separate dep (Pitfall A — STACK.md references to jiwer 3.x are stale)
- [Phase 01]: Pre-commit ruff hook bumped v0.7.4 -> v0.15.12 to match dev-group ruff (string-formatting drift broke make check)
- [Phase 01]: Pydantic v2 BaseModel for STT/LLMChunk/EnvFingerprint over @dataclass — JSON sidecar round-trip required for HARNESS-05/D-12
- [Phase 01]: _StubSubstrate ships under leading-underscore name, never exported in __all__ — gate runners cannot import it accidentally
- [Phase 01]: Lockfile pydantic schemas live in test file (not runtime module) — they are enforcement contracts on data, not application logic
- [Phase 01]: Idempotency-preserving created_utc in manifest authoring scripts (preserve existing timestamp when sha unchanged) — required for D-06 reproducibility
- [Phase 01]: G.711 spectral validation ships with graceful no_reference branch; Twilio reference clip is operator dependency (A4) deferred to Phase 4 synthesis
- [Phase 01]: G.711 lowpass test uses 5 kHz out-of-band tone (above 4 kHz Nyquist) rather than 3.5 kHz (still in soxr passband)
- [Phase 01]: Split render_env from harness venv at the uv project level (not workspace member) to enforce Pitfall 1 isolation; torch<=2.5.1 + kokoro lives entirely in assets/render_env/.venv/
- [Phase 01]: Pre-commit manifest hook now skips .venv/ and site-packages/ paths so deps' bundled test WAVs do not trip INFRA-05; the project-owned-audio invariant is preserved
- [Phase 01]: DR-31 sharing policy v0.1.0 drafted with 4 locked stance elements (methodology+prediction range only pre-SOW, no raw cloud numbers, two-tier presentation MANDATORY, PRD-update review gate); status pending operator approval
- [Phase 01]: Provider asymmetry made explicit per Pitfalls B/C: Vultr full /v2/billing/pending-charges API; RunPod SDK get_pods (cap = 5 prepaid + auto-recharge OFF, NOT a programmatic API); TensorWave stub-with-warning (billing API undocumented)
- [Phase 01]: AST-asserted ordering enforces authorize_spend MUST be the first call in every orchestration provision() — Phase 2/3 contributors cannot bypass the cost-ledger gate without breaking the test
- [Phase 01]: Adapters MUST NOT raise — log WARNING and return (0.0, 0.0) on every error path (network, missing env, JSON, 4xx) so the 5-min watch loop is uninterruptible
- [Phase 02]: [Phase 02-01]: Adapters expose health() returning bool; load_* uses health() check (not exception) for graceful degradation
- [Phase 02]: [Phase 02-01]: DR-27 TTS fallback wired in CUDASubstrate.synthesize() — Chatterbox health=False routes to Kokoro with WARNING log
- [Phase 02]: [Phase 02-01]: LiveKit pipeline ships shim path (SimpleNamespace) — unit tests + workstation dev never need livekit-agents installed; structural parity with real AgentSession surface
- [Phase 02]: [Phase 02-01]: Cuda stack moved to [project.optional-dependencies] cuda group — workstation uv sync clean, pod uses uv sync --extra cuda
- [Phase 02]: [Phase 02-02]: GateRunner base auto-populates the full REPRO-03 tuple via build_result(); pydantic GateResult validation makes missing fields impossible at write-time
- [Phase 02]: [Phase 02-02]: G3 detected_endpoint_ms reads from last STT chunk's end_ms (substrate-agnostic); AgentSession on_user_speech_committed wiring deferred to Plan 02-03 / real-path validation
- [Phase 02]: [Phase 02-02]: G5 probe shape adapter accepts both plan-spec (text/refusal_label) and on-disk probes.json (prompt/expected_label) field names; benign controls tagged control: True for distinct false-refusal accounting
- [Phase 02]: [Phase 02-02]: make g7 stays explicitly deferred (PREFLIGHT-02 message + non-zero exit); test asserts non-zero rather than ==1 because make wraps recipe exit 1 as its own code 2
- [Phase 02]: [Phase 02-03]: Audit manifest scope = audio files only under assets/ (matches tools/check_asset_manifest.py); non-audio source artifacts under assets/ are committed code, not provenance-tracked audio
- [Phase 02]: [Phase 02-03]: provision() return type changed from Authorization to ProvisionResult dataclass (authorization, pod_id, pod_url, image_ref, gpu_type, started_utc); Authorization reachable via .authorization for ledger-contract test
- [Phase 02]: [Phase 02-03]: provision() dry-runs when RUNPOD_API_KEY unset — ledger row still committed so operator sees the spend, but no SDK call; pod_id='dry-run' returned
- [Phase 02]: [Phase 02-03]: pod entrypoint _shutdown() is idempotent via _SHUTDOWN_DONE guard — trap on TERM/INT and post-wait normal exit can both fire it without double-running audit + rsync
- [Phase 02]: [Phase 02-04 PARTIAL]: Tasks 1-3 done (build_strata, run_preflight, OPERATOR-CHECKLIST; commits 1c7e70d, 8cc35e3, 097f95e, ba2c1a4, bd5e6eb). Task 4 (real H100 smoke + sanity) NOT executed — blocked on two upstream gaps surfaced during operator bootstrap dry-run: (a) bench/models.lock.yaml has all 4 entries at revision: pending — both tools/cache_bootstrap.py and tools/fetch_models.py skip pending entries, so a bootstrap pod would be a no-op; (b) tools/run_preflight.py --mode bootstrap defers to operator-side runpodctl with no automation. $0 spent on RunPod this session. Operator chose path C: route to /gsd-plan-phase 02 --gaps for a follow-up plan that resolves the 4 SHAs and auto-provisions the bootstrap pod via the SDK before any real spend.
- [Phase 02]: [Phase 02-05]: HF lockfile populated (real 40-char commit SHAs + per-file SHA-256 for distil-whisper, Qwen3-4B, chatterbox, Kokoro). `--mode bootstrap` now goes through provision() (Hard Constraint #1 preserved). REPRO-02 annotated (schema-enforced != data-populated). E2E test added.
- [Phase 02]: [Phase 02-06]: Custom rbox-pod image (FROM vllm/vllm-openai:v0.10.0) baked with tools/pod_entrypoint.sh as ENTRYPOINT; pushed to ghcr.io/consultingfuture4200/rbox-pod, digest-pinned in _DEFAULT_IMAGE per CLAUDE.md §2.3. Closes the gap that the bare upstream image's CMD ignored BOOTSTRAP_MODE/GATE env vars (incident pod zkqbit98s0uulf 2026-05-06). pod_entrypoint.sh uv-fallback removed (4 sites — system python only since deps are pip-installed in the image, not in a uv-managed venv). requirements.lock regenerated (added runpod 1.9.0). Bootstrap re-run confirmed all 4 HF models cached on /models with revision-pinned paths; T6 idempotency verified via 3 consecutive SKIP-on-rerun cycles. Known limitation: bootstrap pod auto-restarts on clean exit — operator manually terminates; tracked as future P2.6 follow-up.
- [Phase 02]: [Phase 02-07]: Multi-service pod startup (vLLM + Kokoro venv on :8005), corpus_500 baked into image, transport pivoted from rsync-push to fetch_pod-pull (tools/fetch_results.py spawns ~$0.05 diag pod). Image iterated v8→v9→v10→v11→v13→v14→v15→v16 closing startup/transport bugs surfaced in real-spend smoke. Chatterbox-TTS scoped out of image (Python 3.10 vs 3.12 base conflict); DR-27 fallback to Kokoro acceptable for G1 smoke. Smoke verdict pass on session 20260509T231720Z, run 2f6b — all 6 D-25 sub-criteria true; pod self-terminated GONE, wall-clock 185s, estimated true spend ~$0.14.
- [Phase 02]: [Phase 02-08 retroactive]: DEV-1021 fix for image_digest + git_commit lineage on result rows. provision() forwards RBOX_IMAGE_DIGEST env; substrate/cuda.py reads env first (lockfile fallback preserved). Dockerfile ARG GIT_COMMIT placed after heavy COPY/pip layers (preserves ~16GB layer cache across HEAD churn); build script passes git rev-parse HEAD; pod-side _git_commit() falls back to /workspace/.git_commit. Image v18 baked + pushed (_DEFAULT_IMAGE = sha256:abcf19f8…ea9d217). Verified on G2 diag pod jow8x9kugpkgxm: rows show real digest + commit, WER 2.55% re-confirmed (DEV-1083 intact).
- [Phase 03]: [Phase 03-01 amendment D-32-A1]: ROCm base image migrated from CLAUDE.md §2.1's (non-existent) `rocm/vllm:rocm6.4_mi300_ubuntu22.04_py3.11_vllm_0.10.x` to AMD's current stable `rocm/vllm:rocm7.12.0_gfx94X-dcgpu_ubuntu24.04_py3.12_pytorch_2.9.1_vllm_0.16.0` @ `sha256:997f858b…2a8f7` (14.1 GB, last updated 2026-03-27). Driver: original tag never existed on Docker Hub. Bonus: vLLM 0.16 has xgrammar as default structured-output backend (required by GATE-G5). Phase 4 opportunity: matching gfx1151 base now published (`sha256:8a09c886…5a1`) — tightens DERATE-03 cross-substrate consistency by eliminating ROCm/PyTorch/vLLM version-skew between MI300X and Strix Halo measurements. Files: `bench/images.lock.yaml` row updated with `base_image_digest`; `dockerfiles/rocm/Dockerfile` `FROM` now digest-pinned per CLAUDE.md §2.3. See `.planning/phases/03-rocm-validation-archived/03-01-AMENDMENTS.md`.
- [Phase 03]: [Phase 03-01 amendment D-31-A4]: Day-1 MI300X substrate pivoted from Vultr to **TensorWave** (primary). Driver: Vultr's actual MI300X surface is `/v2/plans-metal` (not `/v2/plans?type=gpu` as CLAUDE.md speculated), and the one MI300X SKU is `vbm-256c-2048gb-8-mi300x-gpu` — an 8-GPU bare-metal node, `deploy_ondemand=false`, preemptible-only at $14.80/hr for the whole node. That breaks GATE-CHATTERBOX-D1's $4 spend cap (would cost $29.60) and the Phase 3 $54 MI300X subtotal (would cost $200+). TensorWave at $1.71/GPU-hr on-demand fits the budget. Vultr is **backup-only**. `orchestration/vultr_mi300x.py` stays in repo (sentinel UNSET intact, all 10 tests still pass) for use if Vultr ever publishes a 1-GPU SKU. **Follow-up blocker**: TensorWave provisioning surface unknown (no public REST API like Vultr's `/v2/instances`); a separate research plan is required before Wave 2 spend can run Plan 03-02. See `.planning/phases/03-rocm-validation-archived/03-01-AMENDMENTS.md`.

- [Phase 03]: [Phase 03-01.5 INSERTED 2026-05-11]: Substrate-pivot enabler plan inserted between 03-01 and 03-02 (filename `03-01.5-PLAN.md` sorts lexically between 03-01-SUMMARY.md and 03-02-PLAN.md). Plan is Wave-1.5 (depends_on=03-01); blocks Wave 2 (03-02..06). Task 1 is research-only (operator characterizes TensorWave provisioning surface); Tasks 2-5 conditional on PROCEED verdict; Task 5 has $2 hard cap on real spend. HALT branch downgrades Phase 0 to CUDA-only per DR-31. Plans 03-02..06 unchanged in this insertion (orchestration/mi300x.py dispatch shim added in Task 4 lets them migrate to env-driven provider selection via one-line import edit at execute time, no re-plan needed).

- [Phase 03]: [Phase 03-01.5 REWRITTEN 2026-05-11 per D-31-A4.1]: Primary MI300X substrate retargeted from TensorWave to **RunPod**. Driver: empirical RunPod GraphQL gpuTypes query revealed `AMD Instinct MI300X OAM` listed at `securePrice: 1.99` ($/GPU-hr) on Secure Cloud, per-GPU buyable, `maxGpuCount: 8`, `memoryInGb: 192`. The SKU was not present in CLAUDE.md §1.2 (postdates CLAUDE.md authoring). `lowestPrice(gpuCount=N)` currently returns stock=None globally — same listed-but-thin pattern as the Phase-02 H100 SKU; addressed via the existing `tools/probe_runpod_stock.py` poll loop (extended in Task 1 of the rewritten plan). Cost premium vs TensorWave: $0.28/GPU-hr × ~23 planned MI300X GPU-hours = **+$6.44** against the $150 program ceiling — trivial. Strategic benefit: single substrate covers both Phase 0 rails (CUDA H100 + ROCm MI300X), reusing ~80% of Phase 02's RunPod tooling (`runpod` SDK, `RUNPOD_API_KEY` already in env, `cost/adapters/runpod.py`, `tools/probe_runpod_*.py`, `tools/find_runpod_volume.py`, `results/_pulled/<pod-id>/` pull-back pattern). TensorWave demoted to **secondary fallback** (re-activated only via HALT-STOCK branch → future 03-01.6 plan). Vultr remains backup (sentinel UNSET; unchanged). The previous TensorWave-targeted 03-01.5-PLAN.md is preserved in git history; the rewritten plan retargets the same 6-task structure (probe extension + module + tests + dispatch shim + $2 smoke + operator checkpoint) to the RunPod surface, with shape-parity contract `orchestration.runpod_mi300x.ProvisionResult == orchestration.vultr_mi300x.ProvisionResult` (programmatically asserted). Plan-level verdict branches: PROCEED-RUNPOD / HALT-STOCK (24h stock=None → 03-01.6 TensorWave research) / HALT-COST (smoke >$2 or pod fails to boot → DR-31 CUDA-only downgrade). Deviation from CLAUDE.md §1.2 documented in .planning/phases/03-rocm-validation-archived/03-01-AMENDMENTS.md §D-31-A4.1.

### Pending Todos

None yet.

### Blockers/Concerns

- **NC-R14 (sharing Phase 0 with firm):** RESOLVED 2026-05-06 — DR-31 v0.1.0 approved.
- **Companion documents:** RESOLVED 2026-05-06 — all 6 present in `docs/` (commit e16d86e).
- **CLOUD-02 (RunPod MI300X harness):** PARTIAL — _scheduled for closure in Plan 03-01.5 (RunPod-retargeted per D-31-A4.1, 2026-05-11)_. RunPod (CLOUD-01) account + RUNPOD_API_KEY already in operator env from Phase 02. TensorWave $75 deposited but provisioning surface unknown (now secondary fallback; only activated if HALT-STOCK fires from Plan 03-01.5 Task 6 → 03-01.6 plan). Vultr $75 deposited + adapter verified (backup; sentinel UNSET). Cost-watch loop polls all 3 cleanly. **Phase 3 03-01 amendment D-31-A4.1 (2026-05-11) retargeted the primary MI300X substrate from TensorWave to RunPod** — empirical evidence: RunPod publicly lists MI300X at $1.99/GPU-hr Secure Cloud per-GPU. Wave 2 spend (Plan 03-02) is blocked until `orchestration/runpod_mi300x.py` + dispatch shim land in Plan 03-01.5 (rewritten in place; 6 tasks: probe extension, module, tests, dispatch shim, smoke driver, operator checkpoint). Stock-poll watchdog inside `provision()` raises a STOCK error before any spend if 60 sec of polling returns None; plan-level HALT-STOCK branch escalates to 03-01.6 (TensorWave investigation) if 24h of polls return None at the documented cadence.
- **Plan 03-01 follow-ups:** (1) `orchestration/runpod_mi300x.py` real provision() — **scoped to Plan 03-01.5 (rewritten 2026-05-11 per D-31-A4.1)** as the substrate-pivot enabler; was blocker, now plan; (2) `orchestration/tensorwave_mi300x.py` real provision() — **conditional** on HALT-STOCK branch from Plan 03-01.5 Task 6; only authored if RunPod stock proves chronically unavailable (24h stock=None) → future 03-01.6 plan; (3) `rbox-pod-rocm` derived-image build + push to GHCR + digest pin in `bench/images.lock.yaml` + `orchestration/runpod_mi300x.py:_DEFAULT_IMAGE_RUNPOD` — operator does this once a RunPod-validated dev pod (from Plan 03-01.5 Task 6 smoke) confirms the ROCm 7.12 base runs harness deps cleanly.
- **gfx942 → gfx1151 kernel gap:** dominant residual technical risk. Phase 3 must produce op-by-op kernel-coverage audit; Phase 4 widens confidence bands for "unknown" ops.
- **Phase 3 research recommended:** Chatterbox-Turbo ROCm install on TensorWave MI300X is highest-risk surface (devnen issues #192/#445 unresolved). Consider `/gsd-research-phase` before Phase 3 begins.

## Quick Tasks Completed

| ID | Date | Description | Commits |
|----|------|-------------|---------|
| 260511-vgz | 2026-05-12 | Triage 55 untracked files: gitignore vs atomic commits (post-DR-39 cleanup) | 5 (`6e6c155` gitignore, `bb81ea5` PRD v0.2, `664c9e0` DEV-1083 debug, `414f455` runpod tools, `fe2bf93` Phase 02 results) |

## Session Continuity

Last session: 2026-05-10T16:35:00.000Z
Stopped at: Phase 02 plans 02-04 / 02-07 / 02-08 summaries written; PREFLIGHT-01 closed; REQUIREMENTS / ROADMAP advanced. Phase 3 context (gathered separately at 16:18Z) preserved at .planning/phases/03-rocm-validation-archived/03-CONTEXT.md and DISCUSSION-LOG.md — ready for /gsd-plan-phase 3.
Resume file: .planning/phases/03-rocm-validation-archived/03-CONTEXT.md
Next action: /gsd-verify-work 2 to refresh 02-VERIFICATION.md against new SUMMARY artifacts; then /gsd-plan-phase 3 against the gathered context; DEV-1019 sanity is a parallel operator-driven option (closes PREFLIGHT-02/03 in Phase 2 rather than carrying as a Phase 3 precondition).

Open loose ends:

- 02-VERIFICATION.md still reflects 2026-05-06 state ("gaps_found", 3 BLOCKING gaps); refreshed by /gsd-verify-work 2.
- DEV-1019 sanity not run (PREFLIGHT-02/03 still pending).
- ~22 untracked files in repo (results/_pulled, results/g{1,2,3,5}, results/smoke, results/preflight, secrets/, .planning/debug/, tools/find_runpod_volume.py + 2 probe scripts, docs/receptionbox-technical-prd-v0_2-2026-05-06.md). Decide commit-vs-gitignore per file before Phase 3 starts.
- idle thumbox-spike-rtx5090 pod (vri99tskmvookr) STOPPED 2026-05-10 16:14Z; ~$0.24 sunk; volume preserved (50 GB). Separate from Phase 0; tracked under thUMBox parent project.
