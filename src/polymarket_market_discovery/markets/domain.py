from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


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
