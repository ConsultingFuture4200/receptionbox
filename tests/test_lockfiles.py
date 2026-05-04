"""Lockfile round-trip + schema validation (REPRO-01, REPRO-02)."""

from __future__ import annotations

import pathlib
import re

import yaml
from pydantic import BaseModel, Field

ROOT = pathlib.Path(__file__).resolve().parents[1]
SHA_OR_PENDING = re.compile(r"^([a-f0-9]{40}|pending)$")
DIGEST_OR_PENDING = re.compile(r"^(sha256:[a-f0-9]{64}|pending)$")


# Schemas live in the test file — they're enforcement contracts, not application logic.


class ImageEntry(BaseModel):
    provider: str
    rail: str
    image_ref: str
    tag: str
    digest: str
    registry: str
    captured_utc: str
    notes: str = ""


class ImagesLock(BaseModel):
    images: list[ImageEntry] = Field(min_length=1)


class ModelFile(BaseModel):
    filename: str
    sha256: str


class ModelEntry(BaseModel):
    name: str
    repo_id: str
    revision: str
    files: list[ModelFile] = Field(default_factory=list)
    notes: str = ""


class ModelsLock(BaseModel):
    models: list[ModelEntry] = Field(min_length=1)


def test_images_lock_validates() -> None:
    raw = yaml.safe_load((ROOT / "bench" / "images.lock.yaml").read_text())
    lock = ImagesLock.model_validate(raw)
    assert len(lock.images) >= 4  # cuda x2 + rocm x2 (vllm + pytorch each)
    rails = {img.rail for img in lock.images}
    assert rails == {"cuda", "rocm"}


def test_images_lock_digest_format() -> None:
    raw = yaml.safe_load((ROOT / "bench" / "images.lock.yaml").read_text())
    for img in raw["images"]:
        assert DIGEST_OR_PENDING.match(img["digest"]), (
            f"{img['image_ref']}:{img['tag']} digest must be sha256:<64hex> or 'pending', "
            f"got {img['digest']!r}"
        )


def test_models_lock_validates() -> None:
    raw = yaml.safe_load((ROOT / "bench" / "models.lock.yaml").read_text())
    lock = ModelsLock.model_validate(raw)
    names = {m.name for m in lock.models}
    assert {
        "distil_whisper_large_v3_int8",
        "qwen3_4b_awq_int4",
        "chatterbox_turbo",
        "kokoro_82m",
    } <= names


def test_models_lock_revision_format() -> None:
    raw = yaml.safe_load((ROOT / "bench" / "models.lock.yaml").read_text())
    for m in raw["models"]:
        assert SHA_OR_PENDING.match(m["revision"]), (
            f"{m['name']} revision must be 40-char hex SHA or 'pending', got {m['revision']!r}"
        )
        for f in m.get("files", []):
            assert f["sha256"] == "pending" or re.match(r"^[a-f0-9]{64}$", f["sha256"]), (
                f"{m['name']}/{f['filename']} sha256 must be 64-hex or 'pending'"
            )


def test_fetch_models_module_imports() -> None:
    """tools/fetch_models.py must import cleanly (proves huggingface_hub installed)."""
    import importlib

    mod = importlib.import_module("tools.fetch_models")
    assert callable(mod.fetch_pinned)
    assert callable(mod.main)
