"""Cost-watch adapter tests. Adapters MUST NOT raise even on error paths."""

from __future__ import annotations

import asyncio
import logging

import httpx
import pytest

from cost.adapters import runpod as rp
from cost.adapters import tensorwave as tw
from cost.adapters import vultr as v


def _run(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


@pytest.fixture
def no_env_vars(monkeypatch):
    monkeypatch.delenv("RUNPOD_API_KEY", raising=False)
    monkeypatch.delenv("VULTR_API_KEY", raising=False)


def test_runpod_no_api_key_warns_and_returns_zero(no_env_vars, caplog) -> None:
    caplog.set_level(logging.WARNING)

    async def go():
        async with httpx.AsyncClient() as client:
            return await rp.poll(client)

    spend, projected = _run(go())
    assert (spend, projected) == (0.0, 0.0)
    assert any("RUNPOD_API_KEY" in rec.message for rec in caplog.records)


def test_vultr_no_api_key_warns_and_returns_zero(no_env_vars, caplog) -> None:
    caplog.set_level(logging.WARNING)

    async def go():
        async with httpx.AsyncClient() as client:
            return await v.poll(client)

    spend, projected = _run(go())
    assert (spend, projected) == (0.0, 0.0)
    assert any("VULTR_API_KEY" in rec.message for rec in caplog.records)


def test_tensorwave_always_warns_per_pitfall_c(caplog) -> None:
    caplog.set_level(logging.WARNING)

    async def go():
        async with httpx.AsyncClient() as client:
            return await tw.poll(client)

    spend, projected = _run(go())
    assert (spend, projected) == (0.0, 0.0)
    assert any(
        "Pitfall C" in rec.message or "tensorwave" in rec.message.lower() for rec in caplog.records
    )


def test_vultr_handles_404_gracefully(monkeypatch, caplog) -> None:
    """Simulated 404 — adapter logs warning, returns zero, never raises."""
    monkeypatch.setenv("VULTR_API_KEY", "fake-key-for-test")
    caplog.set_level(logging.WARNING)

    def transport_handler(request):
        return httpx.Response(404, text="not found")

    async def go():
        transport = httpx.MockTransport(transport_handler)
        async with httpx.AsyncClient(transport=transport) as client:
            return await v.poll(client)

    spend, projected = _run(go())
    assert (spend, projected) == (0.0, 0.0)


def test_vultr_parses_pending_charges(monkeypatch) -> None:
    """Successful happy path — sum of pending charges."""
    monkeypatch.setenv("VULTR_API_KEY", "fake-key-for-test")

    def transport_handler(request):
        return httpx.Response(
            200,
            json={
                "pending_charges": [
                    {"amount": "12.50", "description": "MI300X compute"},
                    {"amount": "1.20", "description": "egress"},
                ]
            },
        )

    async def go():
        transport = httpx.MockTransport(transport_handler)
        async with httpx.AsyncClient(transport=transport) as client:
            return await v.poll(client)

    spend, projected = _run(go())
    assert spend == pytest.approx(13.70)
    assert projected == 0.0


def test_watch_loop_runs_one_iteration(monkeypatch, caplog) -> None:
    """End-to-end: watch_loop with iterations=1 polls all providers and exits."""
    from cost import watch

    async def fake_poll(client):
        return (1.23, 4.56)

    monkeypatch.setitem(watch.ADAPTERS, "runpod", fake_poll)
    monkeypatch.setitem(watch.ADAPTERS, "tensorwave", fake_poll)
    monkeypatch.setitem(watch.ADAPTERS, "vultr", fake_poll)
    caplog.set_level(logging.INFO)
    asyncio.run(
        watch.watch_loop(
            ["runpod", "tensorwave", "vultr"],
            poll_interval_s=0,
            iterations=1,
        )
    )
    msgs = [rec.message for rec in caplog.records]
    assert any("runpod: cumulative=$1.23" in m for m in msgs)
