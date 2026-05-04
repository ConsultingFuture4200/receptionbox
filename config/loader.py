"""Config loaders for INFRA-04. Each YAML file has a matching pydantic model.

Loaders are explicit (not auto-discovery) so import paths are visible to
ruff and to gate runners. Validation is strict: missing fields raise
ValidationError (not silent defaults), per pydantic v2 behavior.
"""

from __future__ import annotations

import pathlib
from typing import Literal

import yaml
from pydantic import BaseModel, Field, field_validator

CONFIG_DIR = pathlib.Path("config")


# --- models.yaml ---


class ModelEntry(BaseModel):
    repo_id: str
    filename: str | None = None
    quantization: str | None = None
    format: str
    notes: str | None = None


class ModelsConfig(BaseModel):
    stt: ModelEntry
    llm: ModelEntry
    tts_primary: ModelEntry
    tts_fallback: ModelEntry


def load_models(path: pathlib.Path = CONFIG_DIR / "models.yaml") -> ModelsConfig:
    return ModelsConfig.model_validate(yaml.safe_load(path.read_text()))


# --- substrates.yaml ---


class SubstrateEntry(BaseModel):
    provider: str
    gpu: str
    image_ref: str
    image_tag: str
    fallback_provider: str | None = None
    cuda_version: str | None = None
    rocm_version: str | None = None


class SubstratesConfig(BaseModel):
    cuda: SubstrateEntry
    rocm: SubstrateEntry


def load_substrates(path: pathlib.Path = CONFIG_DIR / "substrates.yaml") -> SubstratesConfig:
    return SubstratesConfig.model_validate(yaml.safe_load(path.read_text()))


# --- gates.yaml ---


class GateEntry(BaseModel):
    asset_corpus: str
    concurrency: list[int]
    max_minutes: int = Field(gt=0)
    threshold_sweep_ms: list[int] | None = None
    benign_control_corpus: str | None = None
    reference_prompt_path: str | None = None
    engines: list[str] | None = None
    call_count: int | None = None

    @field_validator("concurrency")
    @classmethod
    def _concurrency_positive(cls, v: list[int]) -> list[int]:
        if not v or any(c <= 0 for c in v):
            raise ValueError("concurrency must be a non-empty list of positive ints")
        return v


class GatesConfig(BaseModel):
    g1: GateEntry
    g2: GateEntry
    g3: GateEntry
    g5: GateEntry
    g7: GateEntry
    smoke: GateEntry
    canary: GateEntry


def load_gates(path: pathlib.Path = CONFIG_DIR / "gates.yaml") -> GatesConfig:
    return GatesConfig.model_validate(yaml.safe_load(path.read_text()))


# --- budget.yaml ---


class GateBudget(BaseModel):
    projected_cost_per_run_usd: float = Field(ge=0)
    expected_runs: int = Field(ge=0)


class BudgetConfig(BaseModel):
    """Per-gate cost projection. Consumed by INFRA-06 cost ledger.

    `projected_total(safety_factor)` returns the per-gate projected cost
    ceiling (cost_per_run * runs * safety_factor) used by
    `cost.ledger.authorize_spend()` headroom check.
    """

    safety_factor: float = Field(default=1.5, ge=1.0)
    provider_caps: dict[Literal["runpod", "tensorwave", "vultr"], float]
    gates: dict[str, GateBudget]

    def projected_total(self, gate: str, safety_factor: float | None = None) -> float:
        sf = safety_factor if safety_factor is not None else self.safety_factor
        if gate not in self.gates:
            raise KeyError(f"Unknown gate: {gate}")
        b = self.gates[gate]
        return b.projected_cost_per_run_usd * b.expected_runs * sf


def load_budget(path: pathlib.Path = CONFIG_DIR / "budget.yaml") -> BudgetConfig:
    return BudgetConfig.model_validate(yaml.safe_load(path.read_text()))
