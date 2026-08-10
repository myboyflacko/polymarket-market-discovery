import importlib

from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, inspect


EXPECTED_TABLES = {
    "market_discovery_runs",
    "market_discovery_strategy_runs",
    "whale_snapshots",
    "market_discovery_observations",
    "market_registry_sync_runs",
    "polymarket_markets",
    "polymarket_tokens",
    "market_status_snapshots",
    "orderbook_collection_runs",
    "orderbook_collection_items",
    "orderbook_snapshots",
}


def test_baseline_upgrade_and_downgrade() -> None:
    migration = importlib.import_module(
        "polymarket_market_discovery.core.db.migrations.versions.20260810_0001_baseline"
    )
    engine = create_engine("sqlite+pysqlite:///:memory:")
    with engine.begin() as connection:
        migration.op = Operations(MigrationContext.configure(connection))
        migration.upgrade()
        assert set(inspect(connection).get_table_names()) == EXPECTED_TABLES

        migration.downgrade()
        assert inspect(connection).get_table_names() == []
