# Phase 3: ROCm Validation - Context

**Gathered:** 2026-05-10
**Status:** Ready for planning

<domain>
## Phase Boundary

Phase 3 takes the proven CUDA-rail substrate from Phase 2 (LiveKit Agents → vLLM → faster-whisper → Chatterbox/Kokoro, real-spend-validated on H100 at WER 2.55% post-DEV-1083) and ports it to MI300X / ROCm to produce **measurement-grade data** for G1, G2, G3, G5, G7 against the full pinned corpora at concurrencies N=1/2/4 with per-stage decomposition. This is the data layer Phase 4 derates to Strix Halo (gfx1151) predictions.

Phase 3 also closes three load-bearing audits whose absence would invalidate the gate decision:

- **GATE-CHATTERBOX-D1** — Day 1 ROCm load smoke for Chatterbox-Turbo. The PRD risk register flags this as Medium-High; this gate is the dominant scope-shrink lever (fail → flip primary to Kokoro and re-scope G1/G7).
- **AUDIT-01 (Plan 03-05) Co-residency stack-load** — Whisper + Qwen3-4B + Chatterbox/Kokoro all loaded simultaneously under sustained ≥ 5-min load. Guards the false-pass path where individual gates pass but the integrated runtime OOMs / kernel-mismatches.
- **AUDIT-02 (Plan 03-06) gfx1151 op coverage audit** — `audit/gfx1151_op_status.md` with present/fallback/unknown per critical op for each model. The dominant residual technical risk per `.planning/STATE.md`: an op present on gfx942 (MI300X) but absent on gfx1151 (Strix Halo) turns a soft pass into a guaranteed appliance regression.
- **AUDIT-03 (Plan 03-05, shared harness with AUDIT-01) Engine-swap-under-load** — TTS engine flipped from Chatterbox to Kokoro mid-session (T+2:30 of the 5-min co-residency window) via config-row write to `config/sanity_strata.yaml`; swap-time measured. Proves DR-27 pluggable-TTS architecture viability.

**In-scope (10 requirements):** HARNESS-03 (`substrate/rocm.py`), GATE-CHATTERBOX-D1 (Day-1 kill-switch), GATE-G1 / G2 / G3 / G5 / G7 (full-corpora measurements), AUDIT-01 (co-residency stack-load), AUDIT-02 (gfx1151 op-coverage), AUDIT-03 (engine-swap-under-load).

**Note on AUDIT-ID labels:** `.planning/REQUIREMENTS.md` is authoritative. An earlier draft of this CONTEXT.md (and a planning brief that referenced it) used `AUDIT-01 = provider stub-with-warning honesty` — that mapping was incorrect. The D-34 stub-with-warning posture for `cost/adapters/tensorwave.py` is already enforced by Phase 1 code (`cost/adapters/tensorwave.py:_check()`) and does not need a Phase 3 audit plan.

**Out-of-scope:**
- Phase 4 derating + synthesis judgment (Phase 3 only captures cloud measurements; Phase 4 turns them into Strix Halo predictions)
- TensorWave/Vultr cost-cap rail beyond per-pod ceiling (provider $75 caps already enforced)
- Local Strix Halo validation (no dev unit; Phase 0 stays cloud-only per Phase 1 D-02)
- LiveKit SFU / production agent-worker code (Phase 2+ product, not Phase 0 benchmarks)
- Cloud LLM fallback measurement (FR-R49 OFF default; PROJECT.md out-of-scope)

**Spend ceiling:** $54 per CLAUDE.md §13 cost estimate, hard-capped by Vultr/TensorWave $75 prepaid caps and the $150 Phase-0 program ceiling. After Phase 2 burn (~$1 today), program-level remaining is ~$148.

</domain>

<decisions>
## Implementation Decisions

### Carried forward from Phase 2 (locked, do NOT relitigate)

- **D-09 substrate ABC contract** — `substrate/rocm.py` MUST implement `async def` methods returning `AsyncIterator[Chunk]`. No sync wrappers.
- **D-10 GateResult schema** — every Phase 3 gate run emits a pydantic-validated GateResult with `schema_version="1.0"`, `substrate="rocm"`, all required fields populated. Error rows kept (status="error", measurements NULL).
- **D-11 result storage** — JSONL append per call to `results/{gate}/{run_id}.jsonl`; SQLite index rebuilt by `make report`.
- **D-12 env.json sidecar** — every Phase 3 run emits `results/{gate}/{run_id}.env.json`. ROCm version + PyTorch ROCm wheel + vLLM version recorded (parallel to Phase 2's CUDA + vLLM versions).
- **D-14 substrate composition** — Single `substrate/rocm.py` class implements the ABC by composing 4 backend adapters (vLLM client, faster-whisper engine, Chatterbox client, Kokoro client) — NOT 4 separate substrate classes. Mirrors `substrate/cuda.py:CUDASubstrate`.
- **D-15 LiveKit Agents pipeline** — Use `livekit-agents` 1.x `AgentSession` for the E2E pipeline rig (matches production receptionBOX agent-worker per PRD §4.2 + CLAUDE.md §8). Custom plugins wrap the 4 backends. Per-stage timestamps from `AgentSession`'s native instrumentation.
- **D-16 in-instance watchdog** — `tools/pod_entrypoint.sh` watchdog at `MAX_MINUTES`. Force-terminate via `runpodctl pod stop` (or provider equivalent) on TIMEOUT. `tools/run_preflight._run_gate` enforces the same ceiling client-side.
- **D-17 rsync result-pull on shutdown** — `tools/rsync_results.sh` from SIGTERM trap; `tools.fetch_results` provides the alternate volume-pull path for diag-pod recovery.
- **D-22 / D-23 pre-teardown audit** — `tools/audit_pod_state.py` runs in shutdown chain; `<epoch>.audit.json` written + pulled. Hash-pinned manifest comparison; fail-loud.
- **DEV-1021 provenance pattern** — `provision()` injects `RBOX_IMAGE_DIGEST=<image_ref>` env into the pod; `_lookup_image_digest()` reads env first. Build script passes `--build-arg GIT_COMMIT=$(git rev-parse HEAD)`; Dockerfile bakes `/workspace/.git_commit`. Both fields populate every result row.
- **Cost ledger gate** — `authorize_spend()` MUST be the first call in every `provision()` (Phase 1 AST-asserted). `cost/adapters/*` MUST NOT raise (log WARNING, return `(0.0, 0.0)`).
- **DR-27 pluggable TTS** — Chatterbox unhealthy → Kokoro fallback path stays in `synthesize()`. The Day-1 kill-switch decides which is *primary*; DR-27 fallback still applies to whichever is primary.
- **DR-31 sharing policy** — Phase 3 cloud numbers are internal-only pre-SOW; two-tier presentation rule (Measured cloud / Predicted appliance) applies if any number leaves the harness.

### MI300X provider + Day-1 substrate

- **D-31 [AMENDED to D-31-A4 — 2026-05-11]: TensorWave is Day-1 primary; Vultr demoted to backup.** Original D-31 named Vultr Day-1 on the strength of an already-provisioned account + adapter. Task 5 operator checkpoint surfaced that Vultr's *only* MI300X SKU is `vbm-256c-2048gb-8-mi300x-gpu` — an 8-GPU bare-metal node, `deploy_ondemand=false`, preemptible-only at $14.80/hr for the whole node. Breaks Phase 3's $54 budget 4× over and breaks GATE-CHATTERBOX-D1's $4 spend cap (D-36). TensorWave at ~$1.71/GPU-hr on-demand fits the budget. `orchestration/vultr_mi300x.py` stays in the repo as backup with `_DEFAULT_IMAGE_ROCM` UNSET sentinel intact; a new `orchestration/tensorwave_mi300x.py` is the Day-1 follow-up gated on TensorWave sales unblock. **Wave 2 (Plan 03-02) is currently blocked** on this sales contact; the previous "don't wait for TensorWave" posture no longer applies. See `.planning/phases/03-rocm-validation/03-01-AMENDMENTS.md` for the full rationale.
- **D-32 [AMENDED to D-32-A1 — 2026-05-11]: Separate `rbox-pod-rocm` image.** New Dockerfile at `dockerfiles/rocm/Dockerfile` FROM `rocm/vllm:rocm7.12.0_gfx94X-dcgpu_ubuntu24.04_py3.12_pytorch_2.9.1_vllm_0.16.0` @ `sha256:997f858b…2a8f7` (D-32-A1 migration — CLAUDE.md §2.1's `rocm6.4_mi300_*` tag pattern never existed on Docker Hub). ENTRYPOINT remains `tools/pod_entrypoint.sh`. Build script `scripts/build_pod_image_rocm.sh` takes `--build-arg GIT_COMMIT` (mirrors v18 pattern). Pushed to `ghcr.io/consultingfuture4200/rbox-pod-rocm`. `_DEFAULT_IMAGE_ROCM` constant carries the digest pin per CLAUDE.md §2.3.
- **D-33 (Per-gate max_minutes for Phase 3):** `config/budget.yaml` adds `phase3.max_minutes_per_gate`:
  - `chatterbox_d1: 120` (2-hr Day-1 timebox per D-35 below)
  - `g1: 120` (500-call corpus × N=1/2/4 takes time)
  - `g2: 45` (200 G.711 dual-path)
  - `g3: 20` (threshold sweep across 12 thresholds)
  - `g5: 30` (200 UPL probes)
  - `g7: 45` (30 stimulus pairs warm + cold)
  - Sum ~380 min. At Vultr $1.85/hr ≈ $11.7 per full sanity, leaving headroom for re-runs and contingency inside $54.
- **D-34 (Cost-tracking on ROCm rail):** Wall-clock × $/hr estimate per provider. `cost/adapters/vultr.py` already returns real billing via `/v2/billing/pending-charges` — keep that as the reconciler. `cost/adapters/tensorwave.py` stays stub-with-warning per CLAUDE.md Pitfall C; uses `wall_clock_s × $1.71/hr` as the projected and recorded cost. Audit log writes both estimate and (when available) reconciled value. Honest about the asymmetry in DR-31 two-tier presentation downstream.

### Chatterbox kill-switch + Kokoro fallback policy

- **D-35 (Kill-switch pass criteria):** Chatterbox-Turbo passes Day-1 ROCm load smoke when **all** of:
  1. `devnen/Chatterbox-TTS-Server` container starts and reports GPU device count > 0 via `rocminfo` / torch CUDA-shim probe (per CLAUDE.md §5.1 Pitfall about `count=0` mismatches).
  2. `/v1/audio/speech` endpoint responds 200 to a fixed test prompt within 60 s.
  3. Output audio is valid PCM (`sf.read` parses, RMS > 0.01, duration > 1 s).
  4. No exceptions in container logs during the 30 s test render.

  **Does NOT measure latency** — that's G7. Mixing latency into the kill-switch creates flake (thermal / first-pull variance). Same fixed test prompt gets reused on TensorWave kill-switch when that comes online.
- **D-36 (Day-1 timebox + cost cap):** **2-hr wall-clock, $4 spend cap.** Generous enough to fight one or two devnen-style ROCm install issues (#192 / #445) but small enough that a non-functional path doesn't sink the day. After 2 hr or $4: stop, write `audit/chatterbox_d1_decision.md`, flip primary to Kokoro per D-37, re-scope G1/G7 to use Kokoro as the measured engine. Kokoro is the documented fallback per DR-27; this is not an emergency, it's the planned graceful path.
- **D-37 (Fallback shape — config-row mechanism):** Add `tts.primary: chatterbox|kokoro` to `config/sanity_strata.yaml`. `substrate/rocm.py:synthesize()` reads the row at session start. DR-27 fallback (Chatterbox unhealthy → Kokoro) still applies on top of whichever is primary. **P3.7 engine-swap-under-load demo flips this same config row mid-session** with a measured swap-time (delta between row write and first Kokoro audio chunk). Single source of truth, machine-readable, propagates to G1 / G7 gate runners without code change.
- **D-38 (Decision audit trail):** Three artifacts on Day-1:
  1. `.planning/STATE.md` appends a one-line entry: `2026-MM-DD primary TTS = chatterbox|kokoro per GATE-CHATTERBOX-D1`.
  2. Linear DEV-1022 receives a comment with the JSONL row + decision summary + cost.
  3. `audit/chatterbox_d1_decision.md` is the long-form: install commands tried, container log excerpts, test prompt, output WAV SHA, GPU enumeration evidence, final pass/fail with reasoning. Phase 4 synthesis cites this audit doc.

### Claude's Discretion (operator declined detailed discussion)

The following Phase 3 gray areas were not discussed at this depth — defaults below are documented so operator can override before plan-phase:

- **G2 dual-path mechanism (P3.3)** — Default: same gate runner emits **two rows per asset** with `extras.engine: faster-whisper-int8 | onnx-rt-rocm`. Sequential within a single pod (model loads stay warm; halves pod count). `metrics.wer` and `metrics.ref_text_normalized` stay first-class; `extras.engine` is the discriminator for Phase 4 cross-decoder consistency analysis. Override path: split into two gate sub-runs if the engines turn out to need different sample-rate / VAD profiles.
- **G1 concurrency rig (P3.2)** — Default: `gates/g1/runner.py` accepts `--concurrency N` flag; under the hood it `asyncio.gather()`s N copies of the existing single-call coroutine against N independent LiveKit `AgentSession`s sharing the same vLLM / Whisper / Chatterbox endpoints. Records `extras.concurrency: N` per row. Three pod runs at N=1, N=2, N=4 (separate pods so cold-cache effects don't bleed). Override path: a single longer pod that walks N=1→2→4 in sequence if pod transitions waste too much wall-clock.
- **Co-residency stack-load profile (P3.7)** — Default: 5-min sustained run replays a randomly-permuted slice of the 500-call corpus at N=2 concurrency with all three model classes (Whisper + Qwen3-4B + Chatterbox/Kokoro) loaded; records `nvidia-smi`-equivalent ROCm memory headroom every 10 s, kernel mismatch / OOM / crash flags. Mid-run engine-swap-under-load fires once at the 2:30 mark via D-37 config-row write. Override path: longer/shorter sustained window; different concurrency profile.
- **gfx1151 op coverage audit method (P3.8)** — Default: `tools/audit_op_coverage.py` runs each model through a single representative inference call **with `TORCH_LOGS=output_code` (or ROCm equivalent) capturing op-by-op kernel dispatch**, then cross-references the captured op set against the gfx1151 kernel registry (sourced from PyTorch ROCm release notes + Phoronix Nov 2025 Strix Halo benchmarks data). Output: `audit/gfx1151_op_status.md` with one row per op: `{op_name, model_using, gfx942_status: present, gfx1151_status: present|fallback|unknown, source}`. Override path: live MI300X→Strix-Halo comparison once a Framework Desktop dev unit is on hand (post-Phase-0; not Phase-3 scope).

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### ROADMAP / Requirements / Project
- `.planning/ROADMAP.md` §"Phase 3: ROCm Validation" — phase boundary
- `.planning/REQUIREMENTS.md` §HARNESS-03, §GATE-CHATTERBOX-D1, §GATE-G1/G2/G3/G5/G7, §AUDIT-01..03 — acceptance criteria
- `.planning/PROJECT.md` — overall mission + $150 ceiling + tech stack pins
- `.planning/STATE.md` — Phase 2 closeout state, residual blockers (TensorWave sales pending, gfx1151 kernel gap)

### Phase 1 / 2 carry-forward
- `.planning/phases/01-foundation/01-CONTEXT.md` §D-09 to D-13 — substrate ABC, GateResult schema, env.json sidecar, companion docs
- `.planning/phases/02-cuda-pre-flight/02-CONTEXT.md` §D-14 to D-30 — substrate composition, LiveKit pipeline, watchdog, rsync, audit, smoke + sanity scope, recording schema, repro tuple
- `.planning/research/STACK.md` — exhaustive stack reasoning (esp. ROCm sections)
- `.planning/research/PITFALLS.md` — Pitfalls 1-11 (Pitfall 1 isolation, Pitfall 5 cleanup, Pitfall C TensorWave billing)

### Tech / Operator
- `CLAUDE.md` §1.2 (MI300X cloud — TensorWave + Vultr), §2.1 (ROCm container `rocm/vllm:rocm6.4_mi300_*`), §3 (LLM stack — vLLM ROCm), §4 (STT — faster-whisper + ONNX-RT ROCm), §5.1 (Chatterbox devnen ROCm, Pitfalls), §5.2 (Kokoro moritzchow ROCm), §5.3 (TTS first-audio measurement), §5.4 (G7 quality A/B), §6 (turn detection), §7 (derating methodology — Phase 4 input shape), §8 (LiveKit pipeline), §11 (NOT-to-use list), §13 (cost estimate per gate), §14 (stack summary)
- `docs/decisions/dr-31-sharing-policy.v0.1.0.md` — DR-31 two-tier presentation rule
- `docs/receptionbox-virtual-benchmark-plan-v0_1-2026-05-03.md` §Phase 0 procedures — authoritative virtual benchmark plan
- `docs/receptionbox-technical-prd-v0_2-2026-05-06.md` §4.2 (production agent-worker), §4.5 (STT v2 streaming), §11 (risk register — Chatterbox-ROCm Medium-High)
- `docs/addendum-hardware-pivot-strix-halo-v0_1-2026-04-23.md` — DR-24 Strix Halo / gfx1151 derating context

### Existing code
- `substrate/types.py` — Chunk, GateResult, ABC (Phase 1)
- `substrate/cuda.py` — `CUDASubstrate` (Phase 2; mirror this composition shape for `rocm.py`)
- `substrate/adapters/{vllm_client,faster_whisper_engine,chatterbox_client,kokoro_client}.py` — backend adapters (Phase 2; reusable as-is for Phase 3 with model-dir / endpoint config swap)
- `cost/ledger.py` — authorize_spend / record_spend / BudgetExhausted
- `cost/adapters/vultr.py` — billing-poll adapter (already real; reused for Phase 3 D-34)
- `cost/adapters/tensorwave.py` — stub-with-warning (CLAUDE.md Pitfall C; D-34 documents this asymmetry)
- `orchestration/runpod_h100.py` — Phase 2 reference impl; mirror provision() shape in `vultr_mi300x.py`
- `orchestration/vultr_mi300x.py` — Phase 3 03-01 filled with real `provision()` but PARKED per D-31-A4 (sentinel UNSET); kept as backup-only path
- `orchestration/tensorwave_mi300x.py` — Phase 1 stub; Day-1 primary per D-31-A4 — needs its own follow-up plan once TensorWave sales unblocks (Wave-2 blocker)
- `gates/_runner_base.py`, `gates/g{1,2,3,5}/runner.py` — substrate-agnostic; Phase 3 adds `gates/g7/runner.py` (TTS A/B)
- `tools/pod_entrypoint.sh`, `tools/cache_bootstrap.py`, `tools/audit_pod_state.py`, `tools/rsync_results.sh`, `tools/fetch_results.py`, `tools/run_preflight.py` — operational tooling (Phase 2; reused on ROCm rail with provider-flag awareness)
- `bench/models.lock.yaml` — HF revision SHA pins (already populated for all 4 models in Phase 2 P2.5)
- `bench/images.lock.yaml` — image digest schema (Phase 3 adds `rbox-pod-rocm` row; D-32 + DEV-1021 pattern)
- `config/budget.yaml` — Phase 3 adds `phase3.*` block per D-33
- `config/sanity_strata.yaml` — Phase 3 adds `tts.primary` row per D-37 + populates G7 stratification
- `assets/manifest.csv` — provenance + SHA pins (Phase 1; reused)

### New files Phase 3 introduces
- `substrate/rocm.py` — HARNESS-03 substrate impl
- `dockerfiles/rocm/Dockerfile` (or `Dockerfile.rocm`) + `scripts/build_pod_image_rocm.sh` — D-32
- `gates/g7/runner.py` — TTS A/B gate runner
- `audit/chatterbox_d1_decision.md` — D-38 long-form decision record
- `audit/gfx1151_op_status.md` — AUDIT-02 deliverable
- `tools/audit_op_coverage.py` — op-by-op kernel dispatch capture per Claude's-Discretion default

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **`substrate/cuda.py:CUDASubstrate`** — composition shape (4 adapters, async/streaming, env_fingerprint helpers, DR-27 fallback in `synthesize()`) ports directly to `rocm.py`. Only the model-dir paths, endpoint URLs, and `_lookup_image_digest()` env-var lookup change.
- **`substrate/adapters/*.py`** — Backend adapters are HTTP/HTTP/HTTP/in-process. The HTTP ones (vLLM, Chatterbox, Kokoro) work unchanged on ROCm — only the upstream server is different. The in-process one (faster-whisper) needs the CTranslate2 ROCm build verified, plus the parallel ONNX-RT ROCm path for G2 dual-decode (D-Discretion above).
- **`orchestration/runpod_h100.py:provision()`** — Reference shape for `vultr_mi300x.py:provision()`. Same env-dict pattern (GATE, MAX_MINUTES, RBOX_IMAGE_DIGEST, etc.), same authorize_spend-first contract, same dry-run path on missing API key.
- **`tools/pod_entrypoint.sh`** — Provider-agnostic; reused as-is. Watchdog, cost-watch, SSH setup, rsync trap, audit chain all unchanged.
- **`tools/fetch_results.py`** — Provider-aware via env-overrideable GPU type (`RUNPOD_FETCH_GPU_TYPE`); Phase 3 adds `VULTR_FETCH_GPU_TYPE` (or generic `FETCH_GPU_TYPE`). RTX 4090 fallback worked twice today on US-CA-2 stock shortages — pattern transfers.
- **`cost/adapters/vultr.py`** — Real billing adapter. D-34 leans on this for Vultr-side reconciliation.
- **`gates/_runner_base.py:_git_commit()` + `substrate/cuda.py:_lookup_image_digest()`** — DEV-1021 fix shape (RBOX_IMAGE_DIGEST env + /workspace/.git_commit baked file) is mandatory in `substrate/rocm.py` and any new `Dockerfile.rocm`. No regression allowed.

### Established Patterns (Phases 1 + 2)
- **Async + streaming everywhere** — substrate ABC enforces `AsyncIterator[Chunk]`. `substrate/rocm.py` follows.
- **Adapters MUST NOT raise** — `cost/adapters/*` log + degrade. `cost/adapters/tensorwave.py` already follows; D-34's stub-with-warning posture is the documented honesty.
- **Pydantic everywhere** — env.json + GateResult validated on read AND write.
- **HF revision SHA pinning** — `bench/models.lock.yaml` is the single source. Phase 3 reuses the same SHAs.
- **Image digest pinning by SHA, NOT tag** (CLAUDE.md §2.3) — `_DEFAULT_IMAGE_ROCM` carries `@sha256:...`.
- **Single mechanism for cost control** — in-instance watchdog (D-16) + cost ledger refusal (Phase 1) + provider $75 caps. Phase 3 adds nothing new to the cost-cap rail — just plumbs the same machinery to the ROCm rail.

### Integration Points
- `substrate/_stub.py` import sites (if any remain) → `substrate/rocm.py` swap on the ROCm rail
- `orchestration/vultr_mi300x.py` `provision()` stub body → real Vultr SDK call (or shell-out) after `authorize_spend()` succeeds
- `gates/g7/runner.py` (new) — substrate-agnostic; mirrors `gates/g{1,2,3,5}/runner.py` shape
- `tools/audit_op_coverage.py` (new) — invoked once-per-model on a warm MI300X pod; emits the AUDIT-02 deliverable
- `dockerfiles/rocm/Dockerfile` (new) — separate base, same ENTRYPOINT, same ARG GIT_COMMIT pattern
- `scripts/build_pod_image_rocm.sh` (new) OR add `--rail rocm|cuda` flag to existing `scripts/build_pod_image.sh` — planner's call

</code_context>

<specifics>
## Specific Ideas

- **vLLM serve params** locked in CLAUDE.md §3.1: `--quantization awq` (cloud equivalent of Q4_K_M), `--guided-decoding-backend xgrammar`. ROCm path same flags; verify ROCm 6.4 vLLM Dockerfile matches.
- **faster-whisper params** unchanged from Phase 2: INT8, `vad_filter=True`, `beam_size=1`. **G2 corpus_g711 fix from DEV-1083** (codec-aware decode in `substrate/adapters/faster_whisper_engine.py`) is on `main` and will be in v18+ → ROCm rail inherits the fix automatically.
- **ONNX-RT ROCm path for G2 P3.3** — per CLAUDE.md §4.2, this is the production-runtime parallel decoder. Use `onnxruntime-rocm` Python package; load distil-whisper exported via `optimum.onnxruntime` with the encoder-decoder split. Same input bytes, different decoder → comparable WER per-row.
- **Chatterbox-Turbo** — `devnen/Chatterbox-TTS-Server` ROCm fork (CLAUDE.md §5.1 Notes about `--no-deps` install). Day-1 install commands tracked in `audit/chatterbox_d1_decision.md`; #445 / #192 GitHub issues are the known-bad recipes.
- **Kokoro-82M** — `moritzchow/Kokoro-FastAPI-ROCm` per CLAUDE.md §5.2; `hexgrad/Kokoro-82M` weights pinned. ONNX path (`onnx-community/Kokoro-82M-v1.0-ONNX`) is the documented backup if PyTorch ROCm path is rough.
- **Turn detection** — silero-vad v5 + LiveKit `turn-detector` plugin (CLAUDE.md §6). Threshold sweep 400–1500 ms in 100 ms steps for P3.4 — 12 thresholds, false-positive rate at each. Driven from `gates/g3/runner.py` with `--threshold-ms` flag.
- **vLLM benchmark CLI** (CLAUDE.md §3.3) — reference for TTFT / ITL measurement; gate runners can wrap it OR roll their own with the same fields.
- **Repro tuple population** — DEV-1021 fix carry-forward is mandatory: `RBOX_IMAGE_DIGEST` env + `/workspace/.git_commit` baked file. ROCm rail must populate `image_digest` and `git_commit` correctly from the start; no "fix in Phase 4" loophole.
- **Day-1 sequencing [AMENDED — D-31-A4]** — TensorWave (not Vultr) provisioning + first Chatterbox kill-switch happen on the same pod or back-to-back pods (the Chatterbox docker image cache may survive across pods on the same host — TensorWave behavior here is TBD; the previous Vultr-host-cache assumption does not transfer). Plan 03-02 should account for cold-pull on first TensorWave pod and validate warm-cache behavior empirically.

</specifics>

<deferred>
## Deferred Ideas

- **TensorWave provisioning** — wired up only when sales unblocks. Tracked as a follow-up issue; doesn't gate Phase 3.
- **`tools/audit_op_coverage.py` Strix Halo live comparison** — Phase 0 ships the gfx942-side capture + gfx1151 registry cross-reference. A live MI300X→Strix-Halo comparison requires the Framework Desktop dev unit (post-Phase-0).
- **Engine-swap-under-load via hot reload** — current D-37 plan flips a config row mid-session. A tighter implementation (signal-driven reload of just the TTS adapter, no AgentSession restart) would give a sub-second swap-time. → backlog if the config-row swap-time turns out to be embarrassing.
- **Concurrency stress beyond N=4** — Phase 3 stops at N=4 per the gate spec. N=8 / N=16 stress is appliance-irrelevant (T3 hardware is single-pack-per-appliance per DR-25). → out of program scope.
- **Make verify-provenance target** — DEV-1021 AC #4 was deferred. Phase 4's repro-manifest seal will assert these fields anyway. → backlog or fold into Phase 4 plan.
- **Multi-pack co-residency** — DR-25 v1 is single-pack-per-appliance. Out of Phase 0 scope at every level.
- **Cloud LLM fallback measurement** — FR-R49 OFF default. Out of scope per PROJECT.md.

</deferred>

---

*Phase: 03-rocm-validation*
*Context gathered: 2026-05-10 via 2-area focused discussion (provider/Day-1 + Chatterbox kill-switch); 4 sub-areas to Claude's Discretion*
