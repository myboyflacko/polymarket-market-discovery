import asyncio
from contextlib import contextmanager
from datetime import UTC, datetime

import pytest

from polymarket_market_discovery.markets import service
from polymarket_market_discovery.markets.repository import MarketSyncInput


NOW = datetime(2026, 8, 10, tzinfo=UTC)


@contextmanager
def acquired_lock():
    yield True


def test_parse_gamma_market_keeps_status_and_both_tokens() -> None:
    market = service.parse_gamma_market(
        {
            "conditionId": "condition-1",
            "question": "Question?",
            "endDate": "2026-12-31T00:00:00Z",
            "active": True,
            "closed": False,
            "archived": False,
            "enableOrderBook": True,
            "clobTokenIds": '["yes", "no"]',
            "outcomes": '["Yes", "No"]',
        }
    )

    assert market.active is True
    assert market.closed is False
    assert market.enable_order_book is True
    assert [(token.token_id, token.outcome) for token in market.tokens] == [
        ("yes", "Yes"),
        ("no", "No"),
    ]


def test_registry_fails_if_gamma_omits_a_market(monkeypatch) -> None:
    requested_closed_filters: list[bool] = []

    class EmptyClient:
        async def get_gamma_markets(self, condition_ids, *, closed):
            requested_closed_filters.append(closed)
            return []

    monkeypatch.setattr(service, "pipeline_lock", acquired_lock)
    monkeypatch.setattr(service, "recover_orphaned_runs", lambda **kwargs: None)
    monkeypatch.setattr(
        service,
        "get_market_sync_input",
        lambda: MarketSyncInput(["discovery-1"], ["condition-1"]),
    )
    monkeypatch.setattr(service, "create_market_sync_run", lambda **kwargs: None)
    monkeypatch.setattr(service, "get_polymarket_client", lambda: EmptyClient())
    failures: list[str] = []
    monkeypatch.setattr(
        service,
        "fail_market_sync_run",
        lambda **kwargs: failures.append(kwargs["error_message"]),
    )

    with pytest.raises(ValueError, match="Gamma omitted"):
        asyncio.run(service.MarketRegistryService().run(now=NOW))

    assert failures == ["Gamma omitted requested markets: condition-1"]
    assert requested_closed_filters == [False, True]
