"""HARNESS-01 enforcement: gate runners must not import substrate internals.

Walks gates/ via AST. Phase 1's gates/__init__.py is the only file in the
tree; this test exists so Phase 2/3 contributors who add gates/g1/runner.py
trip the assertion immediately if they regress and import torch / vllm
/ onnxruntime / etc. directly.
"""

from __future__ import annotations

import ast
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
GATES = ROOT / "gates"

FORBIDDEN_IN_GATES = {
    "torch",
    "onnxruntime",
    "vllm",
    "transformers",
    "ctranslate2",
    "faster_whisper",
}


def _root_module(name: str) -> str:
    return name.split(".")[0]


def test_gate_runners_do_not_import_substrate_internals() -> None:
    py_files = list(GATES.rglob("*.py"))
    # Phase 1: only __init__.py exists. Test still runs to validate scaffolding.
    assert len(py_files) >= 1, "Expected at least gates/__init__.py to exist"
    offenders: list[tuple[pathlib.Path, str]] = []
    for py_file in py_files:
        tree = ast.parse(py_file.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if _root_module(alias.name) in FORBIDDEN_IN_GATES:
                        offenders.append((py_file, alias.name))
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                if _root_module(module) in FORBIDDEN_IN_GATES:
                    offenders.append((py_file, module))
    assert not offenders, (
        f"HARNESS-01 violation: gate runners importing forbidden internals: {offenders}"
    )
