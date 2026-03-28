"""Shared test fixtures for integration tests."""

from __future__ import annotations

import pytest
from testcontainers.postgres import PostgresContainer


@pytest.fixture(scope="session")
def postgres_url() -> str:
    """Spin up a fresh PostgreSQL for the test session."""
    with PostgresContainer("postgres:16") as pg:
        yield pg.get_connection_url().replace("psycopg2", "psycopg")
