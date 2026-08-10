import asyncio
from datetime import UTC, datetime
from typing import Any

import pytest

from polymarket_market_discovery.markets.discovery.strategies.whale_leaderboard import (
    LeaderboardEntry,
    WhaleLeaderboardIntersectionStrategy,
    normalize_position_observation,
    select_intersection_whales,
)


NOW = datetime(2026, 8, 10, tzinfo=UTC)
WALLET_ONE = "0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
WALLET_TWO = "0xbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
WALLET_THREE = "0xcccccccccccccccccccccccccccccccccccccccc"


class FakePolymarketClient:
    def __init__(self) -> None:
        self.position_wallets: list[str] = []

    async def get_leaderboard(self, params: Any) -> list[dict[str, Any]]:
        if params.orderBy == "PNL":
            return [
                _leaderboard_row(WALLET_ONE, rank=1, pnl="100", vol="10"),
                _leaderboard_row(WALLET_TWO, rank=2, pnl="90", vol="20"),
            ]
        return [
            _leaderboard_row(WALLET_TWO, rank=1, pnl="90", vol="200"),
            _leaderboard_row(WALLET_THREE, rank=2, pnl="80", vol="180"),
        ]

    async def get_current_positions(self, params: Any) -> list[dict[str, Any]]:
        self.position_wallets.append(params.user)
        assert params.sizeThreshold == 0
        return [_position_row()]


def test_strategy_collects_only_intersection_whales_and_raw_positions() -> None:
    client = FakePolymarketClient()
    strategy = WhaleLeaderboardIntersectionStrategy(wallet_count=25)

    result = asyncio.run(strategy.discover(client=client, generated_at=NOW))

    assert client.position_wallets == [WALLET_TWO]
    assert result.checked_count == 1
    assert result.whales[0].proxy_wallet == WALLET_TWO
    assert result.whales[0].pnl_rank == 2
    assert result.whales[0].volume_rank == 1
    assert result.whales[0].raw_payload["pnl"]["proxyWallet"] == WALLET_TWO
    assert result.observations[0].condition_id == "condition-1"
    assert result.observations[0].held_token_id == "token-yes"
    assert result.observations[0].opposite_token_id == "token-no"
    assert result.observations[0].raw_payload == _position_row()


def test_intersection_preserves_pnl_order() -> None:
    pnl = {
        WALLET_ONE: LeaderboardEntry(WALLET_ONE, 1, _leaderboard_row(WALLET_ONE, 1)),
        WALLET_TWO: LeaderboardEntry(WALLET_TWO, 2, _leaderboard_row(WALLET_TWO, 2)),
    }
    volume = {
        WALLET_TWO: LeaderboardEntry(WALLET_TWO, 1, _leaderboard_row(WALLET_TWO, 1)),
        WALLET_THREE: LeaderboardEntry(
            WALLET_THREE, 2, _leaderboard_row(WALLET_THREE, 2)
        ),
    }

    whales = select_intersection_whales(
        pnl_entries=pnl, volume_entries=volume, observed_at=NOW
    )

    assert [whale.proxy_wallet for whale in whales] == [WALLET_TWO]


def test_position_validation_is_strict() -> None:
    row = _position_row()
    del row["oppositeAsset"]

    with pytest.raises(ValueError, match="oppositeAsset"):
        normalize_position_observation(row=row, wallet=WALLET_ONE, observed_at=NOW)


def _leaderboard_row(
    wallet: str, rank: int, pnl: str = "10", vol: str = "20"
) -> dict[str, Any]:
    return {"proxyWallet": wallet, "rank": rank, "pnl": pnl, "vol": vol}


def _position_row() -> dict[str, Any]:
    return {
        "asset": "token-yes",
        "conditionId": "condition-1",
        "title": "Question?",
        "slug": "question",
        "outcome": "Yes",
        "oppositeAsset": "token-no",
        "oppositeOutcome": "No",
        "size": "10.5",
        "currentValue": "6.2",
        "endDate": "2026-12-31T00:00:00Z",
    }
