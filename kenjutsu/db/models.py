"""SQLAlchemy ORM models for all Phase 1 tables.

Table layout follows the data model in kenjutsu-architecture-v3.md § 10.
All tables are scoped by installation_id — either directly or via FK chain.

Note: github_review_id and github_comment_ids are added here (DEM-150).
The base schema (DEM-141) provides all other columns; DEM-150 adds the
publishing-state columns needed for idempotent GitHub review publishing.

Uses SQLAlchemy 2.0 Mapped annotations for full Pyright compatibility.
"""

import enum
from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


metadata = Base.metadata


class ReviewStatus(enum.StrEnum):
    queued = "queued"
    processing = "processing"
    complete = "complete"
    failed = "failed"
    superseded = "superseded"
    aborted = "aborted"


# ---------------------------------------------------------------------------
# installations — tenants
# ---------------------------------------------------------------------------


class Installation(Base):
    __tablename__ = "installations"

    id: Mapped[UUID] = mapped_column(
        sa.Uuid(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")
    )
    github_id: Mapped[int] = mapped_column(sa.BigInteger, nullable=False, unique=True)
    account_name: Mapped[str] = mapped_column(sa.Text, nullable=False)
    account_type: Mapped[str] = mapped_column(sa.Text, nullable=False)
    plan: Mapped[str] = mapped_column(sa.Text, nullable=False)
    settings_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default=sa.text("'{}'"))
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")
    )


# ---------------------------------------------------------------------------
# repos — enabled repos per installation
# ---------------------------------------------------------------------------


class Repo(Base):
    __tablename__ = "repos"

    id: Mapped[UUID] = mapped_column(
        sa.Uuid(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")
    )
    installation_id: Mapped[UUID] = mapped_column(
        sa.Uuid(as_uuid=True),
        sa.ForeignKey("installations.id", ondelete="CASCADE"),
        nullable=False,
    )
    github_id: Mapped[int] = mapped_column(sa.BigInteger, nullable=False, unique=True)
    full_name: Mapped[str] = mapped_column(sa.Text, nullable=False)
    default_branch: Mapped[str] = mapped_column(sa.Text, nullable=False, server_default=sa.text("'main'"))
    config_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default=sa.text("'{}'"))
    mirror_path: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    active_index_version: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    indexed_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True), nullable=True)


# ---------------------------------------------------------------------------
# reviews — one per PR review run
# ---------------------------------------------------------------------------


class Review(Base):
    __tablename__ = "reviews"

    id: Mapped[UUID] = mapped_column(
        sa.Uuid(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")
    )
    repo_id: Mapped[UUID] = mapped_column(
        sa.Uuid(as_uuid=True),
        sa.ForeignKey("repos.id", ondelete="CASCADE"),
        nullable=False,
    )
    pr_number: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    head_sha: Mapped[str] = mapped_column(sa.Text, nullable=False)
    base_sha: Mapped[str] = mapped_column(sa.Text, nullable=False)
    index_version_id: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    context_source: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    trigger: Mapped[str] = mapped_column(sa.Text, nullable=False)
    status: Mapped[ReviewStatus] = mapped_column(
        sa.Enum(ReviewStatus, name="review_status"),
        nullable=False,
        default=ReviewStatus.queued,
    )
    model_used: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    tokens_in: Mapped[int | None] = mapped_column(sa.Integer, nullable=True)
    tokens_out: Mapped[int | None] = mapped_column(sa.Integer, nullable=True)
    cost_usd: Mapped[Decimal | None] = mapped_column(sa.Numeric(12, 6), nullable=True)
    latency_ms_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    findings_raw_count: Mapped[int | None] = mapped_column(sa.Integer, nullable=True)
    findings_published_count: Mapped[int | None] = mapped_column(sa.Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")
    )
    # Publishing state — added in DEM-150
    github_review_id: Mapped[int | None] = mapped_column(sa.BigInteger, nullable=True)
    # finding_id (str) → comment_id (int)
    github_comment_ids: Mapped[dict[str, int] | None] = mapped_column(JSONB, nullable=True)


# ---------------------------------------------------------------------------
# findings — individual review findings
# ---------------------------------------------------------------------------


class Finding(Base):
    __tablename__ = "findings"

    id: Mapped[UUID] = mapped_column(
        sa.Uuid(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")
    )
    review_id: Mapped[UUID] = mapped_column(
        sa.Uuid(as_uuid=True),
        sa.ForeignKey("reviews.id", ondelete="CASCADE"),
        nullable=False,
    )
    fingerprint: Mapped[str] = mapped_column(sa.Text, nullable=False)
    file_path: Mapped[str] = mapped_column(sa.Text, nullable=False)
    line_start: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    line_end: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    origin: Mapped[str] = mapped_column(sa.Text, nullable=False)
    confidence: Mapped[str] = mapped_column(sa.Text, nullable=False)
    severity: Mapped[str] = mapped_column(sa.Text, nullable=False)
    category: Mapped[str] = mapped_column(sa.Text, nullable=False)
    publishability: Mapped[str] = mapped_column(sa.Text, nullable=False)
    description: Mapped[str] = mapped_column(sa.Text, nullable=False)
    suggestion: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    evidence_sources_json: Mapped[list[str]] = mapped_column(JSONB, nullable=False, server_default=sa.text("'[]'"))
    published: Mapped[bool] = mapped_column(sa.Boolean, nullable=False, server_default=sa.text("false"))
    github_comment_id: Mapped[int | None] = mapped_column(sa.BigInteger, nullable=True)


# ---------------------------------------------------------------------------
# suppressions — per-repo fingerprint suppressions
# ---------------------------------------------------------------------------


class Suppression(Base):
    __tablename__ = "suppressions"

    id: Mapped[UUID] = mapped_column(
        sa.Uuid(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")
    )
    repo_id: Mapped[UUID] = mapped_column(
        sa.Uuid(as_uuid=True),
        sa.ForeignKey("repos.id", ondelete="CASCADE"),
        nullable=False,
    )
    fingerprint: Mapped[str] = mapped_column(sa.Text, nullable=False)
    suppressed_by: Mapped[str] = mapped_column(sa.Text, nullable=False)
    reason: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")
    )


# ---------------------------------------------------------------------------
# webhook_events — raw durable log of all GitHub webhook deliveries
# ---------------------------------------------------------------------------


class WebhookEvent(Base):
    __tablename__ = "webhook_events"

    id: Mapped[UUID] = mapped_column(
        sa.Uuid(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")
    )
    delivery_id: Mapped[str] = mapped_column(sa.Text, nullable=False, unique=True)
    installation_id: Mapped[UUID] = mapped_column(
        sa.Uuid(as_uuid=True),
        sa.ForeignKey("installations.id", ondelete="CASCADE"),
        nullable=False,
    )
    event_type: Mapped[str] = mapped_column(sa.Text, nullable=False)
    payload_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    processed: Mapped[bool] = mapped_column(sa.Boolean, nullable=False, server_default=sa.text("false"))
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")
    )


# ---------------------------------------------------------------------------
# audit_log — immutable per-installation audit trail
# ---------------------------------------------------------------------------


class AuditLog(Base):
    __tablename__ = "audit_log"

    id: Mapped[UUID] = mapped_column(
        sa.Uuid(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")
    )
    installation_id: Mapped[UUID] = mapped_column(
        sa.Uuid(as_uuid=True),
        sa.ForeignKey("installations.id", ondelete="CASCADE"),
        nullable=False,
    )
    repo_id: Mapped[UUID | None] = mapped_column(sa.Uuid(as_uuid=True), nullable=True)
    action: Mapped[str] = mapped_column(sa.Text, nullable=False)
    detail_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default=sa.text("'{}'"))
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")
    )
