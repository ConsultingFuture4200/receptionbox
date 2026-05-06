# Requirements: receptionBOX Phase 0 — Cloud Benchmark Validation

**Defined:** 2026-05-04
**Core Value:** Produce trustworthy go/no-go evidence on receptionBOX feasibility — derated Strix Halo predictions for latency/WER/turn-detection/UPL/TTS — before any sales commitment is made to the firm.

## v1 Requirements

Requirements for the Phase 0 deliverable set. Each maps to roadmap phases.

### Infrastructure & Repo Foundation

- [x] **INFRA-01**: Repo skeleton exists at `~/RBOX` with `bench/`, `assets/`, `gates/`, `derating/`, `synthesis/`, `orchestration/`, `substrate/`, `config/`, `docs/`, `results/` directories
- [x] **INFRA-02**: `pyproject.toml` declares Python 3.11, uv-managed deps; `requirements.lock` (uv lockfile) is committed and reproducible
- [x] **INFRA-03**: `Makefile` exposes single-command targets: `make assets`, `make smoke`, `make g1`, `make g2`, `make g3`, `make g5`, `make g7`, `make report`, `make canary`
- [x] **INFRA-04**: Config-as-code under `config/` — `models.yaml`, `substrates.yaml`, `gates.yaml`, `budget.yaml` with schema validation on load
- [x] **INFRA-05**: `pre-commit` enforces `ruff format` + `ruff check` + assertion that no real-audio files exist outside `assets/manifest`
- [x] **INFRA-06**: Cost ledger is a SQLite-backed module (`cost/ledger.py`) that gates every cloud provisioning call — provisioning refused if `budget_remaining - projected_cost*1.5 < 0`

### Evaluation Asset Curation

- [x] **ASSETS-01**: 500-call synthetic conversation corpus generated from open-licensed sources (legal-vertical scripted dialogues) with persona, intent, and adversity-level metadata; SHA-pinned in `assets/manifest.sha256.txt`
- [x] **ASSETS-02**: 200-clip G.711 μ-law STT evaluation set with 100 neutral + 100 stressed splits; reference transcripts normalized via Whisper BasicTextNormalizer; SHA-pinned
- [x] **ASSETS-03**: Hesitation-heavy adversarial turn-detection set built from 3 sources (filler-word recordings, stutter samples, mid-sentence pauses); SHA-pinned with per-clip ground-truth turn-end timestamps
- [x] **ASSETS-04**: 200 UPL probe corpus + 50-probe benign-question control set; probes cover ≥30 prompt-injection variants, ≥20 fee-quote, ≥20 statute-of-limitations, ≥20 case-outcome, ≥20 procedural-deadline, plus generic substantive-legal-question categories; ground-truth refusal label per probe; SHA-pinned
- [x] **ASSETS-05**: receptionBOX-shaped reference system prompt drafted and committed as `assets/reference_prompt.md` — used for G5 evaluation in lieu of a generic prompt
- [x] **ASSETS-06**: 30-pair TTS A/B preference test set (Chatterbox-Turbo vs Kokoro-82M) with edge-case prompts (numbers, proper nouns, legal terminology); reference utterances + clone-reference clip
- [x] **ASSETS-07**: G.711 transcoding pipeline (`assets/g711.py`) using ffmpeg 7.x `pcm_mulaw` + soxr precision=28; spectral-mask validated against one Twilio→Twilio real-PSTN reference; documented as floor-not-ceiling on degradation
- [x] **ASSETS-08**: `assets/manifest.csv` contains a provenance line per asset (source URL or generator + license + creation date + SHA256); harness-enforced — gate runners refuse to read assets not listed

### Substrate Abstraction & Harness

- [x] **HARNESS-01**: `substrate/__init__.py` defines `Substrate` ABC with `load_stt`, `load_llm`, `load_tts`, `transcribe`, `generate`, `synthesize`, `env_fingerprint` methods; gate runners may not import torch/onnxruntime directly
- [x] **HARNESS-02**: `substrate/cuda.py` implements the ABC for RunPod H100 (vLLM 0.10+ CUDA wheel, faster-whisper INT8, Chatterbox-Turbo CUDA, Kokoro CUDA, LiveKit Agents 1.x)
- [ ] **HARNESS-03**: `substrate/rocm.py` implements the ABC for TensorWave/Vultr MI300X (vLLM ROCm wheel, faster-whisper INT8 ROCm, devnen Chatterbox-TTS-Server, moritzchow Kokoro-FastAPI-ROCm, LiveKit Agents 1.x)
- [x] **HARNESS-04**: Result schema is pydantic-validated with `schema_version` field; results stored as JSONL + Parquet + SQLite index in `results/`
- [x] **HARNESS-05**: Each gate run emits an `env.json` sidecar (substrate fingerprint, model SHAs, image digests, git commit, asset manifest hash, timestamps)
- [x] **HARNESS-06**: Gate runners under `gates/g{1,2,3,5,7}/runner.py` are substrate-agnostic and standalone-invokable via `make gN`

### Cloud Orchestration & Cost Control

- [x] **CLOUD-01**: RunPod account provisioned with provider-level $75 cap; `runpodctl` CLI configured; ephemeral H100 Secure Cloud spin-up scripted in `orchestration/runpod_h100.py`
- [ ] **CLOUD-02**: TensorWave (primary) and Vultr (backup) accounts provisioned with provider-level $75 caps; `orchestration/tensorwave_mi300x.py` + `orchestration/vultr_mi300x.py` scripted
- [x] **CLOUD-03**: `cost-watch.py` daemon runs locally during cloud sessions, polls provider billing APIs every 5 minutes, hard-stops instances if projected daily spend would breach budget
- [ ] **CLOUD-04**: In-instance watchdog terminates the GPU pod after `max_minutes` (per-gate config); rsync result-pull on shutdown trigger
- [ ] **CLOUD-05**: Persistent model cache (HF revision-pinned) on cloud volume to avoid re-downloads across pods; bandwidth cost included in projection
- [ ] **CLOUD-06**: Pre-teardown cloud-storage audit verifies no real-audio or PII files survived the session (Pitfall 5 mitigation)

### CUDA Pre-flight (Gate Phase 1)

- [ ] **PREFLIGHT-01**: 5-call G1 smoke test on RunPod H100 proves substrate + orchestration + cost ledger work end-to-end (~$1, <30 min)
- [ ] **PREFLIGHT-02**: Once smoke passes, sanity runs of G1, G2, G3, G5 on H100 produce non-degenerate baseline numbers (G7 deferred to MI300X)
- [ ] **PREFLIGHT-03**: H100 results stored with substrate fingerprint = `cuda` so cross-substrate consistency check (within 25% projection) is possible in synthesis

### ROCm Validation Gates (Gate Phase 2)

- [ ] **GATE-G1**: End-to-end latency on TensorWave MI300X over 500-call corpus at concurrencies N=1, N=2, N=4 with **per-stage decomposition** (STT TTFT, LLM TTFT, LLM decode, TTS first-audio); report p50/p90/p99 per stage and aggregate; SM-66/67 targets (p90 < 900ms / p99 < 1200ms) measured cloud-side, derated Strix-side
- [ ] **GATE-G2**: STT WER on G.711 μ-law 200-clip set; faster-whisper INT8 + ONNX-Runtime ROCm parallel measurement; SM-68 targets (< 12% neutral / < 18% stressed); WER scored via jiwer 3.x with pinned Whisper BasicTextNormalizer
- [ ] **GATE-G3**: Turn-detection false-positive rate on hesitation adversarial set; threshold sweep 400–1500ms in 100ms steps; SM-69 target (< 2% FPR at default 800ms)
- [ ] **GATE-G5**: UPL guardrail probes (200) + benign control (50) against the **receptionBOX-shaped reference prompt** (ASSETS-05) with grammar-constrained generation ON; SM-71 target (100% pass on probes; 0% false-refusal on control); per-category pass rate broken out
- [ ] **GATE-G7**: TTS A/B preference render on MI300X — both warm-path and cold-path first-audio latency measured; 30 stimulus pairs synthesized for offline blind listening test (5 listeners, async); SM-72 target (≥ 60% prefer cloned)
- [ ] **GATE-CHATTERBOX-D1**: Day-1 Chatterbox-Turbo ROCm load smoke test on MI300X — pass = primary engine for G1/G7; fail = Kokoro becomes primary measurement and synthesis flags Chatterbox as feasibility risk per DR-27

### Critical Audits (ROCm Phase)

- [ ] **AUDIT-01**: Co-residency stack-load test — Whisper + Qwen3-4B + Chatterbox/Kokoro all loaded simultaneously on MI300X under sustained load (≥ 5 min); memory headroom, kernel mismatch, and crash detection
- [ ] **AUDIT-02**: gfx1151 (Strix Halo) kernel-coverage audit — every critical op used by Whisper, Qwen3-4B, Chatterbox, Kokoro is checked against the planned appliance ROCm minor + PyTorch wheel cut; status table per op (present / fallback / unknown) committed as `audit/gfx1151_op_status.md`
- [ ] **AUDIT-03**: Engine-swap-under-load demo — TTS engine flipped from Chatterbox to Kokoro mid-session via Postgres config row (or local equivalent), measured swap-time, no audible disruption — proves DR-27 pluggable-TTS architecture viability

### Derating & Methodology

- [x] **DERATE-01**: `derating/strix_model.py` implements per-stage roofline derating with arithmetic-intensity classification (STT compute-bound INT8; LLM TTFT bandwidth-bound; LLM decode bandwidth-bound; TTS first-audio compute-bound); unit-tested on synthetic data
- [ ] **DERATE-02**: 80% confidence bands derived via bootstrap (`scipy.stats.bootstrap`) on per-stage measurements + LPDDR5X-vs-HBM3 regime-change uncertainty term
- [ ] **DERATE-03**: Cross-substrate consistency check — H100→MI300X projection within 25%; failures flagged in synthesis as methodology warning
- [ ] **DERATE-04**: Q4_K_M ↔ AWQ-Int4 substitution validity characterized — WER and TTFT measured on both quantizations on H100; substitution-error term added to confidence band
- [ ] **DERATE-05**: Ollama-overhead derate (~1.3–1.5×) applied when projecting from vLLM-cloud measurements to Ollama-appliance reality; documented in synthesis methodology section

### Synthesis & Reporting

- [ ] **REPORT-01**: `synthesis/render_report.py` (pandas + jinja2) produces `docs/phase-0-synthesis-v0.1.md` from the SQLite result store; one `make report` target
- [ ] **REPORT-02**: Synthesis includes per-stage tables: measured cloud (MI300X) | derated Strix Halo prediction (point) | derated Strix Halo prediction (80% band) | PRD target | gate verdict using band upper bound
- [ ] **REPORT-03**: Synthesis includes a standalone "Derating Methodology" section that survives Liotta-style adversarial review (per-op arithmetic intensity, regime-change rationale, cross-substrate consistency)
- [ ] **REPORT-04**: Synthesis includes a "What we did not measure" section listing every caveat (gfx1151 unknowns, real-PSTN delta, real-firm prompt delta, listener pool size, etc.)
- [ ] **REPORT-05**: Synthesis includes an unstrippable **sales-safe excerpt** with explicit "predicted, not measured" language for every appliance number; two-tier presentation (Measured cloud / Predicted appliance) on every result
- [ ] **REPORT-06**: Feasibility memo v0.4 fragment generated as `docs/feasibility-memo-v0.4-fragment.md`, ready to merge into the v0.3 baseline (operator drops v0.3 into `docs/`)
- [ ] **REPORT-07**: **Phase 0 gate decision package** committed as `docs/phase-0-gate-decision.md` — pass / soft-pass-with-caveats / fail recommendation, evidence summary, and SOW-ready feasibility excerpt

### Reproducibility

- [x] **REPRO-01**: `bench/images.lock.yaml` pins every Docker image by digest (RunPod NGC pytorch, ROCm vllm, ROCm pytorch)
- [x] **REPRO-02**: `bench/models.lock.yaml` pins every HF model by `revision=<commit_sha>` (Whisper, Qwen3-4B, Chatterbox, Kokoro)
- [x] **REPRO-03**: Every result row records (image_digest, model_sha, asset_manifest_sha, git_commit, run_id, timestamp_utc)
- [ ] **REPRO-04**: End-of-week canary re-run executes a single G1 5-call run and confirms results within tolerance of the original measurement (Pitfall-11 guard)
- [ ] **REPRO-05**: Reproducibility manifest sealed in `docs/repro-manifest-v1.0.md` at end of synthesis; references all locks, audits, and verifies canary status

### Decision Resolutions (PRD NCs)

- [x] **DECISION-NC-R14**: NC-R14 (sharing Phase 0 with firm) resolved with explicit policy recorded in `docs/decisions/dr-31-sharing-policy.md`; defensive default = methodology + prediction range only, no raw cloud numbers; resolution gates Phase 1 completion
- [ ] **DECISION-NC-R12**: NC-R12 (recording-disclosure preamble authority) noted in synthesis "What we did not measure" — Phase 1 work, not Phase 0
- [x] **DECISION-DOCS**: Operator drops parent thUMBox PRDs (technical + business v2.1), discovery addendum v0.2, hardware-pivot addendum v0.1, feasibility memo v0.3, virtual benchmark plan v0.1 into `docs/` before Phase 1 (Foundation) completion

## v2 Requirements

Deferred to post-Phase-0 work (Phase 1 discovery and beyond).

### Phase 1 Discovery Prep

- **DISC-01**: Outside-counsel ethics opinion package
- **DISC-02**: 90-day call-volume audit template for firm
- **DISC-03**: Existing-PBX integration discovery questionnaire
- **DISC-04**: Kill-criteria scoring rubric (KC-1 through KC-5)
- **DISC-05**: Pricing-model worksheet
- **DISC-06**: Joint-review presentation template

### Strix Halo Hardware Validation

- **STRIX-01**: Local benchmarks on a Framework Desktop dev unit (post-procurement)
- **STRIX-02**: Direct gfx1151 kernel-presence smoke test (≤30 min, post-Phase-0 if Strix unit accessible)
- **STRIX-03**: 30-day production stability soak (Phase 2 deliverable)

## Out of Scope

Explicitly excluded. Documented to prevent scope creep.

| Feature | Reason |
|---------|--------|
| Production receptionBOX runtime (LiveKit SFU service, agent-worker as deployable, full v1 product) | Phase 0 produces benchmark harnesses, not the v1 product runtime — Phase 2 work |
| Real client audio in any corpus | Privilege exposure with no recovery path; Pitfall 5 |
| Local Strix Halo benchmarks | No Framework Desktop dev unit on hand; cloud-only by operator decision |
| G4 concurrency benchmark (full SM-70 100-call concurrent load) | Captured at N=1/2/4 in GATE-G1; full SM-70 is Phase 1 hardware work |
| G6 (deferred per virtual benchmark plan v0.1; identity TBD on doc drop) | Out of Phase 0 scope by design |
| Cloud LLM fallback (Anthropic Claude Haiku) measurement | FR-R49 OFF by default; not on the local-only critical path |
| Outbound calling / TCPA validation | DR-30 — v1 inbound-only |
| Multi-pack co-residency benchmarks | DR-25 — v1 single-pack-per-appliance |
| Additional TTS engines (VoxCPM2, Fish Audio S2 Pro, Voxtral, Qwen3-TTS) | Phase 2 candidate per DR-27; Phase 0 measures Chatterbox + Kokoro only |
| Sales pitch deck / partnership PDF updates | Sales artifacts subordinate to PRD per §0.5; not a Phase 0 deliverable |
| Parent thUMBox platform development | Treated as available substrate; Phase 0 does not modify parent services |

## Traceability

Populated by `gsd-roadmapper` after ROADMAP.md creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| INFRA-01 | Phase 1 | Complete |
| INFRA-02 | Phase 1 | Complete |
| INFRA-03 | Phase 1 | Complete |
| INFRA-04 | Phase 1 | Complete |
| INFRA-05 | Phase 1 | Complete |
| INFRA-06 | Phase 1 | Complete |
| ASSETS-01 | Phase 1 | Complete |
| ASSETS-02 | Phase 1 | Complete |
| ASSETS-03 | Phase 1 | Complete |
| ASSETS-04 | Phase 1 | Complete |
| ASSETS-05 | Phase 1 | Complete |
| ASSETS-06 | Phase 1 | Complete |
| ASSETS-07 | Phase 1 | Complete |
| ASSETS-08 | Phase 1 | Complete |
| HARNESS-01 | Phase 1 | Complete |
| HARNESS-02 | Phase 2 | Complete |
| HARNESS-03 | Phase 3 | Pending |
| HARNESS-04 | Phase 1 | Complete |
| HARNESS-05 | Phase 2 | Complete |
| HARNESS-06 | Phase 2 | Complete |
| CLOUD-01 | Phase 1 | Partial-pending-operator (skeleton + ledger gate shipped; awaits $75 deposit + API key) |
| CLOUD-02 | Phase 1 | Partial-pending-operator (skeletons + adapters shipped; awaits TensorWave + Vultr $75 deposits) |
| CLOUD-03 | Phase 1 | Partial-pending-operator (cost-watch daemon + 3 adapters shipped; awaits ledger bootstrap with funded caps) |
| CLOUD-04 | Phase 2 | Pending |
| CLOUD-05 | Phase 2 | Pending |
| CLOUD-06 | Phase 2 | Pending |
| PREFLIGHT-01 | Phase 2 | Pending |
| PREFLIGHT-02 | Phase 2 | Pending |
| PREFLIGHT-03 | Phase 2 | Pending |
| GATE-G1 | Phase 3 | Pending |
| GATE-G2 | Phase 3 | Pending |
| GATE-G3 | Phase 3 | Pending |
| GATE-G5 | Phase 3 | Pending |
| GATE-G7 | Phase 3 | Pending |
| GATE-CHATTERBOX-D1 | Phase 3 | Pending |
| AUDIT-01 | Phase 3 | Pending |
| AUDIT-02 | Phase 3 | Pending |
| AUDIT-03 | Phase 3 | Pending |
| DERATE-01 | Phase 1 | Complete |
| DERATE-02 | Phase 4 | Pending |
| DERATE-03 | Phase 4 | Pending |
| DERATE-04 | Phase 4 | Pending |
| DERATE-05 | Phase 4 | Pending |
| REPORT-01 | Phase 4 | Pending |
| REPORT-02 | Phase 4 | Pending |
| REPORT-03 | Phase 4 | Pending |
| REPORT-04 | Phase 4 | Pending |
| REPORT-05 | Phase 4 | Pending |
| REPORT-06 | Phase 4 | Pending |
| REPORT-07 | Phase 4 | Pending |
| REPRO-01 | Phase 1 | Complete |
| REPRO-02 | Phase 1 | Complete |
| REPRO-03 | Phase 2 | Complete |
| REPRO-04 | Phase 4 | Pending |
| REPRO-05 | Phase 4 | Pending |
| DECISION-NC-R14 | Phase 1 | Partial-pending-operator (DR-31 v0.1.0 drafted; awaits operator review/approval) |
| DECISION-NC-R12 | Phase 4 | Pending |
| DECISION-DOCS | Phase 1 | Partial-pending-operator (checklist + presence test shipped; awaits operator drop of 6 companion docs) |

**Coverage:**
- v1 requirements: 58 total
- Mapped to phases: 58
- Unmapped: 0 (full coverage)

**Per-phase distribution:**
- Phase 1 (Foundation): 24 requirements
- Phase 2 (CUDA Pre-flight): 10 requirements
- Phase 3 (ROCm Validation): 10 requirements
- Phase 4 (Synthesis & Gate Decision): 14 requirements

---
*Requirements defined: 2026-05-04*
*Last updated: 2026-05-04 after roadmap creation (traceability populated)*
