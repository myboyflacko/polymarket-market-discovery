from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    BigInteger,
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

from polymarket_market_discovery.core.db.base import Base


BIGINT_PK = BigInteger().with_variant(Integer, "sqlite")


class MarketDiscoveryRun(Base):
    __tablename__ = "market_discovery_runs"

    run_id: Mapped[str] = mapped_column(String, primary_key=True)
    status: Mapped[str] = mapped_column(String, nullable=False)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    strategies: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    checked_wallet_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
    observation_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    discovered_market_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
    registry_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    config_json: Mapped[dict[str, Any]] = mapped_column(
        JSON, nullable=False, default=dict
    )
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class MarketDiscoveryStrategyRun(Base):
    __tablename__ = "market_discovery_strategy_runs"
    __table_args__ = (
        UniqueConstraint(
            "discovery_run_id", "strategy", name="uq_strategy_run_strategy"
        ),
    )

    id: Mapped[int] = mapped_column(BIGINT_PK, primary_key=True, autoincrement=True)
    discovery_run_id: Mapped[str] = mapped_column(
        ForeignKey("market_discovery_runs.run_id", ondelete="CASCADE"), nullable=False
    )
    strategy: Mapped[str] = mapped_column(String, nullable=False)
    strategy_version: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    checked_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    observation_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    config_json: Mapped[dict[str, Any]] = mapped_column(
        JSON, nullable=False, default=dict
    )
    error_message: Mapped[str | None] = mapped_column(Text)


class WhaleSnapshot(Base):
    __tablename__ = "whale_snapshots"
    __table_args__ = (
        UniqueConstraint(
            "strategy_run_id", "proxy_wallet", name="uq_whale_strategy_wallet"
        ),
    )

    id: Mapped[int] = mapped_column(BIGINT_PK, primary_key=True, autoincrement=True)
    strategy_run_id: Mapped[int] = mapped_column(
        ForeignKey("market_discovery_strategy_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    proxy_wallet: Mapped[str] = mapped_column(String, nullable=False)
    pnl_rank: Mapped[int] = mapped_column(Integer, nullable=False)
    volume_rank: Mapped[int] = mapped_column(Integer, nullable=False)
    pnl: Mapped[Decimal] = mapped_column(Numeric, nullable=False)
    volume: Mapped[Decimal] = mapped_column(Numeric, nullable=False)
    observed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    raw_payload: Mapped[dict[str, Any]] = mapped_column(
        JSON, nullable=False, default=dict
    )


class MarketDiscoveryObservation(Base):
    __tablename__ = "market_discovery_observations"
    __table_args__ = (
        Index(
            "ix_discovery_observations_condition_observed",
            "condition_id",
            "observed_at",
        ),
        Index("ix_discovery_observations_strategy_run", "strategy_run_id"),
    )

    id: Mapped[int] = mapped_column(BIGINT_PK, primary_key=True, autoincrement=True)
    strategy_run_id: Mapped[int] = mapped_column(
        ForeignKey("market_discovery_strategy_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    whale_snapshot_id: Mapped[int | None] = mapped_column(
        ForeignKey("whale_snapshots.id", ondelete="CASCADE")
    )
    condition_id: Mapped[str] = mapped_column(String, nullable=False)
    held_token_id: Mapped[str] = mapped_column(String, nullable=False)
    opposite_token_id: Mapped[str] = mapped_column(String, nullable=False)
    outcome: Mapped[str] = mapped_column(String, nullable=False)
    opposite_outcome: Mapped[str] = mapped_column(String, nullable=False)
    position_size: Mapped[Decimal] = mapped_column(Numeric, nullable=False)
    current_value: Mapped[Decimal] = mapped_column(Numeric, nullable=False)
    title: Mapped[str | None] = mapped_column(String)
    slug: Mapped[str | None] = mapped_column(String)
    event_id: Mapped[str | None] = mapped_column(String)
    event_slug: Mapped[str | None] = mapped_column(String)
    end_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    observed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    evidence_json: Mapped[dict[str, Any]] = mapped_column(
        JSON, nullable=False, default=dict
    )
    raw_payload: Mapped[dict[str, Any]] = mapped_column(
        JSON, nullable=False, default=dict
    )


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
    __table_args__ = (Index("ix_polymarket_tokens_condition", "condition_id"),)

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
    raw_latest_payload: Mapped[dict[str, Any]] = mapped_column(
        JSON, nullable=False, default=dict
    )


class MarketStatusSnapshot(Base):
    __tablename__ = "market_status_snapshots"
    __table_args__ = (
        Index("ix_market_status_condition_checked", "condition_id", "checked_at"),
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
