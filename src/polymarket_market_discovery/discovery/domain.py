from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, Field


class MarketDiscoveryObservationPayload(BaseModel):
    proxy_wallet: str | None = None
    condition_id: str
    held_token_id: str
    opposite_token_id: str
    outcome: str
    opposite_outcome: str
    position_size: Decimal
    current_value: Decimal
    title: str | None = None
    slug: str | None = None
    event_id: str | None = None
    event_slug: str | None = None
    end_date: datetime | None = None
    observed_at: datetime
    evidence_json: dict[str, Any] = Field(default_factory=dict)
    raw_payload: dict[str, Any] = Field(default_factory=dict)


class StrategyDiscoveryResult(BaseModel):
    strategy: str
    strategy_version: str
    observations: list[MarketDiscoveryObservationPayload] = Field(default_factory=list)
    generated_at: datetime

    @property
    def market_count(self) -> int:
        return len({item.condition_id for item in self.observations})


class StrategyExecutionLogEntry(BaseModel):
    strategy: str
    version: str
    status: Literal["running", "completed", "failed"]
    started_at: datetime
    finished_at: datetime | None = None
    error_message: str | None = None


class DiscoveryRunResult(BaseModel):
    run_id: str | None
    status: Literal["completed", "failed", "skipped"]
    strategies: list[str] = Field(default_factory=list)
    observation_count: int = 0
    discovered_market_count: int = 0
    generated_at: datetime
    skip_reason: str | None = None


__all__ = [
    "DiscoveryRunResult",
    "MarketDiscoveryObservationPayload",
    "StrategyDiscoveryResult",
    "StrategyExecutionLogEntry",
]
