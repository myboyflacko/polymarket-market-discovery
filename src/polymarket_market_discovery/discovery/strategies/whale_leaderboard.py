from __future__ import annotations

import asyncio
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from polymarket_market_discovery.discovery.domain import (
    DiscoveryEvidenceEnvelope,
    DiscoveryEvidenceItem,
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
WHALE_POSITION_EVIDENCE_KIND = "whale_position"
WHALE_POSITION_EVIDENCE_SOURCE = "polymarket_data_api.current_positions"


class WhalePositionEvidenceData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    proxy_wallet: str = Field(min_length=1)
    outcome_token_id: str = Field(min_length=1)
    opposite_token_id: str = Field(min_length=1)
    outcome: str = Field(min_length=1)
    opposite_outcome: str = Field(min_length=1)
    position_size: Decimal
    current_value: Decimal
    raw_position: dict[str, Any]


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
            )
            for wallet in wallets
        ]
    )
    evidence_by_condition: dict[str, list[DiscoveryEvidenceItem]] = {}
    for result in results:
        for condition_id, evidence_item in result:
            evidence_by_condition.setdefault(condition_id, []).append(evidence_item)

    return [
        MarketDiscoveryObservationPayload(
            condition_id=condition_id,
            observed_at=observed_at,
            evidence_json=DiscoveryEvidenceEnvelope(items=evidence_items),
        )
        for condition_id, evidence_items in evidence_by_condition.items()
    ]


async def _collect_single_wallet_positions(
    *,
    client: PolymarketClient,
    wallet: str,
) -> list[tuple[str, DiscoveryEvidenceItem]]:
    positions: list[tuple[str, DiscoveryEvidenceItem]] = []
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
            positions.append(_normalize_position_evidence(row=row, wallet=wallet))

        if len(page) < params.limit:
            break
        offset += params.limit
    return positions


def _normalize_position_evidence(
    *,
    row: dict[str, Any],
    wallet: str,
) -> tuple[str, DiscoveryEvidenceItem]:
    condition_id = _required_string(row, "conditionId")
    data = WhalePositionEvidenceData(
        proxy_wallet=wallet,
        outcome_token_id=_required_string(row, "asset"),
        opposite_token_id=_required_string(row, "oppositeAsset"),
        outcome=_required_string(row, "outcome"),
        opposite_outcome=_required_string(row, "oppositeOutcome"),
        position_size=_required_decimal(row, "size"),
        current_value=_required_decimal(row, "currentValue"),
        raw_position=row,
    )
    return condition_id, DiscoveryEvidenceItem(
        kind=WHALE_POSITION_EVIDENCE_KIND,
        source=WHALE_POSITION_EVIDENCE_SOURCE,
        data=data.model_dump(mode="json"),
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
