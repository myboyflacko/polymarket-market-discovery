from __future__ import annotations

import argparse
import asyncio
import logging
from pathlib import Path
from typing import TYPE_CHECKING

from polymarket_market_discovery.core.logging import configure_logging
from polymarket_market_discovery.discovery.registry import (
    available_strategy_names,
)

if TYPE_CHECKING:
    from polymarket_market_discovery.discovery.service import (
        MarketDiscoveryService,
    )
    from polymarket_market_discovery.markets.service import MarketRegistryService
    from polymarket_market_discovery.orderbooks.service import (
        OrderbookCollectionService,
    )
    from polymarket_market_discovery.pipeline.coordinator import PipelineCoordinator


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
    schedule_parser.add_argument("--discovery-interval", type=positive_int, default=900)
    schedule_parser.add_argument("--markets-interval", type=positive_int, default=900)
    schedule_parser.add_argument(
        "--orderbooks-interval", type=positive_int, default=300
    )
    add_service_arguments(schedule_parser, include_registry_age=False)
    return parser


def add_service_arguments(
    parser: argparse.ArgumentParser, *, include_registry_age: bool = True
) -> None:
    parser.add_argument(
        "--strategy",
        action="append",
        choices=available_strategy_names(),
        help="Discovery strategy; repeat to select several. Defaults to all.",
    )
    parser.add_argument("--market-batch-size", type=positive_int, default=100)
    parser.add_argument("--orderbook-batch-size", type=positive_int, default=50)
    if include_registry_age:
        parser.add_argument(
            "--market-registry-max-age-seconds", type=positive_int, default=1800
        )


async def run_once(args: argparse.Namespace) -> None:
    if args.service == "all":
        result = await build_pipeline_coordinator(args, scheduled=False).run_once()
        print_pipeline_result(result)
        return
    if args.service == "discovery":
        result = await build_discovery_service(args.strategy).run()
        print(
            f"Discovery {result.status}: run_id={result.run_id} "
            f"markets={result.discovered_market_count} observations={result.observation_count}"
        )
    if args.service == "markets":
        result = await build_market_service(args.market_batch_size).run()
        print(
            f"Markets {result.status}: run_id={result.run_id} "
            f"checked={result.checked_market_count} created={result.created_market_count} "
            f"updated={result.updated_market_count}"
        )
    if args.service == "orderbooks":
        result = await build_orderbook_service(
            args.orderbook_batch_size, args.market_registry_max_age_seconds
        ).run()
        print(
            f"Orderbooks {result.status}: run_id={result.run_id} "
            f"markets={result.selected_market_count} tokens={result.selected_token_count} "
            f"success={result.success_count} "
            f"failure={result.failure_count}"
        )


async def schedule(args: argparse.Namespace) -> None:
    await build_pipeline_coordinator(args, scheduled=True).run_forever()


def build_discovery_service(
    strategy_names: list[str] | None,
) -> MarketDiscoveryService:
    from polymarket_market_discovery.discovery.service import (
        MarketDiscoveryService,
    )

    return MarketDiscoveryService(strategy_names=strategy_names)


def build_market_service(batch_size: int) -> MarketRegistryService:
    from polymarket_market_discovery.markets.service import MarketRegistryService

    return MarketRegistryService(batch_size=batch_size)


def build_orderbook_service(
    batch_size: int, market_registry_max_age_seconds: int = 1800
) -> OrderbookCollectionService:
    from polymarket_market_discovery.orderbooks.service import (
        OrderbookCollectionService,
    )

    return OrderbookCollectionService(
        batch_size=batch_size,
        market_registry_max_age_seconds=market_registry_max_age_seconds,
    )


def build_pipeline_coordinator(
    args: argparse.Namespace, *, scheduled: bool
) -> PipelineCoordinator:
    from polymarket_market_discovery.pipeline.coordinator import PipelineCoordinator

    registry_max_age = (
        args.markets_interval * 2
        if scheduled
        else args.market_registry_max_age_seconds
    )
    coordinator_options = (
        {
            "discovery_interval": args.discovery_interval,
            "market_interval": args.markets_interval,
            "orderbook_interval": args.orderbooks_interval,
        }
        if scheduled
        else {}
    )
    return PipelineCoordinator(
        discovery_runner=build_discovery_service(args.strategy).run,
        market_runner=build_market_service(args.market_batch_size).run,
        orderbook_runner=build_orderbook_service(
            args.orderbook_batch_size, registry_max_age
        ).run,
        **coordinator_options,
    )


def print_pipeline_result(result: object) -> None:
    print(f"Pipeline {getattr(result, 'status')}")
    for layer in ("discovery", "markets", "orderbooks"):
        layer_result = getattr(result, layer, None)
        if layer_result is not None:
            print(
                f"{layer.title()} {layer_result.status}: "
                f"run_id={layer_result.run_id}"
            )
    for layer, error in getattr(result, "errors", {}).items():
        print(f"{layer.title()} failed: error={error}")


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
