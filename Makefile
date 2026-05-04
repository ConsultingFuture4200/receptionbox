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

# Phase 2/3 placeholders — fail explicitly so operator knows they're not implemented
smoke g1 g2 g3 g5 g7:
	@echo "Gate $@ ships in Phase 2/3; not yet implemented." >&2
	@exit 1

# Phase 4 placeholders
report:
	@echo "Phase 4 — synthesis report not yet implemented." >&2
	@exit 1

canary:
	@echo "Phase 4 — end-of-week canary (REPRO-04) not yet implemented." >&2
	@exit 1
