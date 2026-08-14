from __future__ import annotations

import asyncio
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from polymarket_market_discovery.core.db import recovery
from polymarket_market_discovery.core.db.models import (
    MarketDiscoveryObservation,
    MarketDiscoveryRun,
    MarketRegistrySyncRun,
    MarketStatusSnapshot,
    OrderbookCollectionRun,
    PolymarketMarket,
    PolymarketToken,
)
from polymarket_market_discovery.core.time import ensure_utc
from polymarket_market_discovery.markets import repository as market_repository
from polymarket_market_discovery.markets import service as market_service
from polymarket_market_discovery.orderbooks import repository as orderbook_repository


NOW = datetime(2026, 8, 10, tzinfo=UTC)
MIGRATIONS_DIR = (
    Path(__file__).resolve().parents[2]
    / "src/polymarket_market_discovery/core/db/migrations"
)


@contextmanager
def acquired_lock() -> Iterator[bool]:
    yield True


@pytest.fixture
def baseline_database(tmp_path: Path):
    database_path = tmp_path / "registry-integration.sqlite"
    database_url = f"sqlite+pysqlite:///{database_path}"
    config = Config()
    config.set_main_option("script_location", str(MIGRATIONS_DIR))
    config.attributes["database_url"] = database_url
    command.upgrade(config, "head")

    engine = create_engine(database_url, future=True)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False, future=True)

    @contextmanager
    def database_session() -> Iterator[Session]:
        with session_factory() as session:
            yield session

    return session_factory, database_session


def test_market_registry_sync_persists_complete_current_state_and_history(
    monkeypatch, baseline_database
) -> None:
    session_factory, database_session = baseline_database
    _bind_database(monkeypatch, database_session)
    with session_factory() as session:
        session.add(
            MarketDiscoveryRun(
                run_id="discovery-1",
                status="completed",
                started_at=NOW - timedelta(days=2),
                finished_at=NOW - timedelta(days=1),
                strategies=["strategy-one", "strategy-two"],
            )
        )
        session.add_all(
            [
                _observation(
                    "discovery-1",
                    "strategy-one",
                    "new-market",
                    NOW - timedelta(days=2),
                ),
                _observation(
                    "discovery-1",
                    "strategy-two",
                    "new-market",
                    NOW - timedelta(days=1),
                ),
            ]
        )
        session.add_all(
            [
                _market("existing-market", active=False, closed=False, archived=False),
                _market("terminal-market", active=False, closed=True, archived=False),
            ]
        )
        session.add_all(
            [
                _token("existing-yes", "existing-market", "Yes", 0),
                _token("existing-no", "existing-market", "No", 1),
                _token("terminal-yes", "terminal-market", "Yes", 0),
                _token("terminal-no", "terminal-market", "No", 1),
            ]
        )
        session.commit()

    gamma = SuccessfulGammaClient()
    monkeypatch.setattr(market_service, "get_polymarket_client", lambda: gamma)

    result = asyncio.run(market_service.MarketRegistryService().run(now=NOW))

    assert result.status == "completed"
    assert result.input_discovery_run_ids == ["discovery-1"]
    assert result.checked_market_count == 2
    assert result.created_market_count == 1
    assert result.updated_market_count == 1
    assert gamma.calls == [
        (["existing-market", "new-market"], False),
        (["new-market"], True),
    ]

    with session_factory() as session:
        sync = session.get(MarketRegistrySyncRun, result.run_id)
        discovery = session.get(MarketDiscoveryRun, "discovery-1")
        new_market = session.get(PolymarketMarket, "new-market")
        existing_market = session.get(PolymarketMarket, "existing-market")
        terminal_market = session.get(PolymarketMarket, "terminal-market")
        snapshots = list(
            session.scalars(
                select(MarketStatusSnapshot).order_by(
                    MarketStatusSnapshot.condition_id
                )
            )
        )
        tokens = list(
            session.scalars(
                select(PolymarketToken)
                .where(
                    PolymarketToken.condition_id.in_(
                        ["existing-market", "new-market"]
                    )
                )
                .order_by(PolymarketToken.condition_id, PolymarketToken.outcome_index)
            )
        )

    assert sync is not None and sync.status == "completed"
    assert (
        sync.checked_market_count,
        sync.created_market_count,
        sync.updated_market_count,
    ) == (2, 1, 1)
    assert discovery is not None and discovery.registry_synced_at is not None
    assert new_market is not None
    assert ensure_utc(new_market.first_discovered_at) == NOW - timedelta(days=2)
    assert ensure_utc(new_market.last_discovered_at) == NOW - timedelta(days=1)
    assert new_market.closed is True
    assert new_market.raw_latest_payload["conditionId"] == "new-market"
    assert existing_market is not None and existing_market.active is True
    assert existing_market.title == "Existing updated"
    assert terminal_market is not None
    assert ensure_utc(terminal_market.status_checked_at) == NOW
    assert [snapshot.condition_id for snapshot in snapshots] == [
        "existing-market",
        "new-market",
    ]
    assert all(snapshot.raw_payload["conditionId"] for snapshot in snapshots)
    assert [(token.condition_id, token.token_id) for token in tokens] == [
        ("existing-market", "existing-yes"),
        ("existing-market", "existing-no"),
        ("new-market", "new-yes"),
        ("new-market", "new-no"),
    ]
    assert all(not hasattr(token, "raw_latest_payload") for token in tokens)
    existing_tokens = [
        token for token in tokens if token.condition_id == "existing-market"
    ]
    assert all(ensure_utc(token.last_seen_at) > NOW for token in existing_tokens)

    orderbook_repository.create_orderbook_collection_run(
        run_id="orderbooks-1", started_at=NOW, config_json={}
    )
    selected = orderbook_repository.snapshot_collectable_markets(
        run_id="orderbooks-1", selected_at=NOW
    )
    assert [item.token_id for item in selected] == ["existing-yes", "existing-no"]
    with session_factory() as session:
        orderbook_run = session.get(OrderbookCollectionRun, "orderbooks-1")
    assert orderbook_run is not None and orderbook_run.selected_market_count == 1
    assert orderbook_run.selected_token_count == 2


def test_market_registry_true_idle_skips_without_run(
    monkeypatch, baseline_database
) -> None:
    session_factory, database_session = baseline_database
    _bind_database(monkeypatch, database_session)

    result = asyncio.run(market_service.MarketRegistryService().run(now=NOW))

    assert result.status == "skipped"
    assert result.skip_reason == "no_markets_to_sync"
    with session_factory() as session:
        assert list(session.scalars(select(MarketRegistrySyncRun))) == []


def test_missing_gamma_market_fails_without_partial_state_and_can_retry(
    monkeypatch, baseline_database
) -> None:
    session_factory, database_session = baseline_database
    _bind_database(monkeypatch, database_session)
    with session_factory() as session:
        session.add(
            MarketDiscoveryRun(
                run_id="discovery-retry",
                status="completed",
                started_at=NOW,
                finished_at=NOW,
                strategies=["strategy"],
            )
        )
        session.add(
            _observation("discovery-retry", "strategy", "retry-market", NOW)
        )
        session.commit()

    gamma = RetryGammaClient()
    monkeypatch.setattr(market_service, "get_polymarket_client", lambda: gamma)

    with pytest.raises(ValueError, match="Gamma omitted requested markets"):
        asyncio.run(market_service.MarketRegistryService().run(now=NOW))

    failed_run_id = f"{NOW.strftime('%Y%m%dT%H%M%S%fZ')}-markets"
    with session_factory() as session:
        failed_run = session.get(MarketRegistrySyncRun, failed_run_id)
        discovery = session.get(MarketDiscoveryRun, "discovery-retry")
        assert failed_run is not None and failed_run.status == "failed"
        assert discovery is not None and discovery.registry_synced_at is None
        assert session.get(PolymarketMarket, "retry-market") is None
        assert list(session.scalars(select(MarketStatusSnapshot))) == []

    gamma.available = True
    retry_result = asyncio.run(
        market_service.MarketRegistryService().run(now=NOW + timedelta(seconds=1))
    )

    assert retry_result.status == "completed"
    assert retry_result.created_market_count == 1
    with session_factory() as session:
        discovery = session.get(MarketDiscoveryRun, "discovery-retry")
        assert discovery is not None and discovery.registry_synced_at is not None
        assert session.get(PolymarketMarket, "retry-market") is not None
        assert len(list(session.scalars(select(MarketStatusSnapshot)))) == 1


def test_token_invariant_failure_rolls_back_and_keeps_discovery_pending(
    monkeypatch, baseline_database
) -> None:
    session_factory, database_session = baseline_database
    _bind_database(monkeypatch, database_session)
    with session_factory() as session:
        session.add(
            MarketDiscoveryRun(
                run_id="discovery-token-change",
                status="completed",
                started_at=NOW,
                finished_at=NOW,
                strategies=["strategy"],
            )
        )
        session.add(
            _observation(
                "discovery-token-change", "strategy", "existing-market", NOW
            )
        )
        session.add(
            _market("existing-market", active=True, closed=False, archived=False)
        )
        session.add_all(
            [
                _token("existing-yes", "existing-market", "Yes", 0),
                _token("existing-no", "existing-market", "No", 1),
            ]
        )
        session.commit()

    monkeypatch.setattr(
        market_service,
        "get_polymarket_client",
        lambda: ChangedTokenGammaClient(),
    )

    with pytest.raises(ValueError, match="Token set changed for market"):
        asyncio.run(market_service.MarketRegistryService().run(now=NOW))

    failed_run_id = f"{NOW.strftime('%Y%m%dT%H%M%S%fZ')}-markets"
    with session_factory() as session:
        failed_run = session.get(MarketRegistrySyncRun, failed_run_id)
        discovery = session.get(MarketDiscoveryRun, "discovery-token-change")
        market = session.get(PolymarketMarket, "existing-market")
        tokens = list(
            session.scalars(
                select(PolymarketToken).order_by(PolymarketToken.outcome_index)
            )
        )
        snapshots = list(session.scalars(select(MarketStatusSnapshot)))
    assert failed_run is not None and failed_run.status == "failed"
    assert failed_run.error_message == "Token set changed for market existing-market"
    assert discovery is not None and discovery.registry_synced_at is None
    assert market is not None and market.raw_latest_payload == {"version": "original"}
    assert [token.token_id for token in tokens] == ["existing-yes", "existing-no"]
    assert snapshots == []


class SuccessfulGammaClient:
    def __init__(self) -> None:
        self.calls: list[tuple[list[str], bool]] = []

    async def get_gamma_markets(
        self, condition_ids: list[str], *, closed: bool
    ) -> list[dict[str, object]]:
        self.calls.append((condition_ids, closed))
        if closed:
            return [_gamma_market("new-market", closed=True, title="New closed")]
        return [
            _gamma_market(
                "existing-market",
                token_ids=["existing-yes", "existing-no"],
                title="Existing updated",
            )
        ]


class RetryGammaClient:
    def __init__(self) -> None:
        self.available = False

    async def get_gamma_markets(
        self, condition_ids: list[str], *, closed: bool
    ) -> list[dict[str, object]]:
        if not self.available:
            return []
        return [_gamma_market("retry-market", title="Retry market")]


class ChangedTokenGammaClient:
    async def get_gamma_markets(
        self, condition_ids: list[str], *, closed: bool
    ) -> list[dict[str, object]]:
        return [
            _gamma_market(
                "existing-market",
                title="Must roll back",
                token_ids=["replacement-yes", "existing-no"],
            )
        ]


def _bind_database(monkeypatch, database_session) -> None:
    monkeypatch.setattr(market_repository, "database_session", database_session)
    monkeypatch.setattr(orderbook_repository, "database_session", database_session)
    monkeypatch.setattr(recovery, "database_session", database_session)
    monkeypatch.setattr(market_service, "pipeline_lock", acquired_lock)


def _observation(
    run_id: str, strategy: str, condition_id: str, observed_at: datetime
) -> MarketDiscoveryObservation:
    return MarketDiscoveryObservation(
        discovery_run_id=run_id,
        strategy=strategy,
        strategy_version="v1",
        condition_id=condition_id,
        observed_at=observed_at,
        evidence_json={
            "schema_version": 1,
            "items": [{"kind": "test", "source": "test", "data": {}}],
        },
    )


def _market(
    condition_id: str, *, active: bool, closed: bool, archived: bool
) -> PolymarketMarket:
    return PolymarketMarket(
        condition_id=condition_id,
        title=f"{condition_id} original",
        active=active,
        closed=closed,
        archived=archived,
        enable_order_book=True,
        first_discovered_at=NOW - timedelta(days=5),
        last_discovered_at=NOW - timedelta(days=5),
        status_checked_at=NOW,
        raw_latest_payload={"version": "original"},
    )


def _token(
    token_id: str, condition_id: str, outcome: str, outcome_index: int
) -> PolymarketToken:
    return PolymarketToken(
        token_id=token_id,
        condition_id=condition_id,
        outcome=outcome,
        outcome_index=outcome_index,
        first_seen_at=NOW,
        last_seen_at=NOW,
    )


def _gamma_market(
    condition_id: str,
    *,
    closed: bool = False,
    title: str,
    token_ids: list[str] | None = None,
) -> dict[str, object]:
    return {
        "conditionId": condition_id,
        "title": title,
        "active": not closed,
        "closed": closed,
        "archived": False,
        "enableOrderBook": not closed,
        "clobTokenIds": token_ids or ["new-yes", "new-no"],
        "outcomes": ["Yes", "No"],
    }
