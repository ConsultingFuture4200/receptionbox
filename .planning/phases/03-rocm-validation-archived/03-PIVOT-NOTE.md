---
phase: 03-rocm-validation
type: pivot-note
date: 2026-05-11
status: SUPERSEDES the existing phase 3 scope
authority: DR-39 (`docs/decisions/dr-39-jetson-pivot.v0.1.0.md`) RATIFIED 2026-05-11
---

# Phase 3 PIVOT NOTE — RATIFIED 2026-05-11

DR-39 RATIFIED: the receptionBOX appliance target SoC has changed from **AMD Strix Halo (gfx1151)** → **NVIDIA Jetson AGX Orin 64GB**. All Phase 3 ROCm-targeted work on this directory is **superseded**. This note is the durable record of what happens to each artifact.

## Why this happened

See `docs/decisions/dr-39-jetson-pivot.v0.1.0.md` §§2 + 10. Short version:

- MI300X cloud supply is structurally constrained (Vultr 8-GPU-bare-metal-preemptible breaks budget; TensorWave sales-gated ≥7 days; RunPod EU-RO-1 stock dry).
- Parent thUMBox + UMB Group ratified the product pivot to Jetson AGX Orin 64GB.
- Phase 3's ROCm shape collapses because there's no AMD silicon in the new product target.

## Disposition of existing artifacts in this directory

| File | Status under DR-39 | What to do with it |
|---|---|---|
| `03-CONTEXT.md` | obsolete-but-keep | Historical record of the gathered ROCm context. Don't update. New Phase 3 will get a fresh `03-CONTEXT.md` after the Orin dev kit arrives. |
| `03-DISCUSSION-LOG.md` | obsolete-but-keep | Same — audit trail of the ROCm-era discussion. |
| `03-RESEARCH.md` | obsolete-but-keep | Same — ROCm domain research; archival value. |
| `03-01-PLAN.md` | parked-archival | Code already shipped (`substrate/rocm.py`, `Dockerfile.rocm`, `orchestration/vultr_mi300x.py`, etc.). Keep code in repo as optional ROCm path if vendor strategy ever flips back. Plan file remains as documentation of what was built. |
| `03-01-SUMMARY.md` | parked-archival | Same — closure record of the substrate work. |
| `03-01-AMENDMENTS.md` | parked-archival | Same — D-31-A4 + D-32-A1 record. Note that DR-39 supersedes both. |
| `03-01.5-PLAN.md` | obsolete | RunPod MI300X stock-poll + orchestration. No longer relevant — Phase 3 doesn't need an MI300X enabler. |
| `03-02-PLAN.md` | obsolete | GATE-CHATTERBOX-D1 ROCm kill-switch. No ROCm risk to validate; Chatterbox-CUDA already validated in Phase 2. |
| `03-03-PLAN.md` | redirect | GATE-G1/G2/G3/G5 — will be rewritten as Orin-direct measurements in the new Phase 3 plan set. The gate-runner code itself is substrate-agnostic and stays. |
| `03-04-PLAN.md` | redirect | GATE-G7 TTS A/B — same. |
| `03-05-PLAN.md` | redirect | AUDIT-01 co-residency + AUDIT-03 engine-swap — will be rewritten as direct-on-Orin variants. |
| `03-06-PLAN.md` | obsolete | AUDIT-02 gfx1151 op-coverage. No AMD silicon in the new product target; closed by product retarget. |

**No file is deleted.** The parked-archival code keeps optionality if AMD strategy ever reverses; the obsolete plans stay as historical record.

## New Phase 3 shape (placeholder for the new plan set)

Phase 3 retitled: **Jetson Orin Validation**. New scope:

1. **Buy 1× Jetson AGX Orin 64GB Developer Kit.** ~$2k from NVIDIA / Arrow / Amazon. ~3-7 day shipping. Operator action.
2. **Set up Orin dev kit** at operator workstation. Flash JetPack 6.x, verify CUDA 12.x toolchain.
3. **`substrate/jetson.py`** — sibling to `substrate/cuda.py`. Composes the same 4 backend adapters (vLLM, faster-whisper, Chatterbox, Kokoro) with Orin-specific image / endpoint / model-path configuration. TensorRT-LLM optional optimization layer.
4. **Direct measurement of G1, G2, G3, G5, G7** on Orin (replaces the cloud-MI300X measurement). Uses the same gate runners under `gates/g{1,2,3,5,7}/runner.py` — they're substrate-agnostic per HARNESS-06.
5. **AUDIT-01 co-residency** on Orin — trivially runnable alongside the gate measurements.
6. **AUDIT-03 engine-swap** on Orin — same.
7. **AUDIT-02 gfx1151 op-coverage** — CLOSED by DR-39 (no AMD silicon in new target).
8. **GATE-CHATTERBOX-D1** — CLOSED by DR-39 (no ROCm risk; Chatterbox-CUDA already validated in Phase 2).

## Derate methodology under DR-39

Original: cloud MI300X (gfx942) → derate to Strix Halo (gfx1151). Two derate hops, cross-architecture.

New: Phase 2 H100 measurements (already done) → Orin Direct measurements (Phase 3). **No further derate.** Orin Direct IS the appliance SoC; what you measure on the dev kit is what the appliance does.

The Phase 4 synthesis report's "What we did not measure" section shrinks dramatically. The firm conversation talk-track becomes: "we measured Phase 0 directly on the target hardware."

## Phase 0 timeline impact

Original projected closure: ~2 weeks (cloud ROCm work was the long pole).

Under DR-39: ~5-7 calendar days from Orin dev kit arrival. Pre-arrival work is bounded by shipping time, not engineering time.

## What the operator needs to do next

1. **Order the Orin dev kit** — Jetson AGX Orin 64GB Developer Kit (NVIDIA SKU 945-13730-0050-000 or similar). Confirm shipping address + estimated arrival date.
2. **Update Linear issues:**
   - DEV-1011 (Phase 3 parent) — comment with DR-39 ratification + new scope
   - DEV-1022 (GATE-CHATTERBOX-D1) — close as obsolete
   - DEV-1023..1026 (P3.2..P3.5 gates) — comment with redirect; new sub-issues will replace them with Orin-direct shape
   - DEV-1027 (GATE-G7) — comment with redirect
   - DEV-1028 (P3.7 co-residency + engine-swap) — comment with redirect
   - DEV-1029 (P3.8 gfx1151 op-coverage) — close as obsolete
   - DEV-1082 (ROCm baseline pinning) — close as obsolete
3. **Communicate the pivot to the inbound firm** — discovery addendum positioning may need updating if "AMD on-prem appliance" was a sales-talk-track item.
4. **Run `/gsd-plan-phase 3`** after Orin arrives to draft the new plan set.

## What stays in the repo for optionality

The 03-01 substrate code (parked-archival): `substrate/rocm.py`, `dockerfiles/rocm/Dockerfile`, `scripts/build_pod_image_rocm.sh`, `orchestration/vultr_mi300x.py`, `orchestration/tensorwave_mi300x.py` stub, `bench/images.lock.yaml` ROCm row. All tested code. Zero ongoing maintenance burden; reactivation is a few hours of work if vendor strategy ever reverses.
