from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, Field

from polymarket_market_discovery.discovery.domain import DiscoveryRunResult
from polymarket_market_discovery.markets.domain import MarketRegistrySyncResult
from polymarket_market_discovery.orderbooks.domain import OrderBookCollectionResult

logger = logging.getLogger(__name__)

PipelineStatus = Literal["completed", "partial", "failed", "skipped"]
LayerName = Literal["discovery", "markets", "orderbooks"]
LayerTrigger = Literal["manual", "bootstrap", "scheduled", "cascade"]
DiscoveryRunner = Callable[..., Awaitable[DiscoveryRunResult]]
MarketRunner = Callable[..., Awaitable[MarketRegistrySyncResult]]
OrderbookRunner = Callable[..., Awaitable[OrderBookCollectionResult]]
LayerRunner = DiscoveryRunner | MarketRunner | OrderbookRunner
LayerResult = DiscoveryRunResult | MarketRegistrySyncResult | OrderBookCollectionResult
MonotonicClock = Callable[[], float]
WallClock = Callable[[], datetime]
Sleep = Callable[[float], Awaitable[None]]


class PipelineRunResult(BaseModel):
    status: PipelineStatus
    discovery: DiscoveryRunResult | None = None
    markets: MarketRegistrySyncResult | None = None
    orderbooks: OrderBookCollectionResult | None = None
    triggers: dict[LayerName, LayerTrigger] = Field(default_factory=dict)
    errors: dict[LayerName, str] = Field(default_factory=dict)
    generated_at: datetime


class PipelineCoordinator:
    def __init__(
        self,
        *,
        discovery_runner: DiscoveryRunner,
        market_runner: MarketRunner,
        orderbook_runner: OrderbookRunner,
        discovery_interval: int = 900,
        market_interval: int = 900,
        orderbook_interval: int = 300,
        monotonic_clock: MonotonicClock = time.monotonic,
        wall_clock: WallClock | None = None,
        sleep: Sleep = asyncio.sleep,
    ) -> None:
        if min(discovery_interval, market_interval, orderbook_interval) < 1:
            raise ValueError("Pipeline intervals must be greater than zero")
        self._discovery_runner = discovery_runner
        self._market_runner = market_runner
        self._orderbook_runner = orderbook_runner
        self._intervals: dict[LayerName, int] = {
            "discovery": discovery_interval,
            "markets": market_interval,
            "orderbooks": orderbook_interval,
        }
        self._monotonic_clock = monotonic_clock
        self._wall_clock = wall_clock or (lambda: datetime.now(UTC))
        self._sleep = sleep

    async def run_once(self) -> PipelineRunResult:
        return await self._run_cycle(
            due={"discovery", "markets", "orderbooks"},
            default_trigger="manual",
        )

    async def run_forever(self) -> None:
        await self._run_cycle(
            due={"discovery", "markets", "orderbooks"},
            default_trigger="bootstrap",
        )
        started_at = self._monotonic_clock()
        deadlines = {
            layer: started_at + interval
            for layer, interval in self._intervals.items()
        }
        while True:
            await self._sleep(
                max(0.0, min(deadlines.values()) - self._monotonic_clock())
            )
            now = self._monotonic_clock()
            due: set[LayerName] = {
                layer for layer, deadline in deadlines.items() if deadline <= now
            }
            for layer in due:
                deadline = deadlines[layer]
                interval = self._intervals[layer]
                elapsed_intervals = int((now - deadline) // interval) + 1
                deadlines[layer] = deadline + elapsed_intervals * interval
            await self._run_cycle(due=due, default_trigger="scheduled")

    async def _run_cycle(
        self, *, due: set[LayerName], default_trigger: LayerTrigger
    ) -> PipelineRunResult:
        generated_at = self._wall_clock()
        cycle = generated_at.isoformat()
        triggers: dict[LayerName, LayerTrigger] = {
            layer: default_trigger for layer in due
        }
        errors: dict[LayerName, str] = {}
        discovery = markets = orderbooks = None

        if "discovery" in due:
            discovery = await self._run_layer(
                "discovery", self._discovery_runner, generated_at,
                triggers["discovery"], cycle, errors,
            )
            if discovery is not None and discovery.status == "completed":
                if "markets" not in due:
                    triggers["markets"] = "cascade"
                due.add("markets")
        if "markets" in due:
            markets = await self._run_layer(
                "markets", self._market_runner, generated_at,
                triggers["markets"], cycle, errors,
            )
            if markets is not None and markets.status == "completed":
                if "orderbooks" not in due:
                    triggers["orderbooks"] = "cascade"
                due.add("orderbooks")
        if "orderbooks" in due:
            orderbooks = await self._run_layer(
                "orderbooks", self._orderbook_runner, generated_at,
                triggers["orderbooks"], cycle, errors,
            )

        results = [result for result in (discovery, markets, orderbooks) if result]
        pipeline_result = PipelineRunResult(
            status=_aggregate_status(results=results, errors=errors),
            discovery=discovery,
            markets=markets,
            orderbooks=orderbooks,
            triggers=triggers,
            errors=errors,
            generated_at=generated_at,
        )
        logger.info(
            "Pipeline cycle finished",
            extra={"event": "pipeline.cycle.finished", "context": {
                "cycle": cycle, "status": pipeline_result.status,
                "layers": list(triggers),
            }},
        )
        return pipeline_result

    async def _run_layer(
        self, layer: LayerName, runner: LayerRunner, now: datetime,
        trigger: LayerTrigger, cycle: str, errors: dict[LayerName, str],
    ) -> LayerResult | None:
        try:
            result = await runner(now=now)
            logger.info(
                "Pipeline layer finished",
                extra={"event": f"pipeline.layer.{result.status}", "context": {
                    "cycle": cycle, "layer": layer, "trigger": trigger,
                    "status": result.status, "run_id": result.run_id,
                }},
            )
            return result
        except Exception as exc:
            errors[layer] = str(exc)
            logger.exception(
                "Pipeline layer failed",
                extra={"event": "pipeline.layer.failed", "context": {
                    "cycle": cycle, "layer": layer, "trigger": trigger,
                    "status": "failed", "run_id": None, "error": str(exc),
                }},
            )
            return None


def _aggregate_status(
    *, results: list[LayerResult], errors: dict[LayerName, str]
) -> PipelineStatus:
    statuses = [result.status for result in results]
    has_success = "completed" in statuses or "partial" in statuses
    has_failure = bool(errors) or "failed" in statuses or "partial" in statuses
    if has_success and has_failure:
        return "partial"
    if has_failure:
        return "failed"
    if statuses and all(status == "skipped" for status in statuses):
        return "skipped"
    return "completed"
