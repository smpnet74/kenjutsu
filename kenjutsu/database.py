"""Database engine and session factory.

Reads DATABASE_URL from the environment. When the variable is absent
(unit tests, local dev without Postgres) the module is importable but
creating a session will fail at runtime, which is the correct behaviour.
"""

from __future__ import annotations

import os

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker


def _get_database_url() -> str:
    url = os.environ.get("DATABASE_URL", "")
    if not url:
        raise RuntimeError(
            "DATABASE_URL environment variable is not set. "
            "Set it to a PostgreSQL connection string, e.g. "
            "postgres://user:password@host:5432/dbname"
        )
    # psycopg3 uses postgresql:// scheme; normalise legacy postgres:// prefix
    if url.startswith("postgres://"):
        url = "postgresql+psycopg" + url[len("postgres") :]
    elif url.startswith("postgresql://") and "+psycopg" not in url:
        url = url.replace("postgresql://", "postgresql+psycopg://", 1)
    return url


# Lazy engine — instantiated on first use so tests that never touch the DB
# do not require DATABASE_URL to be set.
_engine = None
_SessionLocal = None


def get_engine():
    global _engine
    if _engine is None:
        _engine = create_engine(_get_database_url(), pool_pre_ping=True)
    return _engine


def get_session_factory():
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=get_engine())
    return _SessionLocal


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""
