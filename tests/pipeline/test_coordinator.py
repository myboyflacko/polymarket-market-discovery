import asyncio
from datetime import UTC, datetime

import pytest

from polymarket_market_discovery.discovery.domain import DiscoveryRunResult
from polymarket_market_discovery.markets.domain import MarketRegistrySyncResult
from polymarket_market_discovery.orderbooks.domain import OrderBookCollectionResult
from polymarket_market_discovery.pipeline.coordinator import PipelineCoordinator

NOW = datetime(2026, 8, 14, tzinfo=UTC)


def test_run_once_uses_last_known_good_orderbooks_after_upstream_error() -> None:
    calls: list[str] = []
    async def discovery(*, now):
        calls.append("discovery")
        raise RuntimeError("data api unavailable")
    async def markets(*, now):
        calls.append("markets")
        return MarketRegistrySyncResult(
            run_id=None, status="skipped", skip_reason="no_markets_to_sync",
            generated_at=now,
        )
    async def orderbooks(*, now):
        calls.append("orderbooks")
        return OrderBookCollectionResult(
            run_id="o", status="completed", success_count=2, generated_at=now
        )
    result = asyncio.run(PipelineCoordinator(
        discovery_runner=discovery, market_runner=markets,
        orderbook_runner=orderbooks, wall_clock=lambda: NOW,
    ).run_once())
    assert calls == ["discovery", "markets", "orderbooks"]
    assert result.status == "partial"
    assert result.errors == {"discovery": "data api unavailable"}


def test_run_forever_bootstraps_then_uses_fixed_layer_cadence() -> None:
    elapsed = 0.0
    calls: list[tuple[str, float]] = []
    async def discovery(*, now):
        calls.append(("discovery", elapsed))
        return DiscoveryRunResult(run_id="d", status="completed", generated_at=now)
    async def markets(*, now):
        calls.append(("markets", elapsed))
        return MarketRegistrySyncResult(run_id="m", status="completed", generated_at=now)
    async def orderbooks(*, now):
        calls.append(("orderbooks", elapsed))
        return OrderBookCollectionResult(run_id="o", status="completed", generated_at=now)
    async def sleep(seconds):
        nonlocal elapsed
        if elapsed >= 900:
            raise StopScheduler
        elapsed += seconds
    coordinator = PipelineCoordinator(
        discovery_runner=discovery, market_runner=markets,
        orderbook_runner=orderbooks, monotonic_clock=lambda: elapsed,
        wall_clock=lambda: NOW, sleep=sleep,
    )
    with pytest.raises(StopScheduler):
        asyncio.run(coordinator.run_forever())
    assert calls == [
        ("discovery", 0.0), ("markets", 0.0), ("orderbooks", 0.0),
        ("orderbooks", 300.0), ("orderbooks", 600.0),
        ("discovery", 900.0), ("markets", 900.0), ("orderbooks", 900.0),
    ]


def test_missed_ticks_are_coalesced_without_catch_up_burst() -> None:
    elapsed = 0.0
    calls: list[tuple[str, float]] = []
    async def run(name, result_type, now):
        calls.append((name, elapsed))
        return result_type(run_id=name, status="completed", generated_at=now)
    async def sleep(seconds):
        nonlocal elapsed
        if elapsed >= 1000:
            raise StopScheduler
        elapsed = 1000.0
    coordinator = PipelineCoordinator(
        discovery_runner=lambda **kw: run("discovery", DiscoveryRunResult, kw["now"]),
        market_runner=lambda **kw: run("markets", MarketRegistrySyncResult, kw["now"]),
        orderbook_runner=lambda **kw: run("orderbooks", OrderBookCollectionResult, kw["now"]),
        monotonic_clock=lambda: elapsed, wall_clock=lambda: NOW, sleep=sleep,
    )
    with pytest.raises(StopScheduler):
        asyncio.run(coordinator.run_forever())
    assert calls == [
        ("discovery", 0.0), ("markets", 0.0), ("orderbooks", 0.0),
        ("discovery", 1000.0), ("markets", 1000.0), ("orderbooks", 1000.0),
    ]


class StopScheduler(Exception):
    pass
