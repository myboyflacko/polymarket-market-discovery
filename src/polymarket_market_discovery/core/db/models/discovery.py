from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    Integer,
    JSON,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from polymarket_market_discovery.core.db.models.base import BIGINT_PK, Base


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


class MarketDiscoveryObservation(Base):
    __tablename__ = "market_discovery_observations"
    __table_args__ = (
        Index(
            "ix_discovery_observations_condition_observed",
            "condition_id",
            "observed_at",
        ),
        Index("ix_discovery_observations_discovery_run", "discovery_run_id"),
    )

    id: Mapped[int] = mapped_column(BIGINT_PK, primary_key=True, autoincrement=True)
    discovery_run_id: Mapped[str] = mapped_column(
        ForeignKey("market_discovery_runs.run_id", ondelete="CASCADE"), nullable=False
    )
    proxy_wallet: Mapped[str | None] = mapped_column(String)
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


__all__ = ["MarketDiscoveryObservation", "MarketDiscoveryRun"]
