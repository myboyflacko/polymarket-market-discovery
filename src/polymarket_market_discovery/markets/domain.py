from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Literal, Protocol

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from polymarket_market_discovery.polymarket.client import PolymarketClient


class WhaleSnapshotPayload(BaseModel):
    proxy_wallet: str
    pnl_rank: int
    volume_rank: int
    pnl: Decimal
    volume: Decimal
    observed_at: datetime
    raw_payload: dict[str, Any] = Field(default_factory=dict)


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
    whales: list[WhaleSnapshotPayload] = Field(default_factory=list)
    observations: list[MarketDiscoveryObservationPayload] = Field(default_factory=list)
    checked_count: int = 0
    generated_at: datetime

    @property
    def market_count(self) -> int:
        return len({item.condition_id for item in self.observations})


class DiscoveryRunResult(BaseModel):
    run_id: str | None
    status: Literal["completed", "failed", "skipped"]
    strategies: list[str] = Field(default_factory=list)
    checked_wallet_count: int = 0
    observation_count: int = 0
    discovered_market_count: int = 0
    generated_at: datetime
    skip_reason: str | None = None


class MarketTokenPayload(BaseModel):
    token_id: str
    outcome: str
    outcome_index: int


class PolymarketMarketPayload(BaseModel):
    condition_id: str
    event_id: str | None = None
    slug: str | None = None
    title: str | None = None
    question: str | None = None
    end_date: datetime | None = None
    active: bool | None = None
    closed: bool | None = None
    archived: bool | None = None
    enable_order_book: bool | None = None
    tokens: list[MarketTokenPayload]
    raw_payload: dict[str, Any] = Field(default_factory=dict)


class MarketRegistrySyncResult(BaseModel):
    run_id: str | None
    status: Literal["completed", "failed", "skipped"]
    input_discovery_run_ids: list[str] = Field(default_factory=list)
    checked_market_count: int = 0
    created_market_count: int = 0
    updated_market_count: int = 0
    generated_at: datetime
    skip_reason: str | None = None


class MarketDiscoveryStrategy(Protocol):
    name: str
    version: str

    def config(self) -> dict[str, Any]: ...

    async def discover(
        self,
        *,
        client: PolymarketClient,
        generated_at: datetime,
    ) -> StrategyDiscoveryResult: ...
