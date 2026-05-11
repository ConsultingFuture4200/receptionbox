---
phase: 03-rocm-validation
plan: 01
type: amendments
origin: Task 5 (human-verify checkpoint) operator findings, 2026-05-11
amendments:
  - id: D-31-A4
    target: CLAUDE.md §1.2 + PLAN frontmatter D-31 (Vultr Day-1)
    nature: substrate pivot (primary → backup)
  - id: D-32-A1
    target: CLAUDE.md §2.1 / §14 + bench/images.lock.yaml + dockerfiles/rocm/Dockerfile
    nature: image migration (ROCm 6.4 stub → ROCm 7.12 digest-pinned)
tags: [amendment, operator-checkpoint, rocm, image-pin, substrate-pivot, vultr, tensorwave]
---

# Plan 03-01 Amendments — Task 5 Checkpoint Closure

This document closes the Task 5 (`checkpoint:human-verify`) gate by recording the two
amendments operator-approved on 2026-05-11 after running the checkpoint verification
steps in `03-01-PLAN.md` §Task 5. The previous agent (commits `5a00169`, `b2dd730`,
`e110a9f`, `f6297e4`) carried CLAUDE.md assumptions forward verbatim; the operator's
own runs surfaced that two of those assumptions were stale or incorrect. Both
amendments are substrate-agnostic — they update *what we build with* but not the
HARNESS-03 design that's already on disk.

## Summary

| Amendment | What broke | Resolution | Scope |
| --------- | ---------- | ---------- | ----- |
| **D-32-A1** | `rocm/vllm:rocm6.4_mi300_ubuntu22.04_py3.11_vllm_0.10.x` tag does not exist on Docker Hub (CLAUDE.md §2.1 extrapolated a pattern that never matched AMD's actual schema) | Migrate base image to current AMD-published tag: `rocm/vllm:rocm7.12.0_gfx94X-dcgpu_ubuntu24.04_py3.12_pytorch_2.9.1_vllm_0.16.0` @ `sha256:997f858b…2a8f7` | `bench/images.lock.yaml` + `dockerfiles/rocm/Dockerfile` |
| **D-31-A4** | `GET /v2/plans?type=gpu` returned 400; correct endpoint is `/v2/plans-metal`; the one MI300X SKU is on-demand-disabled and forces buying an 8-GPU node at $14.80/hr preemptible | Pivot primary MI300X substrate to **TensorWave** (~$1.71/GPU-hr per CLAUDE.md §1.2); Vultr demoted to backup-only | Decision-level only — `orchestration/vultr_mi300x.py` stays in repo as backup; sentinel guard remains UNSET |

Both were operator-approved verbally during the Task 5 checkpoint. No additional
operator decision is required to close Plan 03-01.

---

## D-32-A1: Base Image Migration (CLAUDE.md §2.1 / §14)

### What was assumed

CLAUDE.md §2.1 specified the ROCm base image as:

```
rocm/vllm:rocm6.4_mi300_ubuntu22.04_py3.11_vllm_0.10.x
```

This was carried verbatim into:

- `dockerfiles/rocm/Dockerfile` (the `FROM` line)
- `bench/images.lock.yaml` (the `rocm/vllm` row, tagged `rocm6.4_mi300_ubuntu22.04_py3.11_vllm_0.10.0`)
- Plan 03-01 Task 2 acceptance criteria (`grep -n 'FROM rocm/vllm:rocm6.4_mi300_*' ...`)
- Task 5 verification step ("Resolve `rocm/vllm:rocm6.4_mi300_*` digest (Assumption A1)")

### What was actually observed

Operator ran:

```bash
docker pull rocm/vllm:rocm6.4_mi300_ubuntu22.04_py3.11_vllm_0.10.x
```

The pull failed: the tag does not exist on Docker Hub. CLAUDE.md §2.1's tag string
was an extrapolated pattern, not a tag AMD has ever actually published. AMD has
also rotated their tag schema at least twice since CLAUDE.md was written (Sept 2025
state), so even the underlying pattern is now stale.

### What the amendment is

Migrate to the current AMD-published ROCm 7.12 base image:

| Field | Value |
| ----- | ----- |
| **Tag** | `rocm/vllm:rocm7.12.0_gfx94X-dcgpu_ubuntu24.04_py3.12_pytorch_2.9.1_vllm_0.16.0` |
| **Digest** | `sha256:997f858b973cb4e9566653a180c79bc27170bd87585a6930f9257346869a28f7` |
| **Size** | 14.1 GB (15,174,735,464 bytes) |
| **Last updated** | 2026-03-27 |
| **Architecture** | `gfx94X-dcgpu` — covers MI300X (gfx942) and MI325X |

### Why operator approved

1. **Necessity.** The CLAUDE.md tag does not exist; there is no "fix" that uses
   the original string. Migration is the only path forward.

2. **Currency.** ROCm 7.12 is AMD's current stable as of 2026-03; CLAUDE.md §2.1
   cited 6.4 because that was current at the time CLAUDE.md was written. The
   migration brings us in line with what AMD ships and tests.

3. **xgrammar requirement.** vLLM 0.16 has `xgrammar` as the default
   structured-output backend, which CLAUDE.md §3.1 already names as the
   required engine for GATE-G5 (UPL grammar-constrained generation). vLLM 0.10.x
   (the CLAUDE.md spec) predates that default — would have required an opt-in
   flag at best, a separate install at worst. The migration eliminates that
   risk.

4. **Phase 4 derating bonus.** AMD now publishes a parallel
   `rocm/vllm:rocm7.12.0_gfx1151_*` image — same ROCm version, same PyTorch,
   same vLLM, just built for Strix Halo's `gfx1151` architecture. Concretely:

   - **gfx94X-dcgpu (MI300X) digest**: `sha256:997f858b973cb4e9566653a180c79bc27170bd87585a6930f9257346869a28f7`
   - **gfx1151 (Strix Halo) digest**: `sha256:8a09c886e1bab993f5e12faec669579c8455e5ca1ab31553350f87c3e26ca5a1`

   This is a **major Phase 4 opportunity**: the derating story (Phase 4) is
   dramatically tighter if MI300X and Strix Halo measurements share the same
   ROCm / PyTorch / vLLM version. Version-skew is removed as a confounding
   variable in the cross-substrate consistency check (DERATE-03), which
   shrinks the "what we did not measure" caveat list and the 80% confidence
   bands. **Flag for Phase 4**: use the matching gfx1151 image when local
   Strix Halo validation begins.

### What this amendment does NOT change

- **HARNESS-03 design** is unchanged. `substrate/rocm.py` does not care which
  ROCm version is in the base image; it composes the same 4 adapters and
  returns `substrate="rocm"` either way.
- **Acceptance criteria language** in Task 2 (grep for `FROM rocm/vllm:rocm6.4_mi300_*`)
  is now stale but harmless — the plan is closed, the acceptance criteria
  served their purpose at Task 2 commit time, and the SUMMARY records the
  corrected state.
- **Pod image** (`rbox-pod-rocm`) digest stays `pending` in `bench/images.lock.yaml`.
  The pod image is the derived image (rebuilt FROM the new base + harness deps).
  The operator builds + pushes that separately once a TensorWave-validated dev
  pod confirms the new base actually runs faster-whisper / Kokoro / Chatterbox.
  That work is deferred (see "Deferred work" below).

---

## D-31-A4: Substrate Pivot — Vultr → TensorWave (Day-1 Primary)

### What was assumed

Plan 03-01 frontmatter D-31 named Vultr as the Day-1 MI300X provider, with
TensorWave as the substrate that "gets wired up when sales contact unblocks".
This was opposite to CLAUDE.md §1.2's table, which lists TensorWave as primary
and Vultr as backup. The plan's choice was justified at write-time by Vultr
already being adapter-verified (`cost/adapters/vultr.py:_check()` works against
`/v2/billing/pending-charges`) — i.e., choosing the substrate with the
already-built tooling.

Task 5's verification step was:

```bash
curl -s -H "Authorization: Bearer $VULTR_API_KEY" "https://api.vultr.com/v2/plans?type=gpu" | jq '.plans[] | select(.id | contains("MI300"))'
```

### What was actually observed

The `GET /v2/plans?type=gpu` query returned:

```
400: Please provide a valid type:
  all, vdc, vhp, vhf, vc2, voc, vcg, vdg, vdm, vx1, voc-g, voc-s, voc-c, voc-m
```

`type=gpu` was speculative — Vultr's actual valid types are listed in the error
message and "gpu" is not one of them. After enumerating those endpoints, the
operator found the correct surface for MI300X is `GET /v2/plans-metal` (bare-metal
plans, not virtualized cloud-GPU plans).

The MI300X SKU on Vultr's bare-metal surface:

| Field | Value |
| ----- | ----- |
| Plan ID | `vbm-256c-2048gb-8-mi300x-gpu` |
| Shape | 8× MI300X bare-metal node (1536 GB VRAM total) |
| CPU / RAM | 128 cores EPYC 9534 / 2 TB |
| `deploy_ondemand` | **false** (cannot buy on demand) |
| `deploy_preemptible` | true |
| Preemptible price | **$14.80/hr** for the entire 8-GPU node |
| On-demand price (disabled) | $31.92/hr |

### Why this breaks Plan 03-01's economics

| Phase 3 line item | Plan 03-01 budget (Vultr-as-assumed) | Vultr-as-actually-shaped |
| ----------------- | ------------------------------------ | ------------------------ |
| GATE-CHATTERBOX-D1 (D-36 spend cap $4) | 2 hr × $1.85/hr = $3.70 | 2 hr × $14.80/hr = **$29.60** |
| G1 sanity pod (per CLAUDE.md §13) | ~$9 | ~$72 |
| Full Phase 3 MI300X subtotal (CLAUDE.md §13) | ~$54 | **>$200** |
| Operational risk | None | Preemptible-only → eviction risk mid-200-call G1 run |

This breaks both the per-gate spend caps (D-36) and the Phase 3 program
ceiling ($54 per CLAUDE.md §13, hard-capped at $150 per PROJECT.md). Even at
preemptible pricing Vultr would burn ~50% of the entire Phase 0 budget on
GATE-CHATTERBOX-D1 alone.

### What the amendment is

Pivot the Day-1 primary MI300X substrate to **TensorWave** (~$1.71/GPU-hr
on-demand, single-GPU shape, per CLAUDE.md §1.2). Vultr is demoted to
backup-only status.

This is the substrate ordering CLAUDE.md §1.2's table already specifies. The
plan had it inverted because the planner front-loaded "which substrate has
working cost-adapter tooling" over "which substrate has economically usable
MI300X SKUs". The latter is more load-bearing — without economically usable
SKUs, the cost adapter is measuring a substrate we cannot use.

### Concrete downstream impact

| File / artifact | Status after this amendment |
| --------------- | --------------------------- |
| `orchestration/vultr_mi300x.py` | **Stays in repo as BACKUP code.** Not deleted. The real `provision()` body, sentinel guard, `_DEFAULT_IMAGE_ROCM` constant, and DEV-1021 env wiring all remain valid — we just don't call it on Day-1. |
| `_DEFAULT_IMAGE_ROCM` UNSET sentinel | **Stays UNSET.** Explicit-failure-on-Vultr-provisioning is the correct posture while Vultr is backup-only. When/if Vultr is re-validated as a viable substrate (e.g., they introduce a 1-GPU SKU), the sentinel gets a real digest at that time. |
| `tests/test_vultr_provisioning.py` | All 10 tests still relevant. Sentinel guard test continues to validate the loud-fail path that backup-mode now relies on. |
| `bench/images.lock.yaml` `rbox-pod-rocm` row | Stays `digest: pending`. The pod image build + push is deferred (see below). |
| Plan 03-02 (Chatterbox kill-switch) | Will need to provision via TensorWave, not Vultr. **Requires a TensorWave orchestration module that does not yet exist.** This is the dominant follow-up surfaced by this amendment. |
| `config/budget.yaml` `phase3.hourly_rate_usd` | Both rates remain accurate (`vultr: 1.85` is wrong for the actual MI300X SKU but is correct for Vultr's other GPU SKUs that the cost adapter still cares about; `tensorwave: 1.71` is the rate now driving Day-1 spend projections). No edit required. |

### Why operator approved

1. **Budget feasibility.** Vultr's actual MI300X economics break the Phase 0
   spend ceiling 4× over even at preemptible pricing. TensorWave's per-GPU
   on-demand model fits CLAUDE.md §13's $54 subtotal.

2. **Operational risk reduction.** Preemptible-only provisioning is brittle
   for 200-call corpora that must run to completion. TensorWave's on-demand
   path eliminates eviction risk.

3. **Alignment with CLAUDE.md §1.2.** This amendment restores the original
   ordering CLAUDE.md specifies; the plan's inversion was a planner
   shortcut that did not survive operator API-surface verification.

4. **Backup-substrate value preserved.** Keeping `vultr_mi300x.py` in the repo
   means if Vultr ever introduces a 1-GPU SKU, the orchestration code is ready
   — we just re-pin the image digest and lift the sentinel. Zero rework.

---

## Deferred Work (Created by This Amendment)

### 1. TensorWave orchestration module (`orchestration/tensorwave_mi300x.py`)

**Required before Wave 2 spend.** Plan 03-02 (Chatterbox kill-switch) is the
first plan that would actually provision an MI300X pod. It cannot run against
the current `tensorwave_mi300x.py` stub.

**Blocker:** TensorWave does not appear to publish a public REST API
analogous to Vultr's `/v2/instances`. Provisioning surface candidates need
research:

- TensorWave dashboard (manual click-to-provision; no automation)
- TensorWave CLI (if it exists)
- Partner API access (would require sales contact — same blocker that has
  stalled CLOUD-02 per STATE.md "Blockers/Concerns")

**Recommendation:** Spawn a separate research plan (`/gsd-research` or a new
Wave 1.5 plan) to characterize TensorWave's provisioning surface BEFORE
Plan 03-02 attempts a real-spend run. Do NOT scaffold the module
speculatively in this continuation — the surface needs to be known first.

This continuation agent explicitly does NOT create
`orchestration/tensorwave_mi300x.py` for that reason.

### 2. `rbox-pod-rocm` pod image build + push

The derived pod image (FROM the new ROCm 7.12 base + harness deps + baked
ENTRYPOINT) still needs to be built and pushed to GHCR. Operator does this
once a TensorWave-validated dev pod confirms the new base actually runs the
harness deps (faster-whisper / Kokoro / Chatterbox) cleanly.

Build command (unchanged from Plan 03-01 Task 2):

```bash
echo "$GHCR_TOKEN" | docker login ghcr.io -u consultingfuture4200 --password-stdin
scripts/build_pod_image_rocm.sh ghcr.io/consultingfuture4200/rbox-pod-rocm:v1 --push
```

Then paste the resolved `@sha256:...` digest into:

- `bench/images.lock.yaml` `rbox-pod-rocm` row (`digest: pending` → real)
- `orchestration/vultr_mi300x.py` `_DEFAULT_IMAGE_ROCM` (only when Vultr is
  re-promoted from backup; until then, sentinel stays)
- A future `orchestration/tensorwave_mi300x.py` `_DEFAULT_IMAGE_ROCM`
  constant (created by the deferred TensorWave module work)

---

## Phase 4 Opportunity Callout

The matching gfx1151 image
(`sha256:8a09c886e1bab993f5e12faec669579c8455e5ca1ab31553350f87c3e26ca5a1`)
means Phase 4's derating story can — for the first time — compare MI300X and
Strix Halo measurements *with the same ROCm version, the same PyTorch wheel,
and the same vLLM*. The DERATE-03 cross-substrate consistency check becomes
a real apples-to-apples comparison instead of a within-25%-with-version-skew
estimate.

This should be incorporated into the Phase 4 CONTEXT (`04-CONTEXT.md`)
when that phase is planned. The cost is essentially zero — the operator
already has both digests on hand.

---

## Approval

Operator approved both amendments verbally during the Task 5 checkpoint
session on 2026-05-11. No further decision required to close Plan 03-01.
