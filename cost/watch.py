"""5-minute cost-watch daemon (CLOUD-03).

Run alongside any cloud session:
    uv run python -m cost.watch --providers runpod,tensorwave

Polls each provider's adapter every 5 minutes. Logs spend visibility.
Hard-stop logic (terminate-pod-on-breach) ships in Phase 2 (CLOUD-04
in-instance watchdog) — Phase 1 is visibility-only.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from collections.abc import Callable, Coroutine

import httpx

from cost.adapters import runpod as runpod_adapter
from cost.adapters import tensorwave as tw_adapter
from cost.adapters import vultr as vultr_adapter

POLL_INTERVAL_S = 300  # 5 minutes per CLOUD-03

ADAPTERS: dict[
    str,
    Callable[[httpx.AsyncClient], Coroutine[None, None, tuple[float, float]]],
] = {
    "runpod": runpod_adapter.poll,
    "tensorwave": tw_adapter.poll,
    "vultr": vultr_adapter.poll,
}


async def watch_loop(
    active_providers: list[str],
    *,
    poll_interval_s: int = POLL_INTERVAL_S,
    iterations: int | None = None,
) -> None:
    """Poll each provider every poll_interval_s. Runs forever unless iterations set."""
    async with httpx.AsyncClient() as client:
        i = 0
        while iterations is None or i < iterations:
            for provider in active_providers:
                if provider not in ADAPTERS:
                    logging.warning(f"[watch] unknown provider: {provider}")
                    continue
                try:
                    spend, projected = await ADAPTERS[provider](client)
                    logging.info(
                        f"[watch] {provider}: cumulative=${spend:.2f} "
                        f"projected_daily=${projected:.2f}"
                    )
                except Exception as e:
                    logging.warning(f"[watch] {provider} adapter raised (should not): {e}")
            i += 1
            if iterations is None or i < iterations:
                await asyncio.sleep(poll_interval_s)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--providers",
        default="runpod,tensorwave",
        help="Comma-separated provider list (runpod,tensorwave,vultr)",
    )
    parser.add_argument("--interval", type=int, default=POLL_INTERVAL_S)
    parser.add_argument(
        "--iterations",
        type=int,
        default=None,
        help="Stop after N iterations (default: forever)",
    )
    args = parser.parse_args()
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )
    providers = [p.strip() for p in args.providers.split(",") if p.strip()]
    try:
        asyncio.run(
            watch_loop(providers, poll_interval_s=args.interval, iterations=args.iterations)
        )
    except KeyboardInterrupt:
        logging.info("[watch] stopped by operator")
    return 0


if __name__ == "__main__":
    sys.exit(main())
