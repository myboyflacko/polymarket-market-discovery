"""Polymarket market discovery baseline.

Revision ID: 20260810_0001
Revises:
Create Date: 2026-08-10 00:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "20260810_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None
BIGINT_PK = sa.BigInteger().with_variant(sa.Integer(), "sqlite")


def upgrade() -> None:
    op.create_table(
        "market_discovery_runs",
        sa.Column("run_id", sa.String(), primary_key=True),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.Column("strategies", sa.JSON(), nullable=False),
        sa.Column("checked_wallet_count", sa.Integer(), nullable=False),
        sa.Column("observation_count", sa.Integer(), nullable=False),
        sa.Column("discovered_market_count", sa.Integer(), nullable=False),
        sa.Column("registry_synced_at", sa.DateTime(timezone=True)),
        sa.Column("config_json", sa.JSON(), nullable=False),
        sa.Column("error_message", sa.Text()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_table(
        "market_discovery_observations",
        sa.Column("id", BIGINT_PK, primary_key=True, autoincrement=True),
        sa.Column(
            "discovery_run_id",
            sa.String(),
            sa.ForeignKey("market_discovery_runs.run_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("proxy_wallet", sa.String()),
        sa.Column("condition_id", sa.String(), nullable=False),
        sa.Column("held_token_id", sa.String(), nullable=False),
        sa.Column("opposite_token_id", sa.String(), nullable=False),
        sa.Column("outcome", sa.String(), nullable=False),
        sa.Column("opposite_outcome", sa.String(), nullable=False),
        sa.Column("position_size", sa.Numeric(), nullable=False),
        sa.Column("current_value", sa.Numeric(), nullable=False),
        sa.Column("title", sa.String()),
        sa.Column("slug", sa.String()),
        sa.Column("event_id", sa.String()),
        sa.Column("event_slug", sa.String()),
        sa.Column("end_date", sa.DateTime(timezone=True)),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("evidence_json", sa.JSON(), nullable=False),
        sa.Column("raw_payload", sa.JSON(), nullable=False),
    )
    op.create_index(
        "ix_discovery_observations_condition_observed",
        "market_discovery_observations",
        ["condition_id", "observed_at"],
    )
    op.create_index(
        "ix_discovery_observations_discovery_run",
        "market_discovery_observations",
        ["discovery_run_id"],
    )

    op.create_table(
        "market_registry_sync_runs",
        sa.Column("run_id", sa.String(), primary_key=True),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.Column("input_discovery_run_ids", sa.JSON(), nullable=False),
        sa.Column("checked_market_count", sa.Integer(), nullable=False),
        sa.Column("created_market_count", sa.Integer(), nullable=False),
        sa.Column("updated_market_count", sa.Integer(), nullable=False),
        sa.Column("error_message", sa.Text()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_table(
        "polymarket_markets",
        sa.Column("condition_id", sa.String(), primary_key=True),
        sa.Column("event_id", sa.String()),
        sa.Column("slug", sa.String()),
        sa.Column("title", sa.String()),
        sa.Column("question", sa.String()),
        sa.Column("end_date", sa.DateTime(timezone=True)),
        sa.Column("active", sa.Boolean()),
        sa.Column("closed", sa.Boolean()),
        sa.Column("archived", sa.Boolean()),
        sa.Column("enable_order_book", sa.Boolean()),
        sa.Column("first_discovered_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_discovered_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status_checked_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("raw_latest_payload", sa.JSON(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "ix_polymarket_markets_collection_status",
        "polymarket_markets",
        ["active", "closed", "archived"],
    )
    op.create_table(
        "polymarket_tokens",
        sa.Column("token_id", sa.String(), primary_key=True),
        sa.Column(
            "condition_id",
            sa.String(),
            sa.ForeignKey("polymarket_markets.condition_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("outcome", sa.String(), nullable=False),
        sa.Column("outcome_index", sa.Integer(), nullable=False),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("raw_latest_payload", sa.JSON(), nullable=False),
    )
    op.create_index(
        "ix_polymarket_tokens_condition", "polymarket_tokens", ["condition_id"]
    )
    op.create_table(
        "market_status_snapshots",
        sa.Column("id", BIGINT_PK, primary_key=True, autoincrement=True),
        sa.Column(
            "sync_run_id",
            sa.String(),
            sa.ForeignKey("market_registry_sync_runs.run_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "condition_id",
            sa.String(),
            sa.ForeignKey("polymarket_markets.condition_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("checked_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("active", sa.Boolean()),
        sa.Column("closed", sa.Boolean()),
        sa.Column("archived", sa.Boolean()),
        sa.Column("enable_order_book", sa.Boolean()),
        sa.Column("end_date", sa.DateTime(timezone=True)),
        sa.Column("raw_payload", sa.JSON(), nullable=False),
    )
    op.create_index(
        "ix_market_status_condition_checked",
        "market_status_snapshots",
        ["condition_id", "checked_at"],
    )

    op.create_table(
        "orderbook_collection_runs",
        sa.Column("run_id", sa.String(), primary_key=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("selected_market_count", sa.Integer(), nullable=False),
        sa.Column("selected_token_count", sa.Integer(), nullable=False),
        sa.Column("success_count", sa.Integer(), nullable=False),
        sa.Column("failure_count", sa.Integer(), nullable=False),
        sa.Column("config_json", sa.JSON(), nullable=False),
        sa.Column("error_message", sa.Text()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_table(
        "orderbook_collection_items",
        sa.Column("id", BIGINT_PK, primary_key=True, autoincrement=True),
        sa.Column(
            "run_id",
            sa.String(),
            sa.ForeignKey("orderbook_collection_runs.run_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("condition_id", sa.String(), nullable=False),
        sa.Column("token_id", sa.String(), nullable=False),
        sa.Column("outcome", sa.String(), nullable=False),
        sa.Column(
            "market_status_checked_at", sa.DateTime(timezone=True), nullable=False
        ),
        sa.Column("selected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("api_error", sa.Text()),
        sa.UniqueConstraint("run_id", "token_id", name="uq_orderbook_item_run_token"),
    )
    op.create_index("ix_orderbook_items_run", "orderbook_collection_items", ["run_id"])
    op.create_table(
        "orderbook_snapshots",
        sa.Column("id", BIGINT_PK, primary_key=True, autoincrement=True),
        sa.Column(
            "run_id",
            sa.String(),
            sa.ForeignKey("orderbook_collection_runs.run_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("condition_id", sa.String(), nullable=False),
        sa.Column("token_id", sa.String(), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("exchange_timestamp", sa.DateTime(timezone=True)),
        sa.Column("exchange_timestamp_raw", sa.String()),
        sa.Column("best_bid", sa.Numeric()),
        sa.Column("best_ask", sa.Numeric()),
        sa.Column("midpoint", sa.Numeric()),
        sa.Column("spread", sa.Numeric()),
        sa.Column("last_trade_price", sa.Numeric()),
        sa.Column("bid_depth_top_1", sa.Numeric()),
        sa.Column("ask_depth_top_1", sa.Numeric()),
        sa.Column("bid_depth_top_3", sa.Numeric()),
        sa.Column("ask_depth_top_3", sa.Numeric()),
        sa.Column("bid_depth_top_5", sa.Numeric()),
        sa.Column("ask_depth_top_5", sa.Numeric()),
        sa.Column("bid_levels_count", sa.Integer(), nullable=False),
        sa.Column("ask_levels_count", sa.Integer(), nullable=False),
        sa.Column("min_order_size", sa.Numeric()),
        sa.Column("tick_size", sa.Numeric()),
        sa.Column("negative_risk", sa.Boolean()),
        sa.Column("bids", sa.JSON(), nullable=False),
        sa.Column("asks", sa.JSON(), nullable=False),
        sa.Column("book_hash", sa.String()),
        sa.Column("valid_orderbook", sa.Boolean(), nullable=False),
        sa.Column("invalid_reason", sa.Text()),
        sa.Column("parser_version", sa.String(), nullable=False),
        sa.Column("raw_payload", sa.JSON(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint(
            "run_id", "token_id", name="uq_orderbook_snapshot_run_token"
        ),
    )
    op.create_index(
        "ix_orderbook_snapshots_token_generated",
        "orderbook_snapshots",
        ["token_id", "generated_at"],
    )
    op.create_index(
        "ix_orderbook_snapshots_condition_generated",
        "orderbook_snapshots",
        ["condition_id", "generated_at"],
    )
    op.create_index(
        "ix_orderbook_snapshots_valid_generated",
        "orderbook_snapshots",
        ["valid_orderbook", "generated_at"],
    )


def downgrade() -> None:
    op.drop_table("orderbook_snapshots")
    op.drop_table("orderbook_collection_items")
    op.drop_table("orderbook_collection_runs")
    op.drop_table("market_status_snapshots")
    op.drop_table("polymarket_tokens")
    op.drop_table("polymarket_markets")
    op.drop_table("market_registry_sync_runs")
    op.drop_table("market_discovery_observations")
    op.drop_table("market_discovery_runs")
