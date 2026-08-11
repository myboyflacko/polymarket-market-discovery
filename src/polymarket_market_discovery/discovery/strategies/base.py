from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import TYPE_CHECKING

from polymarket_market_discovery.discovery.domain import StrategyDiscoveryResult

if TYPE_CHECKING:
    from polymarket_market_discovery.polymarket.client import PolymarketClient


class BaseMarketDiscoveryStrategy(ABC):
    @property
    @abstractmethod
    def name(self) -> str:
        """Return the stable registry name of the strategy."""

    @property
    @abstractmethod
    def version(self) -> str:
        """Return the implementation version of the strategy."""

    @abstractmethod
    async def discover(
        self,
        *,
        client: PolymarketClient,
        generated_at: datetime,
    ) -> StrategyDiscoveryResult:
        """Discover and normalize market observations."""


__all__ = ["BaseMarketDiscoveryStrategy"]
