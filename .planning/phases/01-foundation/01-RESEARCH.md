# Phase 1: Foundation - Research

**Researched:** 2026-05-04
**Domain:** Repo skeleton + asset corpus build + cost rails + reproducibility lockfiles + Substrate ABC + result schema + derating skeleton + decision documents (zero GPU spend)
**Confidence:** HIGH on tooling (uv/ruff/pytest/pydantic/pre-commit), HIGH on Substrate ABC shape (LiveKit-aligned, locked in CONTEXT.md), HIGH on asset provenance discipline. MEDIUM on provider billing API behavior (Vultr documented; RunPod and TensorWave have known gaps documented below).

## Summary

Phase 1 is structural plumbing under hard locks. CONTEXT.md (D-01..D-13) has already locked every load-bearing design decision — the **Substrate ABC method shape is async-streaming and matches LiveKit Agents 1.x natively**, the **GateResult schema is pydantic v2 with `schema_version: Literal["1.0"]`**, the **cost ledger uses `budget_remaining - projected_cost*1.5 < 0`** with provider-level $75 caps + a `cost-watch.py` 5-min poller as second rail, the **5 corpora are LLM-authored + Kokoro-rendered locally on the GTX 1070**, and the **reference prompt is generic-firm permissive-default**. Research scope is therefore "how to wire these," not "which to choose."

The non-obvious risks for the planner: (1) **jiwer 4.x is current, not 3.x as STACK.md says, and `BasicTextNormalizer` lives in the separate `whisper-normalizer` package**, not in `jiwer` — this is a dependency surprise that affects `pyproject.toml`; (2) **RunPod has no documented programmatic spending-cap endpoint** — the "$75 provider-level cap" is achieved by *funding only $75 in credits* (RunPod is prepaid), not by calling an API; (3) **Vultr is the only one of the three providers with a clean billing-API pending-charges endpoint** (`GET /v2/billing/pending-charges/csv`); RunPod and TensorWave require scraping balance/usage from less-documented surfaces. The cost-watch daemon must therefore be provider-shaped, not symmetric.

**Primary recommendation:** Build the foundation in four serial waves — (W0) repo skeleton + uv + ruff + pre-commit + Makefile shell + config schemas (no business logic, all type-checks), (W1) Substrate ABC + GateResult + result store + derating skeleton + cost ledger module, all unit-tested on synthetic data, (W2) asset corpus generation pipeline + Kokoro-local rendering + manifest enforcement, (W3) decision docs (DR-31 draft + companion-doc drop checklist) + provider account provisioning + cost-watch daemon. W0 unblocks W1/W2/W3; W1 and W2 can run partially in parallel; W3 is mostly operator manual work plus one daemon script.

## User Constraints (from CONTEXT.md)

### Locked Decisions

**Asset corpus generation (D-01 to D-06):**
- D-01 (500-call corpus): Claude-author dialogue scripts against `intent × adversity-level × persona` matrix; render audio with **Kokoro-82M on local GTX 1070** (Pascal sm_61, FP32, ~30-60 min wall clock). Zero cloud GPU spend. Persona/intent/adversity metadata in `assets/manifest.csv`. Provenance line cites generator script + RNG seed + Kokoro revision SHA.
- D-02 (200 G.711 STT eval set): Stratified subset of 500-call corpus — 100 neutral + 100 stressed split by adversity-level metadata. Transcoded via `assets/g711.py` using `ffmpeg aresample=resampler=soxr:precision=28 -c:a pcm_mulaw`. Spectral mask validated against **one Twilio→Twilio reference clip** before corpus locks. Reference transcripts come directly from LLM-authored scripts (ground truth, no STT in loop), normalized via Whisper `BasicTextNormalizer`.
- D-03 (Hesitation adversarial set, G3): **TTS-generated only** (Kokoro), with controlled hesitation patterns. Per-clip ground-truth turn-end timestamps recorded at generation time. Synthesis report frames G3 as **"soft pass with caveats"** per DR-28. Three-source mix deferred.
- D-04 (UPL probes 200 + benign control 50): **Claude-author against full category matrix** (≥30 prompt-injection variants, ≥20 fee-quote, ≥20 statute-of-limitations, ≥20 case-outcome, ≥20 procedural-deadline, balance generic substantive-legal). **Operator reviews every probe** for content-free-ness before commit. Ground-truth refusal label per probe. Benign control 50 covers caller-volume-realistic non-substantive questions.
- D-05 (30 TTS A/B pairs, G7): Hand-authored **text scripts only in Phase 1** — legal terminology, numbers, proper nouns, edge-case prosody. Clone-reference clip = synthetic operator-style sample. Actual A/B render happens on MI300X in Phase 3.
- D-06 (Provenance enforcement, ASSETS-08): `assets/manifest.csv` contains a provenance line per asset. Pre-commit hook (INFRA-05) refuses any audio file under `assets/` not listed in `manifest.csv`. Gate runners refuse to read assets not listed.

**Reference prompt (D-07, D-08):**
- D-07: **Generic-firm, permissive-default**. Placeholder firm name (`{firm_name}`), three placeholder practice areas (`{practice_area}` rendered with family law / personal injury / estate planning). Five explicit refusal categories: fees & rates, statutes of limitations, case outcomes, procedural deadlines, substantive legal information. Two scripted refusal phrasings. Committed as `assets/reference_prompt.md`.
- D-08: Mandatory caveat in synthesis report (Phase 4) — "G5 results evaluated against generic-firm reference prompt; firm-customized production prompt requires re-run during Phase 1 discovery before any go-live." Unstrippable per Pitfall 7 / REPORT-04.

**Harness shape (D-09 to D-12):**
- D-09 (Substrate ABC interface): **Async + streaming**. All three core methods are `async def` returning `AsyncIterator[Chunk]`:
  - `transcribe(audio: AsyncIterator[bytes], *, sample_rate: int) -> AsyncIterator[STTChunk]`
  - `generate(prompt: str, *, grammar: Grammar | None = None, max_tokens: int) -> AsyncIterator[LLMChunk]` — `grammar` carries xgrammar constraint for G5
  - `synthesize(text: str, *, voice: VoiceRef | None = None) -> AsyncIterator[bytes]` — PCM chunks
  - Plus `env_fingerprint() -> EnvFingerprint` (sync) and `async def load_{stt,llm,tts}() -> None`
  - Matches LiveKit Agents 1.x natively — no Phase 3 rework.
  - Gate runners may NOT import torch / onnxruntime / vllm directly (HARNESS-01 enforced).
- D-10 (Result schema, GateResult): Pydantic model with `schema_version: Literal["1.0"]`. Required fields: `run_id`, `gate` (g1/g2/g3/g5/g7/smoke/canary), `asset_id`, `asset_manifest_sha`, `substrate` (cuda/rocm), `image_digest`, `model_shas: dict[str,str]`, `git_commit`, `timestamp_utc`, `concurrency`, `status` (ok/error/timeout), `error_kind`, `error_msg`. Per-stage timing fields nullable: `stt_ttft_ms`, `llm_ttft_ms`, `llm_decode_ms_per_tok`, `tts_first_audio_ms`, `e2e_ms`. Gate-specific payload in `metrics: dict`; raw vendor metadata in `extras: dict`.
- D-11 (Result storage): **JSONL primary, SQLite index, Parquet on demand**. Each gate write appends a JSON line to `results/{gate}/{run_id}.jsonl`. SQLite index at `results/index.sqlite` rebuilt by `make report` from JSONL (idempotent). Parquet generated lazily. **Error rows keep schema** with `status='error'`, populated `error_kind`/`error_msg`, NULL measurements — failures visible, not silently filtered.
- D-12 (env.json sidecar): Each gate run emits `results/{gate}/{run_id}.env.json` with substrate fingerprint, model SHAs, image digest, git commit, asset manifest hash, ROCm/CUDA version, vLLM version, timestamps. Schema validated by pydantic on read.

**DECISION-DOCS (D-13):** Operator has all 5 companion docs locally and will copy them into `docs/` during Phase 1. Planner includes drop as explicit Phase 1 task **early in the wave** so blocker surfaces fast. Required: parent thUMBox technical PRD v2.1, parent thUMBox business PRD v2.1, discovery addendum v0.2, hardware-pivot addendum v0.1, feasibility memo v0.3, virtual benchmark plan v0.1.

### Claude's Discretion

- **DR-31 sharing policy (DECISION-NC-R14):** User declined to discuss; defensive default from PROJECT.md applies. Claude drafts `docs/decisions/dr-31-sharing-policy.md` based on PRD §13 NC-R14 + Pitfall 10. Stance: methodology + prediction range only pre-SOW; no raw cloud numbers; PRD-update review gates any sales-artifact reference to Phase 0 numbers; two-tier (Measured cloud / Predicted appliance) presentation mandatory when numbers travel.
- **Cost ledger projection mechanism (INFRA-06, CLOUD-03):** Static per-gate config in `config/budget.yaml` with `projected_cost_per_run_usd` and `expected_runs` per gate, multiplied by 1.5 safety factor. Dynamic refinement from prior-run data deferred to Phase 4.
- **Pre-commit no-real-audio assertion (INFRA-05):** Pre-commit hook walks `assets/` for any file matching `*.wav|*.mp3|*.flac|*.opus|*.ogg` and fails commit if path absent from `assets/manifest.csv`.
- **Foundation execution order:** Planner decides wave structure. Suggested: (1) repo skeleton + uv lockfile + Makefile + config schemas + pre-commit (no GPU dependency); (2) Substrate ABC + GateResult schema + derating/strix_model.py skeleton + cost ledger module; (3) asset generation; (4) decision docs.

### Deferred Ideas (OUT OF SCOPE)

- Two-prompt comparison run for G5 (Phase 3 backlog).
- Three-source hesitation set (Phase 1 discovery backlog).
- Public prompt-injection corpus integration (Garak, PromptBench) (Phase 1 discovery backlog; license review needed).
- Cloud TTS API rendering path (ElevenLabs / OpenAI TTS) (backlog; out-of-budget).
- Dynamic cost-projection refinement from prior-run actuals (Phase 4 candidate).

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| INFRA-01 | Repo skeleton at `~/RBOX` with bench/, assets/, gates/, derating/, synthesis/, orchestration/, substrate/, config/, docs/, results/ | §Repo Skeleton below — directory tree with purpose per dir |
| INFRA-02 | `pyproject.toml` declares Python 3.11, uv-managed; `requirements.lock` (or `uv.lock`) committed | §uv lockfile pattern; PEP 735 dependency-groups for dev/test split |
| INFRA-03 | `Makefile` exposes `make assets`, `make smoke`, `make g1..g7`, `make report`, `make canary` | §Makefile targets table |
| INFRA-04 | Config-as-code under `config/` — `models.yaml`, `substrates.yaml`, `gates.yaml`, `budget.yaml` with schema validation on load | §Config schemas (pydantic-settings + YAML) |
| INFRA-05 | `pre-commit` enforces `ruff format` + `ruff check` + no-real-audio assertion | §Pre-commit hooks (ruff-pre-commit + custom local hook) |
| INFRA-06 | Cost ledger SQLite-backed module gating cloud provisioning; `budget_remaining - projected_cost*1.5 < 0` refusal rule | §Cost ledger module — schema, API, dry-run unit test |
| ASSETS-01 | 500-call synthetic conversation corpus, persona/intent/adversity metadata, SHA-pinned | §Asset generation pipeline — Kokoro-local rendering, manifest format |
| ASSETS-02 | 200-clip G.711 μ-law set, 100 neutral + 100 stressed, normalized references, SHA-pinned | §G.711 transcoding (`ffmpeg aresample=resampler=soxr:precision=28 -c:a pcm_mulaw`) |
| ASSETS-03 | Hesitation adversarial set with per-clip ground-truth turn-end timestamps | §TTS-generated hesitation pipeline; "soft pass with caveats" framing |
| ASSETS-04 | 200 UPL probes + 50 benign control with category coverage and refusal labels | §UPL probe authoring template — JSON schema with category, prompt, expected_label |
| ASSETS-05 | `assets/reference_prompt.md` committed | §Reference prompt content (locked verbatim in CONTEXT.md specifics) |
| ASSETS-06 | 30-pair TTS A/B preference set with edge-case prompts; clone-reference clip | §TTS A/B text-script template (Phase 1 ships text only) |
| ASSETS-07 | `assets/g711.py` ffmpeg pipeline + spectral validation | §G.711 transcoder module + scipy/librosa spectral check |
| ASSETS-08 | `assets/manifest.csv` with provenance per asset; harness-enforced | §Manifest CSV schema + enforcement in pre-commit + `assets.load()` |
| HARNESS-01 | `substrate/__init__.py` defines `Substrate` ABC; gate runners may not import torch/onnxruntime directly | §Substrate ABC pattern — abc.ABC, async streaming methods, lint-rule enforcement |
| HARNESS-04 | Result schema pydantic-validated with `schema_version`; results stored as JSONL+SQLite+Parquet | §GateResult schema (pydantic v2 Literal discriminator pattern) + storage |
| CLOUD-01 | RunPod account provisioned with $75 cap, runpodctl configured, `orchestration/runpod_h100.py` scripted | §RunPod cap mechanism — prepaid credits as cap; SDK skeleton |
| CLOUD-02 | TensorWave (primary) + Vultr (backup) accounts with $75 caps; orchestration scripts | §TensorWave/Vultr provisioning — credit-based cap; provider-shaped APIs |
| CLOUD-03 | `cost-watch.py` daemon polls billing APIs every 5 min; hard-stops on projected breach | §cost-watch daemon — Vultr `/v2/billing/pending-charges/csv` is documented; RunPod uses `runpod-python` SDK + balance scraping; TensorWave gap |
| DERATE-01 | `derating/strix_model.py` per-stage roofline derating skeleton; unit-tested on synthetic data | §Derating skeleton — function signatures per stage class (compute-bound vs bandwidth-bound) |
| REPRO-01 | `bench/images.lock.yaml` pins every Docker image by digest | §Image lockfile schema (provider, image, digest, ROCm/CUDA version) |
| REPRO-02 | `bench/models.lock.yaml` pins every HF model by `revision=<commit_sha>` | §Model lockfile schema + `hf_hub_download(revision=...)` verify pattern |
| DECISION-NC-R14 | NC-R14 sharing policy resolved in `docs/decisions/dr-31-sharing-policy.md` | §DR-31 draft outline (Claude's-discretion drafting) |
| DECISION-DOCS | Operator drops 5 parent/companion docs into `docs/` before Phase 1 close | §Companion-doc drop checklist task |

## Project Constraints (from CLAUDE.md)

CLAUDE.md is the technology-stack lockdown for the entire project. Phase 1 must NOT deviate; research explores HOW to wire pinned tools, not WHETHER to use them.

| Directive | Authority Level | Phase 1 Implication |
|-----------|----------------|---------------------|
| Use `uv` not `pip` for the harness env | §11 What NOT to Use | `pyproject.toml` + `uv.lock` (or `requirements.lock` per INFRA-02 wording); `uv pip install` in Makefile recipes |
| `pyproject.toml`, not `setup.py`; Python 3.11 | Operator global + INFRA-02 | `pyproject.toml` with `requires-python = ">=3.11,<3.12"` |
| `ruff format` + `ruff check` (no black, no isort, no flake8) | Operator global + INFRA-05 | Single `[tool.ruff]` block in `pyproject.toml`; pre-commit uses `astral-sh/ruff-pre-commit` |
| `pytest` for tests (no unittest as primary) | Operator global | `tests/` dir; `pytest` in dev dependency-group |
| HF revision SHA pinning + Docker image digest pinning | §9 Reproducibility Stack + REPRO-01/02 | `models.lock.yaml` records `revision: <40-char SHA>`; `images.lock.yaml` records `digest: sha256:...` |
| No emoji in code or docs | Operator global | Applies to all Phase 1 files including reference prompt, decision docs |
| File versioning for deliverable docs (`*.v0.X.Y.md`) | Operator global | `dr-31-sharing-policy.v0.1.0.md` (file-version aware) |
| Commit Engine style (atomic, type(scope): summary + bullets) | Operator global | Each task = one commit minimum; phase 1 produces ~20-30 atomic commits |
| Synthetic / open-licensed audio only — no PII | PROJECT constraint + Pitfall 11 | Pre-commit hook enforces; manifest enforcement covers data-residency posture |
| `outlines` library forbidden (use xgrammar via vLLM) | §11 What NOT to Use | Substrate ABC's `Grammar` type wraps xgrammar JSON schema, NOT outlines |
| `whisper.cpp` forbidden on cloud GPUs (use faster-whisper INT8) | §11 What NOT to Use | Substrate impl in Phase 2/3 must use faster-whisper; ABC must accept its return shape |
| `pyannote-audio` forbidden for streaming VAD (use silero-vad v5) | §11 What NOT to Use | LiveKit silero plugin path locked |
| Real customer audio forbidden anywhere | §11 + PROJECT + Pitfall 11 | Pre-commit hook + manifest enforcement |

## Standard Stack

### Core (verified versions, May 2026)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Python | 3.11.x | Interpreter | Operator preference; LiveKit Agents 1.x supports 3.10+; faster-whisper, vLLM compatible |
| uv | ≥0.4.x (latest, e.g., 0.5.x) | Dependency resolver + env manager | [VERIFIED: docs.astral.sh/uv] Operator-pinned; replaces pip/poetry/pip-tools |
| pydantic | v2.x (e.g., 2.11+) | GateResult schema, config validation | [VERIFIED: docs.pydantic.dev] Discriminated unions via `Literal` + `schema_version`; v2 is the standard |
| ruff | ≥0.7.x (matches latest pre-commit hook tag, e.g., `v0.15.x`) | Linter + formatter | [VERIFIED: github.com/astral-sh/ruff-pre-commit] Replaces black/isort/flake8 |
| pytest | ≥8.x | Test runner | [ASSUMED: training] Industry standard; matches operator preference |
| pytest-asyncio | ≥0.24 | Async test support for Substrate ABC stub tests | [ASSUMED: training] Required because ABC methods are async |
| pre-commit | ≥4.x | Hook orchestration | [VERIFIED: ruff-pre-commit docs] Standard for Python projects 2026 |
| jinja2 | ≥3.1 | Synthesis report templating (Phase 4 use; install in Phase 1) | [CITED: STACK.md §10] |
| pyyaml or ruamel.yaml | latest | Config loaders | [ASSUMED: training] `pyyaml` simpler; `ruamel.yaml` if round-trip needed |
| pandas | ≥2.x | Result aggregation (Phase 4) | [CITED: STACK.md §10] |
| matplotlib | ≥3.x | Plots (Phase 4) | [CITED: STACK.md §10] |
| scipy | ≥1.13 | `scipy.stats.bootstrap` for CIs (Phase 4) | [CITED: STACK.md §10] |
| pyloudnorm | latest | Audio loudness normalization (G7, Phase 3) | [CITED: STACK.md §10] |

**Asset-rendering venv (separate, GTX 1070 sm_61):**

| Library | Version | Purpose |
|---------|---------|---------|
| torch | ≤2.5.x with CUDA 12.x wheel | sm_61 still supported through 2.5; sm_61 deprecation warning expected starting in 2.6+ wheels [CITED: CONTEXT.md specifics] |
| Kokoro-FastAPI or `kokoro` PyPI | latest | Local TTS rendering for ASSETS-01 corpus |
| ffmpeg (system binary, 7.x) | 7.x | G.711 transcoding |
| numpy, soundfile, librosa or scipy.signal | latest | Audio I/O + spectral validation |

> **Pitfall — keep asset-rendering venv separate from harness venv.** The harness venv has no GPU dependencies in Phase 1; it pure-imports pydantic/pytest/ruff. The asset-rendering venv pulls torch + audio libs and is local-GPU-bound. Mixing them couples sm_61 wheel availability into harness reproducibility unnecessarily.

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| **whisper-normalizer** | latest | `BasicTextNormalizer` for G2 reference normalization | [VERIFIED: pypi.org/project/whisper-normalizer] **NOT bundled with jiwer**; install separately. Used by `assets/render_corpus.py` to normalize ground-truth transcripts at corpus-build time |
| jiwer | **4.x** (NOT 3.x as STACK.md says) | WER computation | [VERIFIED: pypi.org/project/jiwer] STACK.md says "3.x"; current is 4.0+. Phase 1 only installs (Phase 3 uses); pin to `^4.0` in pyproject.toml |
| huggingface-hub | ≥0.25 | `hf_hub_download(revision=<sha>)` for model fetch with revision pinning + ETag-based SHA verification | [VERIFIED: docs] |
| pydantic-settings | ≥2.x | YAML config → pydantic model loader | [ASSUMED: training] Cleaner than pyyaml + manual validation |
| sqlite3 (stdlib) | — | Cost ledger + result index | Standard library; no dependency |
| typer or argparse (stdlib) | — | CLI for `cost-watch.py`, `assets/render_corpus.py`, etc. | argparse for stdlib-only; typer if richer help is wanted. **Recommend argparse** to keep dependency surface small |
| runpod (Python SDK) | latest | RunPod orchestration in Phase 2; install skeleton in Phase 1 | [VERIFIED: pypi.org/project/runpod] |
| requests or httpx | latest | Vultr / TensorWave billing API calls in `cost-watch.py` | [ASSUMED: training] httpx for async; requests for sync. Recommend **httpx** for symmetry with LiveKit Agents async style |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| pydantic v2 + Literal discriminator | dataclasses + manual `schema_version` check | Pydantic gives free JSON serialization, validation, JSON Schema export — strictly better for result rows that round-trip through JSONL |
| JSONL + SQLite index | Parquet primary | JSONL is append-only, crash-safe, line-oriented (one error row doesn't corrupt file); SQLite index gives query speed without losing JSONL property. Parquet is columnar, faster for analytics, but rewriting on append is expensive. **D-11 locks JSONL primary; revisit only if Phase 4 analytics force it** |
| ruff | black + isort + flake8 | Three tools vs one; CLAUDE.md locks ruff |
| `requirements.lock` (uv pip compile output) | `uv.lock` (uv project mode) | INFRA-02 says "requirements.lock" but uv project mode produces `uv.lock`. **Recommend `uv.lock` (project mode)** because it integrates with `uv sync`, `uv run`, dependency-groups (PEP 735), and is what uv documentation considers canonical. The INFRA-02 wording appears to predate uv project mode; flag as a planner clarification but use `uv.lock` |

**Installation skeleton:**
```bash
# Harness env (root pyproject.toml)
uv init --python 3.11
uv add pydantic ruff pytest pytest-asyncio pre-commit pyyaml pydantic-settings huggingface-hub httpx jinja2 pandas matplotlib scipy pyloudnorm jiwer whisper-normalizer
uv add --dev mypy types-pyyaml

# Asset-rendering venv (separate, under assets/render_env/)
cd assets/render_env
uv init --python 3.11
uv add "torch<=2.5" kokoro soundfile librosa
```

**Version verification commands** (run in Wave 0):
```bash
uv --version
ruff --version
python -c "import pydantic; print(pydantic.VERSION)"
ffmpeg -version | head -1
python -c "import jiwer; print(jiwer.__version__)"
python -c "from whisper_normalizer.basic import BasicTextNormalizer; print('ok')"
```

## Architecture Patterns

### Recommended Project Structure

```
~/RBOX/
├── pyproject.toml            # Harness deps (no torch); uv project root
├── uv.lock                   # Generated; committed; reproducible
├── .pre-commit-config.yaml   # ruff-check + ruff-format + custom no-real-audio
├── Makefile                  # Single-command targets (assets, smoke, g1-g7, report, canary)
├── README.md
├── CLAUDE.md                 # (already exists) Tech stack lockdown
├── .planning/                # (already exists) GSD planning artifacts
│
├── assets/
│   ├── manifest.csv          # ASSETS-08 single source of truth (provenance per asset)
│   ├── manifest.sha256.txt   # SHA-256 of every asset file
│   ├── reference_prompt.md   # ASSETS-05 (D-07 locked content)
│   ├── render_corpus.py      # Local Kokoro renderer for ASSETS-01
│   ├── g711.py               # ASSETS-07 ffmpeg pipeline + spectral validation
│   ├── render_env/           # Separate uv venv with torch+kokoro
│   ├── scripts/              # LLM-authored dialogue scripts (json/yaml)
│   ├── corpus_500/           # Rendered 500-call WAVs (gitignored except by manifest)
│   ├── corpus_g711/          # 200 G.711 μ-law clips
│   ├── corpus_hesitation/    # Hesitation adversarial set
│   ├── corpus_upl/           # 200 UPL probes (JSON, no audio)
│   ├── corpus_benign/        # 50 benign control probes (JSON)
│   └── corpus_tts_pairs/     # 30 A/B text scripts (Phase 1 = text only)
│
├── substrate/
│   ├── __init__.py           # HARNESS-01 — Substrate ABC + protocol
│   ├── types.py              # STTChunk, LLMChunk, EnvFingerprint, VoiceRef, Grammar dataclasses/pydantic
│   └── _stub.py              # In-memory deterministic stub Substrate for unit tests
│
├── harness/
│   ├── results.py            # GateResult pydantic model (D-10) + JSONL writer (D-11)
│   ├── store.py              # SQLite index rebuild from JSONL
│   └── env_fingerprint.py    # EnvFingerprint capture utilities
│
├── gates/
│   └── __init__.py           # Phase 1 placeholder; runners land in Phase 2
│
├── derating/
│   ├── __init__.py
│   ├── strix_model.py        # DERATE-01 skeleton (per-stage roofline)
│   ├── op_classes.py         # ComputeBoundOp, BandwidthBoundOp, UnknownOp dataclasses
│   └── tests/                # Unit tests on synthetic per-stage measurements
│
├── synthesis/
│   └── __init__.py           # Phase 4 placeholder
│
├── orchestration/
│   ├── __init__.py
│   ├── runpod_h100.py        # CLOUD-01 skeleton
│   ├── tensorwave_mi300x.py  # CLOUD-02 primary
│   └── vultr_mi300x.py       # CLOUD-02 backup
│
├── cost/
│   ├── __init__.py
│   ├── ledger.py             # INFRA-06 SQLite-backed ledger; spend authorization API
│   ├── watch.py              # CLOUD-03 cost-watch daemon (5-min poller)
│   └── adapters/
│       ├── runpod.py         # Provider-specific balance/usage probe
│       ├── tensorwave.py     # Provider-specific balance/usage probe
│       └── vultr.py          # Provider-specific (uses /v2/billing/pending-charges)
│
├── config/
│   ├── models.yaml           # HF model identifiers; consumed alongside bench/models.lock.yaml
│   ├── substrates.yaml       # cuda/rocm config (image refs, env vars, etc.)
│   ├── gates.yaml            # Per-gate config (asset corpus IDs, concurrency, max_minutes)
│   └── budget.yaml           # Per-gate projected_cost_per_run_usd + expected_runs (INFRA-06)
│
├── bench/
│   ├── images.lock.yaml      # REPRO-01 — Docker image digests
│   └── models.lock.yaml      # REPRO-02 — HF model commit SHAs
│
├── docs/
│   ├── decisions/
│   │   └── dr-31-sharing-policy.v0.1.0.md   # DECISION-NC-R14 (Claude drafts)
│   ├── thumbox-technical-prd-v2_1-2026-04-16.md      # operator-dropped
│   ├── thumbox-business-prd-v2_1-2026-04-16.md       # operator-dropped
│   ├── addendum-receptionbox-discovery-v0_2-2026-04-22.md  # operator-dropped
│   ├── addendum-hardware-pivot-strix-halo-v0_1-2026-04-23.md  # operator-dropped
│   ├── receptionbox-technical-feasibility-memo-v0_3-2026-04-23.md  # operator-dropped
│   └── receptionbox-virtual-benchmark-plan-v0_1-2026-05-03.md  # operator-dropped
│
├── audit/
│   └── .gitkeep              # gfx1151_op_status.md lands here in Phase 3
│
├── results/                  # Gate runs (Phase 2+); .gitkeep in Phase 1
│   ├── .gitignore            # Ignore *.jsonl, *.parquet but keep .gitkeep + index.sqlite
│   └── .gitkeep
│
└── tests/
    ├── test_harness_results.py
    ├── test_substrate_abc.py
    ├── test_cost_ledger.py
    ├── test_derating_strix.py
    ├── test_assets_manifest.py
    └── test_g711_pipeline.py    # Spectral mask regression
```

### Pattern 1: Substrate ABC (HARNESS-01)

**What:** A pure-Python abstract base class that defines the gate-runner contract. Concrete implementations (`substrate/cuda.py`, `substrate/rocm.py`) ship in Phase 2/3. In Phase 1 only the ABC + a deterministic in-memory stub for tests exists.

**When to use:** Anywhere a gate runner needs STT/LLM/TTS — gate runners depend on `Substrate`, never on `torch` / `vllm` / `onnxruntime`.

**Example (locked from D-09):**
```python
# Source: D-09 in CONTEXT.md + LiveKit Agents 1.x async-iterator pattern
# substrate/__init__.py
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from .types import STTChunk, LLMChunk, EnvFingerprint, VoiceRef, Grammar


class Substrate(ABC):
    """Cloud-GPU substrate for receptionBOX Phase 0 benchmarking.

    All three core methods are async streaming. Matches LiveKit Agents 1.x
    natively — when Phase 3 wires LiveKit AgentSession, no rework needed.
    """

    @abstractmethod
    async def load_stt(self) -> None: ...

    @abstractmethod
    async def load_llm(self) -> None: ...

    @abstractmethod
    async def load_tts(self) -> None: ...

    @abstractmethod
    async def transcribe(
        self,
        audio: AsyncIterator[bytes],
        *,
        sample_rate: int,
    ) -> AsyncIterator[STTChunk]:
        """Stream partial hypotheses from streaming audio bytes."""
        ...

    @abstractmethod
    async def generate(
        self,
        prompt: str,
        *,
        grammar: Grammar | None = None,
        max_tokens: int,
    ) -> AsyncIterator[LLMChunk]:
        """Stream LLM tokens. `grammar` carries xgrammar constraint for G5."""
        ...

    @abstractmethod
    async def synthesize(
        self,
        text: str,
        *,
        voice: VoiceRef | None = None,
    ) -> AsyncIterator[bytes]:
        """Stream PCM audio chunks."""
        ...

    @abstractmethod
    def env_fingerprint(self) -> EnvFingerprint:
        """Return image digest, model SHAs, ROCm/CUDA version, GPU SKU.

        Sync because env capture is point-in-time and shouldn't suspend.
        """
        ...
```

**HARNESS-01 enforcement (lint rule):** Add a `tach` or custom ruff rule (or simpler: a pytest assertion that walks `gates/` AST) verifying no module under `gates/` imports `torch`, `onnxruntime`, `vllm`, `transformers` directly. Phase 1 ships the test even though `gates/` is empty — Phase 2/3 contributors get the failure immediately if they regress.

```python
# tests/test_harness_isolation.py
import ast
import pathlib

FORBIDDEN_IN_GATES = {"torch", "onnxruntime", "vllm", "transformers", "ctranslate2", "faster_whisper"}

def test_gate_runners_do_not_import_substrate_internals():
    for py_file in pathlib.Path("gates").rglob("*.py"):
        tree = ast.parse(py_file.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    root = alias.name.split(".")[0]
                    assert root not in FORBIDDEN_IN_GATES, f"{py_file} imports {alias.name}"
            elif isinstance(node, ast.ImportFrom):
                root = (node.module or "").split(".")[0]
                assert root not in FORBIDDEN_IN_GATES, f"{py_file} imports from {node.module}"
```

### Pattern 2: GateResult Pydantic Schema (HARNESS-04, D-10)

**What:** Versioned result row that is the single shape every gate writes. JSONL append-only; SQLite index built from JSONL; Parquet on demand.

**Pattern (pydantic v2 with `Literal` discriminator for future schema versions):**
```python
# Source: D-10 in CONTEXT.md + pydantic v2 discriminated-union pattern
# harness/results.py
from datetime import datetime
from typing import Literal
from pydantic import BaseModel, Field

GateName = Literal["g1", "g2", "g3", "g5", "g7", "smoke", "canary"]
Status = Literal["ok", "error", "timeout"]
Substrate = Literal["cuda", "rocm"]


class GateResult(BaseModel):
    """Single row in results/{gate}/{run_id}.jsonl.

    Versioned via schema_version Literal to allow future evolution
    via pydantic discriminated union. Today only "1.0" exists.
    """
    schema_version: Literal["1.0"] = "1.0"

    # Identity
    run_id: str
    gate: GateName
    asset_id: str
    asset_manifest_sha: str

    # Substrate fingerprint
    substrate: Substrate
    image_digest: str
    model_shas: dict[str, str]            # e.g., {"whisper": "abc...", "qwen3": "def..."}
    git_commit: str
    timestamp_utc: datetime

    # Run config
    concurrency: int

    # Outcome (Liotta-survivable: error rows keep schema)
    status: Status
    error_kind: str | None = None
    error_msg: str | None = None

    # Per-stage timings (nullable — single schema serves all gates and error rows)
    stt_ttft_ms: float | None = None
    llm_ttft_ms: float | None = None
    llm_decode_ms_per_tok: float | None = None
    tts_first_audio_ms: float | None = None
    e2e_ms: float | None = None

    # Gate-specific payload
    metrics: dict = Field(default_factory=dict)
    extras: dict = Field(default_factory=dict)
```

**JSONL writer (append-only, crash-safe):**
```python
# harness/results.py (continued)
import json
import pathlib

def append_result(result: GateResult, results_dir: pathlib.Path = pathlib.Path("results")) -> None:
    out = results_dir / result.gate / f"{result.run_id}.jsonl"
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("a") as f:
        f.write(result.model_dump_json() + "\n")
```

**SQLite index rebuild (from JSONL — idempotent, run by `make report`):**
```python
# harness/store.py
import json
import sqlite3
import pathlib

INDEX_SCHEMA = """
CREATE TABLE IF NOT EXISTS results (
    run_id TEXT,
    gate TEXT,
    asset_id TEXT,
    substrate TEXT,
    image_digest TEXT,
    git_commit TEXT,
    timestamp_utc TEXT,
    concurrency INTEGER,
    status TEXT,
    e2e_ms REAL,
    metrics_json TEXT,
    schema_version TEXT,
    PRIMARY KEY (run_id, asset_id, gate)
);
CREATE INDEX IF NOT EXISTS idx_gate ON results(gate);
CREATE INDEX IF NOT EXISTS idx_substrate ON results(substrate);
"""

def rebuild_index(results_dir: pathlib.Path = pathlib.Path("results")) -> None:
    db = results_dir / "index.sqlite"
    db.unlink(missing_ok=True)
    conn = sqlite3.connect(db)
    conn.executescript(INDEX_SCHEMA)
    for jsonl in results_dir.rglob("*.jsonl"):
        with jsonl.open() as f:
            for line in f:
                row = json.loads(line)
                conn.execute(
                    "INSERT OR REPLACE INTO results VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                    (row["run_id"], row["gate"], row["asset_id"], row["substrate"],
                     row["image_digest"], row["git_commit"], row["timestamp_utc"],
                     row["concurrency"], row["status"], row.get("e2e_ms"),
                     json.dumps(row.get("metrics", {})), row["schema_version"]),
                )
    conn.commit()
    conn.close()
```

### Pattern 3: Cost Ledger (INFRA-06)

**What:** SQLite-backed module that is the only path to cloud provisioning. Every `runpodctl pod create` (Phase 2) goes through `ledger.authorize_spend(provider, gate, projected_cost)` first. Refusal rule: `budget_remaining - projected_cost*1.5 < 0`.

**Schema:**
```python
# cost/ledger.py
import sqlite3
import datetime
import pathlib
from dataclasses import dataclass

CREATE_SQL = """
CREATE TABLE IF NOT EXISTS budget (
    provider TEXT PRIMARY KEY,        -- 'runpod' | 'tensorwave' | 'vultr'
    cap_usd REAL NOT NULL,            -- $75 per provider (CLOUD-01/02)
    spent_usd REAL NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS authorizations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    provider TEXT NOT NULL,
    gate TEXT NOT NULL,
    projected_cost_usd REAL NOT NULL,
    safety_factor REAL NOT NULL,      -- 1.5 (locked)
    authorized_at TEXT NOT NULL,
    actual_cost_usd REAL,             -- filled in on session close
    status TEXT NOT NULL              -- 'authorized' | 'spent' | 'cancelled'
);
"""

class BudgetExhausted(Exception):
    pass

@dataclass
class Authorization:
    id: int
    provider: str
    gate: str
    projected_cost: float

def authorize_spend(
    provider: str,
    gate: str,
    projected_cost: float,
    safety_factor: float = 1.5,
    db_path: pathlib.Path = pathlib.Path("cost/ledger.sqlite"),
) -> Authorization:
    """Authorize a cloud provisioning request.

    Refuses if budget_remaining - projected_cost * safety_factor < 0.
    Returns Authorization on success.
    """
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.executescript(CREATE_SQL)
    row = conn.execute(
        "SELECT cap_usd, spent_usd FROM budget WHERE provider=?", (provider,)
    ).fetchone()
    if row is None:
        raise BudgetExhausted(f"Provider {provider} not initialized in ledger")
    cap, spent = row
    remaining = cap - spent
    headroom = remaining - projected_cost * safety_factor
    if headroom < 0:
        raise BudgetExhausted(
            f"{provider}: remaining=${remaining:.2f}, "
            f"projected=${projected_cost:.2f}*{safety_factor}=${projected_cost*safety_factor:.2f}, "
            f"headroom=${headroom:.2f}"
        )
    cur = conn.execute(
        "INSERT INTO authorizations(provider, gate, projected_cost_usd, safety_factor, authorized_at, status) "
        "VALUES (?, ?, ?, ?, ?, 'authorized')",
        (provider, gate, projected_cost, safety_factor, datetime.datetime.utcnow().isoformat()),
    )
    auth_id = cur.lastrowid
    conn.commit()
    conn.close()
    return Authorization(auth_id, provider, gate, projected_cost)

def initialize_provider(provider: str, cap_usd: float, db_path: pathlib.Path = pathlib.Path("cost/ledger.sqlite")) -> None:
    conn = sqlite3.connect(db_path)
    conn.executescript(CREATE_SQL)
    conn.execute("INSERT OR REPLACE INTO budget(provider, cap_usd, spent_usd) VALUES (?, ?, 0)", (provider, cap_usd))
    conn.commit()
    conn.close()
```

**Dry-run unit test (REQUIRED by ROADMAP success criterion 2):**
```python
# tests/test_cost_ledger.py
import pytest
import pathlib
from cost import ledger

def test_authorizes_below_threshold(tmp_path: pathlib.Path):
    db = tmp_path / "ledger.sqlite"
    ledger.initialize_provider("runpod", 75.0, db_path=db)
    auth = ledger.authorize_spend("runpod", "g1-smoke", 10.0, db_path=db)
    assert auth.provider == "runpod"

def test_refuses_when_safety_breach(tmp_path):
    db = tmp_path / "ledger.sqlite"
    ledger.initialize_provider("runpod", 75.0, db_path=db)
    # 50 * 1.5 = 75 = cap; refuse strictly less than 0 OK is the rule
    with pytest.raises(ledger.BudgetExhausted):
        ledger.authorize_spend("runpod", "g1", 50.01, db_path=db)

def test_refuses_unknown_provider(tmp_path):
    db = tmp_path / "ledger.sqlite"
    with pytest.raises(ledger.BudgetExhausted):
        ledger.authorize_spend("unknown", "g1", 1.0, db_path=db)
```

### Pattern 4: cost-watch.py Daemon (CLOUD-03)

**What:** Local Python daemon (run by operator alongside any cloud session). Polls each provider's billing API every 5 minutes. If projected daily spend exceeds remaining budget, hard-stops the relevant provider's pods.

**Provider asymmetry (verified May 2026):**

| Provider | Documented billing API endpoint | Our adapter approach |
|----------|--------------------------------|----------------------|
| **Vultr** | `GET /v2/billing/pending-charges/csv` ([VERIFIED: docs.vultr.com/platform/billing]); `GET /v2/account` for balance | httpx GET with Bearer token; parse pending charges total; clean and standard |
| **RunPod** | No documented programmatic spending-cap API. `runpod-python` SDK exposes `get_pods()` with `costPerHr`; balance accessible via REST/GraphQL. Provider-level cap = "fund only $75 in credits" (RunPod is prepaid; runs out of credits → all pods stop). | runpod SDK `get_pods()` to enumerate active pods + their `costPerHr`; multiply by elapsed time for cumulative spend. Initial cap enforced by **only depositing $75**. [CITED: runpod.io/blog/manage-runpod-account-funding] |
| **TensorWave** | No documented public billing API. Operator-funded prepaid; same "fund $75 only" pattern. | Adapter is a stub for Phase 1; logs a warning every poll until manual operator-side checks confirm spend. Recommend operator dashboard tab kept open in browser during sessions. [ASSUMED: search returned no public TensorWave billing API docs as of May 2026] |

**Daemon skeleton:**
```python
# cost/watch.py
import asyncio
import logging
import time
import httpx
from cost.adapters import runpod as runpod_adapter, tensorwave as tw_adapter, vultr as vultr_adapter

POLL_INTERVAL_S = 300  # 5 minutes (CLOUD-03 spec)

ADAPTERS = {
    "runpod": runpod_adapter.poll,
    "tensorwave": tw_adapter.poll,
    "vultr": vultr_adapter.poll,
}

async def watch_loop(active_providers: list[str]) -> None:
    async with httpx.AsyncClient() as client:
        while True:
            for provider in active_providers:
                try:
                    spend, projected_daily = await ADAPTERS[provider](client)
                    logging.info(f"[{provider}] spend=${spend:.2f} projected_daily=${projected_daily:.2f}")
                    # Hard-stop logic per provider (Phase 2 fills in)
                except Exception as e:
                    logging.warning(f"[{provider}] poll failed: {e}")
            await asyncio.sleep(POLL_INTERVAL_S)

# In Phase 1 the watch_loop only logs — actual hard-stop logic ships with
# Phase 2 (CLOUD-04 watchdog) which can call the runpod/vultr terminate APIs.
```

**Phase 1 deliverable:** Daemon logs spend per provider every 5 minutes. Hard-stop logic stubbed. Real teardown bindings ship with HARNESS-02/HARNESS-03 in Phase 2/3.

### Pattern 5: Asset Manifest (ASSETS-08, INFRA-05)

**Format:** CSV with header. One row per asset. Pre-commit hook and gate runners both consume it.

```csv
asset_id,corpus,path,sha256,license,source,created_utc,generator_script,generator_seed,kokoro_revision,intent,adversity_level,persona,duration_s,sample_rate
call-0001,corpus_500,assets/corpus_500/call-0001.wav,a7c9...e3,synthetic,assets/render_corpus.py,2026-05-04T10:00:00Z,assets/render_corpus.py,42,abc123def456...,intake_inquiry,neutral,nervous_first_time,5.2,16000
g711-0001,corpus_g711,assets/corpus_g711/g711-0001.wav,b8d0...f4,synthetic_transcoded,assets/g711.py,2026-05-04T11:00:00Z,assets/g711.py,42,abc123def456...,intake_inquiry,neutral,nervous_first_time,5.2,8000
upl-0001,corpus_upl,assets/corpus_upl/upl-0001.json,c9e1...05,synthetic,assets/upl_probes/render_probes.py,2026-05-04T12:00:00Z,assets/upl_probes/render_probes.py,42,,fee_quote,prompt_injection,,,
```

**Pre-commit no-real-audio hook (custom local hook in `.pre-commit-config.yaml`):**
```yaml
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.15.0    # pin verified at install time
    hooks:
      - id: ruff-check
        args: [--fix]
      - id: ruff-format

  - repo: local
    hooks:
      - id: assets-manifest-enforcement
        name: Every audio file must be listed in assets/manifest.csv
        entry: python tools/check_asset_manifest.py
        language: python
        files: ^assets/.*\.(wav|mp3|flac|opus|ogg)$
        always_run: true
```

```python
# tools/check_asset_manifest.py
import csv
import pathlib
import sys

ROOT = pathlib.Path(".")
AUDIO_EXTS = {".wav", ".mp3", ".flac", ".opus", ".ogg"}

def main() -> int:
    manifest_path = ROOT / "assets" / "manifest.csv"
    if not manifest_path.exists():
        # Permit empty repo; manifest must exist before audio does
        listed = set()
    else:
        with manifest_path.open() as f:
            reader = csv.DictReader(f)
            listed = {row["path"] for row in reader}
    found = {
        str(p) for p in (ROOT / "assets").rglob("*")
        if p.suffix.lower() in AUDIO_EXTS
    }
    unlisted = found - listed
    if unlisted:
        print("Audio files present but not listed in assets/manifest.csv:", file=sys.stderr)
        for p in sorted(unlisted):
            print(f"  {p}", file=sys.stderr)
        return 1
    return 0

if __name__ == "__main__":
    sys.exit(main())
```

### Pattern 6: Derating Skeleton (DERATE-01)

**What:** Per-stage roofline-style derating. Phase 1 ships type-safe function signatures + unit tests on synthetic data. Phase 4 fills in the real arithmetic-intensity classifications using Phase 3 measurements.

```python
# derating/op_classes.py
from enum import Enum
from dataclasses import dataclass

class OpClass(Enum):
    COMPUTE_BOUND = "compute_bound"        # STT prefill, TTS first-chunk, LLM TTFT
    BANDWIDTH_BOUND = "bandwidth_bound"    # LLM decode tokens/sec
    UNKNOWN = "unknown"                    # gfx1151 kernel-coverage gap; widen CI

@dataclass(frozen=True)
class HardwareSpec:
    name: str
    bandwidth_gb_s: float                  # MI300X 5300 (peak), 4240 (realized 80%); H100 SXM 3350; Strix Halo 212 (realized)
    prompt_processing_factor: float        # 1.0 baseline on MI300X; ~10-15× slower on Strix Halo per Phoronix Nov 2025

@dataclass(frozen=True)
class StageMeasurement:
    stage: str                             # 'stt_prefill', 'llm_ttft', 'llm_decode_per_tok', 'tts_first_chunk'
    op_class: OpClass
    measured_ms: float
    n: int                                 # sample size
```

```python
# derating/strix_model.py
from collections.abc import Iterable
from .op_classes import HardwareSpec, OpClass, StageMeasurement

# Hardware specs (verified from STACK.md §7.1 + CLAUDE.md §7.1)
MI300X = HardwareSpec("MI300X", bandwidth_gb_s=4240.0, prompt_processing_factor=1.0)  # 80% of 5.3 TB/s
H100_SXM = HardwareSpec("H100 SXM", bandwidth_gb_s=3350.0, prompt_processing_factor=1.0)
STRIX_HALO = HardwareSpec("Strix Halo", bandwidth_gb_s=212.0, prompt_processing_factor=12.5)  # 10-15× midpoint

def derate_compute_bound(measured_ms: float, src: HardwareSpec, dst: HardwareSpec) -> float:
    """Compute-bound stages (STT prefill, TTS first-chunk, LLM TTFT).

    Uses prompt_processing_factor ratio. dst slower → higher number.
    """
    return measured_ms * (dst.prompt_processing_factor / src.prompt_processing_factor)

def derate_bandwidth_bound(measured_ms: float, src: HardwareSpec, dst: HardwareSpec) -> float:
    """Bandwidth-bound stages (LLM decode tokens/sec).

    Uses bandwidth ratio. dst slower → higher number.
    """
    return measured_ms * (src.bandwidth_gb_s / dst.bandwidth_gb_s)

def derate_stage(measurement: StageMeasurement, src: HardwareSpec, dst: HardwareSpec) -> float | None:
    """Dispatch on op_class. Returns None for UNKNOWN — caller must widen CI."""
    if measurement.op_class is OpClass.COMPUTE_BOUND:
        return derate_compute_bound(measurement.measured_ms, src, dst)
    elif measurement.op_class is OpClass.BANDWIDTH_BOUND:
        return derate_bandwidth_bound(measurement.measured_ms, src, dst)
    elif measurement.op_class is OpClass.UNKNOWN:
        return None
    raise ValueError(f"Unknown OpClass: {measurement.op_class}")

def derate_pipeline(measurements: Iterable[StageMeasurement], src: HardwareSpec, dst: HardwareSpec) -> dict:
    """Sum per-stage derates → end-to-end estimate.

    Returns dict with per-stage and total. UNKNOWN stages produce None — total is also None.
    """
    out: dict[str, float | None] = {}
    total: float | None = 0.0
    for m in measurements:
        derated = derate_stage(m, src, dst)
        out[m.stage] = derated
        if derated is None:
            total = None
        elif total is not None:
            total += derated
    out["total_ms"] = total
    return out
```

```python
# derating/tests/test_strix_model.py
from derating.op_classes import OpClass, StageMeasurement
from derating.strix_model import (
    MI300X, STRIX_HALO, derate_compute_bound, derate_bandwidth_bound,
    derate_stage, derate_pipeline,
)

def test_compute_bound_strix_slower():
    # Strix Halo prompt processing 12.5× slower than MI300X
    assert derate_compute_bound(100.0, MI300X, STRIX_HALO) == 1250.0

def test_bandwidth_bound_uses_bandwidth_ratio():
    # MI300X 4240 GB/s realized → Strix Halo 212 GB/s = 20× slower
    assert derate_bandwidth_bound(10.0, MI300X, STRIX_HALO) == 200.0

def test_unknown_op_returns_none():
    m = StageMeasurement("stt_prefill", OpClass.UNKNOWN, 100.0, n=500)
    assert derate_stage(m, MI300X, STRIX_HALO) is None

def test_pipeline_total_none_if_any_unknown():
    measurements = [
        StageMeasurement("stt_prefill", OpClass.COMPUTE_BOUND, 100.0, n=500),
        StageMeasurement("llm_decode_per_tok", OpClass.UNKNOWN, 5.0, n=500),
    ]
    out = derate_pipeline(measurements, MI300X, STRIX_HALO)
    assert out["total_ms"] is None
    assert out["stt_prefill"] == 1250.0
    assert out["llm_decode_per_tok"] is None
```

### Anti-Patterns to Avoid

- **Single derating multiplier on end-to-end latency.** Pitfall 2 — Liotta-style review tears it apart. The skeleton must enforce per-stage; do not let Phase 4 introduce a `derate_e2e(ms, ratio)` shortcut.
- **Gate runners importing torch / vllm / onnxruntime directly.** Pitfall + HARNESS-01. Test ships in Phase 1 even though `gates/` is empty — Phase 2 contributors will trip the lint immediately.
- **Bare-tag Docker images (`rocm/vllm:latest`).** Pitfall 9 — Phase 0 → Phase 1 reproducibility decay. `images.lock.yaml` records `digest: sha256:...` always.
- **Mixing harness venv with asset-rendering venv.** Couples sm_61 wheel availability into harness reproducibility unnecessarily. Two separate venvs.
- **Single-source hesitation set without "soft pass with caveats" framing in the synthesis report.** D-03 explicitly accepts the synthetic-only approach but DR-28 requires the caveat. Phase 1 plans must surface this constraint to Phase 4.
- **Manifest CSV without per-asset SHA-256.** Pitfall 11 — provenance discipline. Every row has `sha256` populated.
- **Reference prompt with real firm name, real practice areas, real attorney names.** D-07 locks placeholder-only. UPL probes also content-free per D-04.
- **Cost ledger that allows authorization without persisting.** Authorization must commit to SQLite before cloud API call; if Python crashes mid-flow, the next process must see "spent" not "available."

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Versioned result schema | Custom dataclass + `version: str` field + manual JSON validate | **pydantic v2 with `Literal["1.0"]`** | Free JSON Schema export, free validation, free ser/deser, future discriminated-union path |
| Ground-truth transcript normalization | Custom regex / case-fold / contraction expansion | **`whisper-normalizer` PyPI** (`from whisper_normalizer.basic import BasicTextNormalizer`) | The canonical Whisper-paper normalizer; jiwer 4.x doesn't bundle it |
| WER computation | Custom Levenshtein | **jiwer 4.x** | RapidFuzz C++ backend; standard ASR eval library |
| G.711 transcoding | Hand-rolled μ-law lookup table or sox shell-out without flags | **`ffmpeg aresample=resampler=soxr:precision=28 -c:a pcm_mulaw`** with spectral validation | Pitfall 4 — wrong defaults on resampling/dithering produce artifacts that contaminate WER |
| Spectral validation of G.711 corpus | DIY FFT and "looks right" | **`scipy.signal.welch` PSD compared to G.711 mask** + one Twilio→Twilio reference | D-02 locks Twilio reference comparison |
| Cost cap monitoring | Manual operator vigilance | **Provider-level prepaid cap ($75 deposit)** + `cost-watch.py` poller | Pitfall 8 — manual vigilance is the failure mode; dual rails required |
| HF model download with verification | `wget` URL | **`huggingface_hub.hf_hub_download(repo_id, filename, revision=<sha>)`** | ETag-based SHA verification + cache reuse |
| Pre-commit orchestration | Custom git hook scripts | **`pre-commit` framework** + `astral-sh/ruff-pre-commit` | Standard 2026; one config file; `pre-commit run --all-files` for CI |
| Async streaming pipeline | Threads + queues | **Python `AsyncIterator[T]` with `asyncio`** | Matches LiveKit Agents 1.x natively (D-09); avoids GIL contention |
| Config validation | Manual `if 'foo' not in d: raise` | **pydantic-settings** (loads YAML + validates against pydantic model) | Free type checks, error messages, env-var override |
| Manifest enforcement | grep+find shell hooks | **Pre-commit hook that walks `assets/` and diffs against manifest** | Idempotent, runs locally + in CI; clean Python script |

**Key insight:** Every "Don't Hand-Roll" item below maps to a specific **Pitfall** from `.planning/research/PITFALLS.md`. The Phase 1 deliverables are the *enforcement mechanism* for the pitfalls — the manifest enforces Pitfall 11; the cost ledger enforces Pitfall 8; the per-stage derating skeleton enforces Pitfall 2; the lockfiles enforce Pitfall 9; the pre-commit hooks enforce Pitfall 11; the substrate ABC HARNESS-01 isolation enforces Pitfall 3. Plans that "simplify away" any of these enforcements are reintroducing the pitfall.

## Common Pitfalls

### Pitfall A: jiwer-version drift between STACK.md and current PyPI

**What goes wrong:** STACK.md and CLAUDE.md §14 stack-summary table say "jiwer 3.x". Current PyPI is **jiwer 4.x**. Phase 1 `pyproject.toml` written from STACK.md says `jiwer ^3.0`; `uv pip install` happily resolves an old version; later in Phase 3 someone tries `from whisper_normalizer.basic import BasicTextNormalizer` (because they read it elsewhere) and discovers `whisper-normalizer` is a separately-installed package, not part of jiwer.

**Why it happens:** STACK.md was researched 2026-05-04; jiwer 4.0 release predates that. The "BasicTextNormalizer is in jiwer" assumption appears in some 2024-era tutorials but is wrong — the normalizer was always in OpenAI's `whisper` repo and is now distributed via the `whisper-normalizer` PyPI package.

**How to avoid:**
- Pin **`jiwer ^4.0`** in `pyproject.toml` (not `^3.0`).
- Add **`whisper-normalizer`** as a direct dependency.
- Add a Wave-0 verification step that imports both:
  ```bash
  uv run python -c "import jiwer; from whisper_normalizer.basic import BasicTextNormalizer; print(jiwer.__version__)"
  ```

**Warning signs:** `pyproject.toml` references `^3.0` for jiwer; ground-truth normalization code does `from jiwer import BasicTextNormalizer`; CI passes locally but fails at Phase 3.

### Pitfall B: RunPod has no programmatic spending-cap API

**What goes wrong:** Plan calls for "set $75 cap on RunPod via API." Operator searches docs, finds none. Falls back to manual dashboard (which has a default $80/hr **rate** cap, not a **cumulative** cap). Cost-watch daemon monitors but cannot enforce a cumulative limit.

**Why it happens:** RunPod is prepaid and the platform model is "you fund credits, the credits run out, pods stop." There is no documented cumulative spending cap endpoint as of May 2026 — `runpod-python` SDK exposes `costPerHr` per pod and balance queries, but not a cap-set call. The "spending limit" operator-support can adjust is a fraud-prevention rate cap (default $80/hr), not a budget ceiling.

**How to avoid:**
- The "$75 provider-level cap" on RunPod is achieved by **funding only $75 in credits** at the start of Phase 1. When credits run out, all pods stop automatically (RunPod stops pods when balance covers <10s of remaining runtime, per [VERIFIED: docs.runpod.io]).
- Operator note for Phase 1 task list: "Add $75 to RunPod balance and DO NOT enable auto-recharge."
- `cost-watch.py` polls `runpod.get_pods()` cumulative `costPerHr × elapsed` for visibility; hard-stop logic in Phase 2 calls `runpod.terminate_pod(pod_id)` if projected cumulative > balance.

**Warning signs:** Plan task says "configure RunPod billing API cap"; no operator note about credit-deposit-as-cap; auto-recharge accidentally enabled.

### Pitfall C: TensorWave billing API is undocumented

**What goes wrong:** Symmetric assumption that TensorWave has a `/billing/usage` endpoint like Vultr. Cost-watch adapter for TensorWave 404s every poll. Operator has no programmatic spend visibility.

**Why it happens:** TensorWave is a smaller AMD-first cloud. As of May 2026 their public docs ([VERIFIED: search]) don't expose a billing API endpoint; spend visibility is dashboard-only.

**How to avoid:**
- TensorWave adapter (`cost/adapters/tensorwave.py`) is a **stub** in Phase 1 that logs a WARNING every poll: "TensorWave adapter cannot poll spend programmatically; check dashboard."
- Dual rail still works: provider cap = $75 prepaid, operator manual dashboard check is second rail.
- Document this limitation in `docs/decisions/dr-31-sharing-policy.md` so Phase 4 reproducibility manifest is honest about it.
- If Vultr is used as backup (CLOUD-02), it has the proper API and the adapter there is full-featured.

**Warning signs:** Plan symmetrically treats RunPod / TensorWave / Vultr as same shape; cost-watch logs show 404s for TensorWave; no operator-dashboard-check task in Phase 1.

### Pitfall D: `requirements.lock` vs `uv.lock` confusion

**What goes wrong:** INFRA-02 says "`requirements.lock` (uv lockfile) is committed." The `uv pip compile` command produces a `requirements.txt`-shaped output traditionally called `requirements.lock`. But uv project mode (which is what we want for `uv add`/`uv sync`/dependency-groups support) produces **`uv.lock`** — a TOML file, not pip-compatible format. These are different things.

**Why it happens:** uv has two modes: (1) **pip-compatible** (`uv pip compile requirements.in -o requirements.lock`) for projects migrating from pip-tools; (2) **project mode** (`uv init`, `uv add`, `uv sync`) which manages `pyproject.toml` and produces `uv.lock`. Project mode is the canonical 2026 path and integrates with PEP 735 dependency-groups.

**How to avoid:**
- **Use uv project mode.** `pyproject.toml` + `uv.lock`. Commit both.
- Treat the INFRA-02 wording "requirements.lock" as semantically meaning "the lockfile uv produces" — flag this to the operator as a planner clarification (the file will be `uv.lock`, not `requirements.lock`).
- If the operator strictly wants `requirements.lock` in pip format too, run `uv export --format requirements-txt -o requirements.lock` as a `make export-requirements` target. But the source of truth is `uv.lock`.

**Warning signs:** Plan task says "create `requirements.lock` via `uv pip compile`" and ignores `pyproject.toml` dependency-groups; can't run `uv sync --group dev`; pre-commit doesn't pick up dev deps cleanly.

### Pitfall E: pydantic v2 `Literal` discriminator pitfall — strict matching

**What goes wrong:** Phase 4 wants to add a `schema_version: Literal["1.0", "1.1"]` for an evolved schema. Phase 1 hardcoded `Literal["1.0"]`. Phase 4 either has to (a) bump everything to a discriminated union (clean but invasive) or (b) accept a Union type without a discriminator (slow validation, worse error messages).

**Why it happens:** Discriminated unions in pydantic v2 require **exact** Literal matches. An unknown discriminator value throws ValidationError, not a fallback.

**How to avoid:**
- Today: ship `schema_version: Literal["1.0"] = "1.0"` (locked by D-10). Single value, no union.
- Document in `harness/results.py` docstring: "When schema evolves, convert to `GateResultV1 | GateResultV2 = Field(discriminator='schema_version')` discriminated union; do NOT silently widen the Literal."
- Provide a `harness/migrate.py` placeholder file with TODO so future contributors find the migration path.

**Warning signs:** Future PR replaces `Literal["1.0"]` with `Literal["1.0", "1.1"]` without restructuring as a discriminated union — old readers will choke on "1.1" rows.

### Pitfall F: Pre-commit hook that runs only on staged files misses the manifest discipline

**What goes wrong:** Pre-commit runs `assets-manifest-enforcement` only when staged files match the audio file regex. Operator commits a manifest-only update (CSV change) without re-staging the audio. Hook doesn't run; stale manifest commits.

**Why it happens:** pre-commit by default runs hooks only on changed files. Manifest enforcement is a **whole-tree** check, not a per-file check.

**How to avoid:**
- Set `always_run: true` on the manifest enforcement hook (shown in the example above).
- Run the same check in CI / `make check`.

**Warning signs:** Pre-commit only triggers on audio file changes; manifest CSV out of sync but commits succeed.

## Code Examples

### Common Operation 1: Loading and validating a config YAML

```python
# Source: pydantic-settings standard pattern
# config/loader.py
from pathlib import Path
from pydantic import BaseModel, Field
import yaml

class GateConfig(BaseModel):
    asset_corpus: str
    concurrency: list[int]
    max_minutes: int

class GatesConfig(BaseModel):
    g1: GateConfig
    g2: GateConfig
    g3: GateConfig
    g5: GateConfig
    g7: GateConfig

def load_gates(path: Path = Path("config/gates.yaml")) -> GatesConfig:
    raw = yaml.safe_load(path.read_text())
    return GatesConfig.model_validate(raw)
```

### Common Operation 2: Pinned HF model download with SHA verification

```python
# Source: huggingface_hub revision pinning + ETag SHA verify
# tools/fetch_models.py
from huggingface_hub import hf_hub_download
import yaml
from pathlib import Path

def fetch_pinned(lockfile: Path = Path("bench/models.lock.yaml")) -> None:
    locks = yaml.safe_load(lockfile.read_text())
    for entry in locks["models"]:
        path = hf_hub_download(
            repo_id=entry["repo_id"],
            filename=entry["filename"],
            revision=entry["revision"],   # 40-char commit SHA
            cache_dir="~/.cache/huggingface",
        )
        print(f"OK {entry['repo_id']}@{entry['revision'][:8]} -> {path}")
```

### Common Operation 3: Makefile single-command targets (INFRA-03)

```makefile
# Source: standard Make pattern + INFRA-03 target list
.PHONY: install lint test assets smoke g1 g2 g3 g5 g7 report canary check

install:
	uv sync --all-groups

lint:
	uv run ruff check .
	uv run ruff format --check .

test:
	uv run pytest -q

# Phase 1 deliverables (no GPU spend)
assets-text:        # LLM-author scripts + UPL probes; no audio rendering
	uv run python -m assets.author_scripts
	uv run python -m assets.upl_probes.author_probes

assets-render:      # Local Kokoro rendering on GTX 1070 (asset-render venv)
	cd assets/render_env && uv run python ../render_corpus.py

assets-g711:        # ffmpeg transcode + spectral validation
	uv run python -m assets.g711 --validate

assets:             # Full asset pipeline
	$(MAKE) assets-text
	$(MAKE) assets-render
	$(MAKE) assets-g711

# Phase 2/3 placeholders (Phase 1 ships them as stubs)
smoke g1 g2 g3 g5 g7:
	@echo "Gate $@ not yet implemented; ships in Phase 2/3"
	@false

# Phase 4 placeholder
report:
	uv run python -m harness.store    # rebuild SQLite index
	uv run python -m synthesis.render_report

canary:
	@echo "End-of-week canary; ships in Phase 4 per REPRO-04"
	@false

check:              # CI gate: lint + test + manifest enforcement
	$(MAKE) lint
	$(MAKE) test
	uv run python tools/check_asset_manifest.py
```

## State of the Art

| Old Approach | Current Approach (May 2026) | When Changed | Impact |
|--------------|------------------------------|--------------|--------|
| `pip` + `requirements.txt` | `uv` + `pyproject.toml` + `uv.lock` (project mode) + PEP 735 dependency-groups | uv project mode stable since 2024; PEP 735 standardized 2024 | Phase 1 uses project mode |
| `setup.py` | `pyproject.toml` with PEP 621 metadata | PEP 621 finalized 2021; universal in 2026 | No `setup.py` anywhere |
| `black + isort + flake8` | `ruff` (single tool) | ruff format stable since 2024 | Single `[tool.ruff]` block |
| `unittest` | `pytest` (with `pytest-asyncio` for async code) | Standard since ~2018 | All Phase 1 tests are pytest |
| jiwer 3.x with built-in normalizer | **jiwer 4.x + separate `whisper-normalizer` package** | jiwer 4.0 release | Direct dependency on `whisper-normalizer` |
| Pydantic v1 `BaseModel` | **Pydantic v2** with `model_validate`, `model_dump`, `Literal` discriminators | v2 released 2023; v1 EOL'd 2024 | All schemas v2 |
| `:latest` Docker tags | **`@sha256:` digest pinning** | Reproducibility discipline | `images.lock.yaml` records digests |
| HF model identifier without `revision=` | **`hf_hub_download(repo_id, filename, revision=<40-char-SHA>)`** | HF revision pinning standardized | `models.lock.yaml` records SHAs |

**Deprecated/outdated (do NOT use):**
- `outlines` library for structured generation → use **xgrammar** via vLLM (CLAUDE.md §11). Phase 1's `Grammar` type wraps xgrammar JSON schema.
- `whisper.cpp` on cloud GPUs → use **faster-whisper INT8** (CLAUDE.md §11). Phase 1 doesn't import either; locks the contract for Phase 2/3.
- `pyannote-audio` for streaming VAD → use **silero-vad v5** (CLAUDE.md §11). Phase 1 doesn't import either.
- `pip install -r requirements.txt` for benchmark reproducibility (Pitfall 9).

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | TensorWave has no public billing API as of May 2026 | Pitfall C, cost-watch design | Low — adapter would gain real polling instead of stub; doesn't break design |
| A2 | RunPod's "fund only $75 credits" is a viable cumulative cap mechanism | Pitfall B, CLOUD-01 | Medium — if RunPod adds auto-recharge by default or charges in arrears in some flow, the cap could be breached. Operator must verify auto-recharge is OFF. |
| A3 | sm_61 PyTorch wheels remain available for torch ≤2.5 | Asset-rendering venv | Low — if wheel availability degrades, operator falls back to CPU rendering on Kokoro (slower but functional, possibly hours instead of minutes) |
| A4 | The Twilio→Twilio reference clip can be self-generated by operator pre-Phase-1 | D-02 spectral validation | Medium — if Twilio access requires sign-up/verification delay, blocks ASSETS-07 spectral validation. Mitigation: operator pre-flights this in Wave 0 |
| A5 | LiveKit Agents 1.x signature `transcribe(AsyncIterable[bytes]) -> AsyncIterable[STTChunk]` matches our D-09 substrate ABC | Substrate ABC | Low — if LiveKit's plugin signature differs in detail, Phase 3 wires an adapter shim. The async-iterator shape is what matters. |
| A6 | xgrammar's grammar object is JSON-serializable and can be carried as a `Grammar` type in the ABC | D-09 ABC `generate(grammar: Grammar | None)` | Low — xgrammar accepts JSON Schema strings; `Grammar = str | dict` is a safe placeholder for Phase 1 |
| A7 | pytest 8.x + pytest-asyncio 0.24+ are stable for async ABC stub testing | Test stack | Very low — battle-tested combination |
| A8 | The synthesis report's "soft pass with caveats" language for G3 is acceptable to UMB Group / Eric | D-03, DECISION-NC-R14 | Low — DR-28 explicitly permits soft-pass framing; CONTEXT.md confirms this. Risk only if operator rejects the framing later |
| A9 | The reference prompt placeholder structure (`{firm_name}`, `{practice_area}`) is permissive enough to surface UPL escapes per Pitfall 7 | D-07 | Medium — Pitfall 7 says "generic prompt is more conservative than production"; D-07 specifically authors a *permissive* generic prompt to mitigate, but the gap can never be fully closed pre-firm-customization. Phase 1 caveat (D-08) covers this |

## Open Questions

1. **Strict interpretation of `requirements.lock` (INFRA-02 wording)?**
   - What we know: `uv.lock` is canonical for uv project mode; the wording "requirements.lock" predates project mode adoption.
   - What's unclear: Whether the operator wants both files or just `uv.lock`.
   - Recommendation: Ship `uv.lock` (canonical) + `make export-requirements` target that emits `requirements.lock` in pip-compat format on demand. Surface as planner clarification before Wave 0 starts.

2. **DR-31 sharing policy — should Claude draft to operator review, or operator-author?**
   - What we know: CONTEXT.md "Claude's Discretion" section says "Claude drafts `docs/decisions/dr-31-sharing-policy.md` based on PRD §13 NC-R14 + Pitfall 10." Stance is locked (methodology + prediction range only pre-SOW; two-tier when numbers travel).
   - What's unclear: Whether operator reviews/edits before Phase 1 closes or simply accepts.
   - Recommendation: Plan ships the v0.1.0 draft early in the wave; operator review is an explicit Phase 1 task (1 hour); v0.1.1 if any edits emerge. Phase 1 cannot close until operator signs off (per ROADMAP success criterion 3).

3. **Asset-rendering venv lockfile?**
   - What we know: Two venvs (harness + asset-rendering); harness uses `uv.lock`.
   - What's unclear: Should asset-rendering venv also have a committed lockfile, or is it ephemeral?
   - Recommendation: **Commit `assets/render_env/uv.lock`**. Reproducibility argues for it (REPRO-01/02 spirit); the cost is one extra lockfile.

4. **Should `models.lock.yaml` contain SHA-256 of safetensors / GGUF / ONNX file artifacts, or only HF commit revision SHA?**
   - What we know: REPRO-02 says "pins every HF model by `revision=<commit_sha>`." Pitfall 9 says "SHA-256 of the safetensors / GGUF / ONNX file recorded."
   - What's unclear: Whether commit-SHA pinning alone is enough, or per-file SHA-256 is also required.
   - Recommendation: **Both.** `models.lock.yaml` records `repo_id`, `revision: <commit_sha>` (HF level), and `files: [{filename, sha256}]` (file level). HF's ETag-based caching uses git-sha1 / sha256 already, so we're recording what's on disk. Pitfall 9's belt-and-suspenders is cheap.

5. **Substrate ABC `Grammar` type definition?**
   - What we know: D-09 says `grammar: Grammar | None`. Use is xgrammar.
   - What's unclear: Whether `Grammar` is a `pydantic.BaseModel`, a `str` (JSON schema), a `dict`, or a thin wrapper.
   - Recommendation: Phase 1 ships `Grammar = str | dict[str, Any]` (type alias). xgrammar accepts JSON Schema strings; no need to invent a richer type until Phase 3 actually wires it.

6. **Whether Phase 1 also drafts a lightweight DR-31 *internal* memo (for Eric / Dustin) vs the formal external-facing decision document?**
   - What we know: D-13 says drop companion docs; DECISION-NC-R14 says "explicit policy recorded in `docs/decisions/dr-31-sharing-policy.md`."
   - What's unclear: Whether one document serves both audiences.
   - Recommendation: One document, structured as: §1 Decision (operator-facing), §2 External-sharing rules (firm-facing rationale), §3 Caveats. Avoids two-document drift.

## Environment Availability

Phase 1 is local-only (zero GPU spend), but the operator's local environment must support several dependencies. Probe at start of Wave 0.

| Dependency | Required By | Probe Command | Fallback |
|------------|------------|---------------|----------|
| uv ≥0.4 | INFRA-02 | `uv --version` | Install via `curl -LsSf https://astral.sh/uv/install.sh \| sh` |
| Python 3.11.x | INFRA-02 | `python3.11 --version` | uv can manage Python: `uv python install 3.11` |
| ffmpeg 7.x | ASSETS-07 | `ffmpeg -version \| head -1` | `apt install ffmpeg` (Ubuntu 22.04 has 4.x default; need a backports / static build for 7.x) |
| git ≥2.x | All | `git --version` | Standard apt install |
| GTX 1070 + NVIDIA drivers + CUDA 12.x | ASSETS-01 (local Kokoro rendering) | `nvidia-smi` | If unavailable, fall back to CPU Kokoro — much slower (hours instead of minutes for 500 clips) but produces the same audio |
| sm_61 PyTorch wheel availability | ASSETS-01 (local Kokoro on Pascal) | `python -c "import torch; print(torch.cuda.get_device_capability())"` after install | If sm_61 unsupported in current torch, pin `torch<=2.5` |
| Internet egress (HF Hub, pre-commit hooks, runpod/vultr SDK installs) | All | `curl -sI https://huggingface.co` | None — required |
| pre-commit framework | INFRA-05 | `uv tool install pre-commit` then `pre-commit --version` | uv tool install path |
| Disk space ≥ 30 GB free | Asset corpora + HF cache | `df -h ~/RBOX` | None — required |
| Operator account: RunPod | CLOUD-01 | dashboard sign-up | None — operator manual task |
| Operator account: TensorWave OR Vultr | CLOUD-02 | dashboard sign-up | Vultr is the documented backup if TensorWave UX friction |
| Twilio test number for one G.711 reference clip | D-02 spectral validation | dashboard sign-up | If Twilio sign-up delays Phase 1, accept Pitfall 4 risk and document gap; operator can retro-add reference later |

**Missing dependencies with no fallback:** Internet egress, git, Python 3.11 (uv can install), ≥30 GB disk.

**Missing dependencies with fallback:** GPU (CPU Kokoro fallback), Twilio (defer reference clip; document risk).

## Validation Architecture

**Skipped:** `workflow.nyquist_validation` is `false` in `.planning/config.json`. Per the research template instructions, this section is omitted. The Common Pitfalls and unit-test examples above (test_cost_ledger, test_strix_model, test_harness_isolation, test_assets_manifest) cover the test discipline informally; the planner will translate them into atomic test tasks.

## Security Domain

**`security_enforcement` config:** Not explicitly set in `.planning/config.json`. Treat as enabled per default rule.

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|------------------|
| V2 Authentication | yes (provider API keys for RunPod / Vultr / TensorWave) | Environment variables (`RUNPOD_API_KEY`, `VULTR_API_KEY`); never committed; pre-commit hook for secret detection (TruffleHog or `detect-secrets`) optional but recommended |
| V3 Session Management | no (Phase 1 has no user-facing sessions) | — |
| V4 Access Control | yes (cost ledger gates spend authorization) | INFRA-06 — `authorize_spend()` is the single chokepoint; gate-runner code path enforces by import structure (HARNESS-01) |
| V5 Input Validation | yes (asset manifest, config YAML, GateResult JSONL on read) | pydantic v2 validates every config and result row; manifest CSV pre-commit hook checks shape |
| V6 Cryptography | partial (SHA-256 hashing for asset provenance; HF revision SHA verification) | Use `hashlib.sha256` (stdlib); use `huggingface_hub` ETag-based verification; do not hand-roll |
| V7 Error Handling & Logging | yes (cost-watch, gate runners, ledger) | Errors land in `GateResult` with `status='error'` populated (D-11) — never silently filtered; structured logging via stdlib `logging` |
| V8 Data Protection | yes (regulatory: no PII, no real client audio) | Pre-commit hook (INFRA-05); manifest enforcement; pre-teardown cloud audit (Phase 2 carryover) |
| V9 Communications | yes (HTTPS to provider APIs, HF Hub) | httpx defaults; verify TLS (httpx does by default) |

### Known Threat Patterns for Phase 1

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Real client audio leaks into corpus | Information Disclosure | Pitfall 11; pre-commit hook + manifest enforcement |
| API keys committed to repo | Information Disclosure | `.env` in `.gitignore`; pre-commit `detect-secrets` (optional but cheap); pre-commit hook in CLAUDE.md user safety rules already blocks `.env` writes |
| Cost runaway via stuck pod | Denial of (operator's) Wallet | Provider-level cap ($75 prepaid) + cost-watch daemon (dual rails per Pitfall 8) |
| Spent budget recorded but not authorized (race) | Tampering | SQLite transaction in `authorize_spend`; `INSERT INTO authorizations` commits before returning |
| UPL probe contains real legal facts | Compliance / Reputation | Operator manual review per probe (D-04); manifest provenance line |
| Voice clone reference clip uses identifiable person | Compliance / Reputation | D-05 — synthetic operator-style sample only; no public-figure voices |
| Cloud teardown leaves PII residue | Information Disclosure | CLOUD-06 (Phase 2 deliverable); Phase 1 sets the asset-manifest discipline that enables it |
| Adversarial prompt injection in UPL probes leaks past guardrail | Tampering | D-04 — ≥30 prompt-injection variants; G5 evaluated under grammar-constrained generation (xgrammar) per FR-R31 / FR-R24 |

## Sources

### Primary (HIGH confidence)
- `.planning/phases/01-foundation/01-CONTEXT.md` — D-01..D-13 locked decisions; primary input
- `.planning/REQUIREMENTS.md` — 24 Phase 1 requirements; acceptance criteria
- `.planning/ROADMAP.md` — 5 success criteria for Phase 1
- `.planning/STATE.md` — open blockers (NC-R14, companion docs, gfx1151)
- `.planning/research/PITFALLS.md` — Pitfalls 1, 4, 6, 7, 8, 9, 11 directly drive Phase 1 design
- `/home/bob/RBOX/CLAUDE.md` §1-§15 — full pinned tech stack including §11 What NOT to Use
- `~/.claude/CLAUDE.md` — operator preferences (uv, ruff, pytest, pyproject.toml, no emoji, file versioning)
- [pydantic discriminated unions](https://docs.pydantic.dev/latest/concepts/unions/) — Literal-based discriminator pattern
- [LiveKit Agents async iterator pattern](https://docs.livekit.io/agents/) — confirms D-09 ABC shape matches LiveKit 1.x
- [astral-sh/ruff-pre-commit](https://github.com/astral-sh/ruff-pre-commit) — current pre-commit hook tag (`v0.15.x`); `ruff-check` + `ruff-format` order
- [uv project mode docs](https://docs.astral.sh/uv/guides/projects/) — `uv init`, `uv add`, `uv sync`, `uv.lock`
- [PEP 735 dependency-groups](https://packaging.python.org/en/latest/specifications/pylock-toml/) — `[dependency-groups]` table syntax
- [Vultr billing API](https://docs.vultr.com/platform/billing) — `/v2/billing/pending-charges/csv` documented
- [whisper-normalizer PyPI](https://pypi.org/project/whisper-normalizer/) — `BasicTextNormalizer` distribution
- [jiwer PyPI](https://pypi.org/project/jiwer/) — current 4.x version
- [huggingface_hub revision pinning](https://huggingface.co/docs/huggingface_hub/en/guides/download) — `revision=<sha>` parameter; ETag SHA verification

### Secondary (MEDIUM confidence)
- [RunPod pricing & SDK](https://www.runpod.io/pricing), [runpod-python](https://github.com/runpod/runpod-python) — billing API gap; "fund credits as cap" pattern; `costPerHr` per-pod query
- [TensorWave docs](https://tensorwave.com/) — billing API undocumented; manual dashboard for spend visibility
- [RunPod account funding](https://www.runpod.io/blog/manage-runpod-account-funding) — prepaid model details

### Tertiary (LOW confidence — flagged in Assumptions Log)
- TensorWave billing API non-existence (single-source: their public docs + getdeploying.com mirror as of May 2026); Pitfall C documents the assumption
- Specific Strix Halo prompt-processing factor (12.5×, midpoint of Phoronix 10-15× range) — STACK.md/CLAUDE.md cite Phoronix Nov 2025; the skeleton accepts the parameter as `prompt_processing_factor` and Phase 4 will refine

## Metadata

**Confidence breakdown:**
- Standard stack — HIGH — every library version verified against PyPI / official docs in May 2026
- Architecture (ABC, GateResult, ledger, derating skeleton) — HIGH — patterns locked in CONTEXT.md D-09..D-12; code shapes match pydantic v2 / async-iterator standards
- Asset corpus pipeline — HIGH for tooling (ffmpeg, soxr, Kokoro, manifest format); MEDIUM for the Twilio reference-clip availability
- Cost rails — HIGH for Vultr (documented API), MEDIUM for RunPod ("fund credits" is the cap), LOW-MEDIUM for TensorWave (undocumented; stub adapter)
- Pitfalls (project-specific) — HIGH — directly traced from `.planning/research/PITFALLS.md`
- Decision documents (DR-31) — HIGH for stance (CONTEXT.md locked); MEDIUM for exact prose (Claude drafts; operator may edit)

**Research date:** 2026-05-04
**Valid until:** 2026-06-04 (30 days; tooling stable but provider billing APIs and HF model SHAs can drift; re-verify pinned versions at Wave 0 install time)
