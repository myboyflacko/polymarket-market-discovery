from __future__ import annotations

import argparse
import asyncio
import logging
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import TYPE_CHECKING

from polymarket_market_discovery.core.logging import configure_logging
from polymarket_market_discovery.markets.discovery.registry import (
    available_strategy_names,
    build_strategies,
)

if TYPE_CHECKING:
    from polymarket_market_discovery.markets.discovery.service import (
        MarketDiscoveryService,
    )
    from polymarket_market_discovery.markets.service import MarketRegistryService
    from polymarket_market_discovery.orderbooks.service import (
        OrderbookCollectionService,
    )


logger = logging.getLogger(__name__)
SERVICES = ("discovery", "markets", "orderbooks", "all")


def main(argv: list[str] | None = None) -> int:
    configure_logging()
    args = build_parser().parse_args(argv)
    try:
        if args.command == "init-db":
            init_db()
            print("Database initialized.")
        elif args.command == "run":
            asyncio.run(run_once(args))
        elif args.command == "schedule":
            try:
                asyncio.run(schedule(args))
            except KeyboardInterrupt:
                print("Scheduler stopped.")
        else:
            raise ValueError(f"Unknown command: {args.command}")
    except Exception:
        logger.exception("Command failed", extra={"event": "cli.failed"})
        return 1
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="polymarket-market-discovery",
        description="Discover Polymarket markets and collect their orderbooks.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("init-db", help="Create the fresh database baseline.")

    run_parser = subparsers.add_parser("run", help="Run services once.")
    run_parser.add_argument("service", choices=SERVICES)
    add_service_arguments(run_parser)

    schedule_parser = subparsers.add_parser(
        "schedule", help="Run services continuously."
    )
    schedule_parser.add_argument("service", choices=SERVICES)
    schedule_parser.add_argument("--discovery-interval", type=positive_int, default=900)
    schedule_parser.add_argument("--markets-interval", type=positive_int, default=900)
    schedule_parser.add_argument(
        "--orderbooks-interval", type=positive_int, default=300
    )
    add_service_arguments(schedule_parser)
    return parser


def add_service_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--strategy",
        action="append",
        choices=available_strategy_names(),
        help="Discovery strategy; repeat to select several. Defaults to all.",
    )
    parser.add_argument("--market-batch-size", type=positive_int, default=100)
    parser.add_argument("--orderbook-batch-size", type=positive_int, default=50)


async def run_once(args: argparse.Namespace) -> None:
    if args.service in {"discovery", "all"}:
        result = await build_discovery_service(args.strategy).run()
        print(
            f"Discovery {result.status}: run_id={result.run_id} "
            f"markets={result.discovered_market_count} observations={result.observation_count}"
        )
        if result.status != "completed":
            return
    if args.service in {"markets", "all"}:
        result = await build_market_service(args.market_batch_size).run()
        print(
            f"Markets {result.status}: run_id={result.run_id} "
            f"checked={result.checked_market_count} created={result.created_market_count} "
            f"updated={result.updated_market_count}"
        )
        if result.status != "completed":
            return
    if args.service in {"orderbooks", "all"}:
        result = await build_orderbook_service(args.orderbook_batch_size).run()
        print(
            f"Orderbooks {result.status}: run_id={result.run_id} "
            f"markets={result.selected_market_count} tokens={result.selected_token_count} "
            f"success={result.success_count} "
            f"failure={result.failure_count}"
        )


async def schedule(args: argparse.Namespace) -> None:
    runners: list[Awaitable[None]] = []
    if args.service in {"discovery", "all"}:
        service = build_discovery_service(args.strategy)
        runners.append(
            scheduled_runner(
                interval=args.discovery_interval,
                runner=service.run,
                service="discovery",
            )
        )
    if args.service in {"markets", "all"}:
        service = build_market_service(args.market_batch_size)
        runners.append(
            scheduled_runner(
                interval=args.markets_interval,
                runner=service.run,
                service="markets",
            )
        )
    if args.service in {"orderbooks", "all"}:
        service = build_orderbook_service(args.orderbook_batch_size)
        runners.append(
            scheduled_runner(
                interval=args.orderbooks_interval,
                runner=service.run,
                service="orderbooks",
            )
        )
    await asyncio.gather(*runners)


async def scheduled_runner(
    *, interval: int, runner: Callable[[], Awaitable[object]], service: str
) -> None:
    while True:
        try:
            result = await runner()
            status = getattr(result, "status", "completed")
            logger.info(
                "Scheduled service finished",
                extra={
                    "event": (
                        "service.skipped"
                        if status == "skipped"
                        else "service.failed"
                        if status == "failed"
                        else "service.completed"
                    ),
                    "context": {
                        "service": service,
                        "status": status,
                        "run_id": getattr(result, "run_id", None),
                    },
                },
            )
        except Exception:
            logger.exception(
                "Scheduled service failed",
                extra={"event": "service.failed", "context": {"service": service}},
            )
        await asyncio.sleep(interval)


def build_discovery_service(
    strategy_names: list[str] | None,
) -> MarketDiscoveryService:
    from polymarket_market_discovery.markets.discovery.service import (
        MarketDiscoveryService,
    )

    return MarketDiscoveryService(strategies=build_strategies(strategy_names))


def build_market_service(batch_size: int) -> MarketRegistryService:
    from polymarket_market_discovery.markets.service import MarketRegistryService

    return MarketRegistryService(batch_size=batch_size)


def build_orderbook_service(batch_size: int) -> OrderbookCollectionService:
    from polymarket_market_discovery.orderbooks.service import (
        OrderbookCollectionService,
    )

    return OrderbookCollectionService(batch_size=batch_size)


def init_db() -> None:
    from alembic import command
    from alembic.config import Config

    migrations_dir = Path(__file__).resolve().parent / "core/db/migrations"
    config = Config()
    config.set_main_option("script_location", str(migrations_dir))
    command.upgrade(config, "head")


def positive_int(value: str) -> int:
    parsed = int(value)
    if parsed < 1:
        raise argparse.ArgumentTypeError("Must be greater than zero.")
    return parsed


if __name__ == "__main__":
    raise SystemExit(main())
