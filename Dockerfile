# RunPod pod image for receptionBOX Phase 0 (CUDA path).
#
# Bug fix for Plan 02-05 follow-up: orchestration/runpod_h100.py's provision()
# was setting BOOTSTRAP_MODE=1 as a container env var but never overriding the
# upstream vllm/vllm-openai image's CMD. As a result tools/pod_entrypoint.sh
# (the BOOTSTRAP_MODE reader) never executed and the pod sat in RUNNING with
# the default vLLM OpenAI server CMD, burning $2.99/hr until the operator
# noticed and killed it.
#
# This image bakes the harness in at /workspace and pins ENTRYPOINT to
# tools/pod_entrypoint.sh so BOOTSTRAP_MODE / GATE env vars are actually read.
#
# Build:
#   scripts/build_pod_image.sh <registry>/<repo>:<tag>
# After push, copy the @sha256 digest into orchestration/runpod_h100.py
# (CLAUDE.md §2.3 — image pinning by digest, not tag).

FROM vllm/vllm-openai:v0.10.0

# OS deps:
#   rsync           — pod_entrypoint.sh shutdown chain (tools/rsync_results.sh)
#   openssh-client  — ssh transport for the operator-side rsync push
#   ca-certificates — HF model downloads
#   curl            — runpodctl install + general
RUN apt-get update && apt-get install -y --no-install-recommends \
        rsync openssh-client ca-certificates curl \
    && rm -rf /var/lib/apt/lists/*

# The base image ships python3 / python3.12 but no bare `python`.
# pod_entrypoint.sh falls back to `python -m tools.cache_bootstrap` when `uv`
# is absent (we don't install uv); without this symlink that fallback fails
# with "python: command not found" inside the running pod.
RUN ln -s /usr/bin/python3 /usr/local/bin/python

# runpodctl: best-effort install for in-pod self-stop in pod_entrypoint.sh
# shutdown trap. pod_entrypoint.sh tolerates a missing binary, so failure
# to fetch must NOT break the build.
RUN set -eux; \
    arch="$(uname -m)"; \
    case "$arch" in \
        x86_64)  rp_arch=amd64 ;; \
        aarch64) rp_arch=arm64 ;; \
        *) echo "unsupported arch: $arch" >&2; exit 0 ;; \
    esac; \
    curl -fsSL --retry 3 \
        "https://github.com/runpod/runpodctl/releases/latest/download/runpodctl-linux-${rp_arch}" \
        -o /usr/local/bin/runpodctl \
        && chmod +x /usr/local/bin/runpodctl \
        || echo "[build] runpodctl fetch failed; continuing without it"

WORKDIR /workspace

# Install harness Python deps into the system Python that already has vllm.
# Keeping the base image's vllm/torch in place is mandatory — re-installing
# them via uv would conflict with the vendor-pinned CUDA wheels.
COPY requirements.lock /workspace/requirements.lock
RUN pip install --no-cache-dir -r /workspace/requirements.lock

# CUDA-side runtime extras NOT in requirements.lock (the lockfile excludes the
# pyproject [cuda] extras since the operator workstation does not install
# them). vllm and torch are already in the base image.
#
# `openai` is pinned to vllm 0.10.1's required range (>=1.87.0,<=1.90.0) so the
# livekit-agents install does NOT silently upgrade it past vllm's compat
# ceiling — observed during first build of this image: livekit pulled
# openai 2.35.1 and pip's resolver flagged the conflict but did not roll back.
# vllm imports from openai's old API surface; an unpinned upgrade breaks serve.
RUN pip install --no-cache-dir \
        "openai>=1.87.0,<=1.90.0" \
        "faster-whisper>=1.0,<2.0" \
        "livekit-agents>=1.0,<2.0" \
        "livekit-plugins-silero" \
        "livekit-plugins-turn-detector" \
        "httpx[http2]>=0.27" \
        "xgrammar>=0.1"

# Copy harness source. .dockerignore excludes results/, secrets/, .git, the
# heavy assets/corpus_* trees, .planning/, tests/, docs/.
COPY . /workspace/

# pod_entrypoint.sh probes for `uv` and falls back to `python` when absent.
# Deps are in system Python (above), so no `uv` install needed; `python -m
# tools.cache_bootstrap` resolves correctly.
ENTRYPOINT ["bash", "/workspace/tools/pod_entrypoint.sh"]
