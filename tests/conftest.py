from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from polymarket_market_discovery.core.db.base import Base


@pytest.fixture
def sqlite_database():
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False, future=True)

    @contextmanager
    def database_session() -> Iterator[Session]:
        with session_factory() as session:
            yield session

    return engine, session_factory, database_session
