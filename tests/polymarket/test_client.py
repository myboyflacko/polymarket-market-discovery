import asyncio

import httpx

from polymarket_market_discovery.polymarket.client import PolymarketClient
from polymarket_market_discovery.polymarket.params.profile.current_positions import (
    CurrentPositionsParams,
)


WALLET = "0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"


class NoopLimiter:
    async def wait(self) -> None:
        return None


def limiter_factory(rate: float) -> NoopLimiter:
    return NoopLimiter()


def test_client_uses_public_positions_endpoint_and_gamma_closed_filter() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json=[])

    async def run_requests() -> None:
        async_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        client = PolymarketClient(
            async_client=async_client,
            limiter_factory=limiter_factory,
        )
        await client.get_current_positions(CurrentPositionsParams(user=WALLET))
        await client.get_gamma_markets(["one", "two"], closed=True)
        await async_client.aclose()

    asyncio.run(run_requests())

    assert requests[0].url.path == "/positions"
    assert requests[1].url.path == "/markets"
    assert requests[1].url.params.get_list("condition_ids") == ["one", "two"]
    assert requests[1].url.params["closed"] == "true"
