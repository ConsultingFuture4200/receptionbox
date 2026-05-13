#!/usr/bin/env bash
# Phase 2 pod entrypoint (CLOUD-04, D-16/D-17/D-18).
#
# Runs as the RunPod pod's container CMD. Inputs (env vars set by
# orchestration/runpod_h100.py provision()):
#   GATE              — smoke|g1|g2|g3|g5
#   MAX_MINUTES       — watchdog kill timer (default 30)
#   SSH_PRIVATE_KEY   — operator-injected; written to ~/.ssh/id_ed25519
#   OPERATOR_HOST     — operator workstation hostname / IP for rsync target
#   OPERATOR_USER     — defaults to 'operator'
#   RUNPOD_POD_ID     — populated by RunPod runtime; used for self-stop
#
# Lifecycle:
#   1. Install SSH key (mode 0600); add operator host to known_hosts
#   2. Start cost-watch background daemon (runpod adapter only)
#   3. Start watchdog (sleep $MAX_MINUTES*60; kill -TERM $$)
#   4. Exec gate runner (smoke=g1.runner --n-calls=5; others = sanity strata)
#   5. On TERM/INT trap → _shutdown:
#        a. SIGTERM the runner; wait up to 60s for graceful drain; SIGKILL
#        b. Run tools/audit_pod_state.py (D-22 fail-loud)
#        c. Audit pass → bash tools/rsync_results.sh (full results push)
#           Audit fail → bash tools/rsync_results.sh --audit-only (D-23: log
#           is rsynced but result data is NOT)
#        d. runpodctl pod stop $RUNPOD_POD_ID (self-terminate)
#
# Strict: assets/ is NEVER copied back. The rsync source is results/ only.

# Plan 02-07 v11: pre-flight stderr echoes BEFORE `set -e` and the v10 tee
# redirect. v10 added /models/_boot tee but pod 8040qpqsg5p0be (2026-05-08)
# was in a Docker restart loop with only the NVIDIA base banner in container
# logs and ZERO `[entrypoint]` lines — entrypoint was exiting silently before
# the redirect block ran. These stderr writes hit RunPod's log capture even
# if `set -e` kills us on cd / GATE-unset / tee-block-fail, so the next
# failure mode leaves a fingerprint instead of a black hole.
echo "[entrypoint] v11 starting pid=$$ GATE=${GATE:-UNSET} MAX_MINUTES=${MAX_MINUTES:-UNSET} BOOTSTRAP_MODE=${BOOTSTRAP_MODE:-0} WORKSPACE=${WORKSPACE:-UNSET} HOSTNAME=${HOSTNAME:-} RUNPOD_POD_ID=${RUNPOD_POD_ID:-}" >&2
echo "[entrypoint] v15 pwd=$(pwd) models_dir=$( [[ -d /models ]] && echo yes || echo no ) models_writable=$( [[ -w /models ]] && echo yes || echo no ) workspace_dir=$( [[ -d /workspace ]] && echo yes || echo no ) DIAG_MODE=${DIAG_MODE:-0}" >&2

# Plan 02-07 v12: DIAG_MODE=1 short-circuits to sshd + sleep infinity.
# Lets the operator ssh into a stable container to step through smoke
# startup manually when remote diagnosis is needed. Skipped during normal
# smoke / bootstrap / sanity runs (DIAG_MODE unset → falls through).
# Done BEFORE `set -e` and the GATE check so DIAG_MODE works even when
# the smoke env vars are absent.
if [[ "${DIAG_MODE:-0}" == "1" ]]; then
    echo "[entrypoint] DIAG_MODE=1 — installing pubkey + starting sshd, then sleep infinity" >&2
    mkdir -p /root/.ssh && chmod 700 /root/.ssh
    if [[ -n "${SSH_PUBKEY:-}" ]]; then
        printf '%s\n' "$SSH_PUBKEY" >> /root/.ssh/authorized_keys
    fi
    if [[ -n "${PUBLIC_KEY:-}" && "$PUBLIC_KEY" != "null" ]]; then
        grep -qF "$PUBLIC_KEY" /root/.ssh/authorized_keys 2>/dev/null \
            || printf '%s\n' "$PUBLIC_KEY" >> /root/.ssh/authorized_keys
    fi
    chmod 600 /root/.ssh/authorized_keys
    /usr/sbin/sshd -D -e > /tmp/sshd.log 2>&1 &
    echo "[entrypoint] DIAG sshd started (log: /tmp/sshd.log) — entering sleep infinity" >&2
    exec sleep infinity
fi

set -euo pipefail

: "${GATE:?GATE env var required}"
: "${MAX_MINUTES:=30}"
: "${OPERATOR_USER:=operator}"
WORKSPACE="${WORKSPACE:-/workspace}"
cd "$WORKSPACE"

# Plan 02-07 v10: tee all entrypoint stdout+stderr to a per-pod log file on
# the network volume so failed-host pods (uptime=0, dockerId=null pathology
# observed under RunPod support ticket 2026-05-08) leave evidence behind.
# Subsequent bootstrap pods can `ls /models/_boot/` to triage. Volume mount
# may not be ready instantly on every host; mkdir + tee tolerate a missing
# /models gracefully (we lose log capture on those pods, container still
# runs).
if [[ -d /models ]] && mkdir -p /models/_boot 2>/dev/null; then
    BOOT_LOG="/models/_boot/$(date -u +%Y%m%dT%H%M%SZ)-${HOSTNAME:-$(hostname)}-${RUNPOD_POD_ID:-nopod}-${GATE}.log"
    exec > >(tee -a "$BOOT_LOG") 2>&1
    echo "[entrypoint] boot log -> $BOOT_LOG"
fi

# Plan 02-05 Task 2: bootstrap mode short-circuits to cache_bootstrap, then
# exits. No gate runner, no rsync, no audit chain — there are no result
# files to pull. Same volume mount (/models) as smoke/sanity so the cache
# survives across pods (D-19, D-21).
if [[ "${BOOTSTRAP_MODE:-0}" = "1" ]]; then
    echo "[entrypoint] BOOTSTRAP_MODE=1 — running cache_bootstrap and exiting"
    # The pod image installs deps into system Python via pip (Dockerfile).
    # `uv run` would create a separate Python 3.11 venv (per pyproject
    # requires-python) that does NOT inherit those deps — so always invoke
    # the system `python` directly. Same applies to the gate-runner and
    # cost-watch invocations below (plan 02-06).
    python -m tools.cache_bootstrap \
        --target /models --lockfile bench/models.lock.yaml
    _rc=$?
    echo "[entrypoint] bootstrap exit=${_rc}"
    # Self-terminate the pod so RunPod's container-restart policy doesn't
    # respawn the entrypoint into an idempotent SKIP loop after success
    # (plan 02-06 known-limitation fix). The Python `runpod` SDK is
    # installed in the image (requirements.lock); RUNPOD_API_KEY is
    # injected by orchestration/runpod_h100.py:provision() only for the
    # bootstrap gate. runpodctl exists in the image but doesn't read the
    # env var reliably (returns 403). Best-effort: any failure here means
    # the container exits cleanly, gets restarted by Docker into a SKIP
    # loop, and the operator / driver-watchdog kills the pod conventionally.
    if [[ -n "${RUNPOD_POD_ID:-}" && -n "${RUNPOD_API_KEY:-}" ]]; then
        echo "[entrypoint] bootstrap done — stopping pod ${RUNPOD_POD_ID}"
        python - <<PYEOF || true
import os, runpod
runpod.api_key = os.environ["RUNPOD_API_KEY"]
runpod.stop_pod(os.environ["RUNPOD_POD_ID"])
print("[entrypoint] runpod.stop_pod accepted")
PYEOF
    fi
    exit "${_rc}"
fi

_setup_ssh() {
    # Plan 02-07 fix: orchestration passes the key as SSH_PRIVATE_KEY_B64 to
    # avoid breaking RunPod's GraphQL mutation on embedded newlines (multi-
    # line PEM). Falls back to plain SSH_PRIVATE_KEY for legacy callers.
    local key_data=""
    if [[ -n "${SSH_PRIVATE_KEY_B64:-}" ]]; then
        key_data=$(printf '%s' "$SSH_PRIVATE_KEY_B64" | base64 -d)
    elif [[ -n "${SSH_PRIVATE_KEY:-}" ]]; then
        key_data="$SSH_PRIVATE_KEY"
    fi
    if [[ -n "$key_data" ]]; then
        mkdir -p ~/.ssh
        # Write the key value to a file. Never echo it to stdout/stderr.
        printf '%s\n' "$key_data" > ~/.ssh/id_ed25519
        chmod 600 ~/.ssh/id_ed25519
        # First-connection TOFU: pre-populate known_hosts so ssh doesn't prompt.
        if [[ -n "${OPERATOR_HOST:-}" ]]; then
            ssh-keyscan -H "$OPERATOR_HOST" >> ~/.ssh/known_hosts 2>/dev/null || true
        fi
        echo "[entrypoint] SSH key installed (path=~/.ssh/id_ed25519, mode=0600)"
    else
        echo "[entrypoint] WARN no SSH_PRIVATE_KEY; rsync will be skipped on shutdown"
    fi

    # Plan 02-07 v7: install operator's pubkey into authorized_keys so
    # operator can ssh INTO the pod for live debugging. SSH_PUBKEY is
    # forwarded by orchestration/runpod_h100.py for all gates. RunPod
    # also auto-injects PUBLIC_KEY (from account-level SSH keys); fall
    # back to that when SSH_PUBKEY isn't set.
    local pub=""
    if [[ -n "${SSH_PUBKEY:-}" ]]; then
        pub="$SSH_PUBKEY"
    elif [[ -n "${PUBLIC_KEY:-}" && "$PUBLIC_KEY" != "null" ]]; then
        pub="$PUBLIC_KEY"
    fi
    if [[ -n "$pub" ]]; then
        mkdir -p /root/.ssh
        chmod 700 /root/.ssh
        # Idempotent: only append if not already there.
        grep -qF "$pub" /root/.ssh/authorized_keys 2>/dev/null \
            || printf '%s\n' "$pub" >> /root/.ssh/authorized_keys
        chmod 600 /root/.ssh/authorized_keys
        echo "[entrypoint] inbound SSH pub key installed (/root/.ssh/authorized_keys)"
    fi
}

_start_sshd() {
    # Background sshd daemon. Plan 02-07 v7. Pod's port 22 is published in
    # orchestration/runpod_h100.py:provision() (ports="8000/http,22/tcp").
    # Operator connects via `ssh -i <key> root@<pod-ip>` once Connect→TCP
    # mapping is read from the RunPod console.
    if command -v /usr/sbin/sshd >/dev/null 2>&1; then
        /usr/sbin/sshd -D -e > /tmp/sshd.log 2>&1 &
        SSHD_PID=$!
        echo "[entrypoint] sshd pid=$SSHD_PID port=22 (log: /tmp/sshd.log)"
    else
        echo "[entrypoint] sshd not installed; skipping inbound SSH"
    fi
}

_start_cost_watch() {
    python -m cost.watch --providers runpod --interval 300 &
    COSTWATCH_PID=$!
    echo "[entrypoint] cost-watch pid=$COSTWATCH_PID"
}

_start_watchdog() {
    (
        sleep $((MAX_MINUTES * 60))
        echo "[watchdog] MAX_MINUTES=${MAX_MINUTES} elapsed; sending SIGTERM"
        kill -TERM "$ENTRY_PID" 2>/dev/null || true
    ) &
    WATCHDOG_PID=$!
    echo "[entrypoint] watchdog pid=$WATCHDOG_PID timer=${MAX_MINUTES}m"
}

# Plan 02-07: start vLLM + Kokoro inference servers as background daemons,
# then health-check both before letting the gate runner begin. Failure to
# come healthy within the per-service budget kills the entrypoint so the
# pod tears down rather than burning a half-broken stack.
#
# Chatterbox is intentionally NOT started in 02-07 — substrate/cuda.py's
# DR-27 fallback (chatterbox.health=False → kokoro) is sufficient for G1
# smoke. Chatterbox install lands in a follow-up plan before G7 (TTS A/B).
_start_inference_services() {
    # Resolve model paths from the cache_bootstrap index (.bootstrap_index.json).
    # Never hardcode the revision SHA — read whatever the lockfile pinned.
    #
    # NOTE: as of substrate/paths.py the WHISPER_DIR resolution below is no
    # longer load-bearing for the gate runners — FasterWhisperEngine now
    # resolves logical lockfile names against /models/.bootstrap_index.json
    # itself. We keep the resolution here defensively (vLLM and Kokoro still
    # need the real on-disk paths for their CLI flags), and so that a single
    # `--whisper-dir=$WHISPER_DIR` works end-to-end without relying on the
    # in-process resolver.
    local idx="/models/.bootstrap_index.json"
    if [[ ! -f "$idx" ]]; then
        echo "[entrypoint] FATAL /models/.bootstrap_index.json missing — bootstrap pod must run first"
        exit 1
    fi
    QWEN_DIR="$(python -c "import json,sys;d=json.load(open('$idx'))['models']['qwen3_4b_awq_int4'];print('/models/'+d['repo_id'].replace('/','__')+'/'+d['revision'])")"
    KOKORO_DIR="$(python -c "import json,sys;d=json.load(open('$idx'))['models']['kokoro_82m'];print('/models/'+d['repo_id'].replace('/','__')+'/'+d['revision'])")"
    WHISPER_DIR="$(python -c "import json,sys;d=json.load(open('$idx'))['models']['distil_whisper_large_v3_int8'];print('/models/'+d['repo_id'].replace('/','__')+'/'+d['revision'])")"
    echo "[entrypoint] resolved Qwen=${QWEN_DIR} Kokoro=${KOKORO_DIR} Whisper=${WHISPER_DIR}"

    # Symlink ONLY the kokoro-v1_0.pth weight file from the cache_bootstrap
    # download into Kokoro-FastAPI's expected `api/src/models/v1_0/` directory.
    # Kokoro-FastAPI ships its own config.json at that path; we leave it alone
    # so any tuning shipped with the wrapper applies. Symlinking the whole
    # directory (ln -sfn $DIR target) creates a NESTED symlink inside the
    # existing dir instead of replacing it (Plan 02-07 v4 → v5 bug fix).
    mkdir -p /opt/kokoro-server/api/src/models/v1_0
    ln -sf "$KOKORO_DIR/kokoro-v1_0.pth" /opt/kokoro-server/api/src/models/v1_0/kokoro-v1_0.pth

    # vLLM serve — the OpenAI-compatible endpoint gates/g1/runner.py talks to.
    # Plan 02-07 v8: drop `--quantization awq`. The lockfile pins
    # `Qwen/Qwen3-4B` (FP16 base) per CLAUDE.md §3.1's "AWQ at serve time"
    # plan, but vLLM's `--quantization awq` flag means "load AWQ-format
    # weights" not "quantize FP→AWQ at load". For smoke we run FP16:
    # 7.5 GB easily fits in H100 80GB. Real AWQ-Int4 is a sanity-time
    # optimization — switch the lockfile to a `Qwen/Qwen3-4B-AWQ` repo and
    # restore the flag in a follow-up plan.
    python -m vllm.entrypoints.openai.api_server \
        --model "$QWEN_DIR" \
        --served-model-name "Qwen/Qwen3-4B" \
        --port 8000 \
        --host 127.0.0.1 \
        --max-model-len 4096 \
        --guided-decoding-backend xgrammar \
        > /tmp/vllm.log 2>&1 &
    VLLM_PID=$!
    echo "[entrypoint] vllm pid=$VLLM_PID port=8000 (log: /tmp/vllm.log)"

    # Kokoro-FastAPI — TTS. Isolated venv so its torch 2.8.0+cu129 doesn't
    # upgrade the system torch 2.7.1+cu128 used by vllm + faster-whisper.
    # Port 8005 to match gates/g1/runner.py's --kokoro-url default.
    (
        cd /opt/kokoro-server
        export USE_GPU=true USE_ONNX=false
        export PYTHONPATH=/opt/kokoro-server:/opt/kokoro-server/api
        # MODEL_DIR / VOICES_DIR override the upstream defaults
        # ("/app/api/src/...") which assume the project lives at /app rather
        # than our /opt/kokoro-server. Use absolute paths so pydantic-settings
        # treats them as-is (no project-root prefixing).
        export MODEL_DIR=/opt/kokoro-server/api/src/models
        export VOICES_DIR=/opt/kokoro-server/api/src/voices/v1_0
        /opt/kokoro-venv/bin/python -m uvicorn api.src.main:app \
            --host 127.0.0.1 --port 8005 \
            > /tmp/kokoro.log 2>&1
    ) &
    KOKORO_PID=$!
    echo "[entrypoint] kokoro pid=$KOKORO_PID port=8005 (log: /tmp/kokoro.log)"

    # Health-check budgets. v13 bump: 2026-05-08 SSH'd into a diag pod and
    # measured Qwen3-4B FP16 cold-load on H100 NVL at 145s — exceeded the
    # prior 120s vLLM ceiling, FATAL'd, exited 1, and Docker restart-looped
    # the container indefinitely. New ceilings give 2× headroom over the
    # measured cold path. Kokoro CPU bumped from 90s to 180s for similar
    # safety (the venv hasn't been cold-load measured under load).
    local deadline_vllm=$((SECONDS + 300))
    local deadline_kokoro=$((SECONDS + 180))
    local vllm_ok=0 kokoro_ok=0
    while (( SECONDS < deadline_vllm || SECONDS < deadline_kokoro )); do
        if (( ! vllm_ok )) && curl -sf -o /dev/null http://127.0.0.1:8000/v1/models 2>/dev/null; then
            vllm_ok=1
            echo "[entrypoint] vllm healthy at $((SECONDS))s"
        fi
        if (( ! kokoro_ok )) && curl -sf -o /dev/null http://127.0.0.1:8005/v1/audio/voices 2>/dev/null; then
            kokoro_ok=1
            echo "[entrypoint] kokoro healthy at $((SECONDS))s"
        fi
        if (( vllm_ok && kokoro_ok )); then
            echo "[entrypoint] all services healthy"
            return 0
        fi
        sleep 2
    done
    echo "[entrypoint] FATAL services not healthy in budget — vllm=${vllm_ok} kokoro=${kokoro_ok}"
    echo "[entrypoint] --- vllm tail ---"; tail -50 /tmp/vllm.log 2>/dev/null
    echo "[entrypoint] --- kokoro tail ---"; tail -50 /tmp/kokoro.log 2>/dev/null
    # v13: self-terminate before exit. Without this, `exit 1` triggers RunPod's
    # Docker restart policy → container respawns → same FATAL → infinite loop
    # burning $$ until the operator-side smoke timeout fires (observed: 65 min
    # at $3.07/hr = $3.33). Same SDK pattern as the BOOTSTRAP_MODE branch.
    if [[ -n "${RUNPOD_POD_ID:-}" && -n "${RUNPOD_API_KEY:-}" ]]; then
        echo "[entrypoint] self-terminating pod ${RUNPOD_POD_ID} (FATAL path)" >&2
        python - <<PYEOF || true
import os, runpod
runpod.api_key = os.environ["RUNPOD_API_KEY"]
runpod.terminate_pod(os.environ["RUNPOD_POD_ID"])
print("[entrypoint] runpod.terminate_pod accepted")
PYEOF
    fi
    exit 1
}

# Idempotency guard so the trap doesn't fire twice (TERM + normal exit).
_SHUTDOWN_DONE=0

_shutdown() {
    if [[ "$_SHUTDOWN_DONE" -eq 1 ]]; then
        return 0
    fi
    _SHUTDOWN_DONE=1
    echo "[entrypoint] SIGTERM received; running shutdown sequence"

    # 1. Stop the gate runner gracefully.
    if [[ -n "${RUNNER_PID:-}" ]]; then
        kill -TERM "$RUNNER_PID" 2>/dev/null || true
        for _ in $(seq 1 60); do
            kill -0 "$RUNNER_PID" 2>/dev/null || break
            sleep 1
        done
        kill -KILL "$RUNNER_PID" 2>/dev/null || true
    fi

    # 1b. Stop inference servers + sshd (Plan 02-07). Audit looks at results/,
    # not at live processes, but leaving these running while we rsync is wasteful.
    for svc_pid in "${VLLM_PID:-}" "${KOKORO_PID:-}" "${SSHD_PID:-}"; do
        [[ -n "$svc_pid" ]] && kill -TERM "$svc_pid" 2>/dev/null || true
    done

    # 2. Pre-teardown audit (D-22 fail-loud).
    AUDIT_LOG="${WORKSPACE}/results/${GATE}/$(date -u +%s).audit.json"
    mkdir -p "$(dirname "$AUDIT_LOG")"
    AUDIT_RC=0
    python tools/audit_pod_state.py \
        --root "$WORKSPACE" \
        --manifest assets/manifest.csv \
        --results-dir results \
        --audit-log "$AUDIT_LOG" || AUDIT_RC=$?
    echo "[entrypoint] audit exit=$AUDIT_RC log=$AUDIT_LOG"

    # 3a. Persist results to the network volume so a follow-up fetch pod can
    # rsync them off-pod. Container disk (/workspace) is ephemeral —
    # the v13 smoke pod ran 5/5 calls fine but the JSONL was lost when the
    # pod terminated (verdict: "no JSONL found"). v14 always copies to
    # /models/_results/<pod_id>/<gate>/ regardless of OPERATOR_HOST so the
    # operator can pull via tools/fetch_results.py later. Volume is mounted
    # for smoke/sanity gates; bootstrap doesn't take this branch (early exit).
    if [[ -d /models ]]; then
        DEST="/models/_results/${RUNPOD_POD_ID:-nopod}/${GATE}"
        mkdir -p "$DEST"
        cp -a "${WORKSPACE}/results/${GATE}/." "$DEST/" 2>/dev/null \
            || echo "[entrypoint] warn: failed to persist results to $DEST"
        echo "[entrypoint] results persisted to $DEST"
    fi

    # 3b. Legacy direct-rsync to operator workstation. Off by default; the
    # v14 fetch-pod path in tools/fetch_results.py is the supported transport
    # for cloud-only Phase 0. Kept for operators who run the harness from a
    # publicly-reachable workstation.
    if [[ -n "${OPERATOR_HOST:-}" && -f ~/.ssh/id_ed25519 ]]; then
        if [[ "$AUDIT_RC" -eq 0 ]]; then
            bash tools/rsync_results.sh
        else
            bash tools/rsync_results.sh --audit-only
        fi
    else
        echo "[entrypoint] skip operator rsync (no OPERATOR_HOST or SSH key)"
    fi

    # 4. Self-terminate the pod. v13: switched runpodctl → runpod SDK
    # (matches the BOOTSTRAP_MODE branch). runpodctl shells out and frequently
    # 403s on env-injected RUNPOD_API_KEY (observed plan 02-06); the Python
    # SDK is what actually works in-pod.
    if [[ -n "${RUNPOD_POD_ID:-}" && -n "${RUNPOD_API_KEY:-}" ]]; then
        python - <<PYEOF || true
import os, runpod
runpod.api_key = os.environ["RUNPOD_API_KEY"]
runpod.terminate_pod(os.environ["RUNPOD_POD_ID"])
print("[entrypoint] shutdown trap: runpod.terminate_pod accepted")
PYEOF
    fi

    exit "$AUDIT_RC"
}

trap _shutdown TERM INT
ENTRY_PID=$$

_setup_ssh
_start_sshd
_start_cost_watch
_start_watchdog
_start_inference_services

# Plan 03-05 / AUDIT-03: install Ollama on demand for the Ollama-vs-vLLM
# overhead measurement. Skipped for non-audit gates so non-audit runs
# don't pay the install + pull cost (~1.5 GB model + a few seconds).
if [[ "$GATE" == audit_* || "$GATE" == audit-* ]]; then
    if ! command -v ollama >/dev/null 2>&1; then
        echo "[entrypoint] installing Ollama for ${GATE}..."
        if curl -fsSL https://ollama.com/install.sh | sh; then
            nohup ollama serve > /tmp/ollama.log 2>&1 &
            OLLAMA_PID=$!
            echo "[entrypoint] ollama serve pid=${OLLAMA_PID} (log: /tmp/ollama.log)"
            # Wait briefly for the daemon socket before pulling.
            for _ in 1 2 3 4 5 6 7 8 9 10; do
                if ollama list >/dev/null 2>&1; then break; fi
                sleep 1
            done
            ollama pull "${OLLAMA_MODEL:-qwen3:4b-q4_K_M}" \
                || echo "[entrypoint] WARNING ollama pull failed; AUDIT-03 will record ollama_not_installed errors"
        else
            echo "[entrypoint] WARNING Ollama install failed; AUDIT-03 will record ollama_not_installed errors"
        fi
    else
        echo "[entrypoint] ollama already present: $(ollama --version 2>&1 | head -1)"
    fi
fi

# Exec the gate runner. D-24: smoke profile is g1.runner --n-calls=5 against
# corpus_500. Sanity gates use config/sanity_strata.yaml (Plan 02-04).
#
# 2026-05-09 (post-v14 follow-up): pass --whisper-dir from the bootstrap-
# index-resolved WHISPER_DIR. Runner defaults are
# `--whisper-dir=/models/distil_whisper_large_v3_int8` — the LOGICAL name
# from the lockfile, not the on-disk repo+revision path. Without this
# override the FasterWhisperEngine got an HFValidationError trying to
# interpret the logical name as a HF repo_id, the STT path silently
# yielded nothing, and stt_ttft_ms / e2e_ms stayed null in the JSONL —
# breaking D-25 d_per_stage_timings. WHISPER_DIR is set inside
# _start_inference_services with no `local`, so it's already in scope here.
if [[ "$GATE" == "smoke" ]]; then
    python -m gates.g1.runner --gate=smoke --n-calls=5 --corpus=corpus_500 \
        --whisper-dir="$WHISPER_DIR" &
else
    # Plan 03-02 / image v19: honor STRATA_PATH env override. Defaults to the
    # Phase 02 sanity subset (10/10 assets per gate) for backward compat;
    # Phase 3 callers set STRATA_PATH=config/phase3_strata.yaml to get full
    # corpora (200 g711 / 51 hesitation / 500 calls / etc).
    STRATA_PATH="${STRATA_PATH:-config/sanity_strata.yaml}"
    echo "[entrypoint] gate=$GATE strata=$STRATA_PATH"
    python -m gates."$GATE".runner --gate="$GATE" --strata="$STRATA_PATH" \
        --whisper-dir="$WHISPER_DIR" &
fi
RUNNER_PID=$!
echo "[entrypoint] runner pid=$RUNNER_PID gate=$GATE whisper_dir=$WHISPER_DIR"

# Wait for the runner. SIGTERM trap intercepts at watchdog timeout / operator stop.
wait "$RUNNER_PID" || true

# Normal exit path: still run the audit + rsync sequence.
_shutdown
