"""Integration tests: Alembic migrations against a real PostgreSQL instance.

These tests verify:
1. `alembic upgrade head` runs cleanly
2. The resulting schema matches the spec (all Phase 1 tables and required columns)
"""

from __future__ import annotations

import pytest
import sqlalchemy as sa
from alembic import command as alembic_cmd
from alembic.config import Config

EXPECTED_TABLES = {
    "installations",
    "repos",
    "reviews",
    "findings",
    "suppressions",
    "webhook_events",
    "audit_log",
}

# Required columns per table (subset check — not exhaustive but covers the spec)
REQUIRED_COLUMNS: dict[str, set[str]] = {
    "installations": {"id", "github_id", "account_name", "account_type", "plan", "settings_json", "created_at"},
    "repos": {
        "id",
        "installation_id",
        "github_id",
        "full_name",
        "default_branch",
        "config_json",
        "mirror_path",
        "active_index_version",
        "indexed_at",
    },
    "reviews": {
        "id",
        "repo_id",
        "pr_number",
        "head_sha",
        "base_sha",
        "index_version_id",
        "context_source",
        "trigger",
        "status",
        "model_used",
        "tokens_in",
        "tokens_out",
        "cost_usd",
        "latency_ms_json",
        "findings_raw_count",
        "findings_published_count",
        "created_at",
    },
    "findings": {
        "id",
        "review_id",
        "fingerprint",
        "file_path",
        "line_start",
        "line_end",
        "origin",
        "confidence",
        "severity",
        "category",
        "publishability",
        "description",
        "suggestion",
        "evidence_sources_json",
        "published",
        "github_comment_id",
    },
    "suppressions": {"id", "repo_id", "fingerprint", "suppressed_by", "reason", "created_at"},
    "webhook_events": {"id", "delivery_id", "installation_id", "event_type", "payload_json", "processed", "created_at"},
    "audit_log": {"id", "installation_id", "repo_id", "action", "detail_json", "created_at"},
}


@pytest.fixture(scope="module")
def migrated_engine(postgres_url: str) -> sa.Engine:
    """Run alembic upgrade head and return a connected engine."""
    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", postgres_url)
    alembic_cmd.upgrade(cfg, "head")
    engine = sa.create_engine(postgres_url)
    yield engine
    engine.dispose()


def test_upgrade_head_runs_clean(migrated_engine: sa.Engine) -> None:
    """alembic upgrade head completes without error."""
    # If we got here the fixture ran without exception — that IS the test.
    assert migrated_engine is not None


def test_all_phase1_tables_exist(migrated_engine: sa.Engine) -> None:
    """All Phase 1 tables are present after migration."""
    inspector = sa.inspect(migrated_engine)
    actual_tables = set(inspector.get_table_names())
    missing = EXPECTED_TABLES - actual_tables
    assert not missing, f"Missing tables after migration: {missing}"


@pytest.mark.parametrize("table_name", sorted(EXPECTED_TABLES))
def test_required_columns_exist(migrated_engine: sa.Engine, table_name: str) -> None:
    """Each Phase 1 table has its required columns."""
    inspector = sa.inspect(migrated_engine)
    actual_cols = {col["name"] for col in inspector.get_columns(table_name)}
    expected = REQUIRED_COLUMNS[table_name]
    missing = expected - actual_cols
    assert not missing, f"Table '{table_name}' is missing columns: {missing}"


def test_reviews_status_is_enum(migrated_engine: sa.Engine) -> None:
    """reviews.status column uses the review_status enum type."""
    inspector = sa.inspect(migrated_engine)
    cols = {c["name"]: c for c in inspector.get_columns("reviews")}
    status_col = cols["status"]
    # The type name should reflect a PostgreSQL enum
    assert "review_status" in str(status_col["type"]).lower() or hasattr(status_col["type"], "enums"), (
        f"reviews.status should be an enum, got: {status_col['type']}"
    )


def test_installation_id_scoping(migrated_engine: sa.Engine) -> None:
    """All tables that need installation_id scoping have it (directly or via FK chain)."""
    inspector = sa.inspect(migrated_engine)

    # Direct installation_id column: installations, repos, webhook_events, audit_log
    direct_scoped = {"installations", "webhook_events", "audit_log"}
    for table in direct_scoped:
        cols = {c["name"] for c in inspector.get_columns(table)}
        assert "installation_id" in cols or table == "installations", (
            f"Table '{table}' is missing installation_id for tenant scoping"
        )

    # repos must have installation_id FK
    repos_cols = {c["name"] for c in inspector.get_columns("repos")}
    assert "installation_id" in repos_cols, "repos must have installation_id for tenant scoping"

    # reviews scoped via repo_id → repos → installation_id
    reviews_cols = {c["name"] for c in inspector.get_columns("reviews")}
    assert "repo_id" in reviews_cols, "reviews must have repo_id (chains to installation_id)"

    # findings scoped via review_id → reviews → repo_id → installation_id
    findings_cols = {c["name"] for c in inspector.get_columns("findings")}
    assert "review_id" in findings_cols, "findings must have review_id (chains to installation_id)"


def test_webhook_events_delivery_id_unique(migrated_engine: sa.Engine) -> None:
    """webhook_events.delivery_id has a unique constraint for idempotency."""
    inspector = sa.inspect(migrated_engine)
    unique_constraints = inspector.get_unique_constraints("webhook_events")
    unique_cols = {col for uc in unique_constraints for col in uc["column_names"]}
    # Also check indexes
    indexes = inspector.get_indexes("webhook_events")
    for idx in indexes:
        if idx.get("unique"):
            unique_cols.update(idx["column_names"])
    assert "delivery_id" in unique_cols, "webhook_events.delivery_id must be unique for idempotency"
