---
phase: 03-rocm-validation
plan: 01
type: amendments
origin: Task 5 (human-verify checkpoint) operator findings, 2026-05-11
amendments:
  - id: D-31-A4
    target: CLAUDE.md §1.2 + PLAN frontmatter D-31 (Vultr Day-1)
    nature: substrate pivot (primary → backup)
  - id: D-31-A4.1
    target: AMENDMENTS.md §D-31-A4 + Plan 03-01.5 (TensorWave-targeted) + CLAUDE.md §1.2
    nature: substrate pivot (TensorWave → RunPod primary; TensorWave demoted to secondary fallback)
  - id: D-32-A1
    target: CLAUDE.md §2.1 / §14 + bench/images.lock.yaml + dockerfiles/rocm/Dockerfile
    nature: image migration (ROCm 6.4 stub → ROCm 7.12 digest-pinned)
tags: [amendment, operator-checkpoint, rocm, image-pin, substrate-pivot, vultr, tensorwave, runpod]
---

# Plan 03-01 Amendments — Task 5 Checkpoint Closure

This document closes the Task 5 (`checkpoint:human-verify`) gate by recording the two
amendments operator-approved on 2026-05-11 after running the checkpoint verification
steps in `03-01-PLAN.md` §Task 5. The previous agent (commits `5a00169`, `b2dd730`,
`e110a9f`, `f6297e4`) carried CLAUDE.md assumptions forward verbatim; the operator's
own runs surfaced that two of those assumptions were stale or incorrect. Both
amendments are substrate-agnostic — they update *what we build with* but not the
HARNESS-03 design that's already on disk.

A third amendment, **D-31-A4.1**, was added later the same day after a ~10-minute
empirical investigation of RunPod's GraphQL surface revealed that RunPod publicly
lists MI300X at $1.99/GPU-hr Secure Cloud — a fact not present in CLAUDE.md §1.2.
D-31-A4.1 retargets the primary MI300X substrate to RunPod and demotes the
just-pivoted TensorWave to secondary fallback. See its own section below.

## Summary

| Amendment | What broke / what changed | Resolution | Scope |
| --------- | ------------------------- | ---------- | ----- |
| **D-32-A1** | `rocm/vllm:rocm6.4_mi300_ubuntu22.04_py3.11_vllm_0.10.x` tag does not exist on Docker Hub (CLAUDE.md §2.1 extrapolated a pattern that never matched AMD's actual schema) | Migrate base image to current AMD-published tag: `rocm/vllm:rocm7.12.0_gfx94X-dcgpu_ubuntu24.04_py3.12_pytorch_2.9.1_vllm_0.16.0` @ `sha256:997f858b…2a8f7` | `bench/images.lock.yaml` + `dockerfiles/rocm/Dockerfile` |
| **D-31-A4** | `GET /v2/plans?type=gpu` returned 400; correct endpoint is `/v2/plans-metal`; the one MI300X SKU is on-demand-disabled and forces buying an 8-GPU node at $14.80/hr preemptible | Pivot primary MI300X substrate to **TensorWave** (~$1.71/GPU-hr per CLAUDE.md §1.2); Vultr demoted to backup-only | Decision-level only — `orchestration/vultr_mi300x.py` stays in repo as backup; sentinel guard remains UNSET |
| **D-31-A4.1** | RunPod publicly lists MI300X at $1.99/GPU-hr Secure Cloud (per-GPU, on-demand, same surface as Phase 02's H100 work); CLAUDE.md §1.2 did not include this because the SKU appeared after CLAUDE.md was authored | Retarget primary MI300X substrate to **RunPod**. TensorWave demoted to secondary fallback (re-activated only if RunPod stock proves chronically unavailable). Vultr remains backup. | `.planning/phases/03-rocm-validation/03-01.5-PLAN.md` rewritten in place; previous TensorWave version preserved in git history; ROADMAP + REQUIREMENTS + STATE updated. |

Amendments D-32-A1 and D-31-A4 were operator-approved verbally during the Task 5
checkpoint. D-31-A4.1 was approved during a follow-up session ~10 minutes after
D-31-A4 once the RunPod GraphQL evidence was on the table. No additional operator
decision is required to close Plan 03-01.

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
  The operator builds + pushes that separately once a RunPod-validated dev
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

## D-31-A4.1: Substrate Pivot — TensorWave → RunPod (Day-1 Primary; supersedes D-31-A4)

### Context

Amendment D-31-A4 (above, recorded ~10 minutes before this one) pivoted Day-1
MI300X provisioning from Vultr to TensorWave. The corresponding follow-up plan
`03-01.5-PLAN.md` was authored to investigate TensorWave's provisioning surface
before scaffolding `orchestration/tensorwave_mi300x.py`, because CLAUDE.md §1.2
flagged TensorWave UX as "MEDIUM" and operator's sales-access response was
still pending.

Before that plan executed, a brief empirical investigation of RunPod's GraphQL
surface (the same surface Phase 02 already used for H100 work) revealed a fact
not present in CLAUDE.md §1.2: **RunPod publicly lists MI300X at $1.99/GPU-hr
Secure Cloud, per-GPU buyable, on-demand**. CLAUDE.md §1.2 does not name RunPod
for MI300X because the SKU appeared on RunPod after CLAUDE.md was authored.

This amendment retargets the primary substrate to RunPod.

### Evidence

A direct query against RunPod's GraphQL `gpuTypes` endpoint returned:

```
id:           "AMD Instinct MI300X OAM"
displayName:  "MI300X"
manufacturer: "AMD"
memoryInGb:   192
secureCloud:  true
communityCloud: false
maxGpuCount:  8
securePrice:      1.99   # on-demand, per-GPU-hr
secureSpotPrice:  1.99   # spot = same as on-demand (no spot discount)
communityPrice:   0.5    # irrelevant (communityCloud=false)
```

A follow-up `lowestPrice(input: {gpuCount: N})` query across `N in {1, 2, 4, 8}`
returned `stock=None` for all four shapes at probe time — the SKU is listed but
momentarily has no priced offer globally. This matches the H100 pattern observed
during Phase 02 (listed-but-thin stock that recovers as datacenters cycle) and
is addressable through Phase 02's existing stock-poll pattern in
`tools/probe_runpod_stock.py`.

### Rationale

1. **Single substrate for Phase 0.** RunPod handles both Phase 02's H100 work
   (already done) and Phase 03's MI300X work (this amendment). One set of
   substrate caveats to document in Phase 4 derating; one auth surface; one
   set of orchestration patterns to maintain. The version-skew advantage from
   D-32-A1 (matching gfx94X / gfx1151 vLLM images) compounds with this:
   single substrate + matching image versions → tightest possible Phase 4
   cross-substrate consistency story.

2. **Zero new auth burden.** `RUNPOD_API_KEY` is already in the operator's env
   from Phase 02. No new dashboard onboarding, no sales-contact dependency
   (which was the open TensorWave blocker), no new account.

3. **Tooling reuse.** Phase 02 already shipped:

   - `tools/probe_runpod_stock.py` (extended for MI300X in Plan 03-01.5 Task 1)
   - `tools/probe_runpod_dc.py` (datacenter awareness)
   - `tools/find_runpod_volume.py` (network-volume locator)
   - `orchestration/runpod_h100.py` (SDK provisioning pattern to mirror)
   - `cost/adapters/runpod.py` (Pitfall-B cap-watch posture; acceptable for MI300X)
   - `results/_pulled/<pod-id>/` pull-back pattern (12+ entries from H100 work)
   - The `runpod` Python SDK in `requirements.lock`

   This is roughly 80% of the provisioning + telemetry surface for the new
   module. `orchestration/runpod_mi300x.py` is mostly composition over
   existing primitives.

4. **Per-GPU buyable, public self-serve.** Unlike Vultr's 8-GPU bare-metal-only
   shape (D-31-A4 evidence) and unlike TensorWave's still-unknown provisioning
   surface, RunPod sells per-GPU MI300X on-demand through the same GraphQL +
   SDK that Phase 02 already uses.

5. **Trivial cost premium.** $1.99/GPU-hr vs TensorWave's $1.71/GPU-hr = $0.28
   premium. At Phase 0's planned ~23 MI300X GPU-hours (CLAUDE.md §13), that's
   **+$6.44 total** — well under 5% of the $150 program ceiling.

### Risk

The dominant risk is `stock=None` on the stock-poll surface. Mitigation lives
in Plan 03-01.5 Task 1 (extend `probe_runpod_stock.py`) + Task 2 (stock-poll
watchdog inside `orchestration/runpod_mi300x.provision()` raises a STOCK error
before any spend if 60 sec of polling returns None) + plan-level HALT-STOCK
branch that re-activates TensorWave investigation as a new 03-01.6 plan if
24h of polling returns None at the documented cadence.

### Plan impact

| File / artifact | Status after this amendment |
| --------------- | --------------------------- |
| `.planning/phases/03-rocm-validation/03-01.5-PLAN.md` | **Rewritten in place** targeting RunPod instead of TensorWave. Previous TensorWave version preserved in git history at commit `f788b2d` (the commit that introduced the TensorWave plan); reachable via `git show f788b2d:.planning/phases/03-rocm-validation/03-01.5-PLAN.md`. |
| `.planning/ROADMAP.md` Phase 3 description | Updated to reference "RunPod" wording for the 03-01.5 enabler row; plan count stays 7. |
| `.planning/REQUIREMENTS.md` CLOUD-02 row | Description updated to reference RunPod primary; row count unchanged. |
| `.planning/STATE.md` | D-31-A4.1 appended to Decisions; open blocker reworded from "TensorWave harness" to "RunPod harness". |
| `orchestration/vultr_mi300x.py` | **Unchanged.** Still backup, sentinel UNSET intact, all 10 tests still pass. |
| `orchestration/tensorwave_mi300x.py` | **Unchanged.** Phase-1 stub remains. Only re-activated if HALT-STOCK fires from Plan 03-01.5 Task 6 and a new 03-01.6 plan is authored against the original TensorWave-targeted scope. |
| `bench/images.lock.yaml` rbox-pod-rocm row | Stays `digest: pending`. The ROCm 7.12 base from D-32-A1 is substrate-agnostic; derived-image push is still operator-deferred until a RunPod-validated dev pod confirms the new base runs harness deps cleanly. |
| `dockerfiles/rocm/Dockerfile` | **Unchanged.** D-32-A1 base image pin is correct. |
| Plan 03-01 already-completed deliverables (substrate/rocm.py, config/budget.yaml phase3 block, sanity_strata.yaml tts.primary, etc.) | **Unchanged.** All Plan 03-01 outputs survive both D-31-A4 and D-31-A4.1; they are substrate-orchestration-agnostic. |

### Phase 0 budget impact

| Line item | Before D-31-A4.1 (TensorWave $1.71/GPU-hr) | After D-31-A4.1 (RunPod $1.99/GPU-hr) | Delta |
| --------- | ------------------------------------------ | ------------------------------------- | ----- |
| GATE-CHATTERBOX-D1 (D-36 cap $4.00) | 2 hr × $1.71 = $3.42 | 2 hr × $1.99 = $3.98 | +$0.56 (within cap) |
| G1 sanity pod (CLAUDE.md §13) | ~$9 → ~$8.55 | ~$9 → ~$9.95 | +$1.40 |
| Full Phase 3 MI300X subtotal (CLAUDE.md §13) | ~$54 → ~$39.33 | ~$54 → ~$45.77 | +$6.44 |
| Program ceiling ($150) | $54 / $150 = 36% | $54 / $150 = 36% | unchanged (still fits) |

The +$6.44 premium is trivial against the $150 ceiling and against the
operational benefit of reusing Phase 02's RunPod tooling.

### Deviation from CLAUDE.md §1.2

CLAUDE.md §1.2's "TL;DR" table reads:

> MI300X cloud | **TensorWave** primary, **Vultr** as backup

RunPod is NOT listed in §1.2 for MI300X. D-31-A4.1 deviates from §1.2
intentionally because:

- The empirical evidence above postdates CLAUDE.md's authoring
- The cost premium is trivial
- The tooling-reuse benefit is large
- A single substrate for the entire Phase 0 program simplifies Phase 4

The new effective substrate ordering for Phase 0 is:

1. **RunPod** (primary, D-31-A4.1) — $1.99/GPU-hr Secure Cloud, per-GPU
2. **TensorWave** (secondary fallback, demoted from D-31-A4 primary) — only re-activated if HALT-STOCK fires
3. **Vultr** (backup, demoted from original D-31 primary by D-31-A4) — only viable if Vultr publishes a per-GPU MI300X SKU

This ordering should be reflected in any future CLAUDE.md edit. This
amendment file is the canonical source until then.

### What's NOT changed

- `orchestration/vultr_mi300x.py` and `tests/test_vultr_provisioning.py` are
  untouched. Sentinel stays UNSET; backup posture preserved.
- `orchestration/tensorwave_mi300x.py` is untouched (Phase-1 stub).
- `bench/images.lock.yaml` `base_image_digest` for ROCm 7.12 is correct
  (D-32-A1). Substrate-agnostic.
- `dockerfiles/rocm/Dockerfile` digest pin is correct (D-32-A1).
- Plan 03-01 already-completed deliverables — all preserved.
- The deferred work items below (TensorWave module + derived-image build) are
  re-scoped, not eliminated: TensorWave module is now conditional on HALT-STOCK;
  derived-image build is now operator-driven against a RunPod dev pod instead
  of a TensorWave dev pod.

### Why operator approved

1. **Risk reduction.** Eliminating the TensorWave provisioning-surface
   unknown removes the dominant Plan 03-01.5 risk from the prior version.
2. **Tooling reuse.** ~80% of the Phase-02 RunPod infrastructure applies
   directly; planning + execution overhead for the substrate pivot is
   minimized.
3. **Budget headroom.** +$6.44 against $150 ceiling is comfortable.
4. **Single-substrate Phase 4 story.** Cross-substrate consistency check
   (DERATE-03) becomes "RunPod CUDA → RunPod ROCm" — one provider, two SKUs,
   instead of "RunPod CUDA → TensorWave ROCm" with two providers and two
   orchestration patterns.

---

## Deferred Work (Created by These Amendments)

### 1. RunPod MI300X orchestration module (`orchestration/runpod_mi300x.py`)

**Re-scoped from D-31-A4 (originally `orchestration/tensorwave_mi300x.py`).**
Now lives in **Plan 03-01.5 (RunPod-retargeted, D-31-A4.1)**. Task 2 of that
plan creates the module with shape-parity to `orchestration/vultr_mi300x.py`;
Tasks 3-5 wire tests + dispatch shim + smoke pod.

### 2. TensorWave orchestration module (`orchestration/tensorwave_mi300x.py`)

**Conditional** on HALT-STOCK firing from Plan 03-01.5 Task 6. If RunPod stock
proves chronically unavailable (24h of stock=None polls), planner authors a
new **03-01.6** plan re-activating the original D-31-A4 scope (research +
scaffold TensorWave provisioning). Until that conditional fires, the Phase-1
stub remains untouched.

### 3. `rbox-pod-rocm` pod image build + push

**Unchanged.** The derived pod image (FROM the ROCm 7.12 base + harness deps
+ baked ENTRYPOINT) still needs to be built and pushed to GHCR. Operator does
this once a RunPod-validated dev pod (from Plan 03-01.5 Task 6 smoke)
confirms the new base actually runs the harness deps (faster-whisper / Kokoro
/ Chatterbox) cleanly.

Build command (unchanged from Plan 03-01 Task 2):

```bash
echo "$GHCR_TOKEN" | docker login ghcr.io -u consultingfuture4200 --password-stdin
scripts/build_pod_image_rocm.sh ghcr.io/consultingfuture4200/rbox-pod-rocm:v1 --push
```

Then paste the resolved `@sha256:...` digest into:

- `bench/images.lock.yaml` `rbox-pod-rocm` row (`digest: pending` → real)
- `orchestration/runpod_mi300x.py` `_DEFAULT_IMAGE_RUNPOD` (primary; D-31-A4.1)
- `orchestration/vultr_mi300x.py` `_DEFAULT_IMAGE_ROCM` (only when Vultr is
  re-promoted from backup; until then, sentinel stays)
- A future `orchestration/tensorwave_mi300x.py` `_DEFAULT_IMAGE_ROCM`
  constant (only if HALT-STOCK fires and 03-01.6 scaffolds the module)

---

## Phase 4 Opportunity Callout

The matching gfx1151 image
(`sha256:8a09c886e1bab993f5e12faec669579c8455e5ca1ab31553350f87c3e26ca5a1`)
means Phase 4's derating story can — for the first time — compare MI300X and
Strix Halo measurements *with the same ROCm version, the same PyTorch wheel,
and the same vLLM*. The DERATE-03 cross-substrate consistency check becomes
a real apples-to-apples comparison instead of a within-25%-with-version-skew
estimate.

With D-31-A4.1 layered on top (single substrate for both Phase 0 rails), the
Phase 4 derating story is the cleanest it can plausibly be at this budget:
one provider, two SKUs, matching image versions, single auth surface.

This should be incorporated into the Phase 4 CONTEXT (`04-CONTEXT.md`)
when that phase is planned. The cost is essentially zero — the operator
already has both digests on hand.

---

## Approval

- D-32-A1 + D-31-A4: operator approved verbally during the Task 5 checkpoint
  session on 2026-05-11.
- D-31-A4.1: operator approved during a follow-up session ~10 minutes later
  on 2026-05-11, after the RunPod GraphQL evidence (empirical, captured in
  this document under §D-31-A4.1 Evidence) was on the table.

No further decision required to close Plan 03-01.
