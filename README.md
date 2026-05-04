# RBOX — receptionBOX Phase 0 Cloud Benchmark Harness

Pre-discovery cloud benchmark effort that validates whether receptionBOX can
hit its end-to-end latency and quality budgets on Strix Halo (gfx1151) by
running cloud GPU benchmarks (RunPod H100 + TensorWave/Vultr MI300X) and
producing derated predictions plus a feasibility memo.

## Setup

```bash
uv sync --all-groups
uv run pre-commit install
```

## Common targets

```bash
make install   # uv sync --all-groups
make lint      # ruff check + ruff format --check
make test      # pytest
make check     # lint + test + manifest enforcement (CI gate)
make assets    # build all evaluation corpora (Plan 03 + Plan 04)
make report    # rebuild SQLite index + render synthesis (Phase 4)
make export-requirements  # emit requirements.lock (pip-compat) from uv.lock (INFRA-02)
```

See `.planning/ROADMAP.md` for phase plan; `CLAUDE.md` for tech stack lockdown.
