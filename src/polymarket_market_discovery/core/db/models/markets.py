from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from polymarket_market_discovery.core.db.models.base import BIGINT_PK, Base


class MarketRegistrySyncRun(Base):
    __tablename__ = "market_registry_sync_runs"

    run_id: Mapped[str] = mapped_column(String, primary_key=True)
    status: Mapped[str] = mapped_column(String, nullable=False)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    input_discovery_run_ids: Mapped[list[str]] = mapped_column(
        JSON, nullable=False, default=list
    )
    checked_market_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
    created_market_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
    updated_market_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class PolymarketMarket(Base):
    __tablename__ = "polymarket_markets"
    __table_args__ = (
        Index(
            "ix_polymarket_markets_collection_status", "active", "closed", "archived"
        ),
    )

    condition_id: Mapped[str] = mapped_column(String, primary_key=True)
    event_id: Mapped[str | None] = mapped_column(String)
    slug: Mapped[str | None] = mapped_column(String)
    title: Mapped[str | None] = mapped_column(String)
    question: Mapped[str | None] = mapped_column(String)
    end_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    active: Mapped[bool | None] = mapped_column(Boolean)
    closed: Mapped[bool | None] = mapped_column(Boolean)
    archived: Mapped[bool | None] = mapped_column(Boolean)
    enable_order_book: Mapped[bool | None] = mapped_column(Boolean)
    first_discovered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    last_discovered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    status_checked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    raw_latest_payload: Mapped[dict[str, Any]] = mapped_column(
        JSON, nullable=False, default=dict
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class PolymarketToken(Base):
    __tablename__ = "polymarket_tokens"
    __table_args__ = (
        Index("ix_polymarket_tokens_condition", "condition_id"),
        UniqueConstraint(
            "condition_id",
            "outcome_index",
            name="uq_polymarket_token_condition_outcome_index",
        ),
    )

    token_id: Mapped[str] = mapped_column(String, primary_key=True)
    condition_id: Mapped[str] = mapped_column(
        ForeignKey("polymarket_markets.condition_id", ondelete="CASCADE"),
        nullable=False,
    )
    outcome: Mapped[str] = mapped_column(String, nullable=False)
    outcome_index: Mapped[int] = mapped_column(Integer, nullable=False)
    first_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
class MarketStatusSnapshot(Base):
    __tablename__ = "market_status_snapshots"
    __table_args__ = (
        Index("ix_market_status_condition_checked", "condition_id", "checked_at"),
        UniqueConstraint(
            "sync_run_id",
            "condition_id",
            name="uq_market_status_snapshot_run_condition",
        ),
    )

    id: Mapped[int] = mapped_column(BIGINT_PK, primary_key=True, autoincrement=True)
    sync_run_id: Mapped[str] = mapped_column(
        ForeignKey("market_registry_sync_runs.run_id", ondelete="CASCADE"),
        nullable=False,
    )
    condition_id: Mapped[str] = mapped_column(
        ForeignKey("polymarket_markets.condition_id", ondelete="CASCADE"),
        nullable=False,
    )
    checked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    active: Mapped[bool | None] = mapped_column(Boolean)
    closed: Mapped[bool | None] = mapped_column(Boolean)
    archived: Mapped[bool | None] = mapped_column(Boolean)
    enable_order_book: Mapped[bool | None] = mapped_column(Boolean)
    end_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    raw_payload: Mapped[dict[str, Any]] = mapped_column(
        JSON, nullable=False, default=dict
    )


__all__ = [
    "MarketRegistrySyncRun",
    "MarketStatusSnapshot",
    "PolymarketMarket",
    "PolymarketToken",
]
