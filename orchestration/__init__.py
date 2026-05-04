"""Cloud-pod orchestration (CLOUD-01/02).

Each provider's module exposes `provision(*, gate: str, projected_cost: float)`
that gates ALL provisioning calls through `cost.ledger.authorize_spend()`.
Phase 1 ships skeletons; Phase 2 (HARNESS-02) fills the RunPod body;
Phase 3 (HARNESS-03) fills TensorWave + Vultr bodies.
"""
