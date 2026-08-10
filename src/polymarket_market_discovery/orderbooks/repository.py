from __future__ import annotations

from datetime import datetime
from typing import Literal

from sqlalchemy import func, select, update

from polymarket_market_discovery.core.db.engine import database_session
from polymarket_market_discovery.core.db.models import (
    OrderbookCollectionItem,
    OrderbookCollectionRun,
    OrderbookSnapshot,
    PolymarketMarket,
    PolymarketToken,
)
from polymarket_market_discovery.core.time import ensure_utc
from polymarket_market_discovery.orderbooks.domain import (
    OrderBookCollectionItemPayload,
    ParsedOrderBook,
)


def create_orderbook_collection_run(
    *, run_id: str, started_at: datetime, config_json: dict[str, object]
) -> None:
    with database_session() as session:
        session.add(
            OrderbookCollectionRun(
                run_id=run_id,
                started_at=ensure_utc(started_at),
                status="running",
                config_json=config_json,
            )
        )
        session.commit()


def snapshot_collectable_markets(
    *, run_id: str, selected_at: datetime
) -> list[OrderBookCollectionItemPayload]:
    selected_at = ensure_utc(selected_at)
    with database_session() as session:
        rows = session.execute(
            select(
                PolymarketMarket.condition_id,
                PolymarketToken.token_id,
                PolymarketToken.outcome,
                PolymarketMarket.status_checked_at,
            )
            .join(
                PolymarketToken,
                PolymarketToken.condition_id == PolymarketMarket.condition_id,
            )
            .where(
                PolymarketMarket.active.is_(True),
                PolymarketMarket.closed.is_(False),
                PolymarketMarket.archived.is_(False),
                PolymarketMarket.enable_order_book.is_(True),
            )
            .order_by(PolymarketMarket.condition_id, PolymarketToken.outcome_index)
        ).all()
        items = [
            OrderbookCollectionItem(
                run_id=run_id,
                condition_id=row.condition_id,
                token_id=row.token_id,
                outcome=row.outcome,
                market_status_checked_at=ensure_utc(row.status_checked_at),
                selected_at=selected_at,
                status="pending",
            )
            for row in rows
        ]
        session.add_all(items)
        session.execute(
            update(OrderbookCollectionRun)
            .where(OrderbookCollectionRun.run_id == run_id)
            .values(
                selected_market_count=len({row.condition_id for row in rows}),
                selected_token_count=len(rows),
            )
        )
        session.commit()
    return [
        OrderBookCollectionItemPayload(
            condition_id=row.condition_id,
            token_id=row.token_id,
            outcome=row.outcome,
            market_status_checked_at=ensure_utc(row.status_checked_at),
            selected_at=selected_at,
        )
        for row in rows
    ]


def complete_orderbook_collection_run(
    *,
    run_id: str,
    snapshots: list[ParsedOrderBook],
    errors_by_token: dict[str, str],
    finished_at: datetime,
) -> Literal["completed", "partial", "failed"]:
    finished_at = ensure_utc(finished_at)
    success_count = len(snapshots)
    failure_count = len(errors_by_token)
    status = _collection_status(
        success_count=success_count, failure_count=failure_count
    )
    with database_session() as session:
        for snapshot in snapshots:
            session.add(_snapshot_row(run_id=run_id, snapshot=snapshot))
            session.execute(
                update(OrderbookCollectionItem)
                .where(
                    OrderbookCollectionItem.run_id == run_id,
                    OrderbookCollectionItem.token_id == snapshot.token_id,
                )
                .values(status="completed", api_error=None)
            )
        for token_id, error in errors_by_token.items():
            session.execute(
                update(OrderbookCollectionItem)
                .where(
                    OrderbookCollectionItem.run_id == run_id,
                    OrderbookCollectionItem.token_id == token_id,
                )
                .values(status="failed", api_error=error)
            )
        session.execute(
            update(OrderbookCollectionRun)
            .where(OrderbookCollectionRun.run_id == run_id)
            .values(
                finished_at=finished_at,
                status=status,
                success_count=success_count,
                failure_count=failure_count,
                error_message="; ".join(errors_by_token.values()) or None,
            )
        )
        session.commit()
    return status


def fail_orderbook_collection_run(
    *, run_id: str, finished_at: datetime, error_message: str
) -> None:
    finished_at = ensure_utc(finished_at)
    with database_session() as session:
        session.execute(
            update(OrderbookCollectionItem)
            .where(
                OrderbookCollectionItem.run_id == run_id,
                OrderbookCollectionItem.status == "pending",
            )
            .values(status="failed", api_error=error_message)
        )
        session.execute(
            update(OrderbookCollectionRun)
            .where(OrderbookCollectionRun.run_id == run_id)
            .values(
                finished_at=finished_at,
                status="failed",
                failure_count=func.coalesce(
                    select(func.count(OrderbookCollectionItem.id))
                    .where(OrderbookCollectionItem.run_id == run_id)
                    .scalar_subquery(),
                    0,
                ),
                error_message=error_message,
            )
        )
        session.commit()


def _snapshot_row(*, run_id: str, snapshot: ParsedOrderBook) -> OrderbookSnapshot:
    return OrderbookSnapshot(
        run_id=run_id,
        condition_id=snapshot.condition_id,
        token_id=snapshot.token_id,
        generated_at=ensure_utc(snapshot.generated_at),
        exchange_timestamp=snapshot.exchange_timestamp,
        exchange_timestamp_raw=snapshot.exchange_timestamp_raw,
        best_bid=snapshot.best_bid,
        best_ask=snapshot.best_ask,
        midpoint=snapshot.midpoint,
        spread=snapshot.spread,
        last_trade_price=snapshot.last_trade_price,
        bid_depth_top_1=snapshot.bid_depth_top_1,
        ask_depth_top_1=snapshot.ask_depth_top_1,
        bid_depth_top_3=snapshot.bid_depth_top_3,
        ask_depth_top_3=snapshot.ask_depth_top_3,
        bid_depth_top_5=snapshot.bid_depth_top_5,
        ask_depth_top_5=snapshot.ask_depth_top_5,
        bid_levels_count=snapshot.bid_levels_count,
        ask_levels_count=snapshot.ask_levels_count,
        min_order_size=snapshot.min_order_size,
        tick_size=snapshot.tick_size,
        negative_risk=snapshot.negative_risk,
        bids=snapshot.bids,
        asks=snapshot.asks,
        book_hash=snapshot.book_hash,
        valid_orderbook=snapshot.valid_orderbook,
        invalid_reason=snapshot.invalid_reason,
        parser_version=snapshot.parser_version,
        raw_payload=snapshot.raw_payload,
    )


def _collection_status(
    *, success_count: int, failure_count: int
) -> Literal["completed", "partial", "failed"]:
    if failure_count == 0:
        return "completed"
    if success_count == 0:
        return "failed"
    return "partial"
