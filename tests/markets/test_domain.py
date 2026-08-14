import pytest
from pydantic import ValidationError

from polymarket_market_discovery.markets.domain import (
    MarketTokenPayload,
    PolymarketMarketPayload,
)


def test_market_payload_accepts_exactly_two_distinct_outcome_tokens() -> None:
    payload = PolymarketMarketPayload(
        condition_id="condition-1",
        tokens=[
            MarketTokenPayload(token_id="yes", outcome="Yes", outcome_index=0),
            MarketTokenPayload(token_id="no", outcome="No", outcome_index=1),
        ],
    )

    assert [token.token_id for token in payload.tokens] == ["yes", "no"]


@pytest.mark.parametrize(
    ("condition_id", "tokens"),
    [
        (
            "",
            [
                {"token_id": "yes", "outcome": "Yes", "outcome_index": 0},
                {"token_id": "no", "outcome": "No", "outcome_index": 1},
            ],
        ),
        (
            "condition-1",
            [{"token_id": "yes", "outcome": "Yes", "outcome_index": 0}],
        ),
        (
            "condition-1",
            [
                {"token_id": "same", "outcome": "Yes", "outcome_index": 0},
                {"token_id": "same", "outcome": "No", "outcome_index": 1},
            ],
        ),
        (
            "condition-1",
            [
                {"token_id": "yes", "outcome": "Same", "outcome_index": 0},
                {"token_id": "no", "outcome": "Same", "outcome_index": 1},
            ],
        ),
        (
            "condition-1",
            [
                {"token_id": "yes", "outcome": "Yes", "outcome_index": 0},
                {"token_id": "no", "outcome": "No", "outcome_index": 0},
            ],
        ),
        (
            "condition-1",
            [
                {"token_id": "", "outcome": "Yes", "outcome_index": 0},
                {"token_id": "no", "outcome": "No", "outcome_index": 1},
            ],
        ),
        (
            "condition-1",
            [
                {"token_id": "yes", "outcome": "", "outcome_index": 0},
                {"token_id": "no", "outcome": "No", "outcome_index": 1},
            ],
        ),
    ],
)
def test_market_payload_rejects_invalid_binary_token_contract(
    condition_id: str, tokens: list[dict[str, object]]
) -> None:
    with pytest.raises(ValidationError):
        PolymarketMarketPayload(condition_id=condition_id, tokens=tokens)
