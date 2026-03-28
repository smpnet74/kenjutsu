"""Alembic environment configuration.

Reads DATABASE_URL from the environment and configures the migration
context. Supports both online (run against live DB) and offline
(generate SQL script) modes.
"""

from __future__ import annotations

import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

# this is the Alembic Config object
config = context.config

# Interpret the config file for Python logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Import the declarative Base so Alembic can detect schema changes.
# Models that add tables must import Base from kenjutsu.database and
# register themselves before this file runs.
from kenjutsu.database import Base  # noqa: E402

# Include all model modules here so their tables are reflected in Base.metadata.
# Add imports as models are created (DEM-141):
# from kenjutsu.models import ...  (uncomment as models are added in DEM-141)

target_metadata = Base.metadata


def _get_url() -> str:
    url = os.environ.get("DATABASE_URL", "")
    if not url:
        raise RuntimeError("DATABASE_URL must be set to run migrations")
    # Normalise to psycopg3 dialect
    if url.startswith("postgres://"):
        url = "postgresql+psycopg" + url[len("postgres") :]
    elif url.startswith("postgresql://") and "+psycopg" not in url:
        url = url.replace("postgresql://", "postgresql+psycopg://", 1)
    return url


def run_migrations_offline() -> None:
    """Run migrations without a live DB connection (generates SQL output)."""
    url = _get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations against the live database."""
    cfg = config.get_section(config.config_ini_section, {})
    cfg["sqlalchemy.url"] = _get_url()

    connectable = engine_from_config(
        cfg,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
