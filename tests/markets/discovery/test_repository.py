from datetime import UTC, datetime

from sqlalchemy import select

from polymarket_market_discovery.core.db.models import (
    MarketDiscoveryObservation,
    MarketDiscoveryRun,
    WhaleSnapshot,
)
from polymarket_market_discovery.markets.discovery import repository
from polymarket_market_discovery.markets.domain import (
    MarketDiscoveryObservationPayload,
    StrategyDiscoveryResult,
    WhaleSnapshotPayload,
)


NOW = datetime(2026, 8, 10, tzinfo=UTC)
WALLET = "0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"


def test_discovery_persists_append_only_whales_and_positions(
    monkeypatch, sqlite_database
) -> None:
    _, session_factory, test_session = sqlite_database
    monkeypatch.setattr(repository, "database_session", test_session)

    for run_id in ("run-1", "run-2"):
        repository.create_discovery_run(
            run_id=run_id,
            started_at=NOW,
            strategies=[("strategy", "v1", {})],
        )
        result = _result()
        repository.start_strategy_run(
            run_id=run_id, strategy="strategy", started_at=NOW
        )
        repository.complete_strategy_run(run_id=run_id, result=result, finished_at=NOW)
        repository.complete_discovery_run(
            run_id=run_id, results=[result], finished_at=NOW
        )

    with session_factory() as session:
        whales = list(session.scalars(select(WhaleSnapshot)))
        observations = list(session.scalars(select(MarketDiscoveryObservation)))
        runs = list(session.scalars(select(MarketDiscoveryRun)))

    assert len(runs) == 2
    assert len(whales) == 2
    assert len(observations) == 4
    assert {row.condition_id for row in observations} == {"condition-1"}


def _result() -> StrategyDiscoveryResult:
    whale = WhaleSnapshotPayload(
        proxy_wallet=WALLET,
        pnl_rank=1,
        volume_rank=2,
        pnl=100,
        volume=200,
        observed_at=NOW,
    )
    observation = MarketDiscoveryObservationPayload(
        proxy_wallet=WALLET,
        condition_id="condition-1",
        held_token_id="token-yes",
        opposite_token_id="token-no",
        outcome="Yes",
        opposite_outcome="No",
        position_size=10,
        current_value=5,
        observed_at=NOW,
    )
    return StrategyDiscoveryResult(
        strategy="strategy",
        strategy_version="v1",
        whales=[whale],
        observations=[observation, observation.model_copy()],
        checked_count=1,
        generated_at=NOW,
    )
