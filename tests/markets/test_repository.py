from datetime import UTC, datetime

from sqlalchemy import select

from polymarket_market_discovery.core.db.models import (
    MarketDiscoveryObservation,
    MarketDiscoveryRun,
    MarketDiscoveryStrategyRun,
    MarketRegistrySyncRun,
    MarketStatusSnapshot,
    PolymarketMarket,
    PolymarketToken,
)
from polymarket_market_discovery.markets import repository
from polymarket_market_discovery.markets.domain import (
    MarketTokenPayload,
    PolymarketMarketPayload,
)


NOW = datetime(2026, 8, 10, tzinfo=UTC)


def test_registry_deduplicates_discovery_and_stores_both_tokens(
    monkeypatch, sqlite_database
) -> None:
    _, session_factory, test_session = sqlite_database
    monkeypatch.setattr(repository, "database_session", test_session)
    with session_factory() as session:
        session.add(
            MarketDiscoveryRun(
                run_id="discovery-1",
                status="completed",
                started_at=NOW,
                finished_at=NOW,
                strategies=["strategy"],
            )
        )
        strategy = MarketDiscoveryStrategyRun(
            discovery_run_id="discovery-1",
            strategy="strategy",
            strategy_version="v1",
            status="completed",
        )
        session.add(strategy)
        session.flush()
        session.add_all([_observation(strategy.id), _observation(strategy.id)])
        session.commit()

    sync_input = repository.get_market_sync_input()
    assert sync_input.discovery_run_ids == ["discovery-1"]
    assert sync_input.condition_ids == ["condition-1"]

    repository.create_market_sync_run(
        run_id="markets-1",
        started_at=NOW,
        input_discovery_run_ids=sync_input.discovery_run_ids,
    )
    created, updated = repository.complete_market_sync_run(
        run_id="markets-1",
        payloads=[_market_payload()],
        discovery_run_ids=sync_input.discovery_run_ids,
        checked_at=NOW,
    )

    with session_factory() as session:
        market = session.get(PolymarketMarket, "condition-1")
        tokens = list(
            session.scalars(
                select(PolymarketToken).order_by(PolymarketToken.outcome_index)
            )
        )
        snapshots = list(session.scalars(select(MarketStatusSnapshot)))
        discovery = session.get(MarketDiscoveryRun, "discovery-1")
        sync = session.get(MarketRegistrySyncRun, "markets-1")

    assert (created, updated) == (1, 0)
    assert market is not None and market.active is True
    assert [(token.token_id, token.outcome) for token in tokens] == [
        ("token-yes", "Yes"),
        ("token-no", "No"),
    ]
    assert len(snapshots) == 1
    assert discovery is not None and discovery.registry_synced_at is not None
    assert sync is not None and sync.status == "completed"

    refresh_input = repository.get_market_sync_input()
    assert refresh_input.discovery_run_ids == []
    assert refresh_input.condition_ids == ["condition-1"]


def test_terminal_markets_are_not_refreshed(monkeypatch, sqlite_database) -> None:
    _, session_factory, test_session = sqlite_database
    monkeypatch.setattr(repository, "database_session", test_session)
    with session_factory() as session:
        session.add(
            PolymarketMarket(
                condition_id="terminal",
                active=False,
                closed=True,
                archived=False,
                enable_order_book=False,
                first_discovered_at=NOW,
                last_discovered_at=NOW,
                status_checked_at=NOW,
            )
        )
        session.commit()

    assert repository.get_market_sync_input().condition_ids == []


def _observation(strategy_run_id: int) -> MarketDiscoveryObservation:
    return MarketDiscoveryObservation(
        strategy_run_id=strategy_run_id,
        condition_id="condition-1",
        held_token_id="token-yes",
        opposite_token_id="token-no",
        outcome="Yes",
        opposite_outcome="No",
        position_size=10,
        current_value=5,
        observed_at=NOW,
    )


def _market_payload() -> PolymarketMarketPayload:
    return PolymarketMarketPayload(
        condition_id="condition-1",
        title="Question?",
        active=True,
        closed=False,
        archived=False,
        enable_order_book=True,
        tokens=[
            MarketTokenPayload(token_id="token-yes", outcome="Yes", outcome_index=0),
            MarketTokenPayload(token_id="token-no", outcome="No", outcome_index=1),
        ],
        raw_payload={"conditionId": "condition-1"},
    )
