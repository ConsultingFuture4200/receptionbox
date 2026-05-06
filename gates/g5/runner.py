"""G5 UPL guardrail gate runner.

For each probe (UPL adversarial OR benign control), the runner composes:

    {reference_prompt}\n\nUser: {probe}\n\nRespond with valid JSON: ...

…and asks the substrate to generate under an xgrammar-constrained schema
that forces the model to emit `{"refused": <bool>, "reason": <string>}`.

Per-row metrics: refused (parsed), gt_refusal_label, passed,
probe_category, control, model_reason, raw_output (truncated), parse_error.

T-02-02-02 mitigation: model_reason is truncated to 200 chars and
raw_output to 500 chars. Probe text + model output stay out of the
env.json sidecar (sidecar is per-run, not per-row).
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import pathlib
import sys

from gates._runner_base import GateRunner
from harness.results import GateResult
from substrate import Substrate

logger = logging.getLogger(__name__)


# xgrammar JSON schema for refusal output.
REFUSAL_GRAMMAR: dict = {
    "type": "object",
    "properties": {
        "refused": {"type": "boolean"},
        "reason": {"type": "string", "maxLength": 200},
    },
    "required": ["refused", "reason"],
    "additionalProperties": False,
}


def load_reference_prompt(
    path: pathlib.Path = pathlib.Path("assets/reference_prompt.md"),
    *,
    firm_name: str = "Test Firm",
    practice_area: str = "family law",
) -> str:
    """Load `assets/reference_prompt.md` and substitute `{firm_name}` / `{practice_area}`."""
    tpl = path.read_text()
    return tpl.replace("{firm_name}", firm_name).replace("{practice_area}", practice_area)


def _probe_text(asset: dict) -> str:
    """Plan calls the field `text`; the on-disk probes.json calls it `prompt`. Accept both."""
    return asset.get("text") or asset.get("prompt") or ""


def _probe_refusal_label(asset: dict) -> bool:
    """Plan: bool `refusal_label`. probes.json: `expected_label` in {refuse, answer}."""
    if "refusal_label" in asset:
        return bool(asset["refusal_label"])
    label = asset.get("expected_label", "")
    return label == "refuse"


class G5Runner(GateRunner):
    """G5 UPL guardrail runner. One GateResult per probe."""

    def __init__(
        self,
        *,
        substrate: Substrate,
        reference_prompt: str | None = None,
        **kw,
    ) -> None:
        super().__init__(substrate=substrate, gate="g5", **kw)
        self._sys = reference_prompt if reference_prompt is not None else load_reference_prompt()

    async def run_one(self, asset: dict) -> GateResult:
        probe_text = _probe_text(asset)
        gt_refusal = _probe_refusal_label(asset)
        category = asset.get("category", "unknown")
        control = bool(asset.get("control", False))
        full_prompt = (
            f"{self._sys}\n\nUser: {probe_text}\n\n"
            "Respond with valid JSON: "
            '{"refused": <bool>, "reason": <string>}\n\nAssistant: '
        )
        try:
            parts: list[str] = []
            async for chunk in self.substrate.generate(
                full_prompt,
                grammar=REFUSAL_GRAMMAR,
                max_tokens=128,
            ):
                parts.append(chunk.text)
            raw = "".join(parts).strip()
            try:
                parsed = json.loads(raw)
                refused = bool(parsed.get("refused", False))
                reason = str(parsed.get("reason", ""))[:200]
                parse_error: str | None = None
            except json.JSONDecodeError as je:
                refused = False
                reason = ""
                parse_error = str(je)
            passed = refused == gt_refusal
        except Exception as e:
            return self.build_result(
                asset_id=asset["asset_id"],
                status="error",
                error_kind=type(e).__name__,
                error_msg=str(e)[:500],
            )
        return self.build_result(
            asset_id=asset["asset_id"],
            status="ok",
            metrics={
                "refused": refused,
                "gt_refusal_label": gt_refusal,
                "passed": passed,
                "probe_category": category,
                "control": control,
                "model_reason": reason,
                "raw_output": raw[:500],
                "parse_error": parse_error,
            },
        )


def _build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="gates.g5.runner")
    p.add_argument("--gate", default="g5", choices=["g5"])
    p.add_argument("--n-calls", type=int, default=None)
    p.add_argument("--strata", default=None)
    p.add_argument(
        "--probes",
        type=pathlib.Path,
        default=pathlib.Path("assets/upl_probes/probes.json"),
    )
    p.add_argument(
        "--benign",
        type=pathlib.Path,
        default=pathlib.Path("assets/upl_probes/benign_control.json"),
    )
    p.add_argument("--firm-name", default="Test Firm")
    p.add_argument("--practice-area", default="family law")
    p.add_argument("--vllm-url", default="http://127.0.0.1:8000")
    p.add_argument("--vllm-model", default="Qwen/Qwen3-4B")
    p.add_argument("--whisper-dir", default="/models/distil_whisper_large_v3_int8")
    p.add_argument("--chatterbox-url", default="http://127.0.0.1:8004")
    p.add_argument("--kokoro-url", default="http://127.0.0.1:8005")
    p.add_argument("--results-dir", type=pathlib.Path, default=pathlib.Path("results"))
    return p


def _load_probes(probes_path: pathlib.Path, benign_path: pathlib.Path) -> list[dict]:
    """Merge UPL adversarial + benign control probes; tag controls with `control: True`."""
    out: list[dict] = []
    if probes_path.exists():
        for p in json.loads(probes_path.read_text()):
            row = dict(p)
            row.setdefault("asset_id", row.get("probe_id", "upl-?"))
            row.setdefault("control", False)
            out.append(row)
    else:
        logger.warning(f"[g5] probes file not found at {probes_path}")
    if benign_path.exists():
        for p in json.loads(benign_path.read_text()):
            row = dict(p)
            row.setdefault("asset_id", row.get("probe_id", "benign-?"))
            row["control"] = True
            out.append(row)
    else:
        logger.warning(f"[g5] benign control file not found at {benign_path}")
    return out


def _select_probes(args: argparse.Namespace, probes: list[dict]) -> list[dict]:
    """Strata-aware selection per D-27. With --strata pointing at a populated
    config/sanity_strata.yaml, picks probes whose `probe_id` (or `asset_id`)
    appears under `strata.g5.assets`. Falls back to first N (default 12)
    probes when the strata file is absent or empty.
    """
    n_default = args.n_calls or 12
    if args.strata:
        strata_path = pathlib.Path(args.strata)
        if not strata_path.exists():
            logger.warning(
                f"[g5] strata file not found at {strata_path}; "
                f"defaulting to first {n_default} probes"
            )
            return probes[:n_default]
        import yaml

        data = yaml.safe_load(strata_path.read_text())
        wanted = set(data.get("strata", {}).get("g5", {}).get("assets", []))
        if not wanted:
            logger.warning(
                f"[g5] strata file {strata_path} has no g5 assets; "
                f"defaulting to first {n_default} probes"
            )
            return probes[:n_default]
        selected = [p for p in probes if p.get("asset_id") in wanted or p.get("probe_id") in wanted]
        seen = {p.get("asset_id") for p in selected} | {p.get("probe_id") for p in selected}
        missing = wanted - seen
        if missing:
            logger.warning(f"[g5] strata probe_ids not found: {sorted(missing)}")
        return selected
    return probes[:n_default]


async def main_async(argv: list[str]) -> int:
    from substrate.cuda import CUDASubstrate

    args = _build_arg_parser().parse_args(argv)
    sub = CUDASubstrate(
        vllm_url=args.vllm_url,
        vllm_model=args.vllm_model,
        whisper_model_dir=args.whisper_dir,
        chatterbox_url=args.chatterbox_url,
        kokoro_url=args.kokoro_url,
    )
    ref_prompt = load_reference_prompt(
        firm_name=args.firm_name,
        practice_area=args.practice_area,
    )
    probes = _select_probes(args, _load_probes(args.probes, args.benign))
    runner = G5Runner(
        substrate=sub,
        reference_prompt=ref_prompt,
        results_dir=args.results_dir,
    )
    await runner.start()
    results = await runner.run_all(probes)
    ok = sum(1 for r in results if r.status == "ok")
    logger.info(f"[g5] {ok}/{len(results)} ok; run_id={runner.run_id}")
    print(f"[g5] {ok}/{len(results)} ok; run_id={runner.run_id}")
    return 0 if ok == len(results) else 1


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    return asyncio.run(main_async(sys.argv[1:]))


if __name__ == "__main__":
    sys.exit(main())
