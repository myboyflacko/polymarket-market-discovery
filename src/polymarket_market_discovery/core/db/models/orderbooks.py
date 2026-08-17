from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    JSON,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from polymarket_market_discovery.core.db.models.base import BIGINT_PK, Base


class OrderbookCollectionRun(Base):
    __tablename__ = "orderbook_collection_runs"

    run_id: Mapped[str] = mapped_column(String, primary_key=True)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String, nullable=False)
    selected_market_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
    selected_token_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
    success_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failure_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    config_json: Mapped[dict[str, Any]] = mapped_column(
        JSON, nullable=False, default=dict
    )
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class OrderbookCollectionItem(Base):
    __tablename__ = "orderbook_collection_items"
    __table_args__ = (
        UniqueConstraint("run_id", "token_id", name="uq_orderbook_item_run_token"),
        Index("ix_orderbook_items_run", "run_id"),
    )

    id: Mapped[int] = mapped_column(BIGINT_PK, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(
        ForeignKey("orderbook_collection_runs.run_id", ondelete="CASCADE"),
        nullable=False,
    )
    condition_id: Mapped[str] = mapped_column(String, nullable=False)
    token_id: Mapped[str] = mapped_column(String, nullable=False)
    outcome: Mapped[str] = mapped_column(String, nullable=False)
    market_status_checked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    selected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    status: Mapped[str] = mapped_column(String, nullable=False, default="pending")
    api_error: Mapped[str | None] = mapped_column(Text)


class OrderbookSnapshot(Base):
    __tablename__ = "orderbook_snapshots"
    __table_args__ = (
        UniqueConstraint("run_id", "token_id", name="uq_orderbook_snapshot_run_token"),
        Index("ix_orderbook_snapshots_token_generated", "token_id", "generated_at"),
        Index(
            "ix_orderbook_snapshots_condition_generated", "condition_id", "generated_at"
        ),
        Index(
            "ix_orderbook_snapshots_valid_generated", "valid_orderbook", "generated_at"
        ),
    )

    id: Mapped[int] = mapped_column(BIGINT_PK, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(
        ForeignKey("orderbook_collection_runs.run_id", ondelete="CASCADE"),
        nullable=False,
    )
    condition_id: Mapped[str] = mapped_column(String, nullable=False)
    token_id: Mapped[str] = mapped_column(String, nullable=False)
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    exchange_timestamp: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    exchange_timestamp_raw: Mapped[str | None] = mapped_column(String)
    best_bid: Mapped[Decimal | None] = mapped_column(Numeric)
    best_ask: Mapped[Decimal | None] = mapped_column(Numeric)
    midpoint: Mapped[Decimal | None] = mapped_column(Numeric)
    spread: Mapped[Decimal | None] = mapped_column(Numeric)
    last_trade_price: Mapped[Decimal | None] = mapped_column(Numeric)
    bid_depth_top_1: Mapped[Decimal | None] = mapped_column(Numeric)
    ask_depth_top_1: Mapped[Decimal | None] = mapped_column(Numeric)
    bid_depth_top_3: Mapped[Decimal | None] = mapped_column(Numeric)
    ask_depth_top_3: Mapped[Decimal | None] = mapped_column(Numeric)
    bid_depth_top_5: Mapped[Decimal | None] = mapped_column(Numeric)
    ask_depth_top_5: Mapped[Decimal | None] = mapped_column(Numeric)
    bid_levels_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    ask_levels_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    min_order_size: Mapped[Decimal | None] = mapped_column(Numeric)
    tick_size: Mapped[Decimal | None] = mapped_column(Numeric)
    negative_risk: Mapped[bool | None] = mapped_column(Boolean)
    bids: Mapped[list[dict[str, Any]]] = mapped_column(
        JSON, nullable=False, default=list
    )
    asks: Mapped[list[dict[str, Any]]] = mapped_column(
        JSON, nullable=False, default=list
    )
    book_hash: Mapped[str | None] = mapped_column(String)
    valid_orderbook: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    invalid_reason: Mapped[str | None] = mapped_column(Text)
    parser_version: Mapped[str] = mapped_column(String, nullable=False)
    raw_payload: Mapped[dict[str, Any]] = mapped_column(
        JSON, nullable=False, default=dict
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


__all__ = [
    "OrderbookCollectionItem",
    "OrderbookCollectionRun",
    "OrderbookSnapshot",
]
