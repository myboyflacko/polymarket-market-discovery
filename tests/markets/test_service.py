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


def _gamma_row(
    condition_id: str, *, question: str = "Question?"
) -> dict[str, object]:
    return {
        "conditionId": condition_id,
        "question": question,
        "active": True,
        "closed": False,
        "archived": False,
        "enableOrderBook": True,
        "clobTokenIds": [f"{condition_id}-yes", f"{condition_id}-no"],
        "outcomes": ["Yes", "No"],
    }


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


@pytest.mark.parametrize(
    "row",
    [
        {"clobTokenIds": ["yes", "no"], "outcomes": ["Yes", "No"]},
        {
            "conditionId": "condition-1",
            "clobTokenIds": ["yes"],
            "outcomes": ["Yes"],
        },
        {
            "conditionId": "condition-1",
            "clobTokenIds": ["same", "same"],
            "outcomes": ["Yes", "No"],
        },
        {
            "conditionId": "condition-1",
            "clobTokenIds": "not-json",
            "outcomes": ["Yes", "No"],
        },
    ],
)
def test_parse_gamma_market_rejects_malformed_contract(
    row: dict[str, object]
) -> None:
    with pytest.raises(ValueError):
        service.parse_gamma_market(row)


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


def test_registry_skips_true_idle_without_creating_a_run(monkeypatch) -> None:
    monkeypatch.setattr(service, "pipeline_lock", acquired_lock)
    monkeypatch.setattr(service, "recover_orphaned_runs", lambda **kwargs: None)
    monkeypatch.setattr(
        service,
        "get_market_sync_input",
        lambda: MarketSyncInput(discovery_run_ids=[], condition_ids=[]),
    )

    def unexpected_create(**kwargs) -> None:
        raise AssertionError("idle sync must not create a run")

    monkeypatch.setattr(service, "create_market_sync_run", unexpected_create)

    result = asyncio.run(service.MarketRegistryService().run(now=NOW))

    assert result.status == "skipped"
    assert result.run_id is None
    assert result.skip_reason == "no_markets_to_sync"


@pytest.mark.parametrize(
    ("gamma_rows", "error"),
    [
        ([_gamma_row("unexpected")], "Gamma returned unexpected markets: unexpected"),
        (
            [_gamma_row("condition-1"), _gamma_row("condition-1")],
            "Gamma returned duplicate market condition-1",
        ),
        (
            [
                _gamma_row("condition-1", question="First?"),
                _gamma_row("condition-1", question="Conflicting?"),
            ],
            "Gamma returned conflicting market condition-1",
        ),
    ],
)
def test_registry_rejects_unexpected_duplicate_or_conflicting_gamma_markets(
    monkeypatch, gamma_rows: list[dict[str, object]], error: str
) -> None:
    class FakeClient:
        async def get_gamma_markets(self, condition_ids, *, closed):
            return gamma_rows if not closed else []

    monkeypatch.setattr(service, "pipeline_lock", acquired_lock)
    monkeypatch.setattr(service, "recover_orphaned_runs", lambda **kwargs: None)
    monkeypatch.setattr(
        service,
        "get_market_sync_input",
        lambda: MarketSyncInput(["discovery-1"], ["condition-1"]),
    )
    monkeypatch.setattr(service, "create_market_sync_run", lambda **kwargs: None)
    monkeypatch.setattr(service, "get_polymarket_client", lambda: FakeClient())
    monkeypatch.setattr(
        service,
        "complete_market_sync_run",
        lambda **kwargs: pytest.fail("invalid payloads must not be persisted"),
    )
    failures: list[str] = []
    monkeypatch.setattr(
        service,
        "fail_market_sync_run",
        lambda **kwargs: failures.append(kwargs["error_message"]),
    )

    with pytest.raises(ValueError, match=error):
        asyncio.run(service.MarketRegistryService().run(now=NOW))

    assert failures == [error]
