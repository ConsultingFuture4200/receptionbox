# Companion Documents Checklist (D-13)

Phase 1 Foundation cannot close until all 6 companion documents are physically
present in `docs/`. The operator (Dustin) has these files locally and must
copy them into the repo before Phase 2 begins.

This file is verified by `tests/test_companion_docs_present.py`. The test FAILS
until every entry below is checked.

## Required documents

- [ ] `docs/thumbox-technical-prd-v2_1-2026-04-16.md`
      Parent platform technical PRD (DR-19, DR-22, plugin tier, llm-router)
- [ ] `docs/thumbox-business-prd-v2_1-2026-04-16.md`
      Parent platform business PRD
- [ ] `docs/addendum-receptionbox-discovery-v0_2-2026-04-22.md`
      Discovery gate, kill criteria, regulatory posture
- [ ] `docs/addendum-hardware-pivot-strix-halo-v0_1-2026-04-23.md`
      DR-24 Strix Halo pivot — drives derating discipline
- [ ] `docs/receptionbox-technical-feasibility-memo-v0_3-2026-04-23.md`
      Eric-facing feasibility brief; Phase 4 v0.4 update patches against this
- [ ] `docs/receptionbox-virtual-benchmark-plan-v0_1-2026-05-03.md`
      Authoritative on Phase 0 procedures

## Verification

```bash
cd /home/bob/RBOX
uv run pytest tests/test_companion_docs_present.py -v
```

When all 6 files are in place, the test passes and ROADMAP success criterion #3
("operator has dropped … into docs/") is satisfied.

## Operator instructions

```bash
# From wherever the operator's local copies live (example):
cp ~/Documents/thumbox-prds/thumbox-technical-prd-v2_1-2026-04-16.md docs/
cp ~/Documents/thumbox-prds/thumbox-business-prd-v2_1-2026-04-16.md docs/
cp ~/Documents/thumbox-prds/addendum-receptionbox-discovery-v0_2-2026-04-22.md docs/
cp ~/Documents/thumbox-prds/addendum-hardware-pivot-strix-halo-v0_1-2026-04-23.md docs/
cp ~/Documents/thumbox-prds/receptionbox-technical-feasibility-memo-v0_3-2026-04-23.md docs/
cp ~/Documents/thumbox-prds/receptionbox-virtual-benchmark-plan-v0_1-2026-05-03.md docs/
git add docs/*.md
git status
```
