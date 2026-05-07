#!/usr/bin/env bash
# Build and (optionally) push the RunPod pod image, then resolve the
# immutable @sha256 digest the operator must paste into
# orchestration/runpod_h100.py per CLAUDE.md §2.3 (image pinning by digest).
#
# Usage:
#   scripts/build_pod_image.sh <registry>/<repo>:<tag> [--push]
#
# Examples:
#   scripts/build_pod_image.sh docker.io/dustinpowers/rbox-pod:v1
#   scripts/build_pod_image.sh ghcr.io/consultingfuture4200/rbox-pod:v1 --push
#
# Prereqs:
#   - docker buildx available (docker buildx version)
#   - registry login already done (docker login <registry>)
#
# Notes:
#   - Builds linux/amd64 only. RunPod GPU pods are amd64; arm64 builds would
#     waste time and risk pulling the wrong base manifest.
#   - --push is opt-in. The default ("just build") is the safe path: build,
#     inspect, then the operator runs the push manually after eyeballing.

set -euo pipefail

if [[ $# -lt 1 ]]; then
    echo "usage: $0 <registry>/<repo>:<tag> [--push]" >&2
    exit 2
fi

TAG="$1"
PUSH=0
if [[ "${2:-}" == "--push" ]]; then
    PUSH=1
fi

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

if ! command -v docker >/dev/null 2>&1; then
    echo "ERROR: docker not on PATH" >&2
    exit 1
fi

if ! docker buildx version >/dev/null 2>&1; then
    echo "ERROR: docker buildx not available; install or enable buildx" >&2
    exit 1
fi

echo "[build] tag=${TAG} push=${PUSH} context=${REPO_ROOT}"

# --load brings the image into the local docker daemon for inspection.
# --push uploads to the registry. The two flags are mutually exclusive in
# buildx, so we choose at invocation time.
if [[ "$PUSH" -eq 1 ]]; then
    docker buildx build \
        --platform linux/amd64 \
        --tag "$TAG" \
        --file Dockerfile \
        --push \
        .
    echo "[build] pushed ${TAG}; resolving digest"
    # After --push, RepoDigests is populated for the local manifest list.
    DIGEST="$(docker buildx imagetools inspect "$TAG" --format '{{json .Manifest}}' \
        | python3 -c 'import sys,json; m=json.load(sys.stdin); print(m.get("digest",""))')"
    if [[ -n "$DIGEST" ]]; then
        echo
        echo "Digest-pinned reference (paste into orchestration/runpod_h100.py:_DEFAULT_IMAGE):"
        # Strip everything after ':' in TAG to get the bare repo, then append @digest.
        BARE_REPO="${TAG%:*}"
        echo "  ${BARE_REPO}@${DIGEST}"
    else
        echo "[build] could not resolve digest; run 'docker buildx imagetools inspect ${TAG}' manually"
    fi
else
    docker buildx build \
        --platform linux/amd64 \
        --tag "$TAG" \
        --file Dockerfile \
        --load \
        .
    echo "[build] built locally as ${TAG} (not pushed)"
    echo "[build] to push: scripts/build_pod_image.sh ${TAG} --push"
fi
