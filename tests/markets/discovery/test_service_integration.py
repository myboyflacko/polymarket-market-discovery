import asyncio
from collections import Counter
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select

from polymarket_market_discovery.core.db import lock, recovery
from polymarket_market_discovery.core.db.models import (
    MarketDiscoveryObservation,
    MarketDiscoveryRun,
)
from polymarket_market_discovery.core.time import ensure_utc
from polymarket_market_discovery.discovery import repository, service
from polymarket_market_discovery.discovery.registry import build_strategies


NOW = datetime(2026, 8, 10, tzinfo=UTC)
WALLET = "0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"


class DeterministicPolymarketClient:
    def __init__(self) -> None:
        self.leaderboard_orders: list[str] = []
        self.position_wallets: list[str] = []

    async def get_leaderboard(self, params: Any) -> list[dict[str, Any]]:
        self.leaderboard_orders.append(params.orderBy)
        return [{"proxyWallet": WALLET}]

    async def get_current_positions(self, params: Any) -> list[dict[str, Any]]:
        self.position_wallets.append(params.user)
        return [
            _position("condition-1", "token-1-yes", "token-1-no"),
            _position("condition-1", "token-1-yes", "token-1-no"),
            _position("condition-2", "token-2-yes", "token-2-no"),
        ]


def test_discovery_service_persists_complete_registered_strategy_run(
    monkeypatch, sqlite_database
) -> None:
    engine, session_factory, test_session = sqlite_database
    client = DeterministicPolymarketClient()
    monkeypatch.setattr(lock, "create_database_engine", lambda: engine)
    monkeypatch.setattr(recovery, "database_session", test_session)
    monkeypatch.setattr(repository, "database_session", test_session)
    monkeypatch.setattr(service, "get_polymarket_client", lambda: client)

    result = asyncio.run(service.MarketDiscoveryService().run(now=NOW))

    with session_factory() as session:
        runs = list(session.scalars(select(MarketDiscoveryRun)))
        observations = list(
            session.scalars(
                select(MarketDiscoveryObservation).order_by(
                    MarketDiscoveryObservation.id
                )
            )
        )

    registered_strategies = build_strategies()
    expected_strategies = [strategy.name for strategy in registered_strategies]
    expected_versions = [strategy.version for strategy in registered_strategies]
    assert result.status == "completed"
    assert result.run_id is not None
    assert result.strategies == expected_strategies
    assert result.observation_count == 3
    assert result.discovered_market_count == 2
    assert Counter(client.leaderboard_orders) == {"PNL": 1, "VOL": 1}
    assert client.position_wallets == [WALLET]

    assert len(runs) == 1
    run = runs[0]
    assert run.run_id == result.run_id
    assert run.status == "completed"
    assert ensure_utc(run.started_at) == NOW
    assert run.finished_at is not None
    assert ensure_utc(run.finished_at) >= NOW
    assert run.strategies == expected_strategies
    assert [entry["strategy"] for entry in run.strategy_log] == expected_strategies
    assert [entry["version"] for entry in run.strategy_log] == expected_versions
    assert [entry["status"] for entry in run.strategy_log] == [
        "completed"
    ] * len(registered_strategies)
    assert all(entry["finished_at"] is not None for entry in run.strategy_log)
    assert run.observation_count == len(observations) == 3
    assert run.discovered_market_count == 2
    assert [row.discovery_run_id for row in observations] == [run.run_id] * 3
    assert [row.condition_id for row in observations] == [
        "condition-1",
        "condition-1",
        "condition-2",
    ]


def _position(
    condition_id: str, held_token_id: str, opposite_token_id: str
) -> dict[str, Any]:
    return {
        "conditionId": condition_id,
        "asset": held_token_id,
        "oppositeAsset": opposite_token_id,
        "outcome": "Yes",
        "oppositeOutcome": "No",
        "size": "10",
        "currentValue": "5",
    }
