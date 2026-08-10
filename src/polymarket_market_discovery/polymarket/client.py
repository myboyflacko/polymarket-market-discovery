from __future__ import annotations

import asyncio
from collections.abc import Callable
from enum import StrEnum
from functools import lru_cache
from typing import Any, Protocol
from urllib.parse import urljoin

import httpx
from asynciolimiter import StrictLimiter

from polymarket_market_discovery.polymarket.errors import PolymarketRateLimitError
from polymarket_market_discovery.polymarket.params.leaderboard.leaderboard import (
    LeaderboardParams,
)
from polymarket_market_discovery.polymarket.params.orderbook import OrderBooksParams
from polymarket_market_discovery.polymarket.params.profile.current_positions import (
    CurrentPositionsParams,
)
from polymarket_market_discovery.settings import (
    ApiSettings,
    PolymarketClobApiClientSettings,
    PolymarketDataApiClientSettings,
    PolymarketGammaApiClientSettings,
    get_settings,
)


class PolymarketEndpoint(StrEnum):
    POSITIONS = "positions"
    LEADERBOARD = "leaderboard"
    MARKETS = "markets"
    ORDERBOOKS = "orderbooks"


class AsyncRateLimiter(Protocol):
    async def wait(self) -> None: ...


class PolymarketClient:
    def __init__(
        self,
        *,
        settings: PolymarketDataApiClientSettings | None = None,
        gamma_settings: PolymarketGammaApiClientSettings | None = None,
        clob_settings: PolymarketClobApiClientSettings | None = None,
        async_client: httpx.AsyncClient | None = None,
        limiter_factory: Callable[[float], AsyncRateLimiter] = StrictLimiter,
        semaphore: asyncio.Semaphore | None = None,
    ) -> None:
        app_settings = get_settings()
        self.settings = settings or app_settings.polymarket_data_api_client
        self.gamma_settings = gamma_settings or app_settings.polymarket_gamma_api_client
        self.clob_settings = clob_settings or app_settings.polymarket_clob_api_client
        self._client = async_client or httpx.AsyncClient(
            timeout=max(
                self.settings.timeout_seconds,
                self.gamma_settings.timeout_seconds,
                self.clob_settings.timeout_seconds,
            )
        )
        self._owns_client = async_client is None
        self._semaphore = semaphore or asyncio.Semaphore(
            self.settings.max_concurrent_requests
        )
        self._endpoint_limiters = {
            PolymarketEndpoint.POSITIONS: limiter_factory(
                self.settings.positions_requests_per_second
            ),
            PolymarketEndpoint.LEADERBOARD: limiter_factory(
                self.settings.leaderboard_requests_per_second
            ),
            PolymarketEndpoint.MARKETS: limiter_factory(
                self.gamma_settings.requests_per_second
            ),
            PolymarketEndpoint.ORDERBOOKS: limiter_factory(
                self.clob_settings.orderbook_requests_per_second
            ),
        }

    async def __aenter__(self) -> PolymarketClient:
        return self

    async def __aexit__(self, exc_type: object, exc: object, traceback: object) -> None:
        await self.close()

    async def get_current_positions(
        self, params: CurrentPositionsParams
    ) -> dict[str, Any] | list[Any]:
        return await self._get_json(
            base_url=self.settings.base_url,
            endpoint="/positions",
            params=params.output_params(),
            endpoint_kind=PolymarketEndpoint.POSITIONS,
            settings=self.settings,
        )

    async def get_leaderboard(
        self, params: LeaderboardParams = LeaderboardParams()
    ) -> dict[str, Any] | list[Any]:
        return await self._get_json(
            base_url=self.settings.base_url,
            endpoint="/v1/leaderboard",
            params=params.output_params(),
            endpoint_kind=PolymarketEndpoint.LEADERBOARD,
            settings=self.settings,
        )

    async def get_gamma_markets(
        self, condition_ids: list[str], *, closed: bool = False
    ) -> list[dict[str, Any]]:
        if not condition_ids:
            return []
        payload = await self._get_json(
            base_url=self.gamma_settings.base_url,
            endpoint="/markets",
            params={
                "condition_ids": condition_ids,
                "closed": closed,
                "limit": len(condition_ids),
            },
            endpoint_kind=PolymarketEndpoint.MARKETS,
            settings=self.gamma_settings,
        )
        if not isinstance(payload, list) or any(
            not isinstance(item, dict) for item in payload
        ):
            raise ValueError("Gamma markets response must be a list of objects")
        return payload

    async def get_order_books(
        self, params: OrderBooksParams
    ) -> dict[str, Any] | list[Any]:
        return await self._post_json(
            base_url=self.clob_settings.base_url,
            endpoint="/books",
            json=params.output_body(),
            endpoint_kind=PolymarketEndpoint.ORDERBOOKS,
            settings=self.clob_settings,
        )

    async def close(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def _get_json(
        self,
        *,
        base_url: str,
        endpoint: str,
        params: dict[str, Any],
        endpoint_kind: PolymarketEndpoint,
        settings: ApiSettings,
    ) -> dict[str, Any] | list[Any]:
        url = urljoin(base_url, endpoint)
        for attempt in range(1, settings.rate_limit_retry_attempts + 2):
            try:
                await self._endpoint_limiters[endpoint_kind].wait()
                async with self._semaphore:
                    response = await self._client.get(url=url, params=params)
                    response.raise_for_status()
                    return response.json()
            except Exception as exc:
                if (
                    _is_rate_limited(exc)
                    and attempt <= settings.rate_limit_retry_attempts
                ):
                    await asyncio.sleep(settings.rate_limit_backoff_seconds * attempt)
                    continue
                if _is_rate_limited(exc):
                    raise PolymarketRateLimitError(
                        f"Rate limited for {endpoint} after {attempt} attempts"
                    ) from exc
                raise
        raise RuntimeError(f"Request attempts exhausted for {endpoint}")

    async def _post_json(
        self,
        *,
        base_url: str,
        endpoint: str,
        json: list[dict[str, Any]],
        endpoint_kind: PolymarketEndpoint,
        settings: ApiSettings,
    ) -> dict[str, Any] | list[Any]:
        url = urljoin(base_url, endpoint)
        for attempt in range(1, settings.rate_limit_retry_attempts + 2):
            try:
                await self._endpoint_limiters[endpoint_kind].wait()
                async with self._semaphore:
                    response = await self._client.post(url=url, json=json)
                    response.raise_for_status()
                    return response.json()
            except Exception as exc:
                if (
                    _is_rate_limited(exc)
                    and attempt <= settings.rate_limit_retry_attempts
                ):
                    await asyncio.sleep(settings.rate_limit_backoff_seconds * attempt)
                    continue
                if _is_rate_limited(exc):
                    raise PolymarketRateLimitError(
                        f"Rate limited for {endpoint} after {attempt} attempts"
                    ) from exc
                raise
        raise RuntimeError(f"Request attempts exhausted for {endpoint}")


def _is_rate_limited(exc: Exception) -> bool:
    return isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code == 429


@lru_cache(maxsize=1)
def get_polymarket_client() -> PolymarketClient:
    return PolymarketClient()
