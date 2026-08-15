import asyncio
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from sqlalchemy import func, select

from polymarket_market_discovery.core.db.models import (
    MarketDiscoveryRun,
    MarketRegistrySyncRun,
    OrderbookCollectionRun,
    OrderbookSnapshot,
    PolymarketMarket,
    PolymarketToken,
)
from polymarket_market_discovery.discovery import repository as discovery_repository
from polymarket_market_discovery.discovery import service as discovery_service
from polymarket_market_discovery.markets import repository as market_repository
from polymarket_market_discovery.markets import service as market_service
from polymarket_market_discovery.orderbooks import repository as orderbook_repository
from polymarket_market_discovery.orderbooks import service as orderbook_service
from polymarket_market_discovery.pipeline.coordinator import PipelineCoordinator

NOW = datetime(2026, 8, 14, tzinfo=UTC)
WALLET = "0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"


@contextmanager
def acquired_lock():
    yield True


def test_pipeline_bootstrap_and_scheduled_orderbook_tick_persist_end_to_end(
    monkeypatch, sqlite_database
) -> None:
    _, session_factory, database_session = sqlite_database
    client = DeterministicClient()
    for repository in (
        discovery_repository, market_repository, orderbook_repository
    ):
        monkeypatch.setattr(repository, "database_session", database_session)
    for module in (discovery_service, market_service, orderbook_service):
        monkeypatch.setattr(module, "pipeline_lock", acquired_lock)
        monkeypatch.setattr(module, "recover_orphaned_runs", lambda **kwargs: None)
        monkeypatch.setattr(module, "get_polymarket_client", lambda: client)

    elapsed = 0.0
    async def sleep(seconds):
        nonlocal elapsed
        if elapsed >= 300:
            raise StopScheduler
        elapsed += seconds
    coordinator = PipelineCoordinator(
        discovery_runner=discovery_service.MarketDiscoveryService().run,
        market_runner=market_service.MarketRegistryService().run,
        orderbook_runner=orderbook_service.OrderbookCollectionService().run,
        monotonic_clock=lambda: elapsed,
        wall_clock=lambda: NOW + timedelta(seconds=elapsed),
        sleep=sleep,
    )
    with pytest.raises(StopScheduler):
        asyncio.run(coordinator.run_forever())

    with session_factory() as session:
        assert session.scalar(select(func.count(MarketDiscoveryRun.run_id))) == 1
        assert session.scalar(select(func.count(MarketRegistrySyncRun.run_id))) == 1
        runs = list(session.scalars(select(OrderbookCollectionRun)))
        assert session.scalar(select(func.count(OrderbookSnapshot.id))) == 4
    assert [run.status for run in runs] == ["completed", "completed"]
    assert client.orderbook_calls == 2


def test_pipeline_uses_fresh_registry_after_upstream_failures(
    monkeypatch, sqlite_database
) -> None:
    _, session_factory, database_session = sqlite_database
    client = FailingUpstreamClient()
    for repository in (
        discovery_repository, market_repository, orderbook_repository
    ):
        monkeypatch.setattr(repository, "database_session", database_session)
    for module in (discovery_service, market_service, orderbook_service):
        monkeypatch.setattr(module, "pipeline_lock", acquired_lock)
        monkeypatch.setattr(module, "recover_orphaned_runs", lambda **kwargs: None)
        monkeypatch.setattr(module, "get_polymarket_client", lambda: client)
    with session_factory() as session:
        session.add(MarketRegistrySyncRun(
            run_id="seed", status="completed", started_at=NOW, finished_at=NOW,
            input_discovery_run_ids=[],
        ))
        session.add(PolymarketMarket(
            condition_id="condition-1", active=True, closed=False, archived=False,
            enable_order_book=True, first_discovered_at=NOW,
            last_discovered_at=NOW, status_checked_at=NOW,
        ))
        session.add_all([
            _token("token-yes", "Yes", 0), _token("token-no", "No", 1)
        ])
        session.commit()

    result = asyncio.run(PipelineCoordinator(
        discovery_runner=discovery_service.MarketDiscoveryService().run,
        market_runner=market_service.MarketRegistryService().run,
        orderbook_runner=orderbook_service.OrderbookCollectionService().run,
        wall_clock=lambda: NOW,
    ).run_once())

    assert result.status == "partial"
    assert result.errors == {
        "discovery": "data api unavailable", "markets": "gamma unavailable"
    }
    assert result.orderbooks is not None and result.orderbooks.success_count == 2
    with session_factory() as session:
        assert session.scalar(select(func.count(OrderbookSnapshot.id))) == 2


class DeterministicClient:
    def __init__(self):
        self.orderbook_calls = 0

    async def get_leaderboard(self, params: Any):
        return [{"proxyWallet": WALLET}]

    async def get_current_positions(self, params: Any):
        return [{
            "conditionId": "condition-1", "asset": "token-yes",
            "oppositeAsset": "token-no", "outcome": "Yes",
            "oppositeOutcome": "No", "size": "10", "currentValue": "5",
        }]

    async def get_gamma_markets(self, condition_ids, *, closed):
        if closed:
            return []
        return [{
            "conditionId": "condition-1", "title": "Test market",
            "active": True, "closed": False, "archived": False,
            "enableOrderBook": True,
            "clobTokenIds": ["token-yes", "token-no"],
            "outcomes": ["Yes", "No"],
        }]

    async def get_order_books(self, params):
        self.orderbook_calls += 1
        return [{
            "asset_id": request.token_id, "market": "condition-1",
            "bids": [{"price": "0.40", "size": "10"}],
            "asks": [{"price": "0.60", "size": "10"}],
        } for request in params.root]


class FailingUpstreamClient(DeterministicClient):
    async def get_leaderboard(self, params):
        raise RuntimeError("data api unavailable")

    async def get_gamma_markets(self, condition_ids, *, closed):
        raise RuntimeError("gamma unavailable")


class StopScheduler(Exception):
    pass


def _token(token_id, outcome, outcome_index):
    return PolymarketToken(
        token_id=token_id, condition_id="condition-1", outcome=outcome,
        outcome_index=outcome_index, first_seen_at=NOW, last_seen_at=NOW,
    )
