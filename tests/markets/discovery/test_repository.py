from datetime import UTC, datetime

import pytest
from pydantic import ValidationError
from sqlalchemy import select

from polymarket_market_discovery.core.db.models import (
    MarketDiscoveryObservation,
    MarketDiscoveryRun,
)
from polymarket_market_discovery.core.time import ensure_utc
from polymarket_market_discovery.discovery import repository
from polymarket_market_discovery.discovery.domain import (
    DiscoveryEvidenceEnvelope,
    DiscoveryEvidenceItem,
    MarketDiscoveryObservationPayload,
    StrategyDiscoveryResult,
)


NOW = datetime(2026, 8, 10, tzinfo=UTC)


def test_discovery_persists_strategy_market_observations(
    monkeypatch, sqlite_database
) -> None:
    _, session_factory, test_session = sqlite_database
    monkeypatch.setattr(repository, "database_session", test_session)

    for run_id in ("run-1", "run-2"):
        repository.create_discovery_run(
            run_id=run_id,
            started_at=NOW,
        )
        results = [_result("strategy-one"), _result("strategy-two")]
        for result in results:
            repository.start_strategy(
                run_id=run_id,
                strategy=result.strategy,
                version=result.strategy_version,
                started_at=NOW,
            )
            repository.complete_strategy(
                run_id=run_id,
                strategy=result.strategy,
                finished_at=NOW,
            )
        repository.complete_discovery_run(
            run_id=run_id, results=results, finished_at=NOW
        )

    with session_factory() as session:
        observations = list(session.scalars(select(MarketDiscoveryObservation)))
        runs = list(session.scalars(select(MarketDiscoveryRun)))

    assert len(runs) == 2
    assert len(observations) == 4
    assert {row.condition_id for row in observations} == {"condition-1"}
    assert {row.discovery_run_id for row in observations} == {"run-1", "run-2"}
    assert {row.strategy for row in observations} == {
        "strategy-one",
        "strategy-two",
    }
    assert {row.strategy_version for row in observations} == {"v1"}
    assert {
        row.evidence_json["items"][0]["data"]["marker"] for row in observations
    } == {
        "strategy-one",
        "strategy-two",
    }
    for run in runs:
        assert run.status == "completed"
        assert run.finished_at is not None
        assert ensure_utc(run.finished_at) == NOW
        assert run.strategies == ["strategy-one", "strategy-two"]
        assert {entry["version"] for entry in run.strategy_log} == {"v1"}
        assert {entry["status"] for entry in run.strategy_log} == {"completed"}
        assert run.observation_count == 2
        assert run.discovered_market_count == 1


def test_discovery_failure_finishes_run_and_strategy(
    monkeypatch, sqlite_database
) -> None:
    _, session_factory, test_session = sqlite_database
    monkeypatch.setattr(repository, "database_session", test_session)
    repository.create_discovery_run(run_id="failed-run", started_at=NOW)
    repository.start_strategy(
        run_id="failed-run",
        strategy="strategy",
        version="v1",
        started_at=NOW,
    )

    repository.fail_discovery_run(
        run_id="failed-run",
        strategy="strategy",
        finished_at=NOW,
        error_message="discovery failed",
    )

    with session_factory() as session:
        run = session.get(MarketDiscoveryRun, "failed-run")

    assert run is not None
    assert run.status == "failed"
    assert run.finished_at is not None
    assert ensure_utc(run.finished_at) == NOW
    assert run.error_message == "discovery failed"
    assert run.strategy_log[0]["status"] == "failed"
    assert run.strategy_log[0]["error_message"] == "discovery failed"


def test_strategy_result_rejects_duplicate_market_observations() -> None:
    observation = _observation("strategy")

    with pytest.raises(ValidationError, match="duplicate market observations"):
        StrategyDiscoveryResult(
            strategy="strategy",
            strategy_version="v1",
            observations=[observation, observation.model_copy()],
            generated_at=NOW,
        )


def _result(strategy: str) -> StrategyDiscoveryResult:
    return StrategyDiscoveryResult(
        strategy=strategy,
        strategy_version="v1",
        observations=[_observation(strategy)],
        generated_at=NOW,
    )


def _observation(strategy: str) -> MarketDiscoveryObservationPayload:
    return MarketDiscoveryObservationPayload(
        condition_id="condition-1",
        observed_at=NOW,
        evidence_json=DiscoveryEvidenceEnvelope(
            items=[
                DiscoveryEvidenceItem(
                    kind="test_evidence",
                    source="test.repository",
                    data={"marker": strategy},
                )
            ]
        ),
    )
