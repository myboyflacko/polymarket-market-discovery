from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from sqlalchemy.orm import Session

from polymarket_market_discovery.core.db.engine import database_session
from polymarket_market_discovery.core.db.models import (
    MarketDiscoveryObservation,
    MarketDiscoveryRun,
)
from polymarket_market_discovery.core.time import ensure_utc
from polymarket_market_discovery.discovery.domain import (
    StrategyDiscoveryResult,
    StrategyExecutionLogEntry,
)


def create_discovery_run(*, run_id: str, started_at: datetime) -> None:
    with database_session() as session:
        session.add(
            MarketDiscoveryRun(
                run_id=run_id,
                status="running",
                started_at=ensure_utc(started_at),
                strategies=[],
                strategy_log=[],
            )
        )
        session.commit()


def start_strategy(
    *,
    run_id: str,
    strategy: str,
    version: str,
    started_at: datetime,
) -> None:
    started_at = ensure_utc(started_at)
    with database_session() as session:
        run = _get_run(session=session, run_id=run_id)
        if strategy in run.strategies:
            raise ValueError(f"Strategy already started for run {run_id}: {strategy}")
        run.strategies = [*run.strategies, strategy]
        entry = StrategyExecutionLogEntry(
            strategy=strategy,
            version=version,
            status="running",
            started_at=started_at,
        )
        run.strategy_log = [*run.strategy_log, entry.model_dump(mode="json")]
        session.commit()


def complete_strategy(
    *,
    run_id: str,
    strategy: str,
    finished_at: datetime,
) -> None:
    with database_session() as session:
        run = _get_run(session=session, run_id=run_id)
        run.strategy_log = _finish_strategy_log_entry(
            strategy_log=run.strategy_log,
            strategy=strategy,
            status="completed",
            finished_at=finished_at,
        )
        session.commit()


def complete_discovery_run(
    *,
    run_id: str,
    results: list[StrategyDiscoveryResult],
    finished_at: datetime,
) -> None:
    with database_session() as session:
        run = _get_run(session=session, run_id=run_id)
        for result in results:
            for observation in result.observations:
                session.add(
                    MarketDiscoveryObservation(
                        discovery_run_id=run_id,
                        strategy=result.strategy,
                        strategy_version=result.strategy_version,
                        condition_id=observation.condition_id,
                        observed_at=ensure_utc(observation.observed_at),
                        evidence_json=observation.evidence_json.model_dump(mode="json"),
                    )
                )

        run.status = "completed"
        run.finished_at = ensure_utc(finished_at)
        run.observation_count = sum(len(result.observations) for result in results)
        run.discovered_market_count = len(
            {
                observation.condition_id
                for result in results
                for observation in result.observations
            }
        )
        session.commit()


def fail_discovery_run(
    *,
    run_id: str,
    strategy: str | None,
    finished_at: datetime,
    error_message: str,
) -> None:
    finished_at = ensure_utc(finished_at)
    with database_session() as session:
        run = _get_run(session=session, run_id=run_id)
        if strategy is not None:
            run.strategy_log = _finish_strategy_log_entry(
                strategy_log=run.strategy_log,
                strategy=strategy,
                status="failed",
                finished_at=finished_at,
                error_message=error_message,
                required=False,
            )
        run.status = "failed"
        run.finished_at = finished_at
        run.error_message = error_message
        session.commit()


def _get_run(*, session: Session, run_id: str) -> MarketDiscoveryRun:
    run = session.get(MarketDiscoveryRun, run_id)
    if run is None:
        raise ValueError(f"Unknown discovery run: {run_id}")
    return run


def _finish_strategy_log_entry(
    *,
    strategy_log: list[dict[str, Any]],
    strategy: str,
    status: Literal["completed", "failed"],
    finished_at: datetime,
    error_message: str | None = None,
    required: bool = True,
) -> list[dict[str, Any]]:
    updated_log = [dict(item) for item in strategy_log]
    for index in range(len(updated_log) - 1, -1, -1):
        item = updated_log[index]
        if item.get("strategy") == strategy and item.get("status") == "running":
            entry = StrategyExecutionLogEntry.model_validate(
                {
                    **item,
                    "status": status,
                    "finished_at": ensure_utc(finished_at),
                    "error_message": error_message,
                }
            )
            updated_log[index] = entry.model_dump(mode="json")
            return updated_log
    if required:
        raise ValueError(f"No running strategy log for {strategy}")
    return updated_log
