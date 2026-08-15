import asyncio
from contextlib import contextmanager
from datetime import UTC, datetime

from polymarket_market_discovery.orderbooks import service
from polymarket_market_discovery.orderbooks.domain import OrderBookCollectionItemPayload


NOW = datetime(2026, 8, 10, tzinfo=UTC)


@contextmanager
def acquired_lock():
    yield True


@contextmanager
def busy_lock():
    yield False


def test_orderbooks_skip_when_pipeline_is_locked(monkeypatch) -> None:
    monkeypatch.setattr(service, "pipeline_lock", busy_lock)

    result = asyncio.run(service.OrderbookCollectionService().run(now=NOW))

    assert result.status == "skipped"
    assert result.skip_reason == "pipeline_locked"


def test_orderbooks_skip_stale_registry_without_creating_run(monkeypatch) -> None:
    monkeypatch.setattr(service, "pipeline_lock", acquired_lock)
    monkeypatch.setattr(service, "recover_orphaned_runs", lambda **kwargs: None)
    monkeypatch.setattr(
        service, "get_last_successful_market_registry_sync_at",
        lambda: datetime(2026, 8, 9, 23, 29, 59, tzinfo=UTC),
    )
    monkeypatch.setattr(
        service, "create_orderbook_collection_run",
        lambda **kwargs: (_ for _ in ()).throw(AssertionError("must not create run")),
    )
    result = asyncio.run(
        service.OrderbookCollectionService(
            market_registry_max_age_seconds=1800
        ).run(now=NOW)
    )
    assert result.status == "skipped"
    assert result.skip_reason == "stale_market_registry"
    assert result.run_id is None


def test_orderbooks_treat_missing_registry_as_stale(monkeypatch) -> None:
    monkeypatch.setattr(service, "pipeline_lock", acquired_lock)
    monkeypatch.setattr(service, "recover_orphaned_runs", lambda **kwargs: None)
    monkeypatch.setattr(
        service, "get_last_successful_market_registry_sync_at", lambda: None
    )
    result = asyncio.run(service.OrderbookCollectionService().run(now=NOW))
    assert result.skip_reason == "stale_market_registry"


def test_orderbooks_skip_empty_universe_at_freshness_boundary(monkeypatch) -> None:
    monkeypatch.setattr(service, "pipeline_lock", acquired_lock)
    monkeypatch.setattr(service, "recover_orphaned_runs", lambda **kwargs: None)
    monkeypatch.setattr(
        service, "get_last_successful_market_registry_sync_at",
        lambda: datetime(2026, 8, 9, 23, 30, tzinfo=UTC),
    )
    monkeypatch.setattr(service, "has_collectable_markets", lambda: False)
    monkeypatch.setattr(
        service, "create_orderbook_collection_run",
        lambda **kwargs: (_ for _ in ()).throw(AssertionError("must not create run")),
    )
    result = asyncio.run(service.OrderbookCollectionService().run(now=NOW))
    assert result.status == "skipped"
    assert result.skip_reason == "no_collectable_markets"
    assert result.run_id is None


def test_orderbooks_count_each_failed_token(monkeypatch) -> None:
    class FailingClient:
        async def get_order_books(self, params):
            raise RuntimeError("clob unavailable")

    monkeypatch.setattr(service, "pipeline_lock", acquired_lock)
    monkeypatch.setattr(service, "recover_orphaned_runs", lambda **kwargs: None)
    monkeypatch.setattr(
        service, "get_last_successful_market_registry_sync_at", lambda: NOW
    )
    monkeypatch.setattr(service, "has_collectable_markets", lambda: True)
    monkeypatch.setattr(
        service, "create_orderbook_collection_run", lambda **kwargs: None
    )
    monkeypatch.setattr(
        service,
        "snapshot_collectable_markets",
        lambda **kwargs: [_item("yes"), _item("no")],
    )
    monkeypatch.setattr(service, "get_polymarket_client", lambda: FailingClient())
    captured: dict = {}

    def complete(**kwargs):
        captured.update(kwargs)
        return "failed"

    monkeypatch.setattr(service, "complete_orderbook_collection_run", complete)

    result = asyncio.run(service.OrderbookCollectionService(batch_size=50).run(now=NOW))

    assert result.status == "failed"
    assert result.selected_token_count == 2
    assert result.failure_count == 2
    assert captured["errors_by_token"] == {
        "yes": "clob unavailable",
        "no": "clob unavailable",
    }


def _item(token_id: str) -> OrderBookCollectionItemPayload:
    return OrderBookCollectionItemPayload(
        condition_id="condition-1",
        token_id=token_id,
        outcome=token_id.title(),
        market_status_checked_at=NOW,
        selected_at=NOW,
    )
