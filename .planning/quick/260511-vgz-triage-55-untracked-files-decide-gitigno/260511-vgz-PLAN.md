---
quick_id: 260511-vgz
description: "Triage 55 untracked files: decide gitignore vs atomic commits"
mode: quick
tasks: 5
branch: main
autonomous: true
files_modified:
  - .gitignore
  - docs/receptionbox-technical-prd-v0_2-2026-05-06.md
  - .planning/debug/dev-1083-g2-whisper-hallucination.md
  - tools/find_runpod_volume.py
  - tools/probe_runpod_dc.py
  - tools/probe_runpod_stock.py
  - results/_pulled/**
  - results/g1/**
  - results/g2/**
  - results/g3/**
  - results/g5/**
  - results/preflight/**
  - results/smoke/**
---

<objective>
Triage 55 untracked items accumulated during Phase 02 / Phase 03 work into 5 atomic commits — gitignore for sensitive items, real commits for source/docs/tools/evidence — so the working tree is clean before Phase 03 re-plans against the DR-39 Jetson Orin pivot.

Purpose: Sequence matters. The .gitignore patch lands FIRST and is verified to remove sensitive paths from `git status` BEFORE any further `git add` runs. Each subsequent commit stages explicit paths only (never `-A`/`.`). Operator's Commit Engine style applies throughout.

Output: 5 commits on `main`, working tree clean except for any items intentionally ignored.
</objective>

<context>
@.planning/STATE.md
@./CLAUDE.md

Authoritative findings (from orchestrator scout; do NOT re-discover):

**Sensitive (ignore, never commit):**
- `secrets/rboxkey.md` — plaintext RunPod API key (`rpa_78JOR9...`)
- `.claude/settings.local.json` — same RunPod key embedded in an "allow" permission rule
- `.claude/scheduled_tasks.lock` — local Claude-Code runtime state
- `.claude/worktrees/` — local Claude-Code worktree state

Important: ignore specific `.claude/*` paths, NOT the whole `.claude/` dir (shared agent/skill configs may land there later).

**Source / docs (commit):**
- `docs/receptionbox-technical-prd-v0_2-2026-05-06.md`
- `.planning/debug/dev-1083-g2-whisper-hallucination.md`
- `tools/find_runpod_volume.py`, `tools/probe_runpod_dc.py`, `tools/probe_runpod_stock.py`

**Evidence (commit — STACK.md §9 policy):**
- `results/_pulled/` (14 pod-id-named subdirs, 380K)
- `results/g1/`, `results/g2/`, `results/g3/`, `results/g5/` (44K each)
- `results/preflight/` (128K, 31 timestamped JSONs)
- `results/smoke/` (36K)
- Total <1 MB. `.gitignore` already excludes `results/index.sqlite` (DB) but not artifact files — confirming committable-evidence intent.

**Hard rules (operator global CLAUDE.md):**
- Never `git add -A` / `git add .` — stage explicit paths only
- Never `--no-verify`
- Never `git push`
- Don't add Claude as co-author
- Commit Engine style: `type(scope): summary` + bullet body explaining why
</context>

<tasks>

<task type="auto">
  <name>Task 1: gitignore the sensitive paths (MUST be first commit)</name>
  <files>.gitignore</files>
  <action>
Append a new section to `.gitignore` (after the existing "Asset audio outputs" comment block) that excludes the four sensitive paths. Use the Edit tool to add this block verbatim at the end of the file (preserve trailing newline):

```
# Secrets / local runtime state (must NEVER be committed)
# secrets/rboxkey.md contains a live RunPod API key (rpa_...);
# .claude/settings.local.json embeds the same key inside an "allow" permission rule.
# Ignore specific .claude/* paths only — do NOT ignore the whole .claude/ dir,
# since shared agents/skills configs may live there.
secrets/
.claude/settings.local.json
.claude/scheduled_tasks.lock
.claude/worktrees/
```

Then stage and commit ONLY the .gitignore change:

```
git add .gitignore
git commit -m "$(cat <<'EOF'
chore(gitignore): exclude secrets/ and local .claude runtime state

- secrets/rboxkey.md is a plaintext RunPod API key — must never be tracked
- .claude/settings.local.json embeds the same RunPod key inside an "allow"
  permission rule — equally sensitive, same ignore rationale
- .claude/scheduled_tasks.lock and .claude/worktrees/ are local Claude Code
  runtime state, not source
- scoped to specific .claude/* paths (not the whole dir) so shared
  .claude/agents/ or .claude/skills/ configs can still be committed later
EOF
)"
```

After the commit, run `git status --short` and verify NONE of these paths appear in the output:
- `secrets/`, `secrets/rboxkey.md`
- `.claude/settings.local.json`
- `.claude/scheduled_tasks.lock`
- `.claude/worktrees/`

If any of those four still appear in `git status`, STOP and surface the discrepancy — do not proceed to Task 2. (Cause: the .gitignore line did not match; fix the pattern before continuing.)
  </action>
  <verify>
    <automated>git log -1 --format='%s' | grep -q '^chore(gitignore): exclude secrets/ and local .claude runtime state$' && git status --short | grep -E '^\?\? (secrets/|\.claude/settings\.local\.json|\.claude/scheduled_tasks\.lock|\.claude/worktrees/)' && exit 1 || exit 0</automated>
  </verify>
  <done>One commit on main with subject `chore(gitignore): exclude secrets/ and local .claude runtime state`. `git status --short` shows zero of the 4 sensitive paths. Working tree still shows the docs / debug / tools / results untracked items pending later tasks.</done>
</task>

<task type="auto">
  <name>Task 2: commit the receptionBOX PRD v0.2</name>
  <files>docs/receptionbox-technical-prd-v0_2-2026-05-06.md</files>
  <action>
Stage and commit the PRD as a single atomic doc-commit:

```
git add docs/receptionbox-technical-prd-v0_2-2026-05-06.md
git commit -m "$(cat <<'EOF'
docs(prd): add receptionBOX technical PRD v0.2 (2026-05-06)

- authoritative PRD input referenced from CLAUDE.md Constraints
  ("receptionBOX PRD v0.2 is authoritative input", per STATE.md Decisions)
- predates the DR-39 Jetson Orin pivot; product spec itself is
  hardware-agnostic so v0.2 remains the live PRD for Phase 0 gate semantics
- landed in docs/ alongside the other companion documents committed in e16d86e
EOF
)"
```

Do not stage any other path. Use the Bash tool, not heredoc echo to a file.
  </action>
  <verify>
    <automated>git log -1 --format='%s' | grep -q '^docs(prd): add receptionBOX technical PRD v0.2' && git log -1 --name-only --format='' | grep -Fxq 'docs/receptionbox-technical-prd-v0_2-2026-05-06.md' && [ "$(git log -1 --name-only --format='' | grep -v '^$' | wc -l)" = "1" ]</automated>
  </verify>
  <done>Commit on main with subject `docs(prd): add receptionBOX technical PRD v0.2 (2026-05-06)`. Exactly one file changed in that commit.</done>
</task>

<task type="auto">
  <name>Task 3: commit the DEV-1083 G2 Whisper hallucination debug session</name>
  <files>.planning/debug/dev-1083-g2-whisper-hallucination.md</files>
  <action>
Stage and commit the GSD debug session file:

```
git add .planning/debug/dev-1083-g2-whisper-hallucination.md
git commit -m "$(cat <<'EOF'
docs(debug): add DEV-1083 G2 Whisper hallucination root-cause session

- GSD debug session documenting H1 CONFIRMED + fix landed for the G2
  Whisper "noise reinterpretation" hallucination surfaced in Phase 02
- referenced from STATE.md ("WER 2.55% re-confirmed (DEV-1083 intact)" in
  Phase 02-08 retroactive entry); commit makes the underlying analysis
  reproducible from the repo, not just operator memory
- evidence trail for the synthesis report's G2 section
EOF
)"
```
  </action>
  <verify>
    <automated>git log -1 --format='%s' | grep -q '^docs(debug): add DEV-1083' && git log -1 --name-only --format='' | grep -Fxq '.planning/debug/dev-1083-g2-whisper-hallucination.md' && [ "$(git log -1 --name-only --format='' | grep -v '^$' | wc -l)" = "1" ]</automated>
  </verify>
  <done>Commit on main with subject starting `docs(debug): add DEV-1083`. Exactly one file changed.</done>
</task>

<task type="auto">
  <name>Task 4: commit the 3 RunPod tooling scripts</name>
  <files>tools/find_runpod_volume.py, tools/probe_runpod_dc.py, tools/probe_runpod_stock.py</files>
  <action>
Stage all three RunPod utility scripts together (they form one logical RunPod-tooling unit) and commit:

```
git add tools/find_runpod_volume.py tools/probe_runpod_dc.py tools/probe_runpod_stock.py
git commit -m "$(cat <<'EOF'
tools(runpod): add RunPod volume + datacenter + stock probe utilities

- find_runpod_volume.py: prints RunPod network-volume id by name; used
  during Phase 02 pull-back pattern (results/_pulled/<pod-id>/) when
  reattaching volumes to diag pods
- probe_runpod_dc.py: per-datacenter GPU availability probe; surfaces
  US-CA-2 / US-KS-2 stock asymmetry for H100 and (formerly) MI300X SKUs
- probe_runpod_stock.py: GPU stock poll loop; referenced from the
  (now archived) Plan 03-01.5 RunPod-MI300X enabler — kept because the
  same poll loop is reusable for any future RunPod SKU that exhibits the
  "listed but thin" stock=None pattern
- all three are operator-side utilities (no test coverage required); they
  consume RUNPOD_API_KEY from env, never from the repo
EOF
)"
```
  </action>
  <verify>
    <automated>git log -1 --format='%s' | grep -q '^tools(runpod): add RunPod volume + datacenter + stock probe utilities$' && [ "$(git log -1 --name-only --format='' | grep -v '^$' | sort)" = "$(printf 'tools/find_runpod_volume.py\ntools/probe_runpod_dc.py\ntools/probe_runpod_stock.py' | sort)" ]</automated>
  </verify>
  <done>Commit on main with subject `tools(runpod): add RunPod volume + datacenter + stock probe utilities`. Exactly those 3 files changed.</done>
</task>

<task type="auto">
  <name>Task 5: commit Phase 02 evidence artifacts (results/)</name>
  <files>results/_pulled/, results/g1/, results/g2/, results/g3/, results/g5/, results/preflight/, results/smoke/</files>
  <action>
First, sanity-check that `git status --short` does NOT include any sensitive paths (Task 1 .gitignore must already have masked them). If `secrets/`, `.claude/settings.local.json`, `.claude/scheduled_tasks.lock`, or `.claude/worktrees/` still appears, STOP — Task 1 is broken.

Then stage exactly the 7 result subtrees (no broader path, no `-A`):

```
git add results/_pulled/ results/g1/ results/g2/ results/g3/ results/g5/ results/preflight/ results/smoke/
```

Before committing, run `git diff --cached --name-only | head -20` and `git diff --cached --name-only | wc -l` to confirm only `results/...` paths are staged and the count is reasonable (expect dozens of small JSON/JSONL files; total <1 MB).

Then commit:

```
git commit -m "$(cat <<'EOF'
chore(results): commit Phase 02 evidence artifacts (pulls, gates, preflight, smoke)

- results/_pulled/: 14 pod-pull subdirs from Phase 02 (mi300x_stock_check
  + 13 hash-named pod pulls); raw evidence per fetch_results.py pattern
- results/g1/, g2/, g3/, g5/: per-gate run JSONLs + env JSONs
- results/preflight/: 31 timestamped preflight session JSONs (May 6-10 window)
  capturing operator bootstrap dry-runs ahead of real spend
- results/smoke/: 2 smoke audit files from the v18 image smoke pass
  (session 20260509T231720Z, verdict pass — all 6 D-25 sub-criteria true)
- per STACK.md §9 reproducibility policy: "Commit JSON outputs to the repo
  as raw evidence." Total payload <1 MB; results/index.sqlite (the DB,
  state-not-source) remains .gitignored.
EOF
)"
```
  </action>
  <verify>
    <automated>git log -1 --format='%s' | grep -q '^chore(results): commit Phase 02 evidence artifacts' && git status --short | grep -vE '^(\?\? |M )?(secrets/|\.claude/(settings\.local\.json|scheduled_tasks\.lock|worktrees/))$' | grep -qE '^\?\? results/' && exit 1 || git diff --cached --quiet</automated>
  </verify>
  <done>Commit on main with subject `chore(results): commit Phase 02 evidence artifacts (pulls, gates, preflight, smoke)`. `git status --short` shows no remaining `results/_pulled/`, `results/g{1,2,3,5}/`, `results/preflight/`, or `results/smoke/` untracked items. Sensitive paths still hidden (Task 1 still effective). Working tree clean except for any files outside the triaged set (none expected per orchestrator's scout).</done>
</task>

</tasks>

<verification>
After all 5 tasks:

1. `git log --oneline -5` shows the 5 new commits in order: gitignore, prd, debug, tools, results.
2. `git status --short` shows a clean working tree (or only items outside the original 55-untracked-file set, which would be a surprise the operator should see).
3. No commit contains both .gitignore changes AND staged sensitive files (Task 1 sequencing).
4. No `git push` was run.
5. No commit lists Claude as co-author.
6. No commit message uses `--no-verify`.

Quick sanity command:
```
git log --oneline -5
git status --short
git log -5 --pretty=format:'%H %s' | grep -i 'co-authored-by: claude' && exit 1 || echo "no co-author leak"
```
</verification>

<success_criteria>
- [ ] 5 commits exist on `main`, subjects matching the patterns above
- [ ] `.gitignore` excludes `secrets/`, `.claude/settings.local.json`, `.claude/scheduled_tasks.lock`, `.claude/worktrees/`
- [ ] `git status --short` shows none of the 4 sensitive paths
- [ ] `git status --short` shows none of the 7 result subtrees
- [ ] PRD, debug doc, and 3 tools scripts are tracked
- [ ] No Claude co-author trailer in any of the 5 commits
- [ ] No push to remote
</success_criteria>

<output>
After completion, this PLAN.md remains in place under `.planning/quick/260511-vgz-triage-55-untracked-files-decide-gitigno/` as the audit trail for the triage decisions. No SUMMARY.md required for quick mode.
</output>
