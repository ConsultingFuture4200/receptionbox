# Phase 2 Operator Checklist

Status target: Phase 2 (CUDA pre-flight) ready for real spend on RunPod H100.

## TL;DR

- Budget ceiling: $14 (CLAUDE.md §13). Smoke alone: ~$1.35 projected, <$1 actual target.
- Hard pre-condition: `authorize_spend()` is the only programmatic gate. With $75 prepaid + auto-recharge OFF, the RunPod cap is the operator's deposit, NOT a programmatic API cap (Pitfall B in `.planning/phases/01-foundation/01-RESEARCH.md`).
- Default workflow: bootstrap pod (one-time, ~$0.50) → smoke pod (~$1) → sanity sequence (~$2-3) → teardown.
- Driver: `uv run python -m tools.run_preflight --mode {bootstrap,smoke,sanity}`.

## 1. Pre-flight environment

Required env vars (export before invoking the driver):

| Var | Source | Notes |
|-----|--------|-------|
| `RUNPOD_API_KEY` | RunPod Dashboard → Settings → API Keys | Without this, the driver runs in DRY RUN mode (safe for development). |
| `RUNPOD_NETWORK_VOLUME_ID` | RunPod Dashboard → Storage → Network Volumes (create 50 GB volume in same region as the H100 pod) | The `/models` cache lives here per D-19. |
| `SSH_PRIVATE_KEY` | Operator-generated: `ssh-keygen -t ed25519 -f ~/.ssh/rbox_phase2 -N ''; export SSH_PRIVATE_KEY="$(cat ~/.ssh/rbox_phase2)"` | Pod-side rsync writes this to `~/.ssh/id_ed25519`. NEVER log this value. |
| `SSH_PUBKEY` | `cat ~/.ssh/rbox_phase2.pub` | Provisioning passes this to the pod env so it can be added to `authorized_hosts`. |
| `OPERATOR_HOST` | Operator workstation hostname/IP reachable from RunPod | Without this, rsync silently no-ops; smoke still proves correctness. |
| `OPERATOR_USER` | Defaults to `operator`; override if your workstation user differs. | |

## 2. RunPod dashboard

- [ ] Confirm $75 prepaid balance shown on Billing page.
- [ ] Confirm "Auto-Recharge" is OFF on Billing page (this is the cap mechanism — Pitfall B).
- [ ] Confirm a 50 GB network volume exists in a region that hosts H100 PCIe (e.g., US-CA-2). Record its id as `RUNPOD_NETWORK_VOLUME_ID`.
- [ ] On operator workstation: append the contents of `~/.ssh/rbox_phase2.pub` to `~/.ssh/authorized_keys` so the pod can rsync.

## 3. Per-gate spend ceilings (from `config/budget.yaml` `phase2` block)

| Gate | max_minutes | Projected cost @ $2.69/hr |
|------|-------------|---------------------------|
| smoke | 30 | $1.35 |
| g1 | 30 | $1.35 |
| g2 | 15 | $0.67 |
| g3 | 10 | $0.45 |
| g5 | 15 | $0.67 |
| Sum | 100 min | $4.49 (sanity sequence) |
| Cache bootstrap | one-time | ~$0.50 |
| **Phase 2 total target** | | **~$5-6** |
| **Phase 2 ceiling** | | **$14 (CLAUDE.md §13)** |

## 4. Run sequence

Step 1 — Bootstrap the model cache (one-time):

```
export RUNPOD_API_KEY=...
export RUNPOD_NETWORK_VOLUME_ID=...
uv run python -m tools.run_preflight --mode bootstrap
```

This creates a small bootstrap pod that runs `tools/cache_bootstrap.py`, populating `/models/{repo_safe}/{revision}/` for all 4 HF models (`bench/models.lock.yaml`). The pod self-terminates when bootstrap exits.

Step 2 — Smoke (PREFLIGHT-01):

```
export SSH_PRIVATE_KEY="$(cat ~/.ssh/rbox_phase2)"
export SSH_PUBKEY="$(cat ~/.ssh/rbox_phase2.pub)"
export OPERATOR_HOST=...
uv run python -m tools.run_preflight --mode smoke
```

Expected: pod boots, runs 5 calls of G1, watchdog or natural exit triggers SIGTERM trap, pre-teardown audit runs, results rsynced. Driver validates D-25 (a)-(f); on PASS the session manifest's `gates[0].smoke_verdict.pass` is `true`.

Step 3 — Sanity (PREFLIGHT-02):

```
uv run python -m tools.run_preflight --mode sanity
```

Sequential G1 (10) + G2 (10) + G3 (10) + G5 (10) sanity runs driven by `config/sanity_strata.yaml` (D-27). G7 deferred to MI300X (Phase 3) per the Makefile message.

## 5. Failure handling

- **Smoke fail** (any of `a_5_rows`, `b_under_30min`, `c_under_1usd`, `d_per_stage_timings`, `e_env_sidecar`, `f_audit_clean` is `false`): `results/smoke/*.audit.json` may show why; do NOT advance to sanity. Triage:
  - Missing per-stage timing usually = LiveKit shim fallback (no GPU latency captured)
  - Bad rsync usually = SSH key/host issue
  - >$1 usually = pod hung > 30 min
- **Pod stuck**: `runpodctl pod stop $POD_ID`. Cost-watch (running locally during the session) will also hard-stop if cumulative > balance.
- **Audit fail (D-22, fail-loud)**: results data does NOT come back; only the audit log is rsynced. Read the audit log first (in `~/RBOX/results/{gate}/*.audit.json`); the `manifest_check`/`extension_check`/`pii_check` sections tell you which check failed.
- **BudgetExhausted from cost ledger**: provisioning refused before any pod created. Top up RunPod balance OR reduce `phase2.max_minutes_per_gate` and re-run.

## 6. Post-flight verification

After `--mode smoke` passes:

- [ ] `wc -l results/smoke/*.jsonl` shows 5
- [ ] `results/smoke/*.env.json` reads back via `harness.env_sidecar.read_env_sidecar` without error
- [ ] `results/smoke/*.audit.json` shows `summary.violations == 0`
- [ ] Every result row has `substrate == "cuda"` (PREFLIGHT-03)
- [ ] Every result row has non-NULL `(image_digest, model_shas, asset_manifest_sha, git_commit, run_id, timestamp_utc)` (REPRO-03)

After `--mode sanity` passes:

- [ ] `results/g1/*.jsonl` has 10 rows; same for `results/g{2,3,5}/`
- [ ] `results/preflight/{session_id}.json` lists all 4 gates with `status` in {`EXITED`, `GONE`, `STOPPED`, `TERMINATED`}
- [ ] Total spend (cumulative across all 4 gates + bootstrap) < $14
- [ ] Phase 2 closeout: ready to advance to Phase 3 (MI300X) per `.planning/ROADMAP.md`

## 7. Known operational pitfalls

- **Pitfall B (RunPod cap is credit-based)**: Auto-Recharge OFF is the actual cap. If you accidentally enable auto-recharge mid-run, the cost-watch hard-stop is your only line of defense.
- **Pitfall 5 (real-audio leak)**: D-22 audit is the failsafe. Do NOT manually copy any audio file into `~/RBOX/assets/` outside of `make assets`; the audit will refuse.
- **CLOUD-02 (TensorWave)**: Phase 2 does NOT touch TensorWave. Phase 3 will. The TensorWave deposit and key handling are separate operator setup tasks.
- **G7 not exercised here**: PREFLIGHT-02 explicitly defers G7 to MI300X. Do not edit `--mode` to add g7 — the Makefile target `g7` prints "deferred to MI300X" and exits non-zero.

---

Generated by Plan 02-04. Last updated: 2026-05-06.
