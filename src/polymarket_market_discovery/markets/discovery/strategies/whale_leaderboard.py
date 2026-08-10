from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Literal

from pydantic import BaseModel, Field

from polymarket_market_discovery.markets.domain import (
    MarketDiscoveryObservationPayload,
    StrategyDiscoveryResult,
    WhaleSnapshotPayload,
)
from polymarket_market_discovery.polymarket.client import PolymarketClient
from polymarket_market_discovery.polymarket.params.leaderboard.leaderboard import (
    LeaderboardParams,
)
from polymarket_market_discovery.polymarket.params.profile.current_positions import (
    CurrentPositionsParams,
)


LeaderboardOrder = Literal["PNL", "VOL"]
MAX_POSITION_OFFSET = 10_000
POSITION_PAGE_LIMIT = 500


@dataclass(frozen=True)
class LeaderboardEntry:
    proxy_wallet: str
    rank: int
    row: dict[str, Any]


class WhaleLeaderboardIntersectionStrategy(BaseModel):
    name: str = "whale_leaderboard_intersection"
    version: str = "v1"
    wallet_count: int = Field(default=25, ge=1, le=50)
    leaderboard_category: str = "OVERALL"
    leaderboard_time_period: str = "DAY"
    leaderboard_limit: int = Field(default=25, ge=1, le=50)

    def config(self) -> dict[str, Any]:
        return self.model_dump()

    async def discover(
        self,
        *,
        client: PolymarketClient,
        generated_at: datetime,
    ) -> StrategyDiscoveryResult:
        pnl_entries, volume_entries = await asyncio.gather(
            fetch_leaderboard(client=client, strategy=self, order_by="PNL"),
            fetch_leaderboard(client=client, strategy=self, order_by="VOL"),
        )
        whales = select_intersection_whales(
            pnl_entries=pnl_entries,
            volume_entries=volume_entries,
            observed_at=generated_at,
        )
        observations = await collect_wallet_positions(
            client=client,
            whales=whales,
            observed_at=generated_at,
        )
        return StrategyDiscoveryResult(
            strategy=self.name,
            strategy_version=self.version,
            whales=whales,
            observations=observations,
            checked_count=len(whales),
            generated_at=generated_at,
        )


async def fetch_leaderboard(
    *,
    client: PolymarketClient,
    strategy: WhaleLeaderboardIntersectionStrategy,
    order_by: LeaderboardOrder,
) -> dict[str, LeaderboardEntry]:
    entries: dict[str, LeaderboardEntry] = {}
    offset = 0

    while len(entries) < strategy.wallet_count and offset <= 1000:
        params = LeaderboardParams(
            category=strategy.leaderboard_category,
            timePeriod=strategy.leaderboard_time_period,
            orderBy=order_by,
            limit=strategy.leaderboard_limit,
            offset=offset,
        )
        page = await client.get_leaderboard(params)
        if not isinstance(page, list):
            raise ValueError(f"{order_by} leaderboard response must be a list")
        if not page:
            break

        for row in page:
            if not isinstance(row, dict):
                raise ValueError(f"{order_by} leaderboard row must be an object")
            entry = parse_leaderboard_entry(row)
            entries.setdefault(entry.proxy_wallet, entry)
            if len(entries) >= strategy.wallet_count:
                break

        if len(page) < params.limit:
            break
        offset += params.limit

    return entries


def parse_leaderboard_entry(row: dict[str, Any]) -> LeaderboardEntry:
    wallet = required_string(row, "proxyWallet").lower()
    if len(wallet) != 42 or not wallet.startswith("0x"):
        raise ValueError("leaderboard proxyWallet must be a 0x-prefixed address")
    return LeaderboardEntry(
        proxy_wallet=wallet,
        rank=required_int(row, "rank"),
        row=row,
    )


def select_intersection_whales(
    *,
    pnl_entries: dict[str, LeaderboardEntry],
    volume_entries: dict[str, LeaderboardEntry],
    observed_at: datetime,
) -> list[WhaleSnapshotPayload]:
    whales: list[WhaleSnapshotPayload] = []
    for wallet, pnl_entry in pnl_entries.items():
        volume_entry = volume_entries.get(wallet)
        if volume_entry is None:
            continue
        whales.append(
            WhaleSnapshotPayload(
                proxy_wallet=wallet,
                pnl_rank=pnl_entry.rank,
                volume_rank=volume_entry.rank,
                pnl=required_decimal(pnl_entry.row, "pnl"),
                volume=required_decimal(volume_entry.row, "vol"),
                observed_at=observed_at,
                raw_payload={"pnl": pnl_entry.row, "volume": volume_entry.row},
            )
        )
    return whales


async def collect_wallet_positions(
    *,
    client: PolymarketClient,
    whales: list[WhaleSnapshotPayload],
    observed_at: datetime,
) -> list[MarketDiscoveryObservationPayload]:
    results = await asyncio.gather(
        *[
            collect_single_wallet_positions(
                client=client,
                wallet=whale.proxy_wallet,
                observed_at=observed_at,
            )
            for whale in whales
        ]
    )
    return [observation for result in results for observation in result]


async def collect_single_wallet_positions(
    *,
    client: PolymarketClient,
    wallet: str,
    observed_at: datetime,
) -> list[MarketDiscoveryObservationPayload]:
    observations: list[MarketDiscoveryObservationPayload] = []
    offset = 0
    while offset <= MAX_POSITION_OFFSET:
        params = CurrentPositionsParams(
            user=wallet,
            sizeThreshold=0,
            limit=POSITION_PAGE_LIMIT,
            offset=offset,
            sortBy="CURRENT",
            sortDirection="DESC",
        )
        page = await client.get_current_positions(params)
        if not isinstance(page, list):
            raise ValueError(f"positions response for {wallet} must be a list")
        if not page:
            break

        for row in page:
            if not isinstance(row, dict):
                raise ValueError(f"position row for {wallet} must be an object")
            observations.append(
                normalize_position_observation(
                    row=row,
                    wallet=wallet,
                    observed_at=observed_at,
                )
            )

        if len(page) < params.limit:
            break
        offset += params.limit
    return observations


def normalize_position_observation(
    *,
    row: dict[str, Any],
    wallet: str,
    observed_at: datetime,
) -> MarketDiscoveryObservationPayload:
    return MarketDiscoveryObservationPayload(
        proxy_wallet=wallet,
        condition_id=required_string(row, "conditionId"),
        held_token_id=required_string(row, "asset"),
        opposite_token_id=required_string(row, "oppositeAsset"),
        outcome=required_string(row, "outcome"),
        opposite_outcome=required_string(row, "oppositeOutcome"),
        position_size=required_decimal(row, "size"),
        current_value=required_decimal(row, "currentValue"),
        title=optional_string(row.get("title")),
        slug=optional_string(row.get("slug")),
        event_id=optional_string(row.get("eventId")),
        event_slug=optional_string(row.get("eventSlug")),
        end_date=optional_datetime(row.get("endDate")),
        observed_at=observed_at,
        raw_payload=row,
    )


def required_string(row: dict[str, Any], key: str) -> str:
    value = row.get(key)
    if value is None or str(value) == "":
        raise ValueError(f"missing required field {key}")
    return str(value)


def required_int(row: dict[str, Any], key: str) -> int:
    try:
        return int(required_string(row, key))
    except ValueError as exc:
        raise ValueError(f"invalid integer field {key}") from exc


def required_decimal(row: dict[str, Any], key: str) -> Decimal:
    try:
        return Decimal(required_string(row, key))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"invalid decimal field {key}") from exc


def optional_string(value: Any) -> str | None:
    return None if value is None or str(value) == "" else str(value)


def optional_datetime(value: Any) -> datetime | None:
    if value is None or str(value) == "":
        return None
    text = str(value)
    try:
        if text.endswith("Z"):
            return datetime.fromisoformat(text[:-1]).replace(tzinfo=UTC)
        parsed = datetime.fromisoformat(text)
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
    except ValueError as exc:
        raise ValueError("invalid endDate") from exc
