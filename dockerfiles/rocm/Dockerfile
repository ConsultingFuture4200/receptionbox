# RunPod / Vultr / TensorWave pod image for receptionBOX Phase 0 (ROCm path).
#
# Mirrors the CUDA-rail Dockerfile (./Dockerfile at repo root). Bakes
# tools/pod_entrypoint.sh as ENTRYPOINT (Pitfall 10 — base ROCm vllm image's
# default CMD ignores BOOTSTRAP_MODE/GATE env vars).
#
# Build:
#   scripts/build_pod_image_rocm.sh ghcr.io/consultingfuture4200/rbox-pod-rocm:v1 --push
# After push, paste the @sha256 digest into orchestration/vultr_mi300x.py
# (_DEFAULT_IMAGE_ROCM) per CLAUDE.md §2.3 (digest pinning).
#
# Plan 03-01 Task 5 checkpoint amendment D-32-A1 (2026-05-11): base image
# migrated from CLAUDE.md §2.1's
#   rocm/vllm:rocm6.4_mi300_ubuntu22.04_py3.11_vllm_0.10.x
# (which does not exist on Docker Hub — CLAUDE.md spec was an extrapolated
# pattern that never matched AMD's actual tag schema) to AMD's current
# stable ROCm 7.12 base. Pinned by digest per CLAUDE.md §2.3. See
# .planning/phases/03-rocm-validation/03-01-AMENDMENTS.md §D-32-A1.
# Origin tag:
#   rocm/vllm:rocm7.12.0_gfx94X-dcgpu_ubuntu24.04_py3.12_pytorch_2.9.1_vllm_0.16.0

FROM rocm/vllm@sha256:997f858b973cb4e9566653a180c79bc27170bd87585a6930f9257346869a28f7

ARG GIT_COMMIT
RUN echo "${GIT_COMMIT}" > /workspace/.git_commit

# OS deps — matches the CUDA rail's runtime needs:
#   rsync           — pod_entrypoint.sh shutdown chain
#   openssh-client  — operator-side rsync transport
#   ca-certificates — HF model downloads
#   curl, jq        — health probes + JSON parsing in pod_entrypoint.sh
RUN apt-get update && apt-get install -y --no-install-recommends \
        rsync openssh-client ca-certificates curl jq && \
    rm -rf /var/lib/apt/lists/*

# Harness deps. Pin faster-whisper + onnxruntime-rocm to ROCm 6.4 wheels.
# livekit-agents pinned to match Phase 2 lock (1.2.9). jiwer >=4.0 matches
# Phase 1 lock + whisper-normalizer compatibility.
RUN pip install --no-cache-dir \
        "faster-whisper>=1.0,<2.0" \
        onnxruntime-rocm \
        "livekit-agents==1.2.9" \
        livekit-plugins-silero \
        livekit-plugins-turn-detector \
        "httpx[http2]" \
        "pydantic>=2.0" \
        "jiwer>=4.0" \
        whisper-normalizer \
        pyloudnorm \
        pandas \
        scipy \
        soundfile \
        pyyaml \
        runpod

WORKDIR /workspace
COPY . /workspace/
ENTRYPOINT ["bash", "/workspace/tools/pod_entrypoint.sh"]
