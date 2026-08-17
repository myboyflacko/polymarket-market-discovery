from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import func, or_, select, update

from polymarket_market_discovery.core.db.engine import database_session
from polymarket_market_discovery.core.db.models import (
    MarketDiscoveryObservation,
    MarketDiscoveryRun,
    MarketRegistrySyncRun,
    MarketStatusSnapshot,
    PolymarketMarket,
    PolymarketToken,
)
from polymarket_market_discovery.core.time import ensure_utc
from polymarket_market_discovery.markets.domain import PolymarketMarketPayload


@dataclass(frozen=True)
class MarketSyncInput:
    discovery_run_ids: list[str]
    condition_ids: list[str]


def get_market_sync_input() -> MarketSyncInput:
    with database_session() as session:
        discovery_run_ids = list(
            session.scalars(
                select(MarketDiscoveryRun.run_id)
                .where(
                    MarketDiscoveryRun.status == "completed",
                    MarketDiscoveryRun.registry_synced_at.is_(None),
                )
                .order_by(MarketDiscoveryRun.started_at, MarketDiscoveryRun.run_id)
            )
        )
        pending_conditions: set[str] = set()
        if discovery_run_ids:
            pending_conditions.update(
                session.scalars(
                    select(MarketDiscoveryObservation.condition_id)
                    .where(
                        MarketDiscoveryObservation.discovery_run_id.in_(
                            discovery_run_ids
                        )
                    )
                    .distinct()
                )
            )
        refresh_conditions = set(
            session.scalars(
                select(PolymarketMarket.condition_id).where(
                    or_(
                        PolymarketMarket.closed.is_(False),
                        PolymarketMarket.closed.is_(None),
                    ),
                    or_(
                        PolymarketMarket.archived.is_(False),
                        PolymarketMarket.archived.is_(None),
                    ),
                )
            )
        )
    return MarketSyncInput(
        discovery_run_ids=discovery_run_ids,
        condition_ids=sorted(pending_conditions | refresh_conditions),
    )


def create_market_sync_run(
    *, run_id: str, started_at: datetime, input_discovery_run_ids: list[str]
) -> None:
    with database_session() as session:
        session.add(
            MarketRegistrySyncRun(
                run_id=run_id,
                status="running",
                started_at=ensure_utc(started_at),
                input_discovery_run_ids=input_discovery_run_ids,
            )
        )
        session.commit()


def complete_market_sync_run(
    *,
    run_id: str,
    payloads: list[PolymarketMarketPayload],
    discovery_run_ids: list[str],
    checked_at: datetime,
) -> tuple[int, int]:
    checked_at = ensure_utc(checked_at)
    condition_ids = [payload.condition_id for payload in payloads]
    if len(condition_ids) != len(set(condition_ids)):
        raise ValueError("Registry payloads contain duplicate condition IDs")
    with database_session() as session:
        bounds = {
            condition_id: (first_seen, last_seen)
            for condition_id, first_seen, last_seen in session.execute(
                select(
                    MarketDiscoveryObservation.condition_id,
                    func.min(MarketDiscoveryObservation.observed_at),
                    func.max(MarketDiscoveryObservation.observed_at),
                )
                .where(MarketDiscoveryObservation.condition_id.in_(condition_ids))
                .group_by(MarketDiscoveryObservation.condition_id)
            )
        }
        created_count = 0
        updated_count = 0
        for payload in payloads:
            market = session.get(PolymarketMarket, payload.condition_id)
            if market is None:
                if payload.condition_id not in bounds:
                    raise ValueError(
                        f"Cannot create undiscovered market {payload.condition_id}"
                    )
                first_seen, last_seen = bounds[payload.condition_id]
                market = PolymarketMarket(
                    condition_id=payload.condition_id,
                    first_discovered_at=ensure_utc(first_seen),
                    last_discovered_at=ensure_utc(last_seen),
                    status_checked_at=checked_at,
                )
                session.add(market)
                created_count += 1
                session.flush()
                for token_payload in payload.tokens:
                    existing_token = session.get(
                        PolymarketToken, token_payload.token_id
                    )
                    if existing_token is not None:
                        _validate_token_identity(
                            token=existing_token,
                            condition_id=payload.condition_id,
                            outcome=token_payload.outcome,
                            outcome_index=token_payload.outcome_index,
                        )
                        raise ValueError(
                            f"Token {token_payload.token_id} already exists"
                        )
                    session.add(
                        PolymarketToken(
                            token_id=token_payload.token_id,
                            condition_id=payload.condition_id,
                            outcome=token_payload.outcome,
                            outcome_index=token_payload.outcome_index,
                            first_seen_at=checked_at,
                            last_seen_at=checked_at,
                        )
                    )
            else:
                stored_tokens = {
                    token.token_id: token
                    for token in session.scalars(
                        select(PolymarketToken).where(
                            PolymarketToken.condition_id == payload.condition_id
                        )
                    )
                }
                incoming_token_ids = {token.token_id for token in payload.tokens}
                if set(stored_tokens) != incoming_token_ids:
                    raise ValueError(
                        f"Token set changed for market {payload.condition_id}"
                    )
                for token_payload in payload.tokens:
                    token = stored_tokens[token_payload.token_id]
                    _validate_token_identity(
                        token=token,
                        condition_id=payload.condition_id,
                        outcome=token_payload.outcome,
                        outcome_index=token_payload.outcome_index,
                    )
                    token.last_seen_at = checked_at
                if payload.condition_id in bounds:
                    _, last_seen = bounds[payload.condition_id]
                    market.last_discovered_at = max(
                        ensure_utc(market.last_discovered_at), ensure_utc(last_seen)
                    )
                updated_count += 1

            market.event_id = payload.event_id
            market.slug = payload.slug
            market.title = payload.title
            market.question = payload.question
            market.end_date = payload.end_date
            market.active = payload.active
            market.closed = payload.closed
            market.archived = payload.archived
            market.enable_order_book = payload.enable_order_book
            market.status_checked_at = checked_at
            market.raw_latest_payload = payload.raw_payload
            market.updated_at = checked_at
            session.flush()

            session.add(
                MarketStatusSnapshot(
                    sync_run_id=run_id,
                    condition_id=payload.condition_id,
                    checked_at=checked_at,
                    active=payload.active,
                    closed=payload.closed,
                    archived=payload.archived,
                    enable_order_book=payload.enable_order_book,
                    end_date=payload.end_date,
                    raw_payload=payload.raw_payload,
                )
            )

        if discovery_run_ids:
            session.execute(
                update(MarketDiscoveryRun)
                .where(MarketDiscoveryRun.run_id.in_(discovery_run_ids))
                .values(registry_synced_at=checked_at)
            )
        session.execute(
            update(MarketRegistrySyncRun)
            .where(MarketRegistrySyncRun.run_id == run_id)
            .values(
                status="completed",
                finished_at=checked_at,
                checked_market_count=len(payloads),
                created_market_count=created_count,
                updated_market_count=updated_count,
            )
        )
        session.commit()
    return created_count, updated_count


def _validate_token_identity(
    *,
    token: PolymarketToken,
    condition_id: str,
    outcome: str,
    outcome_index: int,
) -> None:
    if token.condition_id != condition_id:
        raise ValueError(f"Token {token.token_id} condition changed")
    if token.outcome != outcome:
        raise ValueError(f"Token {token.token_id} outcome changed")
    if token.outcome_index != outcome_index:
        raise ValueError(f"Token {token.token_id} outcome index changed")


def fail_market_sync_run(
    *, run_id: str, finished_at: datetime, error_message: str
) -> None:
    with database_session() as session:
        session.execute(
            update(MarketRegistrySyncRun)
            .where(MarketRegistrySyncRun.run_id == run_id)
            .values(
                status="failed",
                finished_at=ensure_utc(finished_at),
                error_message=error_message,
            )
        )
        session.commit()
