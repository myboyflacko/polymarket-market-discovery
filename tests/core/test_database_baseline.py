from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.migration import MigrationContext
from sqlalchemy import create_engine, inspect

from polymarket_market_discovery.core.db.models import (
    MarketDiscoveryObservation,
    MarketRegistrySyncRun,
    MarketStatusSnapshot,
    PolymarketMarket,
    PolymarketToken,
)


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
EXPECTED_DISCOVERY_OBSERVATION_COLUMNS = {
    "id",
    "discovery_run_id",
    "strategy",
    "strategy_version",
    "condition_id",
    "observed_at",
    "evidence_json",
}
DISCOVERY_OBSERVATION_UNIQUE_CONSTRAINT = (
    "uq_discovery_observation_run_strategy_condition"
)
MARKET_REGISTRY_COLUMNS = {
    "market_registry_sync_runs": {
        "run_id",
        "status",
        "started_at",
        "finished_at",
        "input_discovery_run_ids",
        "checked_market_count",
        "created_market_count",
        "updated_market_count",
        "error_message",
        "created_at",
    },
    "polymarket_markets": {
        "condition_id",
        "event_id",
        "slug",
        "title",
        "question",
        "end_date",
        "active",
        "closed",
        "archived",
        "enable_order_book",
        "first_discovered_at",
        "last_discovered_at",
        "status_checked_at",
        "raw_latest_payload",
        "created_at",
        "updated_at",
    },
    "polymarket_tokens": {
        "token_id",
        "condition_id",
        "outcome",
        "outcome_index",
        "first_seen_at",
        "last_seen_at",
    },
    "market_status_snapshots": {
        "id",
        "sync_run_id",
        "condition_id",
        "checked_at",
        "active",
        "closed",
        "archived",
        "enable_order_book",
        "end_date",
        "raw_payload",
    },
}
MARKET_REGISTRY_UNIQUE_CONSTRAINTS = {
    "polymarket_tokens": {"uq_polymarket_token_condition_outcome_index"},
    "market_status_snapshots": {"uq_market_status_snapshot_run_condition"},
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
    inspector = inspect(engine)
    assert set(inspector.get_table_names()) == EXPECTED_TABLES
    assert {
        column["name"]
        for column in inspector.get_columns("market_discovery_observations")
    } == EXPECTED_DISCOVERY_OBSERVATION_COLUMNS
    assert {
        constraint["name"]
        for constraint in inspector.get_unique_constraints(
            "market_discovery_observations"
        )
    } == {DISCOVERY_OBSERVATION_UNIQUE_CONSTRAINT}

    for table_name, expected_columns in MARKET_REGISTRY_COLUMNS.items():
        assert {
            column["name"] for column in inspector.get_columns(table_name)
        } == expected_columns
    for table_name, expected_constraints in MARKET_REGISTRY_UNIQUE_CONSTRAINTS.items():
        assert {
            constraint["name"]
            for constraint in inspector.get_unique_constraints(table_name)
        } == expected_constraints


def test_discovery_observation_model_matches_baseline_contract() -> None:
    assert set(MarketDiscoveryObservation.__table__.columns.keys()) == (
        EXPECTED_DISCOVERY_OBSERVATION_COLUMNS
    )
    assert {
        constraint.name
        for constraint in MarketDiscoveryObservation.__table__.constraints
        if constraint.name == DISCOVERY_OBSERVATION_UNIQUE_CONSTRAINT
    } == {DISCOVERY_OBSERVATION_UNIQUE_CONSTRAINT}


def test_market_registry_models_match_baseline_contract() -> None:
    models_by_table = {
        "market_registry_sync_runs": MarketRegistrySyncRun,
        "polymarket_markets": PolymarketMarket,
        "polymarket_tokens": PolymarketToken,
        "market_status_snapshots": MarketStatusSnapshot,
    }
    for table_name, expected_columns in MARKET_REGISTRY_COLUMNS.items():
        assert set(models_by_table[table_name].__table__.columns.keys()) == (
            expected_columns
        )
    for table_name, expected_constraints in MARKET_REGISTRY_UNIQUE_CONSTRAINTS.items():
        assert {
            constraint.name
            for constraint in models_by_table[table_name].__table__.constraints
            if constraint.name is not None
        } == expected_constraints
