"""Shared pytest fixtures for unit and integration tests."""

from __future__ import annotations

import os
import tempfile

import pytest


@pytest.fixture()
def dbos_instance():
    """Initialize DBOS with a temporary SQLite database for a single test.

    Uses SQLite (no Testcontainers required) so integration tests run in
    any environment. DBOS is fully torn down and re-created per test so
    each test starts with a clean DBOS state and a live thread pool.

    Import kenjutsu.pipeline.steps before calling this fixture to ensure
    step functions are registered with DBOS before launch.
    """
    from dbos import DBOS

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test_kenjutsu.sqlite")
        DBOS(config={"name": "kenjutsu-test", "system_database_url": f"sqlite:///{db_path}"})
        DBOS.reset_system_database()
        DBOS.launch()
        yield
        DBOS.destroy()
