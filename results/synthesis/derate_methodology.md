# Derating Methodology (Phase 0 / Phase 3)

## Substrate Chain

- **Measurement:** RunPod H100 PCIe 80GB (CUDA 12.x, vLLM 0.10+)
- **Target:** NVIDIA Jetson AGX Orin 64GB (JetPack 6 / CUDA 12.x)
- Same-vendor, same-stack derate — single hop, no cross-vendor risk surface.

## Per-Stage Derate Ratios (CLAUDE.md §7)

| Stage | Op class | H100 PCIe | Orin 64GB | Ratio |
|-------|----------|-----------|-----------|-------|
| STT encoder | INT8 TOPS sparse | 3026 | 275 | 11.0x |
| LLM prefill | INT8 TOPS sparse | 3026 | 275 | 11.0x |
| LLM decode | LPDDR5 vs HBM3 | 2000 GB/s | 204 GB/s | 9.8x |
| TTS prefill | FP16 TFLOPS sparse | 756 | 32 | 23.6x |

## Production-Runtime Overheads

- **Ollama-overhead factor** (LLM stages only): 1.400x (default (AUDIT-03 absent or non-discriminating))
- **ARM-penalty** (universal): 1.15x (CLAUDE.md §7.2 midpoint of 10-20%)

## Bootstrap Confidence Intervals

All Orin predictions report 95% CIs via `scipy.stats.bootstrap` (percentile
method, `n_resamples=10000`) on the derated sample distribution. CI columns:

- `derated_orin_ci_lo_ms`
- `derated_orin_point_ms` (median of derated samples)
- `derated_orin_ci_hi_ms`

## NVIDIA Published-Benchmark Cross-Check

- **Status:** `awaiting_operator_curation`
- **Comparisons performed:** 0
- **Flags (divergence > 50%):** 0

When `status == "awaiting_operator_curation"`, the operator must populate
`data/nvidia_orin_published_benchmarks.json` with NVIDIA-published Jetson AGX
Orin 64GB numbers (`developer.nvidia.com/embedded/jetson-orin-benchmarks`) and
re-run `python -m synthesis.cross_check_nvidia`.

## Coverage

Derate buckets in this run: **4** (gate x stage x concurrency).

## What We Do NOT Know

- Real PSTN audio vs synthetic mu-law behavior (Phase 0 measures only synthetic)
- Sustained Ollama-vs-vLLM behavior on actual Orin hardware under load
- Orin MAXN power-mode sustained-load thermal behavior
- TensorRT-LLM Orin port speedup over Ollama (likely 1.5-2x; unmeasured here)
- Exact CPU/ARM integration penalty on Orin's Cortex-A78AE (10-20% is a
  first-principles estimate; midpoint 1.15x applied)

## Post-Phase-0 Validation Plan

After Phase 0 passes the gate decision, procure 1x Jetson AGX Orin 64GB
Developer Kit (~$2k, ~1 week ship). Run the same harness against the same
pinned model weights. Confirm predicted ratios within +/-20%. Re-issue the
synthesis report as v0.2 with measured-vs-predicted comparison **before** SOW
execution per CLAUDE.md §7.3.
