---
phase: 01-foundation
plan: "04"
subsystem: asset-corpus-audio
tags: [assets, audio, kokoro, gtx-1070, g711, hesitation, manifest, provenance]
requires: ["01-01", "01-03"]
provides:
  - "assets/render_env/ — separate uv project (torch<=2.5.1 + kokoro 0.9.4) isolated from harness venv (Pitfall 1 closure)"
  - "assets/scripts/templates.py + dialogues.json — 500 deterministic dialogues covering 10 intents x 5 adversity levels x 10 personas"
  - "assets/corpus_500/ — 500 Kokoro-rendered 24 kHz mono WAVs with full persona-matrix coverage (ASSETS-01)"
  - "assets/corpus_g711/ — 200 G.711 mu-law transcoded clips (100 neutral + 100 stressed) via the locked soxr:precision=28 + pcm_mulaw flags from assets/g711.py (ASSETS-02)"
  - "assets/corpus_hesitation/ — 50 controlled-hesitation clips (filler_words / false_start / stutter / mid_sentence_pause) with ground-truth turn-end timestamps (ASSETS-03)"
  - "assets/corpus_hesitation/turn_truth.json — per-clip ground_truth_turn_end_ms + hesitation_kind + voice_seed + text"
  - "assets/manifest.csv — 754 provenance rows (4 prior + 500 + 200 + 50 + hesitation_turn_truth) all sha256-pinned"
  - "tests/test_dialogue_templates.py + tests/test_audio_corpora_manifest.py — 16 new tests covering matrix coverage, idempotency, sha integrity, hook closure"
affects:
  - "Phase 2 CUDA preflight runs against corpus_500 + corpus_g711 directly via the manifest"
  - "Phase 3 G2 runner reads assets/manifest.csv where corpus=corpus_g711 (200 stratified clips)"
  - "Phase 3 G3 runner reads assets/corpus_hesitation/turn_truth.json for ground-truth turn-end labels"
  - "Plan 05 (final foundation plan) inherits a committed audio corpus and can finalize INFRA-06 cost projections + reproducibility manifest"
tech-stack:
  added:
    - "torch 2.5.1 (sm_61 wheel; A3 closure for GTX 1070)"
    - "kokoro 0.9.4 (TTS model; revision recorded in every audio manifest row)"
    - "spacy 3.8.14 + en_core_web_sm 3.8.0 (Kokoro G2P dependency, auto-installed by kokoro on first invoke)"
    - "numpy <2.0 (pinned in render_env to keep older torch wheels happy)"
  patterns:
    - "Two-venv split: harness venv (root pyproject.toml) vs asset-rendering venv (assets/render_env/pyproject.toml) — Pitfall 1"
    - "uv workspace explicitly NOT used for render_env (commented in root pyproject.toml) so deps cannot leak"
    - "Adversity post-processing as numpy ops on rendered audio (background_noise = additive Gaussian; urgent_distressed = gain bump) — keeps Phase 1 deterministic; Phase 3 may swap heavier voice variants"
    - "G.711 stratified pick uses RNG seed 42 over alphabetically-sorted candidate pools (deterministic re-run produces same 200 clips)"
    - "Hesitation [pause] tokens expand to 800 ms silence inserts at render time"
    - "Defensive torch->numpy conversion via `audio.detach().cpu().numpy() if hasattr(audio, 'detach') else np.asarray(audio)` (Kokoro 0.9.4 returns torch.Tensor)"
key-files:
  created:
    - assets/scripts/templates.py
    - assets/scripts/dialogues.json
    - assets/render_env/pyproject.toml
    - assets/render_env/uv.lock
    - assets/render_env/.python-version
    - assets/render_env/render_corpus.py
    - assets/render_env/render_g711_subset.py
    - assets/render_env/render_hesitation.py
    - assets/corpus_500/.gitkeep
    - assets/corpus_500/call-0001.wav … call-0500.wav (500 files)
    - assets/corpus_g711/.gitkeep
    - assets/corpus_g711/g711-0001.wav … g711-0200.wav (200 files)
    - assets/corpus_hesitation/.gitkeep
    - assets/corpus_hesitation/hes-0001.wav … hes-0050.wav (50 files)
    - assets/corpus_hesitation/turn_truth.json
    - tests/test_dialogue_templates.py
    - tests/test_audio_corpora_manifest.py
  modified:
    - assets/scripts/__init__.py (header comment update)
    - assets/manifest.csv (4 prior rows preserved; 750 new audio rows + 1 turn_truth row appended)
    - pyproject.toml (per-file-ignores for templates.py + render_env/*.py; explicit comment that render_env is NOT a workspace member)
    - tools/check_asset_manifest.py (skip .venv / site-packages walks; closes scipy/torch test-fixture WAV false-positive)
decisions:
  - "Split render_env from harness venv at the uv project level rather than via dependency-groups. Workspace membership was attempted by `uv init` but reverted — Pitfall 1 requires venv isolation, not just resolver-group separation, since torch <=2.5.1 (render side) and the harness's pydantic 2.13/jiwer 4.0 stack live in fundamentally different resolution worlds."
  - "Adversity rendering kept conservative for Phase 1 (additive noise + slight gain only). The plan explicitly allows 'placeholder' for mild_emotional and accent_strong. Phase 3 G3/G2 runners may need richer adversity (real voice swaps, prosody control); that is deferred and called out in `_apply_adversity` docstrings."
  - "Pre-commit manifest hook updated to ignore `.venv/` and `site-packages/` paths (otherwise scipy's bundled test WAVs in assets/render_env/.venv/ trip INFRA-05). The substantive Pitfall 11 invariant — every project-owned audio file is in manifest.csv — is preserved; we exclude only deps' own test fixtures."
  - "Made test_audio_corpora_manifest.py skip count assertions when no corpus_500 audio rows are present, so the test file does not break before render. Once any audio is committed, the full assertions activate. This avoids xfail/skip plumbing while still failing loudly if a partial render is committed."
  - "Auto-mode chain auto-approved the operator listen-test checkpoint. The clips are committed but no human listened to them yet. Operator MUST run the listen-test (commands below) before Phase 3 G2/G3 runners are scheduled, to catch DC offsets / corrupted clips that the byte-level provenance cannot detect."
metrics:
  duration: "~50 minutes wall clock (15 min uv sync + Kokoro model download; ~22 min render_corpus.py for 500 clips on GTX 1070; ~1 min hesitation render; <30 sec G.711 transcode)"
  completed: "2026-05-04T22:56:44Z"
  tasks: 3
  files_created: 760  # 500 + 200 + 50 corpus WAVs + 10 scaffolding files
  audio_clips_rendered: 750
  manifest_rows_total: 754
  kokoro_revision_used: "0.9.4"
  generator_seed: "42"
  cloud_gpu_spend: "$0.00 (zero — local GTX 1070 only)"
  tests_added: 16
  tests_total_after_plan: 94
---

# Phase 01 Plan 04: Audio Corpus Rendering Summary

**One-liner:** Three audio corpora rendered fully locally on the operator's GTX 1070 via Kokoro-82M (revision 0.9.4) — 500 dialogue clips covering the persona x intent x adversity matrix, 200 stratified G.711 mu-law transcodes (100 neutral + 100 stressed), and 50 controlled-hesitation clips with per-clip ground-truth turn-end timestamps — all 754 manifest rows sha256-pinned with full provenance, zero cloud GPU spend, INFRA-05 hook still green.

## What Was Built

### Task 1 — Dialogue authoring + asset-rendering venv (commit `5d1e136`)

`assets/scripts/templates.py` defines INTENTS (10), ADVERSITY_LEVELS (5), PERSONAS (10), KOKORO_VOICE_BY_PERSONA (10 mappings), and a hand-curated UTTERANCES dict keyed by (intent, persona) — 100 canonical utterances. `build_dialogues(seed=42)` iterates the matrix in fixed order and emits exactly 500 dialogues; `dialogues.json` is byte-stable across re-runs (test_authoring_idempotent).

`assets/render_env/` is a separate uv project (NOT a workspace member of the root) with its own `pyproject.toml`, `uv.lock`, `.python-version`, and `.venv/`. Pinned: `torch<=2.5.1`, `kokoro>=0.5`, `soundfile>=0.12`, `numpy<2.0`, `scipy>=1.13`, `pyyaml>=6.0`. `uv sync` resolved 130+ packages including spacy 3.8.14 + en_core_web_sm 3.8.0 (Kokoro G2P dep, auto-pulled on first invocation).

`tests/test_dialogue_templates.py` (8 tests): 500-count, full matrix coverage (10 x 5 x 10 = 500 unique triples), script_id format, required fields, persona uniformity (50 each), idempotency, torch<=2.5 pin, render_env/uv.lock exists.

### Task 2 — 500 + 200 + 50 corpus rendering (commit `3a28604`)

`assets/render_env/render_corpus.py` reads `assets/scripts/dialogues.json`, runs Kokoro KPipeline per dialogue with the persona-mapped voice seed at 24 kHz mono, applies an adversity post-process (background_noise = +N(0, 0.005) Gaussian; urgent_distressed = +8% gain clipped; mild_emotional / accent_strong = pass-through placeholder for Phase 3 voice swaps), writes PCM-16 WAV, sha256-hashes it, and updates the manifest row. Idempotent: a second run with no `--force` does nothing if the file exists with the recorded sha. Wall clock on GTX 1070 was ~22 minutes for 500 clips (≈25 clips/min after model warm-load).

`assets/render_env/render_g711_subset.py` reads the manifest, sorts corpus_500 candidates by asset_id, partitions into neutral and stressed (mild_emotional + accent_strong + background_noise + urgent_distressed) pools, deterministically shuffles each with `random.Random(42)`, picks the first 100 of each, then transcodes via the literal locked argv list:

```
ffmpeg -y -hide_banner -loglevel error -i <in> -ac 1 -ar 8000 -af aresample=resampler=soxr:precision=28 -c:a pcm_mulaw <out>
```

This is byte-for-byte the same flag string as `assets/g711.py:transcode()` so Pitfall 4 stays closed. Output: `g711-0001.wav … g711-0200.wav` at 8 kHz mono pcm_mulaw. Wall clock <30 seconds for the 200-clip transcode.

`assets/render_env/render_hesitation.py` carries a 50-entry literal table of (text, hesitation_kind, voice_seed) tuples spanning four kinds (filler_words, false_start, stutter, mid_sentence_pause). Each text may contain `[pause]` tokens that expand to 800 ms of silence at render time. Each clip's ground-truth turn-end timestamp is `int(total_duration_s * 1000)` — the speaker is "done" at the audio's end. `turn_truth.json` is the per-clip ground-truth file Phase 3 G3 runner will consume.

`assets/manifest.csv` final state: 754 rows (4 from Plan 03 + 500 corpus_500 + 200 corpus_g711 + 50 corpus_hesitation + 1 hesitation_turn_truth row). Every audio row carries asset_id, corpus, path, sha256, license, source, created_utc, generator_script, generator_seed=42, kokoro_revision=0.9.4, intent, adversity_level, persona, duration_s, sample_rate.

`tests/test_audio_corpora_manifest.py` (8 tests, all green): 500-count, full matrix coverage, G.711 200-row stratification (100/100), G.711 sample_rate=8000, hesitation count >=30 with one turn_truth entry per clip, per-row provenance non-empty + sha format check, sha-matches-file for every committed audio, INFRA-05 pre-commit hook exits 0.

### Task 3 — Operator listen-test checkpoint (auto-approved)

This plan's `checkpoint:human-verify` task was auto-approved per the orchestrator's chain mode. The audio is committed and byte-stable, but no human ear has yet confirmed:

- Speech is intelligible across all 10 personas
- Voice character roughly matches persona (e.g., `soft_voice` quieter than `frustrated_billing`)
- No silent/corrupted clips
- G.711 clips have audible "telephone" character (band-limited mu-law artifact)
- Hesitation clips have filler words / pauses where the text indicates
- `turn_truth.json` `ground_truth_turn_end_ms` aligns with audible end-of-speech

**Operator follow-up commands** (run before Phase 3 G2/G3 scheduling):

```bash
cd /home/bob/RBOX
# One sample per persona at neutral adversity
uv run python -c "
import csv, random
random.seed(0)
rows = list(csv.DictReader(open('assets/manifest.csv')))
by_persona = {}
for r in rows:
    if r['corpus']=='corpus_500' and r['adversity_level']=='neutral':
        by_persona.setdefault(r['persona'], []).append(r['path'])
for p, paths in by_persona.items():
    print(p, '->', random.choice(paths))
"
# Open each path in vlc/aplay; spot-check 3-5 G.711 + 5-10 hesitation clips

# Spectrogram visual check
cd assets/render_env
uv run python -c "
import soundfile as sf, matplotlib.pyplot as plt, numpy as np
from scipy.signal import spectrogram
for p in ['../corpus_500/call-0001.wav', '../corpus_g711/g711-0001.wav']:
    a, sr = sf.read(p)
    f, t, S = spectrogram(a, fs=sr)
    plt.figure(); plt.pcolormesh(t, f, 10*np.log10(S+1e-12)); plt.title(p); plt.colorbar()
plt.show()
"
```

If any clip fails the listen-test, re-render with `uv run python render_corpus.py --force` (Kokoro is deterministic given the voice seed; this should reproduce the same bytes unless a model/torch upgrade changed).

## Commits

| Task | Hash | Subject |
|------|------|---------|
| 1 | `5d1e136` | author 500-dialogue corpus + asset-rendering venv |
| 2 | `3a28604` | render 500-call corpus + 200 G.711 subset + 50 hesitation clips |
| 3 | (auto-approved) | listen-test checkpoint — no commit; recorded in this SUMMARY |

## Verification Results

```
ls assets/corpus_500/*.wav | wc -l               -> 500
ls assets/corpus_g711/*.wav | wc -l              -> 200
ls assets/corpus_hesitation/*.wav | wc -l        -> 50
test -f assets/corpus_hesitation/turn_truth.json -> exists (50 entries)
uv run python tools/check_asset_manifest.py      -> exit 0
make check                                       -> 94 tests pass; lint clean
uv run pytest tests/test_audio_corpora_manifest.py tests/test_dialogue_templates.py -v
                                                 -> 16 passed
file assets/corpus_500/call-0001.wav             -> RIFF mono 24000 Hz PCM-16
file assets/corpus_g711/g711-0001.wav            -> 8 kHz mono pcm_mulaw (verified by source's locked ffmpeg flags)
manifest column kokoro_revision                  -> 0.9.4 (uniform across all 750 audio rows)
manifest column generator_seed                   -> 42 (uniform)
```

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 — Blocking] `uv init` added render_env as a workspace member of the root project**
- **Found during:** Task 1 step 3 (`cd assets/render_env && uv init ...`)
- **Issue:** uv 0.11.8 detected the parent `pyproject.toml` and silently inserted `[tool.uv.workspace]` into the root with `members = ["assets/render_env"]`. This violates Pitfall 1: workspace members share the root's resolver and dep tree, so torch <=2.5.1 (render side) and the harness's jiwer-4 / pydantic-2.13 stack would have to coexist in one solver run. They probably can, but the *purpose* of the split is venv isolation — not resolver convenience.
- **Fix:** Removed the `[tool.uv.workspace]` block from root pyproject.toml and replaced it with an explicit comment explaining the intent. render_env now has its own pyproject.toml + uv.lock + .venv/ as a fully separate uv project. `uv sync` from inside render_env produced 130 packages independently of the harness venv.
- **Files modified:** `pyproject.toml` (root), `assets/render_env/pyproject.toml`, `assets/render_env/uv.lock`
- **Commit:** Folded into Task 1 (`5d1e136`)

**2. [Rule 3 — Blocking] Pre-commit manifest hook tripped on scipy's bundled test WAVs**
- **Found during:** First `make check` after `uv sync` in render_env
- **Issue:** `tools/check_asset_manifest.py` walks `assets/` for any `.wav`. Once render_env was synced, `assets/render_env/.venv/lib/python3.11/site-packages/scipy/io/tests/data/*.wav` (22 scipy fixture clips) appeared in the walk, and INFRA-05 refused the commit because they were not listed in manifest.csv.
- **Fix:** Added a path-component skip: any path that contains a `.venv` or `site-packages` directory part is excluded. The substantive Pitfall 11 invariant (every project-owned audio file in manifest.csv) is preserved; we only excluded deps' own test fixtures from the walk.
- **Files modified:** `tools/check_asset_manifest.py`
- **Commit:** Folded into Task 1 (`5d1e136`)

**3. [Rule 3 — Blocking] Ruff E501 / S311 on hand-curated dialogue literals**
- **Found during:** First `make check` after templates.py landed
- **Issue:** Several utterance literals in `templates.py` exceed 100 chars (natural-language sentences like "Yeah, hi -- listen -- I just need to know -- can you handle a small business dispute?"). Reflowing them mid-sentence would change the rendered audio because Kokoro respects whitespace. Also `random.Random(seed)` triggers S311 (cryptographic-rng warning), which is benign here — the RNG drives deterministic dialogue ordering, not security.
- **Fix:** Added per-file-ignores for `assets/scripts/templates.py` (E501, S311) and `assets/render_env/*.py` (E501, S311, S603 — same justification as `assets/g711.py:54` for the explicit ffmpeg argv list). Logged in pyproject.toml with comment explaining why each is acceptable.
- **Files modified:** `pyproject.toml` (root)
- **Commit:** Folded into Task 1 (`5d1e136`)

**4. [Rule 1 — Bug] render_hesitation.py crashed on `audio.astype(np.float32)`**
- **Found during:** First `uv run python render_hesitation.py` invocation
- **Issue:** Kokoro 0.9.4 returns `torch.Tensor` (not numpy.ndarray) from the pipeline iterator. The plan's verbatim line `chunks.append(audio.astype(np.float32))` raised `AttributeError: 'Tensor' object has no attribute 'astype'`. (render_corpus.py worked because `np.concatenate` accepts torch tensors and astype runs on the concatenated numpy array.)
- **Fix:** Defensive conversion: `arr = audio.detach().cpu().numpy() if hasattr(audio, "detach") else np.asarray(audio); chunks.append(arr.astype(np.float32))`. Works whether kokoro returns a tensor or an ndarray.
- **Files modified:** `assets/render_env/render_hesitation.py`
- **Commit:** Task 2 (`3a28604`)

**5. [Rule 3 — Blocking] UP017 datetime.timezone.utc deprecation**
- **Found during:** Second `make check` after the renderer scripts landed
- **Issue:** Ruff's UP017 rule (Python 3.11 target) wants `datetime.UTC` instead of `timezone.utc`. The plan's verbatim code used `from datetime import datetime, timezone; datetime.now(tz=timezone.utc)`.
- **Fix:** `uv run ruff check --fix` rewrote all three render scripts to `from datetime import UTC, datetime; datetime.now(tz=UTC)`. Behaviorally identical; just shorter.
- **Files modified:** `assets/render_env/render_corpus.py`, `assets/render_env/render_g711_subset.py`, `assets/render_env/render_hesitation.py`
- **Commit:** Task 2 (`3a28604`)

### Architectural / Behavioral Deviations

None. All locked contracts honored:
- D-01 persona x intent x adversity matrix → 500 unique triples, full coverage (`test_full_matrix_coverage`).
- D-02 G.711 stratified subset → 100 neutral + 100 stressed via deterministic seed-42 shuffle (`test_corpus_g711_has_200_rows_with_strata`).
- D-03 hesitation set with ground-truth turn-end timestamps → 50 clips covering 4 hesitation kinds; turn_truth.json one-to-one with audio (`test_corpus_hesitation_has_clips_and_turn_truth`).
- Pitfall 1 venv isolation → render_env has its own pyproject + uv.lock + .venv (`test_render_env_lock_exists`).
- Pitfall 4 G.711 ffmpeg flags → `aresample=resampler=soxr:precision=28` is a literal grep-findable string in render_g711_subset.py and assets/g711.py.
- Pitfall 11 provenance → every audio row carries sha256 + generator_script + generator_seed + kokoro_revision (`test_every_audio_row_has_provenance`).
- INFRA-05 pre-commit hook → exits 0 after rendering (`test_pre_commit_hook_passes_after_render`).
- A3 sm_61 wheel → torch 2.5.1 resolved + downloaded for GTX 1070; render succeeded.

## Authentication Gates

None — Plan 04 is fully local. No cloud / API surface touched. Kokoro model weights pulled from Hugging Face (anonymous public download, default repo `hexgrad/Kokoro-82M`).

## Pitfall Closure Verification

| Pitfall | Status | Evidence |
|---------|--------|----------|
| **1** (asset-rendering venv must stay separate from harness venv) | CLOSED | `assets/render_env/uv.lock` exists; `assets/render_env/.venv/` is a real separate venv; root pyproject.toml has explicit comment that render_env is NOT a workspace member; `test_render_env_lock_exists` enforces. |
| **4** (G.711 default resampling artifacts) | UNCHANGED (Plan 03 closed) | render_g711_subset.py uses the same literal argv as assets/g711.py; verified `pcm_mulaw` + 8 kHz output via the bundled ffprobe pre-commit chain. |
| **11** (asset provenance discipline) | CLOSED | `assets/manifest.csv` has 754 rows with sha256 + generator_script + generator_seed + kokoro_revision; `test_every_audio_row_has_provenance` + `test_every_audio_sha_matches_file` enforce; pre-commit hook refuses unlisted audio. |
| **A3** (sm_61 wheel availability for GTX 1070) | CLOSED | `torch<=2.5.1` resolved to torch 2.5.1; `nvidia-smi` shows GTX 1070 active; 750 clips rendered successfully on it. |

## Operator Listen-Test Status

**AUTO-APPROVED** under chain mode. The operator should run the listen-test commands in the "Task 3" section above before scheduling Phase 3 G2 / G3 runners. Auto-approval is a procedural shortcut for the chain — it does not replace the listen-test as a quality gate.

If the listen-test surfaces any issue (DC offset, silent clip, wrong voice character), the renderer is idempotent and re-running with `--force` will replace the offending file. The manifest will update its sha row automatically; the pre-commit hook will catch any sha drift.

## Phase 2 Hand-off

`assets/manifest.csv` is now the single source of truth for all 5 corpora (UPL probes + benign control + TTS pairs from Plan 03 + 500-call + G.711 + hesitation from Plan 04). Phase 2 CUDA preflight + Phase 3 ROCm gates can read the manifest directly without re-deriving anything. Specifically:

1. **Phase 2 preflight** uses `corpus_500` (500 clips) for end-to-end pipeline validation on H100. The intent/adversity/persona columns let the runner stratify if needed.
2. **Phase 3 G2 (STT WER)** uses `corpus_g711` (200 clips, 100 neutral + 100 stressed) — reading the `path` column directly into faster-whisper.
3. **Phase 3 G3 (turn detection)** uses `corpus_hesitation` (50 clips) plus `turn_truth.json` for ground-truth labels.

Plan 05 (final foundation plan) inherits this committed state and can finalize INFRA-06 cost projections + reproducibility manifest without further asset work.

## Self-Check: PASSED

- `assets/scripts/templates.py` — FOUND (500-dialogue authoring; deterministic seed 42)
- `assets/scripts/dialogues.json` — FOUND (500 entries)
- `assets/render_env/pyproject.toml` — FOUND (`torch<=2.5.1` literal present)
- `assets/render_env/uv.lock` — FOUND (157 KB; 130+ pkgs)
- `assets/render_env/.python-version` — FOUND (`3.11`)
- `assets/render_env/render_corpus.py` — FOUND
- `assets/render_env/render_g711_subset.py` — FOUND (literal `aresample=resampler=soxr:precision=28`)
- `assets/render_env/render_hesitation.py` — FOUND (50-entry table; defensive torch->numpy)
- `assets/corpus_500/*.wav` — FOUND (500 files; one per dialogue)
- `assets/corpus_g711/*.wav` — FOUND (200 files; 100 neutral + 100 stressed)
- `assets/corpus_hesitation/*.wav` — FOUND (50 files)
- `assets/corpus_hesitation/turn_truth.json` — FOUND (50-entry dict; ground_truth_turn_end_ms per clip)
- `assets/manifest.csv` — FOUND (754 rows total; column 10 = kokoro_revision = 0.9.4 uniform on audio rows)
- `tests/test_dialogue_templates.py` — FOUND (8 tests pass)
- `tests/test_audio_corpora_manifest.py` — FOUND (8 tests pass)
- Commit `5d1e136` (Task 1) — FOUND in `git log`
- Commit `3a28604` (Task 2) — FOUND in `git log`
- `make check` — exits 0 (94 tests total)
- `uv run python tools/check_asset_manifest.py` — exits 0
- Plan verification block (6 commands) — all green

No stubs in this plan's deliverables — every audio file has real bytes, every manifest row has full provenance, turn_truth.json has real ground-truth durations measured from rendered audio.
