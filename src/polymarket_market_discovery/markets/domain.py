from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field, StringConstraints, model_validator


NonEmptyString = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class MarketTokenPayload(BaseModel):
    token_id: NonEmptyString
    outcome: NonEmptyString
    outcome_index: int


class PolymarketMarketPayload(BaseModel):
    condition_id: NonEmptyString
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

    @model_validator(mode="after")
    def validate_binary_token_contract(self) -> PolymarketMarketPayload:
        if len(self.tokens) != 2:
            raise ValueError("Market must have exactly two outcome tokens")
        token_ids = {token.token_id for token in self.tokens}
        outcomes = {token.outcome for token in self.tokens}
        outcome_indices = {token.outcome_index for token in self.tokens}
        if len(token_ids) != 2:
            raise ValueError("Market outcome token IDs must be unique")
        if len(outcomes) != 2:
            raise ValueError("Market outcomes must be unique")
        if len(outcome_indices) != 2:
            raise ValueError("Market outcome indices must be unique")
        return self


class MarketRegistrySyncResult(BaseModel):
    run_id: str | None
    status: Literal["completed", "failed", "skipped"]
    input_discovery_run_ids: list[str] = Field(default_factory=list)
    checked_market_count: int = 0
    created_market_count: int = 0
    updated_market_count: int = 0
    generated_at: datetime
    skip_reason: str | None = None
