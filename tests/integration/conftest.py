"""Shared fixtures for integration tests.

Spins up a real PostgreSQL container once per test session using
Testcontainers. All integration tests share this container to keep
suite runtime short.
"""

from __future__ import annotations

import pytest
from testcontainers.postgres import PostgresContainer


@pytest.fixture(scope="session")
def postgres_dsn() -> str:
    """Start a PostgreSQL container and return its connection DSN.

    The container lives for the full test session and is torn down
    automatically when the session ends.
    """
    with PostgresContainer("postgres:16-alpine") as pg:
        # get_connection_url() returns a SQLAlchemy URL; strip the driver prefix
        # so psycopg can use it directly as a libpq connection string.
        url = pg.get_connection_url()
        yield url.replace("postgresql+psycopg2://", "postgresql://", 1).replace(
            "postgresql+psycopg://", "postgresql://", 1
        )
