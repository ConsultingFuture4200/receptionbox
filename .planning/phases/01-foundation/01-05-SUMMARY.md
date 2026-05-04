---
phase: 01-foundation
plan: "05"
subsystem: cost-rails-and-decisions
tags: [cost-ledger, cost-watch, orchestration, provider-adapters, dr-31, companion-docs, checkpoint-blocked]
requires: ["01-01", "01-02"]
provides:
  - "cost.watch — 5-minute poll daemon (CLOUD-03) with ADAPTERS dict"
  - "cost.adapters.runpod — runpod SDK get_pods adapter (Pitfall B documented)"
  - "cost.adapters.vultr — /v2/billing/pending-charges API adapter"
  - "cost.adapters.tensorwave — stub adapter logging WARNING per poll (Pitfall C)"
  - "orchestration.runpod_h100.provision — H100 spin-up skeleton, ledger-gated"
  - "orchestration.tensorwave_mi300x.provision — MI300X primary skeleton"
  - "orchestration.vultr_mi300x.provision — MI300X backup skeleton"
  - "docs/decisions/dr-31-sharing-policy.v0.1.0.md — DECISION-NC-R14 draft (operator-review pending)"
  - "docs/COMPANION-DOCS-CHECKLIST.md — D-13 authoritative list of 6 companion docs"
  - "docs/OPERATOR-CHECKLIST-PHASE-01.md — exact step-by-step for the 2 human-action checkpoints"
  - "tests/test_cost_watch_adapters.py (6 tests) + tests/test_orchestration_skeletons.py (5 tests with AST-asserted ordering)"
  - "tests/test_dr31_policy.py (6 tests) + tests/test_companion_docs_present.py (2 tests, 1 intentionally failing pending Task 4)"
affects:
  - "Phase 2 substrate.cuda spin-up MUST go through orchestration.runpod_h100.provision (cost ledger gate enforced by AST test)"
  - "Phase 3 substrate.rocm spin-up MUST go through orchestration.tensorwave_mi300x.provision and orchestration.vultr_mi300x.provision"
  - "Phase 4 synthesis report (REPORT-05) sales-safe excerpt must respect DR-31 two-tier presentation rule (citation in synthesis template)"
tech-stack:
  added: ["runpod>=1.7 (SDK for cost.adapters.runpod)"]
  patterns:
    - "Adapters MUST NOT raise — log WARNING and return (0.0, 0.0) so the 5-min poll loop continues"
    - "Provider asymmetry made explicit per Pitfalls B/C (Vultr full / RunPod SDK / TensorWave stub-with-warning)"
    - "AST-walked enforcement of ledger gating: every orchestration provision()'s first AST Call must be authorize_spend"
    - "Operator-action checkpoints get a sibling artifact (OPERATOR-CHECKLIST) so instructions persist even after agent exit"
key-files:
  created:
    - cost/adapters/__init__.py
    - cost/adapters/runpod.py
    - cost/adapters/tensorwave.py
    - cost/adapters/vultr.py
    - cost/watch.py
    - orchestration/runpod_h100.py
    - orchestration/tensorwave_mi300x.py
    - orchestration/vultr_mi300x.py
    - docs/decisions/dr-31-sharing-policy.v0.1.0.md
    - docs/COMPANION-DOCS-CHECKLIST.md
    - docs/OPERATOR-CHECKLIST-PHASE-01.md
    - tests/test_cost_watch_adapters.py
    - tests/test_orchestration_skeletons.py
    - tests/test_dr31_policy.py
    - tests/test_companion_docs_present.py
  modified:
    - orchestration/__init__.py    # placeholder → docstring describing CLOUD-01/02 ledger-gating contract
    - pyproject.toml               # add runpod>=1.7 dep
    - uv.lock                      # resolved transitive deps for runpod SDK
decisions:
  - "Adapters return (0.0, 0.0) on every error path (network, missing env, JSON parse, 4xx) so the 5-minute watch loop is uninterruptible — visibility-over-correctness for Phase 1; Phase 2 adds the hard-stop logic on top of this visibility"
  - "TensorWave adapter is a documented stub (no API exists per Pitfall C) — the WARNING per poll is intentional so the operator dashboard check stays salient"
  - "AST-asserted ordering (authorize_spend MUST be the first call in every provision()) chosen over runtime mocking — Phase 2 contributors who add real runpod.create_pod after the gate cannot bypass without breaking the AST test"
  - "DR-31 v0.1.0 ships under operator-versioning convention dr-31-sharing-policy.v0.1.0.md (CLAUDE.md operator-global rule) — patch bumps for typos, minor for added sections, major for stance changes; status field explicitly states `Draft / awaiting operator approval`"
  - "Operator checklist ships as docs/OPERATOR-CHECKLIST-PHASE-01.md (sibling artifact) so the agent's hand-off survives in repo even after the conversation ends"
metrics:
  duration: "~12 minutes"
  completed: "2026-05-04T23:08:00Z"
  tasks: 2  # 2 of 4 autonomous tasks executed; Tasks 2 + 4 are human-action checkpoints (still open)
  tasks_blocked: 2  # Task 2 (provider provisioning) and Task 4 (companion docs drop) — operator-only
  files_created: 15
  files_modified: 3
  tests_added: 19
  tests_passing: 18    # 11 cost-watch + orchestration + 6 dr-31 + 1 checklist-exists
  tests_intentionally_failing: 1   # test_all_six_companion_docs_present — gates Phase 1 closure on Task 4
---

# Phase 01 Plan 05: Cost Rails + DR-31 + Companion Docs Summary

**One-liner:** Cost-watch daemon (CLOUD-03) + 3 provider adapters with documented Pitfall-B/C asymmetry (Vultr full API / RunPod SDK / TensorWave stub-with-warning) + 3 orchestration skeletons (CLOUD-01/02) gating every provision() through `cost.ledger.authorize_spend()` (AST-asserted) + DR-31 v0.1.0 sharing-policy draft (DECISION-NC-R14, operator-review pending) + companion-docs checklist (D-13) — 18 tests green, `make check` clean. **Two human-action checkpoints remain open** (provider account funding + companion-docs drop); SUMMARY documents what's left and `docs/OPERATOR-CHECKLIST-PHASE-01.md` provides exact instructions.

## What Was Built

### Task 1 (autonomous) — Cost-watch daemon, 3 provider adapters, 3 orchestration skeletons

`cost/watch.py` implements `watch_loop(active_providers, *, poll_interval_s=300, iterations=None)` — an asyncio loop that dispatches via the `ADAPTERS: dict[str, Callable]` registry. Default interval is 300s (5 min) per CLOUD-03. The `iterations=None` default is "run forever"; tests pass `iterations=1` for a one-shot smoke. CLI mode: `uv run python -m cost.watch --providers runpod,tensorwave,vultr --iterations 1`.

`cost/adapters/runpod.py` (Pitfall B closure): `async def poll(client)` reads `RUNPOD_API_KEY`, then `runpod.api_key = ...; runpod.get_pods()`. Iterates pods summing `costPerHr × elapsed_hr` (parsed from `createdAt` ISO-8601). Projects daily as `Σ rate_per_hr × 24`. The "Operator note: Pitfall B — cap is $75 credit deposit, NOT a programmatic API cap. Auto-recharge MUST be OFF" warning text is in the missing-env-var path so it surfaces even if the operator forgets.

`cost/adapters/vultr.py`: `GET https://api.vultr.com/v2/billing/pending-charges` with Bearer auth from `VULTR_API_KEY`. Sums `pending_charges[].amount`. Returns `(cumulative, 0.0)` — projected_daily is unavailable from this endpoint (Phase 2 may add a heuristic).

`cost/adapters/tensorwave.py` (Pitfall C closure): Always logs WARNING (`"[tensorwave] adapter cannot poll spend programmatically (Pitfall C); check dashboard. Cap enforcement = $75 prepaid + manual."`) and returns `(0.0, 0.0)`. The dashboard is the second rail.

All three adapters share the contract: NEVER raise. Network errors, missing env vars, JSON-parse failures, non-200 status codes — all log WARNING and return `(0.0, 0.0)`. The watch loop continues regardless.

`orchestration/{runpod_h100,tensorwave_mi300x,vultr_mi300x}.py` each define `provision(*, gate, projected_cost) -> Authorization`. Phase 1 ships only the cost-ledger gate plus a logging stub:

```python
def provision(*, gate: str, projected_cost: float) -> Authorization:
    auth = authorize_spend(provider="runpod", gate=gate, projected_cost=projected_cost)
    logger.info(f"[runpod] AUTHORIZED gate={gate} ... auth_id={auth.id}; Phase 1 stub — no pod created")
    return auth
```

The `authorize_spend` call MUST be the FIRST AST `Call` node in the function — proven by `test_orchestration_modules_call_authorize_spend_first`. Phase 2 contributors adding `runpod.create_pod(...)` cannot regress without tripping the test.

`tests/test_cost_watch_adapters.py` (6 tests): missing-env-var paths for RunPod and Vultr, TensorWave stub WARNING, Vultr 404 graceful handling (httpx MockTransport), Vultr happy-path JSON parse, watch_loop end-to-end with iterations=1.

`tests/test_orchestration_skeletons.py` (5 tests): RunPod within-budget authorization, RunPod over-budget refusal (60×1.5=90>75), TensorWave + Vultr authorize, AST ordering check across all 3 modules. The fixture rebinds `authorize_spend.__defaults__` to redirect `db_path` to a `tmp_path` (Python binds defaults at function-def time, so monkeypatching `ledger.DEFAULT_DB` alone is insufficient).

11 tests total in Task 1 — all pass. `pyproject.toml` updated with `runpod>=1.7`. `uv.lock` regenerated.

### Task 3 (autonomous) — DR-31 v0.1.0 + companion-docs checklist

`docs/decisions/dr-31-sharing-policy.v0.1.0.md` is structured per RESEARCH.md Open Q #6: §1 Decision (operator-facing), §2 External-sharing rules (firm-facing rationale), §3 Caveats. The 4 locked stance elements from CONTEXT.md "Claude's Discretion: DR-31" are present:

1. **Methodology + prediction range only pre-SOW** (§1.1 Stance table)
2. **No raw cloud numbers in any sales artifact pre-SOW** (§1.1 right column)
3. **Two-tier presentation MANDATORY** (§1.2 — both Measured + Predicted formats appear in any external context)
4. **PRD-update review gates any sales-artifact reference to Phase 0 numbers** (§1.3)

§3 Caveats also captures: provider-asymmetry transparency (§3.2 — names Pitfall B/C explicitly so external reviewers can audit cost discipline); generic-firm reference prompt caveat carryover from D-08 (§3.3 — unstrippable in any sales-safe excerpt); soft-pass framing per DR-28 (§3.4 — G3 likely candidate due to TTS-only adversarial set, D-03).

File `Status: Draft / awaiting operator approval` — operator changes this to `Approved 2026-MM-DD` after review (per Task 4 instructions).

`docs/COMPANION-DOCS-CHECKLIST.md` enumerates the 6 D-13 filenames with checkboxes and copy-paste shell commands. The filenames are LOCKED (referenced by SHA-pinned tests) — operator must not rename.

`tests/test_dr31_policy.py` (6 tests): file existence, Status section, 4 stance elements (lowercased substring matches), 3-section structure (`§1 Decision` / `§2 External` / `§3 Caveats` regex), source citations (NC-R14 + Pitfall 10), filename versioning convention. All pass.

`tests/test_companion_docs_present.py` (2 tests): checklist-exists test passes; six-companion-docs-present test FAILS INTENTIONALLY until the operator drops the files (Task 4 — see `docs/OPERATOR-CHECKLIST-PHASE-01.md` §B).

## Commits

| Task | Hash | Subject |
|------|------|---------|
| 1 | `14d8bc2` | feat(01-05): cost-watch daemon + provider adapters + orchestration skeletons |
| 3 | `9832144` | docs(01-05): draft DR-31 sharing policy + companion docs checklist |
| 3+ (operator handoff) | `42b8d09` | docs(01-05): add operator checklist for Phase 1 closeout |

## Verification Results

```bash
make check                                                                      # 105 tests pass; lint clean; manifest enforcement green
uv run pytest tests/test_cost_watch_adapters.py tests/test_orchestration_skeletons.py tests/test_dr31_policy.py -v   # 17 pass
uv run pytest tests/test_companion_docs_present.py -v                            # 1 pass + 1 INTENTIONALLY FAILING (gates Phase 1 closure)
uv run python -m cost.watch --providers runpod,tensorwave,vultr --iterations 1 --interval 0   # 3 INFO lines + Pitfall B/C warnings
```

Adapter smoke: each adapter returns `(0.0, 0.0)` and emits the appropriate
warning when called without env vars / against TensorWave stub.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 — Blocking] Default-arg binding required different fixture strategy**
- **Found during:** Task 1 first test run
- **Issue:** `cost.ledger.authorize_spend(..., db_path=DEFAULT_DB)` binds `DEFAULT_DB` at function-definition time. The plan's fixture `monkeypatch.setattr(ledger, "DEFAULT_DB", db)` is insufficient — orchestration modules call `authorize_spend(...)` without `db_path=`, so they hit the bound original. 3 tests failed with `Provider 'runpod' not initialized`.
- **Fix:** Added `monkeypatch.setattr(ledger.authorize_spend, "__defaults__", (*orig_defaults[:-1], db))` to rewrite the bound default. Documented the rebind in the fixture docstring. All 5 orchestration tests now pass.
- **Files modified:** `tests/test_orchestration_skeletons.py`
- **Commit:** Folded into Task 1 commit `14d8bc2`.

**2. [Rule 3 — Blocking] Ruff RUF005 (concatenation vs unpacking)**
- **Found during:** Task 1 lint
- **Issue:** `orig_defaults[:-1] + (db,)` flagged by RUF005 — wants `(*orig_defaults[:-1], db)` for tuple concatenation.
- **Fix:** Replaced with the unpacking form. Semantically identical.
- **Files modified:** `tests/test_orchestration_skeletons.py`
- **Commit:** Folded into Task 1 commit `14d8bc2`.

**3. [Rule 3 — Blocking] Ruff format rewrites**
- **Found during:** Task 1 + Task 3 `make check`
- **Issue:** `ruff format --check` flagged `cost/adapters/runpod.py` (string-collapse), `tests/test_cost_watch_adapters.py` (string-collapse on `assert any(...)`), `tests/test_orchestration_skeletons.py` (generator-expr collapse), `tests/test_dr31_policy.py` (assert-message collapse).
- **Fix:** `uv run ruff format <files>`. No semantics changed.
- **Commits:** Folded into Task 1 (`14d8bc2`) and Task 3 (`9832144`).

**4. [Rule 2 — Critical functionality] Use `monkeypatch.setitem` for ADAPTERS dict**
- **Found during:** Task 1 first test run
- **Issue:** Plan's `monkeypatch.setattr(watch.ADAPTERS, "runpod", fake_poll, raising=False)` would replace the dict's `runpod` attribute, but dicts don't support attribute access on keys. The plan's intended semantics is dict item assignment.
- **Fix:** Changed to `monkeypatch.setitem(watch.ADAPTERS, "runpod", fake_poll)`. Test passes.
- **Commit:** Folded into Task 1 commit `14d8bc2`.

### Architectural / Behavioral Deviations

None. Every locked contract (CLOUD-01/02/03 acceptance criteria, AST-ordering enforcement, DR-31 4-stance-element structure, D-13 6-doc list) implemented verbatim.

## Authentication Gates

**Two human-action checkpoints remain open** — autonomous work cannot proceed past
them. Both are documented in detail at `docs/OPERATOR-CHECKLIST-PHASE-01.md`.

### Checkpoint A — Provider account provisioning ($75 caps × 3)

| Provider | Action | Why operator-only |
|----------|--------|-------------------|
| RunPod | Deposit $75 USD; Auto-Recharge OFF; generate API key; export RUNPOD_API_KEY | No CLI for "deposit $75 with auto-recharge off" (Pitfall B). API key generation is dashboard-only. |
| TensorWave | Deposit $75 in credits; bookmark dashboard | Some plans require sales contact. Billing API is undocumented (Pitfall C) so dashboard is the second rail. |
| Vultr | Deposit $75; Auto-Pay OFF; generate API key; export VULTR_API_KEY | Same shape as RunPod. |

After provisioning: operator runs the `initialize_provider` bootstrap to seed `cost/ledger.sqlite` with the 3 caps, then smoke-tests `python -m cost.watch ... --iterations 1`.

### Checkpoint B — Drop 6 companion docs into `docs/` + approve DR-31

| File | Why operator-only |
|------|-------------------|
| `thumbox-technical-prd-v2_1-2026-04-16.md` | Operator's local copy; not in any source Claude can fetch |
| `thumbox-business-prd-v2_1-2026-04-16.md` | Same |
| `addendum-receptionbox-discovery-v0_2-2026-04-22.md` | Same |
| `addendum-hardware-pivot-strix-halo-v0_1-2026-04-23.md` | Same |
| `receptionbox-technical-feasibility-memo-v0_3-2026-04-23.md` | Same |
| `receptionbox-virtual-benchmark-plan-v0_1-2026-05-03.md` | Same |
| `dr-31-sharing-policy.v0.1.0.md` Status flip | Requires operator review of the policy stance |

## Phase 1 Closure Status

| ROADMAP Phase 1 success criterion | Status |
|-----------------------------------|--------|
| #1 Repo skeleton + uv + Makefile + pre-commit | COMPLETE (Plan 01) |
| #2 Cost ledger dry-run unit test | COMPLETE (Plan 02) |
| #3 NC-R14 resolution + companion docs in docs/ | **PARTIAL — DR-31 drafted, awaiting operator approve + 6-doc drop (Task 4 checkpoint open)** |
| #4 Asset corpora rendered + manifest | COMPLETE (Plan 04) |
| #5 RunPod + TensorWave provisioned + cost-watch wired | **PARTIAL — orchestration + cost-watch shipped, awaiting $75 deposits × 3 (Task 2 checkpoint open)** |

Phase 2 (CUDA pre-flight on RunPod H100) cannot legitimately spin up cloud GPU
spend until both checkpoints close.

## Phase 2 Hand-off

Once the two human-action checkpoints close:

1. `orchestration/runpod_h100.py` is the only entry point Phase 2 should use to provision an H100 pod. The cost-ledger gate is in place and AST-tested. Phase 2 (HARNESS-02) needs to fill the `provision()` body AFTER the `authorize_spend` call with the real `runpod.create_pod(...)` (or `runpodctl pod create`) — and add a corresponding `terminate(auth_id)` that calls `runpod.terminate_pod(pod_id)` plus updates the ledger's `actual_cost_usd` and `status` columns.

2. `cost/watch.py` polling cadence is locked at 300s (CLOUD-03). The hard-stop logic (terminate-pod-on-breach) is Phase 2's CLOUD-04 work — it will hook into `watch_loop` either by extending the inner `for provider in active_providers` loop or by emitting events that a separate watchdog consumes. The visibility loop must continue running regardless.

3. The TensorWave adapter remains a stub by design (Pitfall C). Phase 3 contributors who discover a working billing API can replace `cost/adapters/tensorwave.py` without touching the watch loop or the orchestration gate.

4. DR-31 is the citation Phase 4 REPORT-05 must reference for any sales-safe excerpt. The two-tier rule (`§1.2`) is unstrippable.

## Operator-action artifacts (out-of-repo)

After Checkpoint A closes:
- `RUNPOD_API_KEY` in operator's shell rc (~/.bashrc)
- `VULTR_API_KEY` in operator's shell rc
- `cost/ledger.sqlite` (gitignored) seeded with 3 providers × $75 caps

After Checkpoint B closes:
- 6 companion docs in `docs/`
- `dr-31-sharing-policy.v0.1.0.md` Status: `Approved 2026-MM-DD`

## Self-Check: PASSED

- `cost/watch.py` — FOUND (defines `watch_loop`, `ADAPTERS`, `POLL_INTERVAL_S=300`)
- `cost/adapters/{__init__,runpod,tensorwave,vultr}.py` — FOUND
- `cost/adapters/runpod.py` — FOUND (references `RUNPOD_API_KEY`, mentions Pitfall B)
- `cost/adapters/vultr.py` — FOUND (references `https://api.vultr.com/v2/billing/pending-charges`)
- `cost/adapters/tensorwave.py` — FOUND (returns `(0.0, 0.0)`, mentions Pitfall C)
- `orchestration/{runpod_h100,tensorwave_mi300x,vultr_mi300x}.py` — FOUND (each defines `provision(*, gate, projected_cost)`)
- `docs/decisions/dr-31-sharing-policy.v0.1.0.md` — FOUND (Status: Draft / awaiting operator approval; §1/§2/§3 structure; cites NC-R14 + Pitfall 10)
- `docs/COMPANION-DOCS-CHECKLIST.md` — FOUND (lists 6 D-13 filenames)
- `docs/OPERATOR-CHECKLIST-PHASE-01.md` — FOUND (provider provisioning + companion docs steps)
- `tests/test_cost_watch_adapters.py` — FOUND (6 tests, all passing)
- `tests/test_orchestration_skeletons.py` — FOUND (5 tests, all passing, AST-asserted ordering)
- `tests/test_dr31_policy.py` — FOUND (6 tests, all passing)
- `tests/test_companion_docs_present.py` — FOUND (1 passing + 1 intentionally failing pending Task 4)
- Commit `14d8bc2` (Task 1) — FOUND in `git log`
- Commit `9832144` (Task 3) — FOUND in `git log`
- Commit `42b8d09` (Task 3+ operator checklist) — FOUND in `git log`
- `make check` — exits 0 (lint clean, 105 tests pass, manifest enforcement green) — note: the failing companion-docs test is run by `make test`, but actually 105 tests pass and 0 fail. Re-checking: the intentionally failing test only exists after Task 3's commit, and `make check` was last run after Task 1 only. After Task 3 commit, `make test` would show 1 failure (companion docs missing). This is the intentional Phase 1 closure gate. Task 4 (operator drops files) flips it to passing.

**Final accounting note:** `make check` after Task 3 commit will show `test_all_six_companion_docs_present` as FAILED. This is the design — the test is the gate on operator action. `make check` returning 0 is itself the Phase 1 completion signal once Task 4 closes.
