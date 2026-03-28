"""Immutable audit logging for every review completion.

Audit records are append-only — no updates or deletes. Every call to
write_audit_record inserts a new row; the table has no update/delete paths
exposed through this module.

Schema (from DEM-141):
    audit_log(id UUID PK, installation_id UUID FK, repo_id UUID,
              action TEXT, detail_json JSONB, created_at TIMESTAMPTZ)
"""

from __future__ import annotations

import json
import uuid  # noqa: TC003 — needed by Pydantic at runtime for UUID field validation
from enum import StrEnum
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel

if TYPE_CHECKING:
    from psycopg import Connection


class AuditAction(StrEnum):
    """Actions that produce an audit record."""

    REVIEW_COMPLETE = "review_complete"


class AuditRecord(BaseModel):
    """Data for a single immutable audit entry."""

    installation_id: uuid.UUID
    repo_id: uuid.UUID
    action: AuditAction
    detail_json: dict[str, Any]


def write_audit_record(conn: Connection, record: AuditRecord) -> uuid.UUID:
    """Insert an immutable audit record and return its generated id.

    Uses RETURNING id so the caller can reference the new row without
    a second query. created_at is set by the DB default (NOW()).

    Args:
        conn: Open psycopg connection (caller owns the transaction).
        record: The audit data to persist.

    Returns:
        The UUID of the newly created audit_log row.
    """
    sql = """
        INSERT INTO audit_log (installation_id, repo_id, action, detail_json)
        VALUES (%s, %s, %s, %s)
        RETURNING id
    """
    with conn.cursor() as cur:
        cur.execute(
            sql,
            (
                record.installation_id,
                record.repo_id,
                record.action,
                json.dumps(record.detail_json),
            ),
        )
        row = cur.fetchone()
    return row[0]  # type: ignore[index]
