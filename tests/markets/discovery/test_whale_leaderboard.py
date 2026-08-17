import asyncio
from datetime import UTC, datetime
from typing import Any

import pytest
from pydantic import ValidationError

from polymarket_market_discovery.discovery.domain import DiscoveryEvidenceEnvelope
from polymarket_market_discovery.discovery.strategies.whale_leaderboard import (
    WHALE_POSITION_EVIDENCE_KIND,
    WHALE_POSITION_EVIDENCE_SOURCE,
    WhalePositionEvidenceData,
    WhaleLeaderboardIntersectionStrategy,
    _normalize_position_evidence,
    _select_intersection_wallets,
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
        second_position = _position_row()
        second_position["size"] = "20.5"
        second_position["currentValue"] = "12.2"
        return [_position_row(), second_position]


def test_strategy_collects_positions_for_intersection_wallets() -> None:
    client = FakePolymarketClient()
    strategy = WhaleLeaderboardIntersectionStrategy()

    result = asyncio.run(strategy.discover(client=client, generated_at=NOW))

    assert client.position_wallets == [WALLET_TWO]
    assert result.strategy == strategy.name
    assert result.strategy_version == strategy.version
    assert len(result.observations) == 1
    assert result.observations[0].condition_id == "condition-1"
    evidence = result.observations[0].evidence_json
    assert evidence.schema_version == 1
    assert len(evidence.items) == 2
    assert {item.kind for item in evidence.items} == {WHALE_POSITION_EVIDENCE_KIND}
    assert {item.source for item in evidence.items} == {WHALE_POSITION_EVIDENCE_SOURCE}
    first_position = WhalePositionEvidenceData.model_validate(evidence.items[0].data)
    assert first_position.proxy_wallet == WALLET_TWO
    assert first_position.outcome_token_id == "token-yes"
    assert first_position.opposite_token_id == "token-no"
    assert first_position.raw_position == _position_row()


def test_intersection_preserves_pnl_order() -> None:
    pnl = [WALLET_ONE, WALLET_TWO]
    volume = [WALLET_TWO, WALLET_THREE]

    wallets = _select_intersection_wallets(
        pnl_wallets=pnl,
        volume_wallets=volume,
    )

    assert wallets == [WALLET_TWO]


def test_position_validation_is_strict() -> None:
    row = _position_row()
    del row["oppositeAsset"]

    with pytest.raises(ValueError, match="oppositeAsset"):
        _normalize_position_evidence(row=row, wallet=WALLET_ONE)


def test_evidence_contract_validation_is_strict() -> None:
    with pytest.raises(ValidationError, match="at least 1 item"):
        DiscoveryEvidenceEnvelope(items=[])

    data = _position_row()
    del data["asset"]
    with pytest.raises(ValueError, match="asset"):
        _normalize_position_evidence(row=data, wallet=WALLET_ONE)


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
