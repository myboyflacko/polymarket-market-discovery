from datetime import UTC, datetime

import pytest
from sqlalchemy import select

from polymarket_market_discovery.core.db.models import (
    MarketDiscoveryObservation,
    MarketDiscoveryRun,
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
        session.add_all(
            [
                _observation("discovery-1", "strategy-one"),
                _observation("discovery-1", "strategy-two"),
            ]
        )
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
    assert not hasattr(tokens[0], "raw_latest_payload")
    assert len(snapshots) == 1
    assert snapshots[0].raw_payload == {"conditionId": "condition-1"}
    assert discovery is not None and discovery.registry_synced_at is not None
    assert sync is not None and sync.status == "completed"
    assert sync.checked_market_count == 1
    assert sync.created_market_count == 1
    assert sync.updated_market_count == 0

    refresh_input = repository.get_market_sync_input()
    assert refresh_input.discovery_run_ids == []
    assert refresh_input.condition_ids == ["condition-1"]


@pytest.mark.parametrize(
    ("closed", "archived"), [(True, False), (False, True), (True, True)]
)
def test_terminal_markets_are_not_refreshed(
    monkeypatch, sqlite_database, closed: bool, archived: bool
) -> None:
    _, session_factory, test_session = sqlite_database
    monkeypatch.setattr(repository, "database_session", test_session)
    with session_factory() as session:
        session.add(
            PolymarketMarket(
                condition_id="terminal",
                active=False,
                closed=closed,
                archived=archived,
                enable_order_book=False,
                first_discovered_at=NOW,
                last_discovered_at=NOW,
                status_checked_at=NOW,
            )
        )
        session.commit()

    assert repository.get_market_sync_input().condition_ids == []


def test_inactive_or_orderbook_disabled_markets_are_still_refreshed(
    monkeypatch, sqlite_database
) -> None:
    _, session_factory, test_session = sqlite_database
    monkeypatch.setattr(repository, "database_session", test_session)
    with session_factory() as session:
        session.add(
            PolymarketMarket(
                condition_id="non-terminal",
                active=False,
                closed=False,
                archived=False,
                enable_order_book=False,
                first_discovered_at=NOW,
                last_discovered_at=NOW,
                status_checked_at=NOW,
            )
        )
        session.commit()

    assert repository.get_market_sync_input().condition_ids == ["non-terminal"]


def test_empty_discovery_run_completes_once_with_zero_counts(
    monkeypatch, sqlite_database
) -> None:
    _, session_factory, test_session = sqlite_database
    monkeypatch.setattr(repository, "database_session", test_session)
    with session_factory() as session:
        session.add(
            MarketDiscoveryRun(
                run_id="empty-discovery",
                status="completed",
                started_at=NOW,
                finished_at=NOW,
                strategies=["strategy"],
            )
        )
        session.commit()

    sync_input = repository.get_market_sync_input()
    assert sync_input.discovery_run_ids == ["empty-discovery"]
    assert sync_input.condition_ids == []
    repository.create_market_sync_run(
        run_id="empty-sync",
        started_at=NOW,
        input_discovery_run_ids=sync_input.discovery_run_ids,
    )
    assert repository.complete_market_sync_run(
        run_id="empty-sync",
        payloads=[],
        discovery_run_ids=sync_input.discovery_run_ids,
        checked_at=NOW,
    ) == (0, 0)

    with session_factory() as session:
        discovery = session.get(MarketDiscoveryRun, "empty-discovery")
        sync = session.get(MarketRegistrySyncRun, "empty-sync")
    assert discovery is not None and discovery.registry_synced_at is not None
    assert sync is not None and sync.status == "completed"
    assert sync.checked_market_count == 0
    assert sync.created_market_count == 0
    assert sync.updated_market_count == 0


@pytest.mark.parametrize(
    ("tokens", "error"),
    [
        (
            [
                MarketTokenPayload(
                    token_id="replacement", outcome="Yes", outcome_index=0
                ),
                MarketTokenPayload(token_id="token-no", outcome="No", outcome_index=1),
            ],
            "Token set changed for market condition-1",
        ),
        (
            [
                MarketTokenPayload(
                    token_id="token-yes", outcome="Changed", outcome_index=0
                ),
                MarketTokenPayload(token_id="token-no", outcome="No", outcome_index=1),
            ],
            "Token token-yes outcome changed",
        ),
        (
            [
                MarketTokenPayload(token_id="token-yes", outcome="Yes", outcome_index=1),
                MarketTokenPayload(token_id="token-no", outcome="No", outcome_index=0),
            ],
            "Token token-yes outcome index changed",
        ),
    ],
)
def test_token_invariant_failure_rolls_back_all_registry_changes(
    monkeypatch,
    sqlite_database,
    tokens: list[MarketTokenPayload],
    error: str,
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
        session.add(_observation("discovery-1", "strategy"))
        session.add(
            PolymarketMarket(
                condition_id="condition-1",
                title="Original",
                active=True,
                closed=False,
                archived=False,
                enable_order_book=True,
                first_discovered_at=NOW,
                last_discovered_at=NOW,
                status_checked_at=NOW,
                raw_latest_payload={"version": "original"},
            )
        )
        session.add_all(
            [
                PolymarketToken(
                    token_id="token-yes",
                    condition_id="condition-1",
                    outcome="Yes",
                    outcome_index=0,
                    first_seen_at=NOW,
                    last_seen_at=NOW,
                ),
                PolymarketToken(
                    token_id="token-no",
                    condition_id="condition-1",
                    outcome="No",
                    outcome_index=1,
                    first_seen_at=NOW,
                    last_seen_at=NOW,
                ),
            ]
        )
        session.commit()
    repository.create_market_sync_run(
        run_id="markets-1",
        started_at=NOW,
        input_discovery_run_ids=["discovery-1"],
    )

    changed_payload = _market_payload().model_copy(
        update={
            "title": "Changed",
            "tokens": tokens,
            "raw_payload": {"version": "changed"},
        }
    )
    with pytest.raises(ValueError, match=error):
        repository.complete_market_sync_run(
            run_id="markets-1",
            payloads=[changed_payload],
            discovery_run_ids=["discovery-1"],
            checked_at=NOW,
        )

    with session_factory() as session:
        market = session.get(PolymarketMarket, "condition-1")
        discovery = session.get(MarketDiscoveryRun, "discovery-1")
        sync = session.get(MarketRegistrySyncRun, "markets-1")
        snapshots = list(session.scalars(select(MarketStatusSnapshot)))
        stored_tokens = list(
            session.scalars(
                select(PolymarketToken).order_by(PolymarketToken.outcome_index)
            )
        )
    assert market is not None and market.title == "Original"
    assert market.raw_latest_payload == {"version": "original"}
    assert discovery is not None and discovery.registry_synced_at is None
    assert sync is not None and sync.status == "running"
    assert snapshots == []
    assert [(token.token_id, token.outcome, token.outcome_index) for token in stored_tokens] == [
        ("token-yes", "Yes", 0),
        ("token-no", "No", 1),
    ]


def test_existing_token_cannot_be_reassigned_to_a_new_market(
    monkeypatch, sqlite_database
) -> None:
    _, session_factory, test_session = sqlite_database
    monkeypatch.setattr(repository, "database_session", test_session)
    with session_factory() as session:
        session.add(
            MarketDiscoveryRun(
                run_id="discovery-new",
                status="completed",
                started_at=NOW,
                finished_at=NOW,
                strategies=["strategy"],
            )
        )
        observation = _observation("discovery-new", "strategy")
        observation.condition_id = "new-condition"
        session.add(observation)
        session.add(
            PolymarketMarket(
                condition_id="old-condition",
                active=False,
                closed=True,
                archived=False,
                enable_order_book=False,
                first_discovered_at=NOW,
                last_discovered_at=NOW,
                status_checked_at=NOW,
            )
        )
        session.add_all(
            [
                PolymarketToken(
                    token_id="shared-token",
                    condition_id="old-condition",
                    outcome="Yes",
                    outcome_index=0,
                    first_seen_at=NOW,
                    last_seen_at=NOW,
                ),
                PolymarketToken(
                    token_id="old-no",
                    condition_id="old-condition",
                    outcome="No",
                    outcome_index=1,
                    first_seen_at=NOW,
                    last_seen_at=NOW,
                ),
            ]
        )
        session.commit()
    repository.create_market_sync_run(
        run_id="markets-new",
        started_at=NOW,
        input_discovery_run_ids=["discovery-new"],
    )
    payload = PolymarketMarketPayload(
        condition_id="new-condition",
        tokens=[
            MarketTokenPayload(
                token_id="shared-token", outcome="Yes", outcome_index=0
            ),
            MarketTokenPayload(token_id="new-no", outcome="No", outcome_index=1),
        ],
    )

    with pytest.raises(ValueError, match="Token shared-token condition changed"):
        repository.complete_market_sync_run(
            run_id="markets-new",
            payloads=[payload],
            discovery_run_ids=["discovery-new"],
            checked_at=NOW,
        )

    with session_factory() as session:
        assert session.get(PolymarketMarket, "new-condition") is None
        old_token = session.get(PolymarketToken, "shared-token")
        discovery = session.get(MarketDiscoveryRun, "discovery-new")
    assert old_token is not None and old_token.condition_id == "old-condition"
    assert discovery is not None and discovery.registry_synced_at is None


def _observation(discovery_run_id: str, strategy: str) -> MarketDiscoveryObservation:
    return MarketDiscoveryObservation(
        discovery_run_id=discovery_run_id,
        strategy=strategy,
        strategy_version="v1",
        condition_id="condition-1",
        observed_at=NOW,
        evidence_json={
            "schema_version": 1,
            "items": [
                {
                    "kind": "test_evidence",
                    "source": "test.market_repository",
                    "data": {},
                }
            ],
        },
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
