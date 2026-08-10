from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import select, update

from polymarket_market_discovery.core.db.engine import database_session
from polymarket_market_discovery.core.db.models import (
    MarketDiscoveryObservation,
    MarketDiscoveryRun,
    MarketDiscoveryStrategyRun,
    WhaleSnapshot,
)
from polymarket_market_discovery.core.time import ensure_utc
from polymarket_market_discovery.markets.domain import StrategyDiscoveryResult


def create_discovery_run(
    *,
    run_id: str,
    started_at: datetime,
    strategies: list[tuple[str, str, dict[str, Any]]],
) -> None:
    with database_session() as session:
        session.add(
            MarketDiscoveryRun(
                run_id=run_id,
                status="running",
                started_at=ensure_utc(started_at),
                strategies=[name for name, _, _ in strategies],
                config_json={name: config for name, _, config in strategies},
            )
        )
        session.add_all(
            [
                MarketDiscoveryStrategyRun(
                    discovery_run_id=run_id,
                    strategy=name,
                    strategy_version=version,
                    status="pending",
                    config_json=config,
                )
                for name, version, config in strategies
            ]
        )
        session.commit()


def start_strategy_run(*, run_id: str, strategy: str, started_at: datetime) -> None:
    with database_session() as session:
        session.execute(
            update(MarketDiscoveryStrategyRun)
            .where(
                MarketDiscoveryStrategyRun.discovery_run_id == run_id,
                MarketDiscoveryStrategyRun.strategy == strategy,
            )
            .values(status="running", started_at=ensure_utc(started_at))
        )
        session.commit()


def complete_strategy_run(
    *,
    run_id: str,
    result: StrategyDiscoveryResult,
    finished_at: datetime,
) -> None:
    with database_session() as session:
        session.execute(
            update(MarketDiscoveryStrategyRun)
            .where(
                MarketDiscoveryStrategyRun.discovery_run_id == run_id,
                MarketDiscoveryStrategyRun.strategy == result.strategy,
            )
            .values(
                status="completed",
                finished_at=ensure_utc(finished_at),
                checked_count=result.checked_count,
                observation_count=len(result.observations),
            )
        )
        session.commit()


def complete_discovery_run(
    *,
    run_id: str,
    results: list[StrategyDiscoveryResult],
    finished_at: datetime,
) -> None:
    with database_session() as session:
        strategy_rows = {
            row.strategy: row
            for row in session.scalars(
                select(MarketDiscoveryStrategyRun).where(
                    MarketDiscoveryStrategyRun.discovery_run_id == run_id
                )
            )
        }
        for result in results:
            strategy_row = strategy_rows[result.strategy]
            whale_ids: dict[str, int] = {}
            for whale in result.whales:
                row = WhaleSnapshot(
                    strategy_run_id=strategy_row.id,
                    proxy_wallet=whale.proxy_wallet,
                    pnl_rank=whale.pnl_rank,
                    volume_rank=whale.volume_rank,
                    pnl=whale.pnl,
                    volume=whale.volume,
                    observed_at=ensure_utc(whale.observed_at),
                    raw_payload=whale.raw_payload,
                )
                session.add(row)
                session.flush()
                whale_ids[whale.proxy_wallet] = row.id

            for observation in result.observations:
                session.add(
                    MarketDiscoveryObservation(
                        strategy_run_id=strategy_row.id,
                        whale_snapshot_id=(
                            whale_ids.get(observation.proxy_wallet)
                            if observation.proxy_wallet is not None
                            else None
                        ),
                        condition_id=observation.condition_id,
                        held_token_id=observation.held_token_id,
                        opposite_token_id=observation.opposite_token_id,
                        outcome=observation.outcome,
                        opposite_outcome=observation.opposite_outcome,
                        position_size=observation.position_size,
                        current_value=observation.current_value,
                        title=observation.title,
                        slug=observation.slug,
                        event_id=observation.event_id,
                        event_slug=observation.event_slug,
                        end_date=observation.end_date,
                        observed_at=ensure_utc(observation.observed_at),
                        evidence_json=observation.evidence_json,
                        raw_payload=observation.raw_payload,
                    )
                )

        run = session.get(MarketDiscoveryRun, run_id)
        if run is None:
            raise ValueError(f"Unknown discovery run: {run_id}")
        run.status = "completed"
        run.finished_at = ensure_utc(finished_at)
        run.checked_wallet_count = sum(result.checked_count for result in results)
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
        if strategy is not None:
            session.execute(
                update(MarketDiscoveryStrategyRun)
                .where(
                    MarketDiscoveryStrategyRun.discovery_run_id == run_id,
                    MarketDiscoveryStrategyRun.strategy == strategy,
                )
                .values(
                    status="failed",
                    finished_at=finished_at,
                    error_message=error_message,
                )
            )
        session.execute(
            update(MarketDiscoveryStrategyRun)
            .where(
                MarketDiscoveryStrategyRun.discovery_run_id == run_id,
                MarketDiscoveryStrategyRun.status == "pending",
            )
            .values(status="skipped", finished_at=finished_at)
        )
        session.execute(
            update(MarketDiscoveryRun)
            .where(MarketDiscoveryRun.run_id == run_id)
            .values(
                status="failed",
                finished_at=finished_at,
                error_message=error_message,
            )
        )
        session.commit()
