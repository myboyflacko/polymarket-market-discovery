from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import text

from polymarket_market_discovery.core.db.engine import create_database_engine


PIPELINE_LOCK_NAME = "polymarket_market_discovery_pipeline"


@contextmanager
def pipeline_lock() -> Iterator[bool]:
    """Hold the shared collector lock for the complete service execution."""
    engine = create_database_engine()
    with engine.connect() as connection:
        if connection.dialect.name != "postgresql":
            yield True
            return

        acquired = bool(
            connection.scalar(
                text("SELECT pg_try_advisory_lock(hashtext(:lock_name))"),
                {"lock_name": PIPELINE_LOCK_NAME},
            )
        )
        try:
            yield acquired
        finally:
            if acquired:
                connection.execute(
                    text("SELECT pg_advisory_unlock(hashtext(:lock_name))"),
                    {"lock_name": PIPELINE_LOCK_NAME},
                )
