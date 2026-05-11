#!/usr/bin/env bash
# Build + (optionally) push the rbox-pod-rocm image, then resolve the
# immutable @sha256 digest the operator pastes into
# orchestration/vultr_mi300x.py _DEFAULT_IMAGE_ROCM per CLAUDE.md §2.3.
#
# Usage:
#   scripts/build_pod_image_rocm.sh <registry>/<repo>:<tag> [--push]
#
# Examples:
#   scripts/build_pod_image_rocm.sh ghcr.io/consultingfuture4200/rbox-pod-rocm:v1
#   scripts/build_pod_image_rocm.sh ghcr.io/consultingfuture4200/rbox-pod-rocm:v1 --push
#
# Prereqs:
#   - docker buildx available (docker buildx version)
#   - registry login already done (docker login ghcr.io)
#
# Notes:
#   - Builds linux/amd64 only. MI300X cloud pods are amd64.
#   - --push is opt-in (matches scripts/build_pod_image.sh).
#   - GIT_COMMIT is baked into /workspace/.git_commit for DEV-1021 lineage.

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

GIT_COMMIT_VAL="$(git rev-parse HEAD 2>/dev/null || echo unknown)"
echo "[build_pod_image_rocm] tag=${TAG} push=${PUSH} context=${REPO_ROOT}"
echo "[build_pod_image_rocm] GIT_COMMIT=${GIT_COMMIT_VAL}"

if [[ "$PUSH" -eq 1 ]]; then
    docker buildx build \
        --platform linux/amd64 \
        --build-arg "GIT_COMMIT=${GIT_COMMIT_VAL}" \
        --tag "$TAG" \
        --file dockerfiles/rocm/Dockerfile \
        --push \
        .
    echo "[build_pod_image_rocm] pushed ${TAG}; resolving digest"
    DIGEST="$(docker buildx imagetools inspect "$TAG" --format '{{json .Manifest}}' \
        | python3 -c 'import sys,json; m=json.load(sys.stdin); print(m.get("digest",""))')"
    if [[ -n "$DIGEST" ]]; then
        echo
        echo "Digest-pinned reference (paste into orchestration/vultr_mi300x.py:_DEFAULT_IMAGE_ROCM):"
        BARE_REPO="${TAG%:*}"
        echo "  ${BARE_REPO}@${DIGEST}"
    else
        echo "[build_pod_image_rocm] could not resolve digest; run 'docker buildx imagetools inspect ${TAG}' manually"
    fi
else
    docker buildx build \
        --platform linux/amd64 \
        --build-arg "GIT_COMMIT=${GIT_COMMIT_VAL}" \
        --tag "$TAG" \
        --file dockerfiles/rocm/Dockerfile \
        --load \
        .
    echo "[build_pod_image_rocm] built locally as ${TAG} (not pushed)"
    echo "[build_pod_image_rocm] to push: scripts/build_pod_image_rocm.sh ${TAG} --push"
fi
