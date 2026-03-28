"""SQLAlchemy ORM models for Kenjutsu.

Mirrors the canonical schema defined in the DEM-141 migration.
Only the models needed by the webhook server are defined here;
additional models (PR, Review, etc.) will be added in later phases.
"""

from __future__ import annotations

from sqlalchemy import Boolean, DateTime, ForeignKey, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.sql.expression import false, func, text


class Base(DeclarativeBase):
    """Shared declarative base for all ORM models."""


metadata = Base.metadata


class Installation(Base):
    """A GitHub App installation (one per org/user that installs Kenjutsu)."""

    __tablename__ = "installations"

    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    github_installation_id: Mapped[int] = mapped_column(nullable=False, unique=True)
    account_login: Mapped[str] = mapped_column(Text, nullable=False)
    account_type: Mapped[str] = mapped_column(Text, nullable=False)
    suspended: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=false())
    created_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class WebhookEvent(Base):
    """Raw GitHub webhook payloads, persisted for idempotent processing."""

    __tablename__ = "webhook_events"

    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    delivery_id: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    installation_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("installations.id"),
        nullable=False,
    )
    event_type: Mapped[str] = mapped_column(Text, nullable=False)
    payload_json: Mapped[dict] = mapped_column(JSONB, nullable=False)
    processed: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=false())
    created_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
