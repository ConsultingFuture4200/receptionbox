#!/usr/bin/env bash
# Pod → operator workstation results push (D-17).
#
# Source is ALWAYS results/ — never assets/, never workspace root. T1 mitigation
# (no real-audio / PII egress) relies on this invariant; tests/test_pod_entrypoint.py
# greps the source files for any rsync line that mentions assets and fails.
#
# Modes:
#   default       → full push of results/ to operator's ~/RBOX/results/
#   --audit-only  → push ONLY *.audit.json files (D-23: audit failed, no
#                   measurement data may cross the wire)
#
# Inputs (env vars):
#   OPERATOR_HOST  — required
#   OPERATOR_USER  — defaults to 'operator'
#   WORKSPACE      — defaults to /workspace

set -euo pipefail

: "${OPERATOR_HOST:?OPERATOR_HOST env var required}"
: "${OPERATOR_USER:=operator}"
WORKSPACE="${WORKSPACE:-/workspace}"
cd "$WORKSPACE"

AUDIT_ONLY=0
if [[ "${1:-}" == "--audit-only" ]]; then
    AUDIT_ONLY=1
fi

SSH_OPTS="-i $HOME/.ssh/id_ed25519 -o StrictHostKeyChecking=accept-new"

if [[ "$AUDIT_ONLY" -eq 1 ]]; then
    echo "[rsync] audit-only mode — pushing audit log(s) only (D-23)"
    rsync -avz --partial --append-verify \
        -e "ssh ${SSH_OPTS}" \
        --include='*/' \
        --include='*.audit.json' \
        --exclude='*' \
        results/ \
        "${OPERATOR_USER}@${OPERATOR_HOST}:~/RBOX/results/"
else
    echo "[rsync] full results push"
    rsync -avz --partial --append-verify \
        -e "ssh ${SSH_OPTS}" \
        results/ \
        "${OPERATOR_USER}@${OPERATOR_HOST}:~/RBOX/results/"
fi

echo "[rsync] done"
