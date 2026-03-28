"""Unit tests for the audit logging module.

Tests cover AuditRecord model validation and the write_audit_record
function contract (behavior, not DB interaction — that's in integration tests).
"""

from __future__ import annotations

import uuid
from unittest.mock import MagicMock

import pytest
from pydantic import ValidationError

from kenjutsu.publisher.audit import AuditAction, AuditRecord, write_audit_record


class TestAuditAction:
    def test_review_complete_value(self) -> None:
        assert AuditAction.REVIEW_COMPLETE == "review_complete"

    def test_all_expected_actions_present(self) -> None:
        assert set(AuditAction) == {"review_complete"}


class TestAuditRecord:
    def _make_record(self, **overrides: object) -> AuditRecord:
        defaults: dict[str, object] = {
            "installation_id": uuid.uuid4(),
            "repo_id": uuid.uuid4(),
            "action": AuditAction.REVIEW_COMPLETE,
            "detail_json": {
                "findings_count": 3,
                "model_used": "claude-3-5-haiku-20241022",
                "cost_usd": 0.0012,
                "latency_ms": 1850,
            },
        }
        defaults.update(overrides)
        return AuditRecord(**defaults)  # type: ignore[arg-type]

    def test_record_creation(self) -> None:
        record = self._make_record()
        assert record.action == AuditAction.REVIEW_COMPLETE
        assert record.detail_json["findings_count"] == 3

    def test_installation_id_required(self) -> None:
        with pytest.raises(ValidationError):
            AuditRecord(  # type: ignore[call-arg]
                repo_id=uuid.uuid4(),
                action=AuditAction.REVIEW_COMPLETE,
                detail_json={},
            )

    def test_repo_id_required(self) -> None:
        with pytest.raises(ValidationError):
            AuditRecord(  # type: ignore[call-arg]
                installation_id=uuid.uuid4(),
                action=AuditAction.REVIEW_COMPLETE,
                detail_json={},
            )

    def test_action_required(self) -> None:
        with pytest.raises(ValidationError):
            AuditRecord(  # type: ignore[call-arg]
                installation_id=uuid.uuid4(),
                repo_id=uuid.uuid4(),
                detail_json={},
            )

    def test_detail_json_required(self) -> None:
        with pytest.raises(ValidationError):
            AuditRecord(  # type: ignore[call-arg]
                installation_id=uuid.uuid4(),
                repo_id=uuid.uuid4(),
                action=AuditAction.REVIEW_COMPLETE,
            )

    def test_detail_json_empty_dict_is_valid(self) -> None:
        record = self._make_record(detail_json={})
        assert record.detail_json == {}

    def test_installation_id_must_be_uuid(self) -> None:
        with pytest.raises(ValidationError):
            self._make_record(installation_id="not-a-uuid")

    def test_repo_id_must_be_uuid(self) -> None:
        with pytest.raises(ValidationError):
            self._make_record(repo_id="not-a-uuid")

    def test_detail_json_preserves_nested_data(self) -> None:
        detail = {
            "findings_count": 5,
            "model_used": "claude-opus-4-6",
            "cost_usd": 0.045,
            "latency_ms": 4200,
            "per_stage": {"analysis": 1200, "publish": 300},
        }
        record = self._make_record(detail_json=detail)
        assert record.detail_json["per_stage"]["analysis"] == 1200


class TestWriteAuditRecord:
    def _make_record(self) -> AuditRecord:
        return AuditRecord(
            installation_id=uuid.uuid4(),
            repo_id=uuid.uuid4(),
            action=AuditAction.REVIEW_COMPLETE,
            detail_json={"findings_count": 2, "model_used": "test-model", "cost_usd": 0.001, "latency_ms": 500},
        )

    def test_returns_uuid(self) -> None:
        """write_audit_record must return the id of the created record."""
        conn = MagicMock()
        cursor = MagicMock()
        conn.cursor.return_value.__enter__ = MagicMock(return_value=cursor)
        conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        new_id = uuid.uuid4()
        cursor.fetchone.return_value = (new_id,)

        result = write_audit_record(conn, self._make_record())

        assert isinstance(result, uuid.UUID)

    def test_executes_insert(self) -> None:
        """write_audit_record must execute an INSERT into audit_log."""
        conn = MagicMock()
        cursor = MagicMock()
        conn.cursor.return_value.__enter__ = MagicMock(return_value=cursor)
        conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        cursor.fetchone.return_value = (uuid.uuid4(),)

        write_audit_record(conn, self._make_record())

        assert cursor.execute.called
        sql = cursor.execute.call_args[0][0]
        assert "INSERT" in sql.upper()
        assert "audit_log" in sql

    def test_passes_correct_fields(self) -> None:
        """write_audit_record must pass all AuditRecord fields to the query."""
        conn = MagicMock()
        cursor = MagicMock()
        conn.cursor.return_value.__enter__ = MagicMock(return_value=cursor)
        conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        cursor.fetchone.return_value = (uuid.uuid4(),)

        inst_id = uuid.uuid4()
        repo_id = uuid.uuid4()
        record = AuditRecord(
            installation_id=inst_id,
            repo_id=repo_id,
            action=AuditAction.REVIEW_COMPLETE,
            detail_json={"findings_count": 1, "model_used": "m", "cost_usd": 0.0, "latency_ms": 100},
        )

        write_audit_record(conn, record)

        params = cursor.execute.call_args[0][1]
        assert str(inst_id) in str(params) or inst_id in params
        assert str(repo_id) in str(params) or repo_id in params

    def test_no_update_or_delete_exposed(self) -> None:
        """Audit module must not export any update or delete function."""
        import kenjutsu.publisher.audit as audit_module

        for attr in dir(audit_module):
            assert "update" not in attr.lower(), f"Unexpected update function: {attr}"
            assert "delete" not in attr.lower(), f"Unexpected delete function: {attr}"
