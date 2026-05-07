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

### 2.1 Operator-host reachability (Plan 02-07 prerequisite)

The pod's `_shutdown` rsync step targets `${OPERATOR_USER}@${OPERATOR_HOST}` over SSH. RunPod pods egress from the data center; your workstation must be reachable from there. Two paths:

**Tailscale (recommended — no public-IP exposure):**
- [ ] Install Tailscale on the workstation: `curl -fsSL https://tailscale.com/install.sh | sh && sudo tailscale up`
- [ ] Install Tailscale on the pod: it's NOT in the rbox-pod image; instead set `OPERATOR_HOST=<tailscale-ip-of-workstation>` and use the [Tailscale on RunPod guide](https://tailscale.com/kb/1278/) to add the pod as an ephemeral node — OR fall back to the public-IP path below.
- [ ] Test: from another machine, `ssh -i ~/.ssh/rbox_phase2 operator@<tailscale-ip> "echo ok"`.

**Public IP / port forward:**
- [ ] Confirm port 22 (or your sshd port) is open inbound: `sudo ufw status` and `sudo ss -tlnp | grep :22`.
- [ ] Confirm `sshd` is running: `sudo systemctl status ssh`.
- [ ] (Optional but recommended) restrict the new key in `authorized_keys` to RunPod egress CIDRs:
  ```
  from="*.runpod.io,*.runpod.net,...",no-port-forwarding,no-agent-forwarding,command="rsync ..." ssh-ed25519 AAAA... rbox_phase2
  ```
- [ ] Test from another machine: `ssh -i ~/.ssh/rbox_phase2 operator@<public-ip-or-hostname> "echo ok"`.

If neither is set, smoke still proves the runner correctness BUT result data does not come back; D-25 sub-criteria (a) `5_rows`, (e) `env_sidecar`, (f) `audit_clean` will fail because `_validate_smoke` looks for `results/smoke/*.jsonl` locally.

### 2.2 Image readiness (Plan 02-07)

Smoke and sanity gates depend on the rbox-pod image v4+ which bakes:

- vLLM + faster-whisper in system Python (already in v1+).
- Kokoro-FastAPI in an isolated venv at `/opt/kokoro-venv/` (NEW in v4 — TTS server).
- `assets/corpus_500/` audio files (NEW in v4 — smoke needs ≥5 calls).
- `pod_entrypoint.sh` `_start_inference_services` that boots vLLM (port 8000) and Kokoro (port 8005), health-checks both, then runs the gate runner.

Confirm `orchestration/runpod_h100.py:_DEFAULT_IMAGE` matches the v4+ digest before `--mode smoke`. Chatterbox is intentionally NOT in v4 (substrate/cuda.py's DR-27 fallback routes TTS to Kokoro when Chatterbox health=False); a follow-up plan adds Chatterbox before G7 (TTS A/B) needs it.

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

This calls `orchestration.runpod_h100.provision(gate="bootstrap", ...)` (cost-ledger gated, same as smoke/sanity) which spins a bootstrap pod with `BOOTSTRAP_MODE=1`. The pod entrypoint reads that env var and runs `python -m tools.cache_bootstrap --target /models --lockfile bench/models.lock.yaml`, populating `/models/{repo_safe}/{revision}/` for all 4 HF models. The pod self-terminates when bootstrap exits (no SSH/rsync needed for bootstrap — there are no result files to pull). Projected cost: $0.67 ceiling (15 min × $2.69/hr); typical actual: $0.50.

Closed gap: prior to Plan 02-05, this step deferred to operator-side `runpodctl pod create` because (a) `bench/models.lock.yaml` had `revision: pending` for all 4 entries and (b) `--mode bootstrap` returned an `operator-action` stub instead of provisioning. Plan 02-05 resolved real commit SHAs + per-file SHA-256 in the lockfile AND replaced the operator-action stub with the SDK call. Phase 2 is now fully reproducible from `~/RBOX` per CLAUDE.md §Constraints.

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
