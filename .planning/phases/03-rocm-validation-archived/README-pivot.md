# Phase 03 — Archived per DR-39 (RATIFIED 2026-05-11)

This directory was renamed from `.planning/phases/03-rocm-validation/` to
`.planning/phases/03-rocm-validation-archived/` on 2026-05-11 following the
ratification of **DR-39 (Jetson Pivot)** with substituted target
**NVIDIA Jetson AGX Orin 64GB** (not Thor — see DR-39 §10 for the
Thor → Orin substitution rationale).

## What this directory contains

The original Phase 03 — ROCm Validation work. Plan 03-01 shipped (substrate
adapter, ROCm Dockerfile, Vultr orchestration with sentinel guard, Phase 3
budget config). Plans 03-02..06 and the inserted 03-01.5 were planned but
not executed. The companion code at the repo root (`substrate/rocm.py`,
`orchestration/vultr_mi300x.py`, `dockerfiles/rocm/`, related tests)
remains in the tree as an optional ROCm path for future reactivation.

## Why it was archived

Two compounding factors:

1. **Cloud-supply blockers for MI300X**: RunPod stock intermittent / dry,
   TensorWave sales-unblock pending ≥7 days, Vultr's only MI300X SKU is an
   8-GPU bare-metal preemptible node at $14.80/hr (breaks the Phase 0
   budget 4×).
2. **ROCm software-stack maturity concerns** on gfx1151 (the Strix Halo
   appliance target): Chatterbox-Turbo ROCm fork unresolved
   (devnen issues #92/#192/#445), gfx1151 op-coverage gaps in current
   ROCm + PyTorch wheels, bf16 bugs (PyTorch issues #171687/#6034).

The parent thUMBox + UMB Group review then approved a switch to NVIDIA
Jetson AGX Orin 64GB as the new appliance target: mature CUDA + JetPack 6,
BOM-cost-neutral with the Strix Halo path (~$2k vs Thor's ~$3.5–4k),
comfortable workload fit (~2–3× headroom for receptionBOX's concurrency-4
envelope). Phase 3 collapses from "MI300X-cloud-derate to Strix Halo" to
"direct measurement on Orin 64GB Developer Kit" — no further derate, since
Orin IS the appliance SoC.

## Status of artifacts here

| Artifact | Status |
|---|---|
| `03-01-PLAN.md` | Shipped — code merged at repo root (`substrate/rocm.py`, `orchestration/vultr_mi300x.py`, `dockerfiles/rocm/`, `bench/images.lock.yaml` rbox-pod-rocm row, `config/budget.yaml` phase3 block, `config/sanity_strata.yaml`) |
| `03-01-SUMMARY.md` | Shipped |
| `03-01-AMENDMENTS.md` | Historical: D-32-A1 (ROCm 7.12 image migration), D-31-A4 (Vultr → TensorWave pivot), D-31-A4.1 (TensorWave → RunPod pivot). All three amendments are now moot under DR-39. |
| `03-01.5-PLAN.md` | Drafted, never executed (RunPod MI300X harness — moot) |
| `03-02-PLAN.md` (GATE-CHATTERBOX-D1) | Moot under DR-39 (Chatterbox-CUDA already validated in Phase 2) |
| `03-03-PLAN.md`..`03-05-PLAN.md` | Drafted, never executed. Will be re-derived under the new Phase 3 scope (direct Orin measurement) |
| `03-06-PLAN.md` (AUDIT-02 gfx1151 op coverage) | Permanently obsolete — no AMD silicon in the new product target |
| `03-RESEARCH.md`, `03-CONTEXT.md`, `03-DISCUSSION-LOG.md` | Historical research/context — preserved as a record of the substrate-pivot reasoning |

## Reactivation path

If the AMD strategy is ever revived:

```bash
git mv .planning/phases/03-rocm-validation-archived .planning/phases/03-rocm-validation
```

…and re-execute the plans against the same code. Two repo refs preserve
the pre-archive state:

- **Tag**: `pivot/strix-halo-end-state` at commit `4c0bb57`
- **Branch**: `archive/amd-rocm-substrate` on GitHub (protected: no force-push, no delete, enforce_admins=true)

## See also

- `docs/decisions/dr-39-jetson-pivot.v0.1.0.md` — full ratification rationale + §10 Thor → Orin substitution
- Linear issue **DEV-1117** — pivot announcement (note: title and body say "Jetson AGX Thor" and reference "DR-33"; both are wrong as written — ratified target is Orin 64GB, DR number is 39. Issue needs an in-place edit once Linear access is restored.)
- `RBOX/CLAUDE.md` (project tech-stack table) — rewrite pending: remove ROCm sections, pin CUDA / JetPack 6 / CUDA 12.x / Jetson Orin 64GB as the new substrate
- Linear milestone **M3 — MI300X Validation** + parent issue **DEV-1011** — should be cancelled/closed with "killed by DEV-1117 / DR-39" comment once Linear access is restored
