from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator


class DiscoveryEvidenceItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: str = Field(min_length=1)
    source: str = Field(min_length=1)
    data: dict[str, Any]


class DiscoveryEvidenceEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1] = 1
    items: list[DiscoveryEvidenceItem] = Field(min_length=1)


class MarketDiscoveryObservationPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    condition_id: str = Field(min_length=1)
    observed_at: datetime
    evidence_json: DiscoveryEvidenceEnvelope


class StrategyDiscoveryResult(BaseModel):
    strategy: str
    strategy_version: str
    observations: list[MarketDiscoveryObservationPayload] = Field(default_factory=list)
    generated_at: datetime

    @model_validator(mode="after")
    def validate_unique_markets(self) -> Self:
        condition_ids = [item.condition_id for item in self.observations]
        if len(condition_ids) != len(set(condition_ids)):
            raise ValueError("strategy result contains duplicate market observations")
        return self

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
    "DiscoveryEvidenceEnvelope",
    "DiscoveryEvidenceItem",
    "DiscoveryRunResult",
    "MarketDiscoveryObservationPayload",
    "StrategyDiscoveryResult",
    "StrategyExecutionLogEntry",
]
