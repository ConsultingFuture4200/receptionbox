---
phase: 02-cuda-pre-flight
plan: 07
subsystem: pod orchestration / smoke pre-conditions
gap_closure: true
closes_gaps:
  - "Plan 02-04 Task 4 deferral (smoke real-spend prerequisites)"
  - "pod_entrypoint.sh had no in-pod service orchestration (vLLM / Kokoro)"
  - "corpus_500 audio not in image (.dockerignore excluded it)"
  - "operator-side transport: pivoted from rsync push to fetch-pod pull"
requires:
  - "Plan 02-05 (lockfile data + bootstrap SDK provisioning)"
  - "Plan 02-06 (custom rbox-pod image base, entrypoint baked, digest-pinned)"
provides:
  - "Dockerfile: Kokoro-FastAPI installed in isolated venv on :8005"
  - "Dockerfile: corpus_500 bundled in image"
  - "Dockerfile: openssh-server + sshd config + key acceptance"
  - "tools/pod_entrypoint.sh: _start_inference_services + DIAG_MODE branch + Python self-terminate"
  - "tools/fetch_results.py: diag-pod-based result pull from /models/_results/"
  - "Image v8 → v9 → v10 → v11 → v13 → v14 → v15 → v16 iteration"
  - "Smoke real-spend verdict pass (run 2f6b, session 20260509T231720Z)"
tags: [orchestration, smoke, multi-service, transport-pivot, gap-closure]
---

# Phase 02 Plan 07 — Summary

## Outcome

Smoke gate runs end-to-end on real H100 with verdict `pass=True` across all six D-25 sub-criteria (session `20260509T231720Z`, pod `d6ii16l245t41m`, run id `2f6b0aa20acb4ebda0302d51b98c6334`). Closes Plan 02-04 Task 4.

This plan went through eight image iterations and one transport-architecture pivot. Documented below for forensics.

## Task delivery vs original plan

| Task | Planned | Delivered |
|---|---|---|
| T1 — Chatterbox-TTS in image | Bundle `chatterbox-tts` + devnen FastAPI server | **Scoped out.** `chatterbox-tts` requires Python 3.10; image base (`vllm/vllm-openai:v0.10.0`) ships Python 3.12. `substrate/cuda.py`'s DR-27 fallback routes TTS to Kokoro when Chatterbox health=False, which is acceptable for G1 smoke + G1 sanity. Chatterbox install gets a follow-up plan before G7 (TTS A/B) needs it. |
| T2 — Kokoro-FastAPI in image | Clone + pip install upstream `remsky/Kokoro-FastAPI` | Delivered, but in an **isolated venv** (`/opt/kokoro-venv`) to prevent its torch dependency from upgrading the system torch that vllm + faster-whisper rely on. Image v9 switched the kokoro extra from `[gpu]` → `[cpu]` to shrink the image from ~16 GB to ~13 GB compressed (CPU TTS adds ~2 s/call × 5 smoke calls = negligible vs 30-min budget). |
| T3 — Multi-service startup | `_start_inference_services()` in `pod_entrypoint.sh` | Delivered. vLLM via base image / Kokoro via venv; health-budget tuned over iterations (v13 bumped both). Chatterbox path omitted per T1. Symlink at startup wires `/models/hexgrad__Kokoro-82M/<rev>/` into kokoro-server's `MODEL_DIR`. |
| T4 — `corpus_500` in image | Un-ignore `corpus_500` in `.dockerignore` | Delivered. Image audit (`results/smoke/1778368799.audit.json`) reports found_count=500 (expected_count=755 — `corpus_g711` and `corpus_hesitation` still excluded by design, smoke needs only `corpus_500`). Image-size delta ≈ +150 MB compressed. |
| T5 — Operator rsync receiver | Tailscale or public-IP rsync push from pod | **Architecture pivoted.** rsync-push required pod-side egress to the operator workstation, which surfaced Tailscale-on-pod setup friction. Replaced with pull-based transport: `tools/fetch_results.py` spawns a tiny diag pod (~$0.05 / RTX 4090 @ $0.34/hr × ~9 min) that mounts the same network volume and scps `/models/_results/` back to the operator. `pod_entrypoint.sh` now writes results to the network volume and exits without needing inbound reachability to the workstation. Inbound sshd was retained for diagnostic SSH access (image v8). |
| T6 — Build + push image v4 | Single rebuild | **Eight iterations** (v8 → v9 → v10 → v11 → v13 → v14 → v15 → v16). See "Image iteration history" below. |
| T7 — Smoke real-spend | Single pass | Smoke verdict reached `pass=True` after multiple bug-fix iterations (see preflight session log in 02-04-SUMMARY). $0 cumulative spend reported by ledger, ~$0.14 estimated true spend per pass. |
| T8 — Close 02-04-SUMMARY | Write summary | Delivered (this commit). |

## Image iteration history

| Image | Trigger | Fix |
|---|---|---|
| v8 | First build after T1–T4 land | Inbound sshd, base64 SSH key forwarding, AWQ flag drop (`--quantization awq` wasn't valid for the picked model variant), Kokoro symlink |
| v9 | Image size 16 GB compressed | Switched Kokoro extra `[gpu]` → `[cpu]` |
| v10 | Pod restart-looped before _entrypoint.sh log was reachable | Tee entrypoint log to `/models/_boot` for failed-host triage |
| v11 | Restart-loop diagnosis still ambiguous | Pre-tee stderr echoes for visibility before tee opens |
| (v12 skipped) |  |  |
| v13 | vLLM and Kokoro health-checks intermittently failing | Bumped health budgets; added DIAG_MODE branch; pod self-terminates via Python (not the bash trap, which can race with TERM during pip-fueled service starts) |
| v14 | Pod-side rsync push fragile / Tailscale-on-pod friction | Result transport via fetch_pod pull (`tools/fetch_results.py`); cache_bootstrap hardening |
| v15 | Whisper `--whisper-dir` not resolving in some configs | Pass `--whisper-dir` from `bootstrap_index.json` to the gate runner explicitly |
| v16 | G2 sanity wanted corpus_g711 reference transcripts | Bundled `assets/corpus_g711/*.txt` references (audio still excluded); Whisper-path resolution in substrate now reads logical-name → bootstrap-index path |

Additional preflight-driver fix landed alongside (not an image bump): `fix(preflight): terminate pod on TIMEOUT instead of leaking RUNNING` (commit `ab31d97`) — closes a leaked-pod failure mode the smoke iteration surfaced.

## Process notes (carry-forward)

- "A plan that ends in a real-spend acceptance criterion must enumerate every service / asset / config item the spend depends on, not just the orchestrator code." (from original 02-07-PLAN.md `Process Notes`). 02-07 itself proved this — the plan listed three blockers and uncovered five more during execution.
- The cost-watch ledger reports $0.00 because the RunPod billing API lags pod termination. The wall-clock × hourly-rate estimate is the operative truth for budget gates pre-settlement.
- Transport architectures should prefer **pull from neutral ground** (network volume) over **push to operator** when egress reachability is uncertain. The pivot to `fetch_results` removed an entire class of "is my workstation reachable from RunPod" failure modes.

## Operator's next action

Already documented in `02-04-SUMMARY.md`. Short version: `/gsd-verify-work 2` → choose sanity-now vs sanity-as-Phase-3-precondition → `/gsd-discuss-phase 3`.
