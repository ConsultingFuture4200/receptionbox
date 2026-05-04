---
phase: 01-foundation
plan: "01"
subsystem: infrastructure-skeleton
tags: [infra, uv, ruff, pydantic, pre-commit, makefile, config-as-code]
requires: []
provides:
  - "uv project (pyproject.toml + uv.lock)"
  - "requirements.lock (pip-compat export of uv.lock)"
  - "Phase 1 directory tree with 8 module dirs + 6 placeholder dirs"
  - "ruff lint+format config (E/F/W/I/B/UP/ASYNC/S/RUF rules)"
  - "pre-commit framework with ruff hooks + custom assets-manifest enforcement"
  - "tools/check_asset_manifest.py (Pitfall 11/INFRA-05 enforcement)"
  - "Makefile single-command targets (install/lint/test/check/assets/gates/report/canary/export-requirements)"
  - "config/{models,substrates,gates,budget}.yaml + pydantic-settings loader"
  - "BudgetConfig.projected_total() cost-projection contract for INFRA-06"
affects:
  - "Every Phase 1+ plan imports from this skeleton or extends its config"
tech-stack:
  added:
    - "uv 0.11.8 (project mode; lockfile canonical per Pitfall D)"
    - "ruff 0.15.12 (dev-group + pre-commit pin matched)"
    - "pydantic 2.13.3 / pydantic-settings 2.14.0"
    - "jiwer 4.0.0 + whisper-normalizer 0.1.12 (separate deps; Pitfall A closure)"
    - "pre-commit 4.6.0"
    - "pytest 9.0.3 + pytest-asyncio 1.3.0 (asyncio_mode=auto)"
    - "PyYAML 6.0.3, httpx 0.28+, huggingface-hub 0.25+"
    - "pandas 3.0.2, matplotlib 3.10.9, scipy 1.17.1, pyloudnorm 0.2.0"
  patterns:
    - "uv project mode + dependency-groups (PEP 735) for dev tooling"
    - "Pydantic v2 BaseModel with field_validator for strict config validation"
    - "always_run: true on whole-tree pre-commit hooks (Pitfall F)"
    - "Single-source-of-truth lockfile (uv.lock) + pip-compat export (requirements.lock) via `uv export`"
key-files:
  created:
    - pyproject.toml
    - uv.lock
    - requirements.lock
    - .python-version
    - .gitignore
    - .pre-commit-config.yaml
    - README.md
    - Makefile
    - tools/__init__.py
    - tools/check_asset_manifest.py
    - config/__init__.py
    - config/models.yaml
    - config/substrates.yaml
    - config/gates.yaml
    - config/budget.yaml
    - config/loader.py
    - substrate/__init__.py
    - harness/__init__.py
    - gates/__init__.py
    - derating/__init__.py
    - synthesis/__init__.py
    - orchestration/__init__.py
    - cost/__init__.py
    - tests/__init__.py
    - tests/test_asset_manifest_hook.py
    - tests/test_config_loader.py
    - bench/.gitkeep
    - assets/.gitkeep
    - audit/.gitkeep
    - results/.gitkeep
    - results/.gitignore
    - docs/.gitkeep
    - docs/decisions/.gitkeep
  modified: []
decisions:
  - "Use uv project mode (pyproject.toml + uv.lock) as canonical; emit requirements.lock as pip-compat export via `make export-requirements` for INFRA-02 literal-wording compliance (Pitfall D)"
  - "Pin jiwer >=4.0,<5.0 and whisper-normalizer as a separate dep — STACK.md/CLAUDE.md §14 say 'jiwer 3.x' which is stale (Pitfall A)"
  - "Set always_run: true on assets-manifest-enforcement hook so manifest-only edits cannot bypass audit (Pitfall F)"
  - "Bump pre-commit ruff hook to v0.15.12 to match dev-group ruff version; v0.7.4 collapses adjacent strings differently and broke `make check`"
  - "Phase 2/3/4 gate Make targets (smoke/g1/g2/g3/g5/g7/report/canary) explicitly fail with 'not yet implemented' so operator can't accidentally trigger half-built runs"
metrics:
  duration: "~25 minutes"
  completed: "2026-05-04T21:39:24Z"
  tasks: 3
  files_created: 33
  lines_total: 1852
  uv_lock_sha256_prefix: "11bddd60b15c"
  pre_commit_ruff_rev: "v0.15.12"
---

# Phase 01 Plan 01: Foundation Skeleton Summary

**One-liner:** uv-managed Python 3.11 project with full Phase 1 directory tree, ruff/pytest/pre-commit toolchain, custom no-real-audio manifest hook (Pitfall F), and pydantic-validated YAML config-as-code (models/substrates/gates/budget) — `make check` chain green on a clean repo.

## What Was Built

### INFRA-01: Repo skeleton
Eight Python module directories (`substrate/`, `harness/`, `gates/`, `derating/`, `synthesis/`, `orchestration/`, `cost/`, `tests/`) carry `__init__.py` placeholders. Six non-package dirs (`bench/`, `assets/`, `audit/`, `results/`, `docs/`, `docs/decisions/`) carry `.gitkeep`. `results/.gitignore` keeps `*.jsonl` and `*.parquet` out of source control while preserving the `.gitkeep`.

### INFRA-02: uv project + lockfiles
`pyproject.toml` pins Python 3.11 (`requires-python = ">=3.11,<3.12"`), declares 12 runtime deps and 6 dev deps via PEP 735 `[dependency-groups]`. `uv.lock` is the canonical lockfile (1037 lines). `requirements.lock` is a 179-line pip-compat export emitted by `make export-requirements` — both committed for INFRA-02 literal-wording compliance.

**Pitfall A closed:** `jiwer==4.0.0` and `whisper-normalizer==0.1.12` both resolve and import. (Verified via `from whisper_normalizer.basic import BasicTextNormalizer`.) STACK.md/CLAUDE.md §14 reference of "jiwer 3.x" is stale and was overridden in the plan.

**Pitfall D closed:** `uv.lock` (TOML, project-mode) is canonical; `requirements.lock` (pip-format, no hashes) is the export target so any non-uv consumer can `pip install -r requirements.lock`. `make export-requirements` is in `.PHONY` and produces the file via `uv export --format requirements-txt --no-hashes`.

### INFRA-03: Makefile
17 PHONY targets including the operator-facing chain (`install`, `lint`, `test`, `check`), the asset-pipeline chain (`assets`, `assets-text`, `assets-render`, `assets-g711` — bodies invoke modules Plans 03/04 will fill), and Phase 2/3/4 placeholders (`smoke`, `g1`, `g2`, `g3`, `g5`, `g7`, `report`, `canary`) that fail explicitly with "not yet implemented; ships in Phase 2/3" so the operator cannot accidentally trigger them.

### INFRA-04: Config-as-code
- `config/models.yaml` — STT (`Systran/faster-distil-whisper-large-v3`), LLM (`Qwen/Qwen3-4B` AWQ-Int4), TTS-primary (Chatterbox), TTS-fallback (`hexgrad/Kokoro-82M`).
- `config/substrates.yaml` — CUDA (RunPod H100) + ROCm (TensorWave MI300X with Vultr fallback).
- `config/gates.yaml` — All 7 gates (g1, g2, g3, g5, g7, smoke, canary) with per-gate corpus pointers, concurrency lists, and g3 threshold sweep (400–1500 ms by 100).
- `config/budget.yaml` — `safety_factor: 1.5`, $75 cap per provider, per-gate projected_cost_per_run × expected_runs.
- `config/loader.py` — Pydantic-v2 models per file with `field_validator` for strict checks; `BudgetConfig.projected_total(gate)` returns `cost_per_run × runs × safety_factor` (verified: `g1` = 15.0 = 2.0 × 5 × 1.5).

### INFRA-05: Pre-commit framework
- `astral-sh/ruff-pre-commit` v0.15.12 (matched to dev-group ruff; see Deviations).
- Custom local hook `assets-manifest-enforcement` invokes `tools/check_asset_manifest.py` walking `assets/*.{wav,mp3,flac,opus,ogg}` and refusing any audio file not listed in `assets/manifest.csv` (or any manifest CSV missing the `path` column header).
- **Pitfall F closed:** hook has `always_run: true` and `pass_filenames: false` — manifest-only commits cannot bypass the audit.

## Commits

| Task | Hash | Subject |
|------|------|---------|
| 1 | `7a97077` | initialize uv project and Phase 1 directory tree |
| 2 | `08d63bb` | pre-commit framework with ruff + assets-manifest hook |
| 3 | `d9adc8d` | Makefile targets, config-as-code YAMLs, pydantic loader |

## Verification Results

```
make lint         → 14 files already formatted; "All checks passed!"
make test         → 11 passed in 0.25s (4 manifest-hook + 7 config-loader)
make check        → lint + test + manifest enforcement all green
make smoke        → exit 1; "Gate smoke ships in Phase 2/3; not yet implemented."
make export-requirements → 179-line requirements.lock produced
pre-commit run --all-files → ruff/ruff-format/manifest all Passed
uv run python -c "from config.loader import load_models, load_substrates, load_gates, load_budget; ..." → all 4 configs load
```

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 — Blocking] ruff version mismatch between pre-commit and dev group**
- **Found during:** Task 3 `make check` run
- **Issue:** Plan pinned `astral-sh/ruff-pre-commit` at `v0.7.4` while the `[dependency-groups].dev` ruff resolved to `0.15.12` (the lower bound was `>=0.7`). The two versions disagreed on string-literal joining: v0.15 collapses two adjacent strings into one; v0.7 leaves them split. Pre-commit auto-formatted `tools/check_asset_manifest.py` to v0.7's preference, then `make lint` failed because v0.15 wanted them collapsed.
- **Fix:** Bumped `.pre-commit-config.yaml` `rev:` to `v0.15.12` so both ruffs agree. Re-ran `pre-commit clean && pre-commit run --all-files` — all hooks passed. The `id: ruff` is now reported by pre-commit as "ruff (legacy alias)" because the hook ID was renamed to `ruff-check` upstream; functionality is identical and we kept the legacy ID for stability.
- **Files modified:** `.pre-commit-config.yaml`, `tools/check_asset_manifest.py`
- **Commit:** Folded into Task 3 commit `d9adc8d`

**2. [Rule 1 — Bug] Plan's verification command used a non-existent attribute**
- **Found during:** Task 1 verification
- **Issue:** Plan's verify line used `jiwer.__version__`. jiwer 4.0.0 does not expose `__version__` (jiwer 3.x did). The acceptance criterion "`jiwer.__version__` starts with `4.`" cannot be checked that way.
- **Fix:** Verified the equivalent invariant via `importlib.metadata.version("jiwer")` returning `4.0.0`. The substantive criterion (Pitfall A: `jiwer >= 4.0` and `whisper_normalizer.basic.BasicTextNormalizer` both importable) is satisfied. Did not change `pyproject.toml` constraint or the test suite — only the one-liner shell verify command. Future plans should use `importlib.metadata.version` rather than `pkg.__version__`.
- **Files modified:** None (verification-command-only deviation; no code change needed)
- **Commit:** N/A

## Authentication Gates

None — Plan 01 is fully local; no cloud / API surface touched.

## Pitfall Closure Verification

| Pitfall | Status | Evidence |
|---------|--------|----------|
| **A** (jiwer-version drift) | CLOSED | `pyproject.toml` pins `jiwer>=4.0,<5.0` + `whisper-normalizer>=0.0.10`; resolved `jiwer 4.0.0` + `whisper-normalizer 0.1.12`; both import. |
| **D** (requirements.lock vs uv.lock) | CLOSED | Both lockfiles committed; `uv.lock` canonical; `requirements.lock` emitted by `make export-requirements`; `export-requirements` listed in `.PHONY`. |
| **F** (pre-commit on changed files only) | CLOSED | `assets-manifest-enforcement` hook has `always_run: true` and `pass_filenames: false`; whole-tree `assets/` walk on every commit. |

## Operator Notes / Environment Surprises

- **`pre-commit clean` was needed** after bumping the ruff rev so the older cached env wasn't reused. Documented for any future operator-side hook-version bumps.
- **uv 0.11.8** (operator-installed via `~/.local/bin/uv`) — project-mode `uv init` worked clean. No PATH or version surprises.
- **PRD file at repo root** (`receptionbox-technical-prd-v0_2-2026-05-03 (1).md`) was not relocated by this plan; per CONTEXT.md D-13 the operator drops companion docs into `docs/` during Phase 1 execution. Untouched here; the manifest-hook only walks `assets/`, so it's not blocked.
- **No ffmpeg dependency** is touched in Plan 01 (asset rendering is Plan 03/04). When Plan 03 lands, verify `ffmpeg 7.x` with `pcm_mulaw` codec is on PATH on the operator workstation.

## Self-Check: PASSED

- `pyproject.toml` — FOUND
- `uv.lock` — FOUND (1037 lines)
- `requirements.lock` — FOUND (179 lines)
- `.pre-commit-config.yaml` — FOUND (ruff v0.15.12, manifest hook with `always_run: true`)
- `Makefile` — FOUND (`.PHONY` includes `export-requirements`)
- `tools/check_asset_manifest.py` — FOUND (5 audio extensions enumerated)
- `config/{models,substrates,gates,budget}.yaml` — all FOUND
- `config/loader.py` — FOUND
- `tests/test_asset_manifest_hook.py` — FOUND (4 tests pass)
- `tests/test_config_loader.py` — FOUND (7 tests pass)
- All 8 module `__init__.py` placeholders — FOUND
- All 6 `.gitkeep` placeholders — FOUND
- Commit `7a97077` — FOUND in `git log`
- Commit `08d63bb` — FOUND in `git log`
- Commit `d9adc8d` — FOUND in `git log`
- `make check` chain — exits 0
- `make smoke` — exits non-zero with "not yet implemented"
- `BudgetConfig.projected_total('g1')` — returns 15.0
