from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import (
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


class MarketDiscoveryRun(Base):
    __tablename__ = "market_discovery_runs"

    run_id: Mapped[str] = mapped_column(String, primary_key=True)
    status: Mapped[str] = mapped_column(String, nullable=False)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    strategies: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    strategy_log: Mapped[list[dict[str, Any]]] = mapped_column(
        JSON, nullable=False, default=list
    )
    observation_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    discovered_market_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
    registry_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
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
        UniqueConstraint(
            "discovery_run_id",
            "strategy",
            "condition_id",
            name="uq_discovery_observation_run_strategy_condition",
        ),
    )

    id: Mapped[int] = mapped_column(BIGINT_PK, primary_key=True, autoincrement=True)
    discovery_run_id: Mapped[str] = mapped_column(
        ForeignKey("market_discovery_runs.run_id", ondelete="CASCADE"), nullable=False
    )
    strategy: Mapped[str] = mapped_column(String, nullable=False)
    strategy_version: Mapped[str] = mapped_column(String, nullable=False)
    condition_id: Mapped[str] = mapped_column(String, nullable=False)
    observed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    evidence_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)


__all__ = ["MarketDiscoveryObservation", "MarketDiscoveryRun"]
