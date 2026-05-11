---
phase: 02-cuda-pre-flight
plan: 08
subsystem: reproducibility / lineage
gap_closure: true
retroactive: true
closes_gaps:
  - "image_digest='pending' on result rows (REPRO-03 data, not just schema)"
  - "git_commit='unknown' on result rows (REPRO-03 data, not just schema)"
tags: [reproducibility, repro-03, dev-1021, gap-closure, retroactive]
---

# Phase 02 Plan 08 — Summary (DEV-1021)

## Outcome

REPRO-03 data lineage closed: every result row now stamps the deployed image digest and the baked git commit. Verified on G2 diag pod `jow8x9kugpkgxm` (session `20260510T132812Z-dev1021-verify`, image v18, rows show `image_digest=sha256:abcf19f8…ea9d217`, `git_commit=f049bb87…`).

## What shipped

Single commit: `34c3607 fix(02-08): populate image_digest + git_commit in result rows (DEV-1021)`. Five files:

| File | Change |
|---|---|
| `orchestration/runpod_h100.py` | `provision()` forwards `RBOX_IMAGE_DIGEST=image_ref` in pod env; `_DEFAULT_IMAGE` repinned to v18 (`sha256:abcf19f8…ea9d217`) |
| `substrate/cuda.py` | `_lookup_image_digest()` reads env var first, lockfile fallback preserved |
| `Dockerfile` | `ARG GIT_COMMIT=unknown` + `RUN echo "$GIT_COMMIT" > /workspace/.git_commit` placed after heavy layers (no cache invalidation on HEAD churn) |
| `scripts/build_pod_image.sh` | Resolves `GIT_COMMIT=$(git rev-parse HEAD 2>/dev/null || echo unknown)` and passes as build arg |
| `gates/_runner_base.py` | `_git_commit()` fallback chain: `git rev-parse` → `/workspace/.git_commit` → `"unknown"` |

Image v18 built + pushed to `ghcr.io/consultingfuture4200/rbox-pod` with the new baked git commit.

## Smoke / sanity implications

Smoke run `2f6b…` (pre-fix) carries placeholder lineage. Future runs (G1 sanity, G2 sanity, MI300X cohorts) inherit the fix automatically because:

1. `_DEFAULT_IMAGE` points at v18.
2. v18 has `/workspace/.git_commit` baked from the operator's HEAD at build time.
3. `provision()` injects `RBOX_IMAGE_DIGEST` whenever the harness provisions a pod.

A re-run of smoke is *not* required to close Phase 2 because:

- Smoke verdict (D-25) was already `pass=True` on `2f6b`.
- The lineage fix was independently verified on the G2 diag row.
- Phase 4 repro-manifest seal can cite the G2 diag verification as the row-data proof and the smoke verdict as the orchestration proof.

## Carry-forward

Same lesson as 02-05's REPRO-02 closure: schema-enforced ≠ data-populated. Both REPRO-02 and REPRO-03 hit this. Future `/gsd-audit-uat` runs should pull a sampled result row and assert every REPRO-tagged field is non-placeholder.
