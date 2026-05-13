# receptionBOX Phase 0 harness Makefile (INFRA-03).
# All targets run inside the uv-managed env via `uv run`.
.PHONY: install lint test check assets assets-text assets-render assets-g711 \
        smoke g1 g2 g3 g5 g7 report canary export-requirements

install:
	uv sync --all-groups
	uv run pre-commit install

lint:
	uv run ruff check .
	uv run ruff format --check .

test:
	uv run pytest -q

# INFRA-02 literal compliance: emit pip-format requirements.lock from uv.lock
# (uv.lock remains canonical; requirements.lock is the pip-compat export)
export-requirements:
	uv export --format requirements-txt --no-hashes -o requirements.lock

check:
	$(MAKE) lint
	$(MAKE) test
	uv run python tools/check_asset_manifest.py

# Phase 1 asset pipeline (Plans 03 + 04 fill bodies)
assets-text:
	uv run python -m assets.author_scripts
	uv run python -m assets.upl_probes.author_probes
	uv run python -m assets.tts_pairs.author_pairs

assets-render:
	cd assets/render_env && uv run python -m render_corpus

assets-g711:
	uv run python -m assets.g711 --validate

assets:
	$(MAKE) assets-text
	$(MAKE) assets-render
	$(MAKE) assets-g711

# Phase 2 gate runners (HARNESS-06 / Plan 02-02). Endpoint URLs read from
# env with localhost defaults; override by exporting before make invocation.
VLLM_URL ?= http://127.0.0.1:8000
VLLM_MODEL ?= Qwen/Qwen3-4B
WHISPER_DIR ?= /models/distil_whisper_large_v3_int8
CHATTERBOX_URL ?= http://127.0.0.1:8004
KOKORO_URL ?= http://127.0.0.1:8005

_RUNNER_FLAGS = \
	--vllm-url=$(VLLM_URL) \
	--vllm-model=$(VLLM_MODEL) \
	--whisper-dir=$(WHISPER_DIR) \
	--chatterbox-url=$(CHATTERBOX_URL) \
	--kokoro-url=$(KOKORO_URL)

smoke:
	uv run python -m gates.g1.runner --gate=smoke --n-calls=5 --corpus=corpus_500 $(_RUNNER_FLAGS)

g1:
	uv run python -m gates.g1.runner --gate=g1 --strata=config/sanity_strata.yaml $(_RUNNER_FLAGS)

g2:
	uv run python -m gates.g2.runner --gate=g2 --strata=config/sanity_strata.yaml $(_RUNNER_FLAGS)

g3:
	uv run python -m gates.g3.runner --gate=g3 --strata=config/sanity_strata.yaml $(_RUNNER_FLAGS)

g5:
	uv run python -m gates.g5.runner --gate=g5 --strata=config/sanity_strata.yaml $(_RUNNER_FLAGS)

g7:
	uv run python -m gates.g7.runner --gate=g7 --corpus=tts_pairs \
		--audio-out-dir=results/g7/audio $(_RUNNER_FLAGS)

# Phase 4 placeholders
report:
	@echo "Phase 4 — synthesis report not yet implemented." >&2
	@exit 1

canary:
	@echo "Phase 4 — end-of-week canary (REPRO-04) not yet implemented." >&2
	@exit 1
