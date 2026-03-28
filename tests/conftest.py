"""Shared test fixtures.

The `postgres_url` fixture provides a real PostgreSQL instance via Testcontainers.
It is session-scoped: one container runs for the entire test session, which keeps
integration tests fast while still exercising a real database.
"""

from __future__ import annotations

import pytest
from testcontainers.postgres import PostgresContainer


@pytest.fixture(scope="session")
def postgres_url() -> str:
    """Start a PostgreSQL container and return the connection URL.

    The container is stopped automatically when the test session ends.
    """
    with PostgresContainer("postgres:16-alpine") as pg:
        # psycopg3 requires the postgresql+psycopg scheme
        url = pg.get_connection_url().replace("psycopg2", "psycopg")
        yield url
