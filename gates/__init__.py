"""HARNESS-06 substrate-agnostic gate runners.

Contract: every runner takes a Substrate ABC instance + asset corpus path,
emits results/{gate}/{run_id}.jsonl + .env.json. NEVER imports torch /
onnxruntime / vllm / faster_whisper directly (HARNESS-01 — verified by
tests/test_harness_isolation.py).

Concrete runners live under gates/g{1,2,3,5}/runner.py and subclass
GateRunner from gates._runner_base.
"""
