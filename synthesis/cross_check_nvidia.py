"""Cross-check derated Orin predictions against NVIDIA-published benchmarks.

Reads `results/synthesis/orin_derate_table.csv` + `data/nvidia_orin_published_benchmarks.json`.
For each derated prediction, find the closest analog in the NVIDIA dataset and
compute |divergence| = |predicted - published| / published. Flag any > 50%.

If the NVIDIA dataset is the unpopulated TEMPLATE (every `value_*` is None),
emits `nvidia_crosscheck.json` with `status="awaiting_operator_curation"` and
no flags — operator must populate `data/nvidia_orin_published_benchmarks.json`
from developer.nvidia.com/embedded/jetson-orin-benchmarks before the
cross-check is meaningful.
"""

from __future__ import annotations

import json
import pathlib

import pandas as pd

DIVERGENCE_THRESHOLD = 0.5  # 50% — surfaces a flag for operator review

# Map derate-table `stage` -> prefix used in published `workload` names.
_STAGE_TO_WORKLOAD_PREFIX = {
    "stt_ttft": ("whisper",),
    "llm_ttft": ("qwen",),
    "llm_decode": ("qwen",),
    "tts_first_audio": (),  # No published Orin TTS benchmark currently tracked
}


def _published_value(benchmark: dict) -> float | None:
    """Pull the numeric value out of a benchmark entry regardless of unit key."""
    for k, v in benchmark.items():
        if k.startswith("value_") and v is not None:
            return float(v)
    return None


def _has_curated_data(nvidia: dict) -> bool:
    return any(_published_value(b) is not None for b in nvidia.get("benchmarks", []))


def _find_match(stage: str, benchmarks: list[dict]) -> dict | None:
    prefixes = _STAGE_TO_WORKLOAD_PREFIX.get(stage, ())
    if not prefixes:
        return None
    for b in benchmarks:
        workload = b.get("workload", "")
        if any(workload.startswith(p) for p in prefixes):
            return b
    return None


def main() -> int:
    derate_path = pathlib.Path("results/synthesis/orin_derate_table.csv")
    nvidia_path = pathlib.Path("data/nvidia_orin_published_benchmarks.json")
    out_path = pathlib.Path("results/synthesis/nvidia_crosscheck.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)

    nvidia = json.loads(nvidia_path.read_text())
    out: dict = {"comparisons": [], "flags": [], "status": "ok"}

    if not _has_curated_data(nvidia):
        out["status"] = "awaiting_operator_curation"
        out["note"] = (
            "data/nvidia_orin_published_benchmarks.json is a TEMPLATE. "
            "Operator must populate value_* fields with NVIDIA-published numbers from "
            "developer.nvidia.com/embedded/jetson-orin-benchmarks before the "
            "cross-check is meaningful."
        )
        out_path.write_text(json.dumps(out, indent=2))
        print(f"[crosscheck] template detected; awaiting operator data -> {out_path}")
        return 0

    if not derate_path.exists():
        out["status"] = "no_derate_table"
        out["note"] = (
            "results/synthesis/orin_derate_table.csv missing. Run "
            "`python -m synthesis.derate_pipeline` first."
        )
        out_path.write_text(json.dumps(out, indent=2))
        print(f"[crosscheck] no derate table -> {out_path}")
        return 0

    df = pd.read_csv(derate_path)
    for row in df.to_dict("records"):
        match = _find_match(row["stage"], nvidia.get("benchmarks", []))
        if not match:
            continue
        published_val = _published_value(match)
        if published_val is None or published_val == 0:
            continue
        derated_val = float(row["derated_orin_point_ms"])
        divergence = abs(derated_val - published_val) / published_val
        entry = {
            "gate": row.get("gate"),
            "stage": row["stage"],
            "concurrency": row.get("concurrency"),
            "derated_point_ms": derated_val,
            "published_workload": match["workload"],
            "published_value": published_val,
            "divergence": divergence,
        }
        out["comparisons"].append(entry)
        if divergence > DIVERGENCE_THRESHOLD:
            out["flags"].append(
                {**entry, "reason": f"divergence {divergence:.1%} > {DIVERGENCE_THRESHOLD:.0%}"}
            )

    if out["flags"]:
        out["status"] = "flags_present"

    out_path.write_text(json.dumps(out, indent=2))
    print(f"[crosscheck] status={out['status']} flags={len(out['flags'])} -> {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
