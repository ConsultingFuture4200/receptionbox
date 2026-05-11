# rbox-pod-rocm

Custom ROCm pod image for receptionBOX Phase 3 (ROCm validation on
Vultr / TensorWave MI300X).

## Build

```bash
echo "$GHCR_TOKEN" | docker login ghcr.io -u consultingfuture4200 --password-stdin
scripts/build_pod_image_rocm.sh ghcr.io/consultingfuture4200/rbox-pod-rocm:v1 --push
```

The script prints `ghcr.io/consultingfuture4200/rbox-pod-rocm@sha256:...`
at the end. Paste that into:

1. `orchestration/vultr_mi300x.py:_DEFAULT_IMAGE_ROCM`
2. `bench/images.lock.yaml` row where `image_ref: ghcr.io/consultingfuture4200/rbox-pod-rocm`
   (change `digest: pending` to the resolved `sha256:...` value and set
   `captured_utc` to the current ISO timestamp).

## First-pod version-verification probes

Run these inside the first MI300X pod to confirm the ROCm stack is intact
(Plan 03-01 Task 5 / Plan 03-02 Day-1 kill-switch):

```bash
python -c "import vllm; print(vllm.__version__)"      # expect 0.10.x
python -c "import torch; print(torch.__version__, torch.version.hip)"  # expect 2.5.x +rocm6.4 OR 2.6.x +rocm6.4.1
python -c "import faster_whisper; print(faster_whisper.__version__)"   # expect 1.0.x+
rocm-smi --version
```

If any probe fails, STOP — investigate before any real-spend gate run.

## Base image

`FROM rocm/vllm:rocm6.4_mi300_ubuntu22.04_py3.11_vllm_0.10.x` (CLAUDE.md §2.1).
If AMD deprecates this tag, the migration path is `vllm/vllm-openai-rocm`
(requires D-32 amendment per 03-01-PLAN.md Task 5 Step 1 fallback).

## Sentinel guard

Until the operator pastes the resolved digest, `orchestration/vultr_mi300x.py`
carries a loud-fail sentinel (`_DEFAULT_IMAGE_ROCM` contains "UNSET"). The
provision() function raises `VultrProvisionError` BEFORE any network call if
the sentinel is still present — mirroring the Phase 2 Plan 02-06 pattern that
prevented the $1.05 zkqbit98s0uulf incident from recurring.
