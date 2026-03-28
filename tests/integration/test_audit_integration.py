"""Integration tests: review completion writes an audit record to PostgreSQL.

Spins up a real PostgreSQL instance via Testcontainers. Creates the audit_log
table directly (Alembic migrations live in DEM-141; here we just need the
table to exist to verify our write path).
"""

from __future__ import annotations

import uuid

import psycopg
import pytest
from psycopg.rows import dict_row

from kenjutsu.publisher.audit import AuditAction, AuditRecord, write_audit_record


@pytest.fixture(scope="module")
def pg_conn(postgres_dsn: str):
    """Module-scoped psycopg connection with audit_log table pre-created."""
    with psycopg.connect(postgres_dsn, autocommit=False) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS audit_log (
                    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    installation_id UUID NOT NULL,
                    repo_id     UUID NOT NULL,
                    action      TEXT NOT NULL,
                    detail_json JSONB NOT NULL DEFAULT '{}',
                    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
            """)
        conn.commit()
        yield conn


def _sample_record() -> AuditRecord:
    return AuditRecord(
        installation_id=uuid.uuid4(),
        repo_id=uuid.uuid4(),
        action=AuditAction.REVIEW_COMPLETE,
        detail_json={
            "findings_count": 4,
            "model_used": "claude-sonnet-4-6",
            "cost_usd": 0.0023,
            "latency_ms": 2100,
        },
    )


class TestAuditRecordPersistence:
    def test_write_creates_row(self, pg_conn: psycopg.Connection) -> None:
        record = _sample_record()
        record_id = write_audit_record(pg_conn, record)
        pg_conn.commit()

        with pg_conn.cursor(row_factory=dict_row) as cur:
            cur.execute("SELECT * FROM audit_log WHERE id = %s", [record_id])
            row = cur.fetchone()

        assert row is not None
        assert row["id"] == record_id

    def test_write_persists_all_fields(self, pg_conn: psycopg.Connection) -> None:
        inst_id = uuid.uuid4()
        repo_id = uuid.uuid4()
        record = AuditRecord(
            installation_id=inst_id,
            repo_id=repo_id,
            action=AuditAction.REVIEW_COMPLETE,
            detail_json={"findings_count": 7, "model_used": "test", "cost_usd": 0.001, "latency_ms": 300},
        )
        record_id = write_audit_record(pg_conn, record)
        pg_conn.commit()

        with pg_conn.cursor(row_factory=dict_row) as cur:
            cur.execute("SELECT * FROM audit_log WHERE id = %s", [record_id])
            row = cur.fetchone()

        assert row["installation_id"] == inst_id
        assert row["repo_id"] == repo_id
        assert row["action"] == "review_complete"
        assert row["detail_json"]["findings_count"] == 7

    def test_created_at_set_by_db(self, pg_conn: psycopg.Connection) -> None:
        record_id = write_audit_record(pg_conn, _sample_record())
        pg_conn.commit()

        with pg_conn.cursor(row_factory=dict_row) as cur:
            cur.execute("SELECT created_at FROM audit_log WHERE id = %s", [record_id])
            row = cur.fetchone()

        assert row["created_at"] is not None

    def test_append_only_multiple_records(self, pg_conn: psycopg.Connection) -> None:
        """Each call creates a new row; no record is ever modified."""
        id1 = write_audit_record(pg_conn, _sample_record())
        id2 = write_audit_record(pg_conn, _sample_record())
        pg_conn.commit()

        assert id1 != id2

        with pg_conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM audit_log WHERE id IN (%s, %s)", [id1, id2])
            (count,) = cur.fetchone()  # type: ignore[misc]

        assert count == 2

    def test_detail_json_stored_as_jsonb(self, pg_conn: psycopg.Connection) -> None:
        """JSONB storage allows querying nested fields."""
        record = AuditRecord(
            installation_id=uuid.uuid4(),
            repo_id=uuid.uuid4(),
            action=AuditAction.REVIEW_COMPLETE,
            detail_json={"findings_count": 9, "model_used": "probe", "cost_usd": 0.0, "latency_ms": 50},
        )
        record_id = write_audit_record(pg_conn, record)
        pg_conn.commit()

        with pg_conn.cursor() as cur:
            cur.execute(
                "SELECT detail_json->>'model_used' FROM audit_log WHERE id = %s",
                [record_id],
            )
            (model_used,) = cur.fetchone()  # type: ignore[misc]

        assert model_used == "probe"
