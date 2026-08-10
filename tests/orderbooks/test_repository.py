from datetime import UTC, datetime

from sqlalchemy import select

from polymarket_market_discovery.core.db.models import (
    OrderbookCollectionItem,
    OrderbookCollectionRun,
    PolymarketMarket,
    PolymarketToken,
)
from polymarket_market_discovery.orderbooks import repository


NOW = datetime(2026, 8, 10, tzinfo=UTC)


def test_snapshot_selects_both_tokens_of_accumulated_active_markets(
    monkeypatch, sqlite_database
) -> None:
    _, session_factory, test_session = sqlite_database
    monkeypatch.setattr(repository, "database_session", test_session)
    with session_factory() as session:
        session.add_all(
            [
                _market(
                    "active", active=True, closed=False, archived=False, enabled=True
                ),
                _market(
                    "closed", active=False, closed=True, archived=False, enabled=True
                ),
            ]
        )
        session.add_all(
            [
                _token("active-yes", "active", "Yes", 0),
                _token("active-no", "active", "No", 1),
                _token("closed-yes", "closed", "Yes", 0),
                _token("closed-no", "closed", "No", 1),
            ]
        )
        session.commit()

    repository.create_orderbook_collection_run(
        run_id="orderbooks-1", started_at=NOW, config_json={}
    )
    items = repository.snapshot_collectable_markets(
        run_id="orderbooks-1", selected_at=NOW
    )

    with session_factory() as session:
        stored_items = list(session.scalars(select(OrderbookCollectionItem)))
        run = session.get(OrderbookCollectionRun, "orderbooks-1")

    assert [item.token_id for item in items] == ["active-yes", "active-no"]
    assert len(stored_items) == 2
    assert run is not None and run.selected_market_count == 1
    assert run.selected_token_count == 2


def _market(
    condition_id: str,
    *,
    active: bool,
    closed: bool,
    archived: bool,
    enabled: bool,
) -> PolymarketMarket:
    return PolymarketMarket(
        condition_id=condition_id,
        active=active,
        closed=closed,
        archived=archived,
        enable_order_book=enabled,
        first_discovered_at=NOW,
        last_discovered_at=NOW,
        status_checked_at=NOW,
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
