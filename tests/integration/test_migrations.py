"""Integration tests for Alembic migrations.

Requires Docker (Testcontainers spins up PostgreSQL automatically).
Run with: pixi run -e dev test-integration
"""

from __future__ import annotations

import os

import pytest
import sqlalchemy as sa
from alembic import command as alembic_cmd
from alembic.config import Config as AlembicConfig
from sqlalchemy import inspect


@pytest.fixture(scope="module")
def migrated_engine(postgres_url: str):
    """Return an engine after running alembic upgrade head."""
    # env.py reads DATABASE_URL from the environment; set it for the duration
    # of this fixture so alembic can connect to the test container.
    original = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = postgres_url
    try:
        cfg = AlembicConfig("alembic.ini")
        alembic_cmd.upgrade(cfg, "head")
    finally:
        if original is None:
            del os.environ["DATABASE_URL"]
        else:
            os.environ["DATABASE_URL"] = original

    engine = sa.create_engine(postgres_url)
    yield engine
    engine.dispose()


def test_upgrade_head_runs_clean(migrated_engine: sa.Engine) -> None:
    """alembic upgrade head completes without errors."""
    # If we got here, the fixture ran without raising — pass.
    assert migrated_engine is not None


def test_all_tables_exist(migrated_engine: sa.Engine) -> None:
    """All 7 Phase 1 tables exist after migration."""
    inspector = inspect(migrated_engine)
    tables = set(inspector.get_table_names())
    expected = {
        "installations",
        "repos",
        "reviews",
        "findings",
        "suppressions",
        "webhook_events",
        "audit_log",
    }
    assert expected <= tables, f"Missing tables: {expected - tables}"


@pytest.mark.parametrize(
    "table,required_columns",
    [
        ("installations", ["id", "github_id", "account_name", "account_type", "plan", "settings_json", "created_at"]),
        ("repos", ["id", "installation_id", "github_id", "full_name", "default_branch", "config_json"]),
        (
            "reviews",
            ["id", "repo_id", "pr_number", "head_sha", "base_sha", "trigger", "status", "created_at"],
        ),
        ("findings", ["id", "review_id", "fingerprint", "file_path", "line_start", "line_end", "description"]),
        ("suppressions", ["id", "repo_id", "fingerprint", "suppressed_by", "created_at"]),
        ("webhook_events", ["id", "delivery_id", "installation_id", "event_type", "payload_json", "processed"]),
        ("audit_log", ["id", "installation_id", "action", "detail_json", "created_at"]),
    ],
)
def test_required_columns_exist(migrated_engine: sa.Engine, table: str, required_columns: list[str]) -> None:
    """Each table has all required columns from the spec."""
    inspector = inspect(migrated_engine)
    column_names = {col["name"] for col in inspector.get_columns(table)}
    missing = set(required_columns) - column_names
    assert not missing, f"{table} missing columns: {missing}"


def test_tenant_scoping_via_fk_chain(migrated_engine: sa.Engine) -> None:
    """All tables are reachable from installations via FK chain."""
    inspector = inspect(migrated_engine)

    def fk_targets(table: str) -> set[str]:
        return {fk["referred_table"] for fk in inspector.get_foreign_keys(table)}

    # Direct FK to installations
    assert "installations" in fk_targets("repos")
    assert "installations" in fk_targets("webhook_events")
    assert "installations" in fk_targets("audit_log")

    # Via repos → installations
    assert "repos" in fk_targets("reviews")

    # Via reviews → repos → installations
    assert "reviews" in fk_targets("findings")

    # suppressions via repos
    assert "repos" in fk_targets("suppressions")


def test_webhook_events_delivery_id_unique(migrated_engine: sa.Engine) -> None:
    """webhook_events.delivery_id has a unique constraint."""
    inspector = inspect(migrated_engine)
    unique_constraints = inspector.get_unique_constraints("webhook_events")
    unique_cols = [col for uc in unique_constraints for col in uc["column_names"]]
    assert "delivery_id" in unique_cols
