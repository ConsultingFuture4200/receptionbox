# Phase 2: CUDA Pre-flight - Context

**Gathered:** 2026-05-06
**Status:** Ready for planning
**Source:** Operator skipped discussion — Claude's Discretion defaults applied for all gray areas

<domain>
## Phase Boundary

Phase 2 assembles the end-to-end receptionBOX pipeline (LiveKit Agents 1.x → vLLM 0.10+ → faster-whisper INT8 → Chatterbox-Turbo / Kokoro) on RunPod H100 CUDA substrate and runs it once against real spend, proving that:

- The real `substrate/cuda.py` impl (replacing the Phase 1 stub) honors the async/streaming ABC contract from D-09
- `orchestration/runpod_h100.py` actually provisions an H100 pod (replacing the Phase 1 cost-ledger-gate stub)
- Cost ledger authorize-then-spend gate works under real provider billing (CLOUD-01 already verified at $0.00; Phase 2 closes the loop with non-zero spend)
- Result store (JSONL + SQLite + env.json sidecar) ingests gate output correctly under real conditions
- Watchdog + result-pull + pre-teardown audit pipeline proves the cleanup posture works before MI300X (where slip = bigger blast radius)

**In-scope (10 requirements):** HARNESS-02 (substrate/cuda.py), HARNESS-05 (env.json sidecar — real data), HARNESS-06 (substrate-agnostic gate runners under `gates/g{1,2,3,5}/runner.py`), PREFLIGHT-01 (5-call G1 smoke <$1, <30 min), PREFLIGHT-02 (sanity G1/G2/G3/G5 baseline numbers, G7 deferred), PREFLIGHT-03 (substrate fingerprint = `cuda` recorded), CLOUD-04 (in-instance watchdog), CLOUD-05 (persistent HF cache), CLOUD-06 (pre-teardown audit), REPRO-03 (full reproducibility tuple per result row).

**Out-of-scope:**
- HARNESS-03 / `substrate/rocm.py` — Phase 3
- All MI300X provisioning — Phase 3
- G7 TTS A/B — deferred to MI300X (PREFLIGHT-02 explicit)
- Final synthesis / derating / cross-substrate consistency *judgment* — Phase 4 (Phase 2 only sets the recording schema)
- Engine swap drills (Ollama overhead measurement, etc.) — backlog
- Real PSTN audio of any kind (synthetic G.711 only, locked by D-02 Phase 1)

**Spend ceiling:** $14 per cost estimate §13, hard-capped by RunPod $75 prepaid + auto-recharge OFF. Pre-flight is the cheapest substrate before MI300X — burn budget here, not later.

</domain>

<decisions>
## Implementation Decisions

### Carried forward from Phase 1 (locked, do NOT relitigate)

- **D-09 substrate ABC contract** — `substrate/cuda.py` MUST implement `async def` methods returning `AsyncIterator[Chunk]`. No sync wrappers.
- **D-10 GateResult schema** — every Phase 2 gate run emits a pydantic-validated GateResult with `schema_version="1.0"`, all required fields populated, `substrate="cuda"`. Error rows MUST be kept (status="error", measurements NULL) — no silent filtering.
- **D-11 result storage** — JSONL append per call to `results/{gate}/{run_id}.jsonl`; SQLite index rebuilt by `make report`; Parquet on demand only.
- **D-12 env.json sidecar** — every Phase 2 run emits `results/{gate}/{run_id}.env.json` with substrate fingerprint, model SHAs, image digest, git commit, asset manifest hash, CUDA + vLLM versions, timestamps. Real values, not stubs (HARNESS-05 gets its first real-data exercise here).
- **D-13 companion docs** — already present in `docs/` (commit e16d86e).
- **DR-31 sharing policy** — Approved 2026-05-06. Phase 2 cloud numbers are internal-only pre-SOW; two-tier presentation rule applies if any number leaves the harness.
- **Tech stack pins (CLAUDE.md §2)** — Image `vllm/vllm-openai:v0.10.x` (CUDA 12.4) + NGC `pytorch:25.04-py3`. Models pinned via HF revision SHA: `Qwen/Qwen3-4B`, `Systran/faster-distil-whisper-large-v3`, Chatterbox-Turbo, `hexgrad/Kokoro-82M`. xgrammar as guided-decoding-backend in vLLM. silero-vad v5 + LiveKit turn-detector for VAD.

### Substrate impl (HARNESS-02)

- **D-14 (CUDA substrate composition):** Single `substrate/cuda.py` class implements the ABC by composing 4 backend adapters (vLLM client, faster-whisper engine, Chatterbox client, Kokoro client) — NOT 4 separate substrate classes. The substrate is the seam; the adapters are private to it. *(Claude's Discretion — operator did not specify.)*
- **D-15 (LiveKit Agents pipeline):** Use `livekit-agents` 1.x `AgentSession` for the E2E pipeline rig (matches production receptionBOX agent-worker per PRD §4.2 + CLAUDE.md §8). Custom plugins wrap the 4 backends. Per-stage timestamps come from `AgentSession`'s native instrumentation; we do NOT reinvent them. *(Stack pin from CLAUDE.md.)*

### Watchdog + teardown (CLOUD-04)

- **D-16 (Enforcement mechanism):** **In-instance daemon** in the pod entrypoint shell script. After `max_minutes` (per-gate config in `config/budget.yaml`), the daemon sends SIGTERM to the worker process, waits up to 60s for graceful drain, then issues `runpodctl pod stop` against itself. Robust to operator-network partition. *(Claude's Discretion. External-poller fallback is not implemented — single mechanism by design.)*
- **D-17 (Result-pull on shutdown):** **rsync to operator workstation over SSH**, fired from the SIGTERM trap handler in the pod entrypoint BEFORE the pod self-terminates. The destination is `~/RBOX/results/` on the operator workstation; SSH key injected via RunPod env var (operator handles key generation). `assets/` is NEVER copied back — only `results/` (which contains JSONL + env.json + scrubbed traces). *(Claude's Discretion.)*
- **D-18 (Watchdog config schema):** `config/budget.yaml` adds a `phase2.max_minutes_per_gate` map: `smoke: 30, g1: 30, g2: 15, g3: 10, g5: 15`. Sum ≤ 100 minutes total per pre-flight session, well inside the $14 budget at $2.69/hr SXM.

### HF model cache (CLOUD-05)

- **D-19 (Cache placement):** **RunPod network volume**, mounted at `/models` in every pod. Models are pulled once via a one-time bootstrap pod (counted in $14 budget); subsequent pods read-only. Volume size: 50 GB (Qwen3-4B + Whisper + Chatterbox + Kokoro fits in <30 GB; 50 GB headroom). *(Claude's Discretion — chose persistence over cold-start hits.)*
- **D-20 (Bandwidth cost in projection):** Initial bootstrap pull is ~25 GB at RunPod-internal-bandwidth (free for inbound); per-pod re-mount is free. `cost/budget.yaml` line item: `phase2.cache_bootstrap_one_time_usd: 0.50` (storage hour amortization, not bandwidth).
- **D-21 (Cache invalidation):** Models keyed by HF revision SHA in the volume path (`/models/{repo}/{sha}/`). Phase 1 lockfiles (`models.lock.yaml`) drive bootstrap; bumping a SHA in the lockfile triggers a fresh pull on next pod start. No automatic cleanup of old SHAs — operator decides when to prune.

### Pre-teardown audit (CLOUD-06)

- **D-22 (Audit posture):** **Hash-pinned manifest comparison, fail-loud.** Before SIGTERM completes graceful drain, the entrypoint runs `tools/audit_pod_state.py` which: (1) walks the pod filesystem, (2) hashes every file under `~/RBOX/assets/` and `~/RBOX/results/`, (3) confirms every `assets/` file matches `assets/manifest.csv` SHA256 (no extras), (4) confirms no file under `results/` has an audio extension (`.wav|.mp3|.flac|.opus|.ogg`), (5) confirms no PII patterns (regexes for SSN, phone, email) in any text result. Any failure → audit log + non-zero exit + abort the rsync. *(Claude's Discretion — Pitfall 5 mitigation strongest. CLOUD-06 wording mandates the audit; this is the most defensible interpretation.)*
- **D-23 (Audit log destination):** Audit log appended to `results/{run_id}.audit.json` and pulled via rsync. If audit fails, the operator gets the audit log via rsync but NO measurement results — bias to losing the run rather than risking PII egress.

### G1 smoke (PREFLIGHT-01)

- **D-24 (Smoke profile):** **5 sequential calls at concurrency=1.** Production target is conc=1 (single inbound caller per pod); H100 concurrency stress is a separate concern that does NOT need to live in pre-flight. Smoke proves the pipeline assembles + runs once + writes results — concurrency surprises surface in Phase 3 sanity if we want them. *(Claude's Discretion. Concurrency stress moved to deferred ideas.)*
- **D-25 (Smoke success criteria — operationalized):** Smoke passes when (a) all 5 calls return `status="ok"` GateResult rows; (b) total wall clock <30 min; (c) total cost <$1.00 per RunPod billing API; (d) every row has non-NULL stt_ttft_ms / llm_ttft_ms / tts_first_audio_ms / e2e_ms; (e) env.json sidecar present and pydantic-valid; (f) audit log shows zero violations.

### Sanity runs (PREFLIGHT-02)

- **D-26 (Sanity scope):** **Minimal stratified subset, ~10 calls per gate (G1, G2, G3, G5).** Total ~40 calls, projected ~$2-3 at $2.39-2.69/hr SXM. Phase 2 is *pre-flight*, not measurement — sanity exists to (i) catch substrate bugs that smoke missed, (ii) produce non-degenerate baseline numbers for cross-substrate consistency in Phase 4, (iii) NOT compete with Phase 3 MI300X measurement budget. G7 deferred to MI300X per requirement wording. *(Claude's Discretion.)*
- **D-27 (Stratification rule):** G1 = 10 calls drawn from the 500-call corpus stratified by intent (2 per category, 5 categories). G2 = 5 neutral + 5 stressed from the 200 G.711 set. G3 = 10 hesitation clips covering all 4 hesitation patterns from D-03. G5 = 10 probes covering 5 refusal categories (2 per category) + 2 benign controls. The stratification rule is committed to `config/sanity_strata.yaml` and seeded for reproducibility.

### Cross-substrate consistency (PREFLIGHT-03)

- **D-28 (Recording schema):** **Substrate fingerprint = `cuda` recorded on every row** via `substrate` field (already in D-10 schema). No additional Phase 2 work — the schema already supports cross-substrate comparison.
- **D-29 (Consistency methodology — Phase 4 contract):** Per-stage timing tolerance is the primary signal: median(stt_ttft_ms_h100 + 25%) compared against median(stt_ttft_ms_mi300x). Same per-stage check for llm_ttft_ms, llm_decode_ms_per_tok, tts_first_audio_ms, e2e_ms. Per-gate metrics (WER on G2, refusal rate on G5) checked at gate-specific tolerances. Phase 2 ONLY locks the recording schema; the *judgment* lives in Phase 4. *(Claude's Discretion — sets the bar for Phase 4 without overcommitting now.)*

### Reproducibility (REPRO-03)

- **D-30 (Tuple population):** Every result row records `(image_digest, model_sha, asset_manifest_sha, git_commit, run_id, timestamp_utc)` — already required by D-10 schema. Phase 2 enforces population via pydantic validation; missing fields raise on write, not silently NULL. The `run_id` is a ULID generated at gate-runner entry; `git_commit` from `git rev-parse HEAD` at pod boot; `asset_manifest_sha` from sha256 of `assets/manifest.csv`; `image_digest` from `docker inspect` at pod boot; `model_sha` from HF cache dir.

### Claude's Discretion

All decisions D-14 through D-30 above were made under Claude's Discretion mandate (operator declined detailed discussion). Operator can override any of them by editing this CONTEXT.md before plan-phase, or via discuss-phase-resume. Highest-leverage to revisit if you want to push back:

- **D-22 audit posture** — most expensive decision; cheaper alternatives (extension-only check) exist
- **D-26 sanity scope** — could go fuller if budget allows OR thinner if you trust the substrate
- **D-19 cache placement** — pre-baked image alternative is cleaner reproducibility but more setup work

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### ROADMAP / Requirements / Project
- `.planning/ROADMAP.md` §"Phase 2: CUDA Pre-flight" — phase boundary
- `.planning/REQUIREMENTS.md` §HARNESS-02/05/06, §PREFLIGHT-01/02/03, §CLOUD-04/05/06, §REPRO-03 — acceptance criteria
- `.planning/PROJECT.md` — overall mission + budget cap
- `.planning/STATE.md` — Phase 1 closeout state, residual blockers

### Phase 1 carry-forward
- `.planning/phases/01-foundation/01-CONTEXT.md` §D-09 to D-13 — locked decisions Phase 2 inherits
- `.planning/phases/01-foundation/01-RESEARCH.md` — Pitfalls B/C (provider asymmetry), Pitfall 5 (cleanup audit motivation)
- `.planning/research/STACK.md` — exhaustive stack reasoning
- `.planning/research/PITFALLS.md` — Pitfalls 1-11

### Tech / Operator
- `CLAUDE.md` §1 (CUDA Path), §2.2 CUDA container, §3 LLM stack, §4 STT, §5 TTS, §8 LiveKit pipeline, §9 reproducibility, §11 NOT-to-use list, §12.2 install sketch — locked stack pins
- `docs/decisions/dr-31-sharing-policy.v0.1.0.md` — DR-31 (Approved 2026-05-06)
- `docs/receptionbox-virtual-benchmark-plan-v0_1-2026-05-03.md` §Phase 0 procedures — authoritative virtual benchmark plan
- `docs/receptionbox-technical-prd-v0_2-2026-05-03.md` §4.2 (production agent-worker), §0.5 (authority hierarchy)
- `docs/addendum-receptionbox-discovery-v0_2-2026-04-22.md` — discovery-gate semantics, kill criteria

### Existing code
- `substrate/types.py` — Chunk, GateResult, ABC (Phase 1)
- `substrate/_stub.py` — stub to replace with `cuda.py`
- `cost/ledger.py` — authorize_spend / record_spend / BudgetExhausted
- `cost/adapters/runpod.py` — billing-poll adapter
- `orchestration/runpod_h100.py` — provision skeleton (Phase 2 replaces stub with real call)
- `harness/results.py`, `harness/store.py`, `harness/env_fingerprint.py` — result writer + sidecar
- `assets/manifest.csv` — provenance + SHA pins
- `config/budget.yaml` — projected costs (Phase 2 adds `phase2.*` keys)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **Cost ledger** (`cost/ledger.py`) — `authorize_spend()` is the gate. AST-asserted in Phase 1 to be the first call in every orchestration `provision()`. Phase 2 must NOT bypass.
- **Result schema** (`substrate/types.py` GateResult) — pydantic-validated. Phase 2 populates real values for fields Phase 1 only stubbed.
- **RunPod adapter** (`cost/adapters/runpod.py`) — already returns real billing data (verified 2026-05-06). Phase 2 cost-watch loop is ready.
- **Cost watch daemon** (`cost/watch.py`) — runs out-of-band on operator workstation; Phase 2 starts it before pod boot.

### Established Patterns (Phase 1)
- **Async + streaming everywhere** — substrate ABC enforces `AsyncIterator[Chunk]`. Phase 2 implementations follow.
- **Adapters MUST NOT raise** (Phase 1 lock-in) — `cost/adapters/*` log WARNING and return `(0.0, 0.0)` on every error path. Phase 2's substrate adapters follow the same pattern: log + degrade, never crash the watch loop.
- **Pydantic everywhere** — env.json + GateResult validated on read AND write.
- **HF revision SHA pinning** — `bench/configs/models.lock.yaml` is the single source.

### Integration Points
- `substrate/_stub.py` → `substrate/cuda.py` (HARNESS-02): swap import in callers; ABC contract unchanged
- `orchestration/runpod_h100.py` `provision()` stub body → real `runpodctl pod create` (or RunPod SDK) call after `authorize_spend()` succeeds
- `gates/__init__.py` empty → `gates/g{1,2,3,5}/runner.py` per HARNESS-06 (substrate-agnostic, `make gN` invokable)
- New: `tools/audit_pod_state.py` (CLOUD-06) — invoked from pod entrypoint shutdown trap
- New: `config/sanity_strata.yaml` (D-27) — per-gate stratification rules
- New: `config/budget.yaml` `phase2.*` block — watchdog max_minutes + cache bootstrap line item

</code_context>

<specifics>
## Specific Ideas

- **vLLM serve params** locked in CLAUDE.md §3.1: `--quantization awq` (cloud equivalent of Q4_K_M), `--guided-decoding-backend xgrammar`, `--max-num-seqs 1` for Phase 2 (matches conc=1 production target).
- **faster-whisper params**: INT8 quantization, `vad_filter=True`, beam_size=1 (deterministic; matches `Systran/faster-distil-whisper-large-v3`).
- **Chatterbox-Turbo**: CUDA path is well-supported (unlike ROCm). Use upstream `resemble-ai/chatterbox` directly, NOT the devnen ROCm fork (which is for Phase 3 only).
- **Kokoro**: CUDA via `remsky/Kokoro-FastAPI` (upstream), NOT the moritzchow ROCm fork.
- **LiveKit AgentSession**: configure with silero-vad v5 + LiveKit `turn-detector` plugin per CLAUDE.md §8.
- **vLLM benchmark CLI** (`vllm/benchmarks/benchmark_serving.py` per CLAUDE.md §3.3) is the reference for TTFT / ITL measurement; gate runners can wrap it OR roll their own with the same fields.
- **rsync command shape**: `rsync -avz --partial --append-verify ~/RBOX/results/ operator@workstation:~/RBOX/results/` — atomic, resumable.
- **Pod entrypoint** is a shell script `tools/pod_entrypoint.sh` that: (1) starts cost-watch tracker, (2) starts the watchdog, (3) execs the gate runner, (4) on SIGTERM: runs audit, runs rsync, exits.

</specifics>

<deferred>
## Deferred Ideas

- **Concurrency stress profiling** — exercising H100 at conc=2/4/8 to surface batch-affinity issues before MI300X. Useful but not Phase 2 scope. → Phase 3 stretch goal or its own phase.
- **External-poller watchdog (workstation-side)** — operator-side defense in depth in case in-instance daemon hangs. → backlog (cost: another moving part to maintain).
- **Pre-baked custom Docker image** for HF cache (alternative to D-19 network volume) — cleaner reproducibility, more setup work upfront. → Phase 4 if synthesis flags reproducibility gaps.
- **G7 TTS A/B on H100** — explicitly out of scope per PREFLIGHT-02 wording. → Phase 3 MI300X.
- **End-of-week canary re-run** (REPRO-04) — Phase 4 requirement, not Phase 2.
- **PII regex catalog expansion** (D-22) — Phase 2 ships SSN+phone+email regexes; richer catalog (case-number patterns, attorney names) → backlog.
- **Engine-swap drill (Ollama overhead measurement)** — production runtime is Ollama (PRD §4.2), Phase 2 measures via vLLM (ceiling). Quantifying the Ollama derate is a Phase 4 discussion. → backlog.

</deferred>

---

*Phase: 02-cuda-pre-flight*
*Context gathered: 2026-05-06 via skipped-discussion / Claude's Discretion defaults*
