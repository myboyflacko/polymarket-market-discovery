from __future__ import annotations

from polymarket_market_discovery.discovery.strategies.base import (
    BaseMarketDiscoveryStrategy,
)
from polymarket_market_discovery.discovery.strategies.whale_leaderboard import (
    WhaleLeaderboardIntersectionStrategy,
)


STRATEGY_FACTORIES: dict[str, type[BaseMarketDiscoveryStrategy]] = {
    "whale_leaderboard_intersection": WhaleLeaderboardIntersectionStrategy,
}


def available_strategy_names() -> tuple[str, ...]:
    return tuple(STRATEGY_FACTORIES)


def build_strategies(
    names: list[str] | None = None,
) -> list[BaseMarketDiscoveryStrategy]:
    selected_names = names or list(available_strategy_names())
    unknown = sorted(set(selected_names) - set(STRATEGY_FACTORIES))
    if unknown:
        raise ValueError(f"Unknown market discovery strategies: {', '.join(unknown)}")
    return [STRATEGY_FACTORIES[name]() for name in dict.fromkeys(selected_names)]
