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

set -euo pipefail

: "${GATE:?GATE env var required}"
: "${MAX_MINUTES:=30}"
: "${OPERATOR_USER:=operator}"
WORKSPACE="${WORKSPACE:-/workspace}"
cd "$WORKSPACE"

_setup_ssh() {
    if [[ -n "${SSH_PRIVATE_KEY:-}" ]]; then
        mkdir -p ~/.ssh
        # Write the key value to a file. Never echo it to stdout/stderr.
        printf '%s\n' "$SSH_PRIVATE_KEY" > ~/.ssh/id_ed25519
        chmod 600 ~/.ssh/id_ed25519
        # First-connection TOFU: pre-populate known_hosts so ssh doesn't prompt.
        if [[ -n "${OPERATOR_HOST:-}" ]]; then
            ssh-keyscan -H "$OPERATOR_HOST" >> ~/.ssh/known_hosts 2>/dev/null || true
        fi
        echo "[entrypoint] SSH key installed (path=~/.ssh/id_ed25519, mode=0600)"
    else
        echo "[entrypoint] WARN no SSH_PRIVATE_KEY; rsync will be skipped on shutdown"
    fi
}

_start_cost_watch() {
    if command -v uv >/dev/null 2>&1; then
        uv run python -m cost.watch --providers runpod --interval 300 &
    else
        python -m cost.watch --providers runpod --interval 300 &
    fi
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

    # 2. Pre-teardown audit (D-22 fail-loud).
    AUDIT_LOG="${WORKSPACE}/results/${GATE}/$(date -u +%s).audit.json"
    mkdir -p "$(dirname "$AUDIT_LOG")"
    AUDIT_RC=0
    if command -v uv >/dev/null 2>&1; then
        uv run python tools/audit_pod_state.py \
            --root "$WORKSPACE" \
            --manifest assets/manifest.csv \
            --results-dir results \
            --audit-log "$AUDIT_LOG" || AUDIT_RC=$?
    else
        python tools/audit_pod_state.py \
            --root "$WORKSPACE" \
            --manifest assets/manifest.csv \
            --results-dir results \
            --audit-log "$AUDIT_LOG" || AUDIT_RC=$?
    fi
    echo "[entrypoint] audit exit=$AUDIT_RC log=$AUDIT_LOG"

    # 3. Rsync. Audit pass → full results/. Audit fail → audit log only (D-23).
    if [[ -n "${OPERATOR_HOST:-}" && -f ~/.ssh/id_ed25519 ]]; then
        if [[ "$AUDIT_RC" -eq 0 ]]; then
            bash tools/rsync_results.sh
        else
            bash tools/rsync_results.sh --audit-only
        fi
    else
        echo "[entrypoint] skip rsync (no OPERATOR_HOST or SSH key)"
    fi

    # 4. Self-terminate the pod.
    if [[ -n "${RUNPOD_POD_ID:-}" ]] && command -v runpodctl >/dev/null 2>&1; then
        runpodctl pod stop "$RUNPOD_POD_ID" || true
    fi

    exit "$AUDIT_RC"
}

trap _shutdown TERM INT
ENTRY_PID=$$

_setup_ssh
_start_cost_watch
_start_watchdog

# Exec the gate runner. D-24: smoke profile is g1.runner --n-calls=5 against
# corpus_500. Sanity gates use config/sanity_strata.yaml (Plan 02-04).
if [[ "$GATE" == "smoke" ]]; then
    uv run python -m gates.g1.runner --gate=smoke --n-calls=5 --corpus=corpus_500 &
else
    uv run python -m gates."$GATE".runner --gate="$GATE" --strata=config/sanity_strata.yaml &
fi
RUNNER_PID=$!
echo "[entrypoint] runner pid=$RUNNER_PID gate=$GATE"

# Wait for the runner. SIGTERM trap intercepts at watchdog timeout / operator stop.
wait "$RUNNER_PID" || true

# Normal exit path: still run the audit + rsync sequence.
_shutdown
