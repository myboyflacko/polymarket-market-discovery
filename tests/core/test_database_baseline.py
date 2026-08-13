from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.migration import MigrationContext
from sqlalchemy import create_engine, inspect


MIGRATIONS_DIR = (
    Path(__file__).resolve().parents[2]
    / "src/polymarket_market_discovery/core/db/migrations"
)
BASELINE_REVISION = "20260813_0001"
EXPECTED_TABLES = {
    "alembic_version",
    "market_discovery_observations",
    "market_discovery_runs",
    "market_registry_sync_runs",
    "market_status_snapshots",
    "orderbook_collection_items",
    "orderbook_collection_runs",
    "orderbook_snapshots",
    "polymarket_markets",
    "polymarket_tokens",
}


def test_alembic_upgrade_initializes_sqlite_database(tmp_path: Path) -> None:
    database_path = tmp_path / "baseline.sqlite"
    config = Config()
    config.set_main_option("script_location", str(MIGRATIONS_DIR))
    config.attributes["database_url"] = f"sqlite+pysqlite:///{database_path}"

    command.upgrade(config, "head")

    assert database_path.is_file()
    engine = create_engine(f"sqlite+pysqlite:///{database_path}")
    with engine.connect() as connection:
        context = MigrationContext.configure(connection)
        assert context.get_current_revision() == BASELINE_REVISION


def test_alembic_baseline_creates_all_model_tables(tmp_path: Path) -> None:
    database_path = tmp_path / "baseline.sqlite"
    config = Config()
    config.set_main_option("script_location", str(MIGRATIONS_DIR))
    config.attributes["database_url"] = f"sqlite+pysqlite:///{database_path}"

    command.upgrade(config, "head")

    engine = create_engine(f"sqlite+pysqlite:///{database_path}")
    assert set(inspect(engine).get_table_names()) == EXPECTED_TABLES
