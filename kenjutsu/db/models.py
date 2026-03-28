"""SQLAlchemy ORM models for all Phase 1 tables.

Table layout follows the data model in kenjutsu-architecture-v3.md § 10.
All tables are scoped by installation_id — either directly or via FK chain.
"""

from __future__ import annotations

import enum

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase


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

    id = sa.Column(UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()"))
    github_id = sa.Column(sa.BigInteger, nullable=False, unique=True)
    account_name = sa.Column(sa.Text, nullable=False)
    account_type = sa.Column(sa.Text, nullable=False)
    plan = sa.Column(sa.Text, nullable=False)
    settings_json = sa.Column(JSONB, nullable=False, server_default=sa.text("'{}'"))
    created_at = sa.Column(sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()"))


# ---------------------------------------------------------------------------
# repos — enabled repos per installation
# ---------------------------------------------------------------------------


class Repo(Base):
    __tablename__ = "repos"

    id = sa.Column(UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()"))
    installation_id = sa.Column(
        UUID(as_uuid=True), sa.ForeignKey("installations.id", ondelete="CASCADE"), nullable=False
    )
    github_id = sa.Column(sa.BigInteger, nullable=False, unique=True)
    full_name = sa.Column(sa.Text, nullable=False)
    default_branch = sa.Column(sa.Text, nullable=False, server_default=sa.text("'main'"))
    config_json = sa.Column(JSONB, nullable=False, server_default=sa.text("'{}'"))
    mirror_path = sa.Column(sa.Text, nullable=True)
    active_index_version = sa.Column(sa.Text, nullable=True)
    indexed_at = sa.Column(sa.DateTime(timezone=True), nullable=True)


# ---------------------------------------------------------------------------
# reviews — one per PR review run
# ---------------------------------------------------------------------------


class Review(Base):
    __tablename__ = "reviews"

    id = sa.Column(UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()"))
    repo_id = sa.Column(UUID(as_uuid=True), sa.ForeignKey("repos.id", ondelete="CASCADE"), nullable=False)
    pr_number = sa.Column(sa.Integer, nullable=False)
    head_sha = sa.Column(sa.Text, nullable=False)
    base_sha = sa.Column(sa.Text, nullable=False)
    index_version_id = sa.Column(sa.Text, nullable=True)
    context_source = sa.Column(sa.Text, nullable=True)
    trigger = sa.Column(sa.Text, nullable=False)
    status = sa.Column(
        sa.Enum(ReviewStatus, name="review_status", create_type=False),
        nullable=False,
        default=ReviewStatus.queued,
    )
    model_used = sa.Column(sa.Text, nullable=True)
    tokens_in = sa.Column(sa.Integer, nullable=True)
    tokens_out = sa.Column(sa.Integer, nullable=True)
    cost_usd = sa.Column(sa.Numeric(12, 6), nullable=True)
    latency_ms_json = sa.Column(JSONB, nullable=True)
    findings_raw_count = sa.Column(sa.Integer, nullable=True)
    findings_published_count = sa.Column(sa.Integer, nullable=True)
    created_at = sa.Column(sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()"))


# ---------------------------------------------------------------------------
# findings — individual review findings
# ---------------------------------------------------------------------------


class Finding(Base):
    __tablename__ = "findings"

    id = sa.Column(UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()"))
    review_id = sa.Column(UUID(as_uuid=True), sa.ForeignKey("reviews.id", ondelete="CASCADE"), nullable=False)
    fingerprint = sa.Column(sa.Text, nullable=False)
    file_path = sa.Column(sa.Text, nullable=False)
    line_start = sa.Column(sa.Integer, nullable=False)
    line_end = sa.Column(sa.Integer, nullable=False)
    origin = sa.Column(sa.Text, nullable=False)
    confidence = sa.Column(sa.Text, nullable=False)
    severity = sa.Column(sa.Text, nullable=False)
    category = sa.Column(sa.Text, nullable=False)
    publishability = sa.Column(sa.Text, nullable=False)
    description = sa.Column(sa.Text, nullable=False)
    suggestion = sa.Column(sa.Text, nullable=True)
    evidence_sources_json = sa.Column(JSONB, nullable=False, server_default=sa.text("'[]'"))
    published = sa.Column(sa.Boolean, nullable=False, server_default=sa.text("false"))
    github_comment_id = sa.Column(sa.BigInteger, nullable=True)


# ---------------------------------------------------------------------------
# suppressions — per-repo fingerprint suppressions
# ---------------------------------------------------------------------------


class Suppression(Base):
    __tablename__ = "suppressions"

    id = sa.Column(UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()"))
    repo_id = sa.Column(UUID(as_uuid=True), sa.ForeignKey("repos.id", ondelete="CASCADE"), nullable=False)
    fingerprint = sa.Column(sa.Text, nullable=False)
    suppressed_by = sa.Column(sa.Text, nullable=False)
    reason = sa.Column(sa.Text, nullable=True)
    created_at = sa.Column(sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()"))


# ---------------------------------------------------------------------------
# webhook_events — raw durable log of all GitHub webhook deliveries
# ---------------------------------------------------------------------------


class WebhookEvent(Base):
    __tablename__ = "webhook_events"

    id = sa.Column(UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()"))
    delivery_id = sa.Column(sa.Text, nullable=False, unique=True)
    installation_id = sa.Column(
        UUID(as_uuid=True), sa.ForeignKey("installations.id", ondelete="CASCADE"), nullable=False
    )
    event_type = sa.Column(sa.Text, nullable=False)
    payload_json = sa.Column(JSONB, nullable=False)
    processed = sa.Column(sa.Boolean, nullable=False, server_default=sa.text("false"))
    created_at = sa.Column(sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()"))


# ---------------------------------------------------------------------------
# audit_log — immutable per-installation audit trail
# ---------------------------------------------------------------------------


class AuditLog(Base):
    __tablename__ = "audit_log"

    id = sa.Column(UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()"))
    installation_id = sa.Column(
        UUID(as_uuid=True), sa.ForeignKey("installations.id", ondelete="CASCADE"), nullable=False
    )
    repo_id = sa.Column(UUID(as_uuid=True), nullable=True)
    action = sa.Column(sa.Text, nullable=False)
    detail_json = sa.Column(JSONB, nullable=False, server_default=sa.text("'{}'"))
    created_at = sa.Column(sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()"))
