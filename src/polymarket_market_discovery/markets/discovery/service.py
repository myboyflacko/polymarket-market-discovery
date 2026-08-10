from __future__ import annotations

from datetime import UTC, datetime

from polymarket_market_discovery.core.db.lock import pipeline_lock
from polymarket_market_discovery.core.db.recovery import recover_orphaned_runs
from polymarket_market_discovery.core.time import ensure_utc
from polymarket_market_discovery.markets.discovery.repository import (
    complete_discovery_run,
    complete_strategy_run,
    create_discovery_run,
    fail_discovery_run,
    start_strategy_run,
)
from polymarket_market_discovery.markets.domain import (
    DiscoveryRunResult,
    MarketDiscoveryStrategy,
    StrategyDiscoveryResult,
)
from polymarket_market_discovery.polymarket.client import get_polymarket_client


class MarketDiscoveryService:
    def __init__(self, *, strategies: list[MarketDiscoveryStrategy]) -> None:
        if not strategies:
            raise ValueError("At least one discovery strategy is required")
        self.strategies = strategies

    async def run(self, *, now: datetime | None = None) -> DiscoveryRunResult:
        started_at = ensure_utc(now or datetime.now(UTC))
        with pipeline_lock() as acquired:
            if not acquired:
                return DiscoveryRunResult(
                    run_id=None,
                    status="skipped",
                    strategies=[strategy.name for strategy in self.strategies],
                    generated_at=started_at,
                    skip_reason="pipeline_locked",
                )
            recover_orphaned_runs(recovered_at=started_at)
            return await self._run_locked(started_at=started_at)

    async def _run_locked(self, *, started_at: datetime) -> DiscoveryRunResult:
        run_id = _build_run_id(started_at)
        create_discovery_run(
            run_id=run_id,
            started_at=started_at,
            strategies=[
                (strategy.name, strategy.version, strategy.config())
                for strategy in self.strategies
            ],
        )
        results: list[StrategyDiscoveryResult] = []
        current_strategy: str | None = None
        try:
            client = get_polymarket_client()
            for strategy in self.strategies:
                current_strategy = strategy.name
                strategy_started_at = datetime.now(UTC)
                start_strategy_run(
                    run_id=run_id,
                    strategy=strategy.name,
                    started_at=strategy_started_at,
                )
                result = await strategy.discover(
                    client=client,
                    generated_at=started_at,
                )
                if result.strategy != strategy.name:
                    raise ValueError(
                        "Strategy result name does not match registered strategy"
                    )
                complete_strategy_run(
                    run_id=run_id,
                    result=result,
                    finished_at=datetime.now(UTC),
                )
                results.append(result)

            complete_discovery_run(
                run_id=run_id,
                results=results,
                finished_at=datetime.now(UTC),
            )
        except Exception as exc:
            fail_discovery_run(
                run_id=run_id,
                strategy=current_strategy,
                finished_at=datetime.now(UTC),
                error_message=str(exc),
            )
            raise

        return DiscoveryRunResult(
            run_id=run_id,
            status="completed",
            strategies=[result.strategy for result in results],
            checked_wallet_count=sum(result.checked_count for result in results),
            observation_count=sum(len(result.observations) for result in results),
            discovered_market_count=len(
                {
                    observation.condition_id
                    for result in results
                    for observation in result.observations
                }
            ),
            generated_at=started_at,
        )


def _build_run_id(generated_at: datetime) -> str:
    return f"{generated_at.strftime('%Y%m%dT%H%M%S%fZ')}-discovery"
