# Operator Checklist — Phase 1 Foundation Closeout

**Status:** OPEN — two human-action checkpoints remain before Phase 1 can be marked complete.
**Created:** 2026-05-04 (Plan 01-05 execution)
**Owner:** Dustin Powers (operator)

Phase 1 autonomous work is complete. Two operator-only steps remain because
they require:
- (Checkpoint A) Logging into provider dashboards to deposit credits — no CLI replacement exists (Pitfall B closure for RunPod).
- (Checkpoint B) Copying 6 local files into the repo — these are not in any source Claude can fetch.

When both checkpoints are complete, run the verification block at the end of
this document and update REQUIREMENTS.md from `partial-pending-operator` to
`complete` for CLOUD-01, CLOUD-02, CLOUD-03, DECISION-NC-R14, DECISION-DOCS.

---

## Checkpoint A — Provider account provisioning ($75 caps)

### A.1 RunPod (CLOUD-01)

1. Go to <https://runpod.io> and sign in (create account if needed).
2. Navigate to **Billing → Add Credits**. Deposit exactly **$75 USD**.
3. **CRITICAL — set Auto-Recharge OFF.** Settings → Billing → Auto-Recharge → toggle off.
   This is the cap mechanism (Pitfall B in `.planning/phases/01-foundation/01-RESEARCH.md`).
   RunPod has no programmatic cumulative-spend cap as of May 2026; the prepaid-only-$75
   deposit is the cap.
4. Settings → API Keys → Generate API key (read+write scope OK).
5. Set in shell rc (e.g., `~/.bashrc`) — DO NOT commit:
   ```bash
   export RUNPOD_API_KEY=<your-key>
   ```
6. Reload shell. Verify:
   ```bash
   cd /home/bob/RBOX
   uv run python -c "
   import asyncio, httpx
   from cost.adapters.runpod import poll
   async def go():
       async with httpx.AsyncClient() as c:
           print(await poll(c))
   asyncio.run(go())
   "
   ```
   Expected: `(0.0, 0.0)` and NO warning about missing key. (Warnings about
   no active pods are fine — there are none yet.)

### A.2 TensorWave (CLOUD-02 primary)

1. Go to <https://tensorwave.com> and sign up.
2. Deposit **$75** in credits (operator may need to contact sales for some plans).
3. Bookmark the dashboard tab — operator manual checks are the second rail
   because TensorWave's billing API is undocumented (Pitfall C). The cost-watch
   adapter logs a WARNING per poll by design.
4. No env var needed for Phase 1 stub.

### A.3 Vultr (CLOUD-02 backup)

1. Go to <https://vultr.com> and sign up if not already.
2. Add **$75** in credits via Account → Billing → Add Funds.
3. Disable auto-recharge: Account → Billing → Auto-Pay → off.
4. Generate API key: Account → API → Personal Access Token.
5. Set in shell rc — DO NOT commit:
   ```bash
   export VULTR_API_KEY=<your-key>
   ```
6. Reload shell. Verify:
   ```bash
   cd /home/bob/RBOX
   uv run python -c "
   import asyncio, httpx
   from cost.adapters.vultr import poll
   async def go():
       async with httpx.AsyncClient() as c:
           print(await poll(c))
   asyncio.run(go())
   "
   ```
   Expected: `(0.0, 0.0)` and NO warning about missing key.

### A.4 Initialize the local cost ledger (one-time bootstrap)

```bash
cd /home/bob/RBOX
uv run python -c "
from cost.ledger import initialize_provider
initialize_provider('runpod', 75.0)
initialize_provider('tensorwave', 75.0)
initialize_provider('vultr', 75.0)
print('OK')
"
```

The DB lands at `cost/ledger.sqlite` (gitignored).

### A.5 Smoke-test the full cost-watch loop

```bash
uv run python -m cost.watch --providers runpod,tensorwave,vultr --iterations 1 --interval 0
```

Expected: 3 INFO log lines (one per provider) showing `cumulative=$0.00`. The
TensorWave line will also emit a WARNING (Pitfall C — by design).

---

## Checkpoint B — Drop 6 companion documents into `docs/`

### B.1 Copy the files

The 6 required filenames (locked, do NOT rename — they are referenced by SHA-pinned
tests):

```
thumbox-technical-prd-v2_1-2026-04-16.md
thumbox-business-prd-v2_1-2026-04-16.md
addendum-receptionbox-discovery-v0_2-2026-04-22.md
addendum-hardware-pivot-strix-halo-v0_1-2026-04-23.md
receptionbox-technical-feasibility-memo-v0_3-2026-04-23.md
receptionbox-virtual-benchmark-plan-v0_1-2026-05-03.md
```

```bash
cd /home/bob/RBOX
# Adjust the source paths to where your local copies live.
cp /path/to/thumbox-technical-prd-v2_1-2026-04-16.md docs/
cp /path/to/thumbox-business-prd-v2_1-2026-04-16.md docs/
cp /path/to/addendum-receptionbox-discovery-v0_2-2026-04-22.md docs/
cp /path/to/addendum-hardware-pivot-strix-halo-v0_1-2026-04-23.md docs/
cp /path/to/receptionbox-technical-feasibility-memo-v0_3-2026-04-23.md docs/
cp /path/to/receptionbox-virtual-benchmark-plan-v0_1-2026-05-03.md docs/
```

### B.2 Verify presence

```bash
uv run pytest tests/test_companion_docs_present.py -v
```

Both tests must pass.

### B.3 Review DR-31 v0.1.0

```bash
less docs/decisions/dr-31-sharing-policy.v0.1.0.md
```

Decide:
- **Approve as-is** → edit the Status line to `Approved 2026-MM-DD` (use today's UTC date).
- **Edit and bump version** → save as `dr-31-sharing-policy.v0.1.1.md` (patch — typos / phrasing) or `v0.2.0.md` (minor — new sections).
- **Reject** → flag the disagreement in `.planning/STATE.md` Blockers; agent will redraft.

### B.4 Update Status if approved

In `docs/decisions/dr-31-sharing-policy.v0.1.0.md`, change:

```
**Status:** Draft / awaiting operator approval
```

to:

```
**Status:** Approved 2026-MM-DD
```

### B.5 Final verify and commit

```bash
cd /home/bob/RBOX
make check
uv run pytest tests/test_dr31_policy.py tests/test_companion_docs_present.py -v
```

All tests pass. Then:

```bash
git add docs/
git status   # review
git commit -m "$(cat <<'EOF'
docs(01-foundation): add 6 companion docs + approve DR-31 sharing policy

- Drop parent thUMBox + addenda + feasibility memo + benchmark plan into docs/
- DR-31 v0.1.0 sharing-policy decision approved per CONTEXT.md DR-31 stance
- Closes ROADMAP Phase 1 success criteria #3
EOF
)"
```

---

## When both checkpoints complete

Mark the following requirements as complete in `.planning/REQUIREMENTS.md`
(change `[ ]` to `[x]` and update the traceability table from `Pending` to `Complete`):

- CLOUD-01 (RunPod $75 + auto-recharge OFF + API key set + orchestration skeleton wired)
- CLOUD-02 (TensorWave $75 + Vultr $75 + auto-recharge OFF + API key set + orchestration skeletons wired)
- CLOUD-03 (cost-watch daemon polls all 3 providers with 5-min cadence)
- DECISION-NC-R14 (DR-31 v0.1.0 approved)
- DECISION-DOCS (6 companion docs present)

Then run:

```bash
node $HOME/.claude/get-shit-done/bin/gsd-tools.cjs roadmap update-plan-progress 01
node $HOME/.claude/get-shit-done/bin/gsd-tools.cjs requirements mark-complete CLOUD-01 CLOUD-02 CLOUD-03 DECISION-NC-R14 DECISION-DOCS
```

ROADMAP Phase 1 success criteria #3 (NC-R14 + companion docs) and #5 (cost rails wired)
both close. Phase 2 (CUDA pre-flight on RunPod H100) is unblocked.
