"""Initial Phase 1 schema: installations, repos, reviews, findings, suppressions, webhook_events, audit_log.

Revision ID: 0001
Revises:
Create Date: 2026-03-25

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Enable pgcrypto for gen_random_uuid()
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")

    # ---------------------------------------------------------------------------
    # review_status enum
    # ---------------------------------------------------------------------------
    # Create the enum type directly in PostgreSQL
    op.execute(
        "CREATE TYPE review_status AS ENUM ('queued', 'processing', 'complete', 'failed', 'superseded', 'aborted')"
    )

    # ---------------------------------------------------------------------------
    # installations
    # ---------------------------------------------------------------------------
    op.create_table(
        "installations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("github_id", sa.BigInteger, nullable=False),
        sa.Column("account_name", sa.Text, nullable=False),
        sa.Column("account_type", sa.Text, nullable=False),
        sa.Column("plan", sa.Text, nullable=False),
        sa.Column("settings_json", postgresql.JSONB, nullable=False, server_default=sa.text("'{}'")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("github_id", name="uq_installations_github_id"),
    )

    # ---------------------------------------------------------------------------
    # repos
    # ---------------------------------------------------------------------------
    op.create_table(
        "repos",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("installation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("github_id", sa.BigInteger, nullable=False),
        sa.Column("full_name", sa.Text, nullable=False),
        sa.Column("default_branch", sa.Text, nullable=False, server_default=sa.text("'main'")),
        sa.Column("config_json", postgresql.JSONB, nullable=False, server_default=sa.text("'{}'")),
        sa.Column("mirror_path", sa.Text, nullable=True),
        sa.Column("active_index_version", sa.Text, nullable=True),
        sa.Column("indexed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["installation_id"], ["installations.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("github_id", name="uq_repos_github_id"),
    )
    op.create_index("ix_repos_installation_id", "repos", ["installation_id"])

    # ---------------------------------------------------------------------------
    # reviews
    # ---------------------------------------------------------------------------
    op.create_table(
        "reviews",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("repo_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("pr_number", sa.Integer, nullable=False),
        sa.Column("head_sha", sa.Text, nullable=False),
        sa.Column("base_sha", sa.Text, nullable=False),
        sa.Column("index_version_id", sa.Text, nullable=True),
        sa.Column("context_source", sa.Text, nullable=True),
        sa.Column("trigger", sa.Text, nullable=False),
        sa.Column(
            "status",
            postgresql.ENUM(
                name="review_status",
                create_type=False,
            ),
            nullable=False,
            server_default="queued",
        ),
        sa.Column("model_used", sa.Text, nullable=True),
        sa.Column("tokens_in", sa.Integer, nullable=True),
        sa.Column("tokens_out", sa.Integer, nullable=True),
        sa.Column("cost_usd", sa.Numeric(12, 6), nullable=True),
        sa.Column("latency_ms_json", postgresql.JSONB, nullable=True),
        sa.Column("findings_raw_count", sa.Integer, nullable=True),
        sa.Column("findings_published_count", sa.Integer, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["repo_id"], ["repos.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_reviews_repo_id", "reviews", ["repo_id"])
    op.create_index("ix_reviews_head_sha", "reviews", ["head_sha"])

    # ---------------------------------------------------------------------------
    # findings
    # ---------------------------------------------------------------------------
    op.create_table(
        "findings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("review_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("fingerprint", sa.Text, nullable=False),
        sa.Column("file_path", sa.Text, nullable=False),
        sa.Column("line_start", sa.Integer, nullable=False),
        sa.Column("line_end", sa.Integer, nullable=False),
        sa.Column("origin", sa.Text, nullable=False),
        sa.Column("confidence", sa.Text, nullable=False),
        sa.Column("severity", sa.Text, nullable=False),
        sa.Column("category", sa.Text, nullable=False),
        sa.Column("publishability", sa.Text, nullable=False),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("suggestion", sa.Text, nullable=True),
        sa.Column("evidence_sources_json", postgresql.JSONB, nullable=False, server_default=sa.text("'[]'")),
        sa.Column("published", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("github_comment_id", sa.BigInteger, nullable=True),
        sa.ForeignKeyConstraint(["review_id"], ["reviews.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_findings_review_id", "findings", ["review_id"])
    op.create_index("ix_findings_fingerprint", "findings", ["fingerprint"])

    # ---------------------------------------------------------------------------
    # suppressions
    # ---------------------------------------------------------------------------
    op.create_table(
        "suppressions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("repo_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("fingerprint", sa.Text, nullable=False),
        sa.Column("suppressed_by", sa.Text, nullable=False),
        sa.Column("reason", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["repo_id"], ["repos.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_suppressions_repo_id_fingerprint", "suppressions", ["repo_id", "fingerprint"])

    # ---------------------------------------------------------------------------
    # webhook_events
    # ---------------------------------------------------------------------------
    op.create_table(
        "webhook_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("delivery_id", sa.Text, nullable=False),
        sa.Column("installation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("event_type", sa.Text, nullable=False),
        sa.Column("payload_json", postgresql.JSONB, nullable=False),
        sa.Column("processed", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["installation_id"], ["installations.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("delivery_id", name="uq_webhook_events_delivery_id"),
    )
    op.create_index("ix_webhook_events_installation_id", "webhook_events", ["installation_id"])

    # ---------------------------------------------------------------------------
    # audit_log
    # ---------------------------------------------------------------------------
    op.create_table(
        "audit_log",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("installation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("repo_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("action", sa.Text, nullable=False),
        sa.Column("detail_json", postgresql.JSONB, nullable=False, server_default=sa.text("'{}'")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["installation_id"], ["installations.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_audit_log_installation_id", "audit_log", ["installation_id"])


def downgrade() -> None:
    op.drop_table("audit_log")
    op.drop_table("webhook_events")
    op.drop_table("suppressions")
    op.drop_table("findings")
    op.drop_table("reviews")
    op.drop_table("repos")
    op.drop_table("installations")
    op.execute("DROP TYPE IF EXISTS review_status CASCADE")
