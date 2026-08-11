from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Literal

from polymarket_market_discovery.discovery.domain import (
    MarketDiscoveryObservationPayload,
    StrategyDiscoveryResult,
)
from polymarket_market_discovery.discovery.strategies.base import (
    BaseMarketDiscoveryStrategy,
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


class WhaleLeaderboardIntersectionStrategy(BaseMarketDiscoveryStrategy):
    name = "whale_leaderboard_intersection"
    version = "v1"
    wallet_count = 25
    leaderboard_category = "OVERALL"
    leaderboard_time_period = "DAY"
    leaderboard_limit = 25

    async def discover(
        self,
        *,
        client: PolymarketClient,
        generated_at: datetime,
    ) -> StrategyDiscoveryResult:
        pnl_wallets, volume_wallets = await asyncio.gather(
            _fetch_leaderboard(client=client, strategy=self, order_by="PNL"),
            _fetch_leaderboard(client=client, strategy=self, order_by="VOL"),
        )
        wallets = _select_intersection_wallets(
            pnl_wallets=pnl_wallets,
            volume_wallets=volume_wallets,
        )
        observations = await _collect_wallet_positions(
            client=client,
            wallets=wallets,
            observed_at=generated_at,
        )
        return StrategyDiscoveryResult(
            strategy=self.name,
            strategy_version=self.version,
            observations=observations,
            generated_at=generated_at,
        )


async def _fetch_leaderboard(
    *,
    client: PolymarketClient,
    strategy: WhaleLeaderboardIntersectionStrategy,
    order_by: LeaderboardOrder,
) -> list[str]:
    wallets: list[str] = []
    seen_wallets: set[str] = set()
    offset = 0

    while len(wallets) < strategy.wallet_count and offset <= 1000:
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
            wallet = _parse_leaderboard_wallet(row)
            if wallet in seen_wallets:
                continue
            seen_wallets.add(wallet)
            wallets.append(wallet)
            if len(wallets) >= strategy.wallet_count:
                break

        if len(page) < params.limit:
            break
        offset += params.limit

    return wallets


def _parse_leaderboard_wallet(row: dict[str, Any]) -> str:
    wallet = _required_string(row, "proxyWallet").lower()
    if len(wallet) != 42 or not wallet.startswith("0x"):
        raise ValueError("leaderboard proxyWallet must be a 0x-prefixed address")
    return wallet


def _select_intersection_wallets(
    *,
    pnl_wallets: list[str],
    volume_wallets: list[str],
) -> list[str]:
    volume_wallet_set = set(volume_wallets)
    return [wallet for wallet in pnl_wallets if wallet in volume_wallet_set]


async def _collect_wallet_positions(
    *,
    client: PolymarketClient,
    wallets: list[str],
    observed_at: datetime,
) -> list[MarketDiscoveryObservationPayload]:
    results = await asyncio.gather(
        *[
            _collect_single_wallet_positions(
                client=client,
                wallet=wallet,
                observed_at=observed_at,
            )
            for wallet in wallets
        ]
    )
    return [observation for result in results for observation in result]


async def _collect_single_wallet_positions(
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
                _normalize_position_observation(
                    row=row,
                    wallet=wallet,
                    observed_at=observed_at,
                )
            )

        if len(page) < params.limit:
            break
        offset += params.limit
    return observations


def _normalize_position_observation(
    *,
    row: dict[str, Any],
    wallet: str,
    observed_at: datetime,
) -> MarketDiscoveryObservationPayload:
    return MarketDiscoveryObservationPayload(
        proxy_wallet=wallet,
        condition_id=_required_string(row, "conditionId"),
        held_token_id=_required_string(row, "asset"),
        opposite_token_id=_required_string(row, "oppositeAsset"),
        outcome=_required_string(row, "outcome"),
        opposite_outcome=_required_string(row, "oppositeOutcome"),
        position_size=_required_decimal(row, "size"),
        current_value=_required_decimal(row, "currentValue"),
        title=_optional_string(row.get("title")),
        slug=_optional_string(row.get("slug")),
        event_id=_optional_string(row.get("eventId")),
        event_slug=_optional_string(row.get("eventSlug")),
        end_date=_optional_datetime(row.get("endDate")),
        observed_at=observed_at,
        raw_payload=row,
    )


def _required_string(row: dict[str, Any], key: str) -> str:
    value = row.get(key)
    if value is None or str(value) == "":
        raise ValueError(f"missing required field {key}")
    return str(value)


def _required_decimal(row: dict[str, Any], key: str) -> Decimal:
    try:
        return Decimal(_required_string(row, key))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"invalid decimal field {key}") from exc


def _optional_string(value: Any) -> str | None:
    return None if value is None or str(value) == "" else str(value)


def _optional_datetime(value: Any) -> datetime | None:
    if value is None or str(value) == "":
        return None
    text = str(value)
    try:
        if text.endswith("Z"):
            return datetime.fromisoformat(text[:-1]).replace(tzinfo=UTC)
        parsed = datetime.fromisoformat(text)
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
    except ValueError as exc:
        raise ValueError(f"invalid datetime value: {value!r}") from exc
