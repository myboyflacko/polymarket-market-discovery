from __future__ import annotations

from datetime import datetime

from sqlalchemy import select, update

from polymarket_market_discovery.core.db.engine import database_session
from polymarket_market_discovery.core.db.models import (
    MarketDiscoveryRun,
    MarketRegistrySyncRun,
    OrderbookCollectionItem,
    OrderbookCollectionRun,
)
from polymarket_market_discovery.core.time import ensure_utc


ORPHANED_RUN_ERROR = "Recovered orphaned run after collector lock was released"


def recover_orphaned_runs(*, recovered_at: datetime) -> None:
    """Fail stale running rows after the process-level lock has been acquired."""
    recovered_at = ensure_utc(recovered_at)
    with database_session() as session:
        discovery_runs = session.scalars(
            select(MarketDiscoveryRun).where(MarketDiscoveryRun.status == "running")
        ).all()
        for run in discovery_runs:
            run.strategy_log = [
                {
                    **entry,
                    "status": "failed",
                    "finished_at": recovered_at.isoformat(),
                    "error_message": ORPHANED_RUN_ERROR,
                }
                if entry.get("status") == "running"
                else entry
                for entry in run.strategy_log
            ]
            run.status = "failed"
            run.finished_at = recovered_at
            run.error_message = ORPHANED_RUN_ERROR
        session.execute(
            update(MarketRegistrySyncRun)
            .where(MarketRegistrySyncRun.status == "running")
            .values(
                status="failed",
                finished_at=recovered_at,
                error_message=ORPHANED_RUN_ERROR,
            )
        )
        orphaned_orderbook_ids = session.scalars(
            select(OrderbookCollectionRun.run_id).where(
                OrderbookCollectionRun.status == "running"
            )
        ).all()
        if orphaned_orderbook_ids:
            session.execute(
                update(OrderbookCollectionItem)
                .where(
                    OrderbookCollectionItem.run_id.in_(orphaned_orderbook_ids),
                    OrderbookCollectionItem.status == "pending",
                )
                .values(status="failed", api_error=ORPHANED_RUN_ERROR)
            )
            session.execute(
                update(OrderbookCollectionRun)
                .where(OrderbookCollectionRun.run_id.in_(orphaned_orderbook_ids))
                .values(
                    status="failed",
                    finished_at=recovered_at,
                    error_message=ORPHANED_RUN_ERROR,
                )
            )
        session.commit()
