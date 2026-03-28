"""Unit tests for CheckRunPublisher orchestration logic.

Tests exercise the publisher's lifecycle (create → annotate → complete)
using AsyncMock for the CheckRunClient protocol. No HTTP boundary is crossed;
these tests verify call sequencing, payload shape, and batching behaviour.

Real HTTP-boundary integration tests (e.g. Testcontainers + WireMock) are
tracked as a follow-on item.
"""

from __future__ import annotations

from unittest.mock import AsyncMock

from kenjutsu.models.findings import (
    Category,
    Confidence,
    Finding,
    Origin,
    Publishability,
    Severity,
)
from kenjutsu.publisher.check_run import ANNOTATION_BATCH_SIZE, CheckRunPublisher

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_client(check_run_id: int = 42) -> AsyncMock:
    client = AsyncMock()
    client.create_check_run.return_value = {"id": check_run_id}
    client.update_check_run.return_value = {}
    return client


def _make_finding(**overrides: object) -> Finding:
    defaults: dict[str, object] = {
        "file_path": "src/auth.py",
        "line_start": 10,
        "line_end": 12,
        "origin": Origin.LLM,
        "confidence": Confidence.HIGH,
        "severity": Severity.WARNING,
        "category": Category.BUG,
        "description": "Potential null dereference",
    }
    defaults.update(overrides)
    return Finding(**defaults)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# create()
# ---------------------------------------------------------------------------


class TestCreate:
    async def test_create_posts_to_github(self) -> None:
        client = _make_client(check_run_id=99)
        publisher = CheckRunPublisher(client, owner="acme", repo="api", head_sha="abc123")

        run_id = await publisher.create()

        assert run_id == 99
        client.create_check_run.assert_called_once()
        args = client.create_check_run.call_args
        owner, repo, payload = args[0]
        assert owner == "acme"
        assert repo == "api"
        assert payload["head_sha"] == "abc123"
        assert payload["status"] == "in_progress"
        assert "started_at" in payload

    async def test_create_uses_custom_name(self) -> None:
        client = _make_client()
        publisher = CheckRunPublisher(client, owner="acme", repo="api", head_sha="sha")

        await publisher.create(name="Custom Name")

        payload = client.create_check_run.call_args[0][2]
        assert payload["name"] == "Custom Name"

    async def test_create_uses_default_name(self) -> None:
        client = _make_client()
        publisher = CheckRunPublisher(client, owner="acme", repo="api", head_sha="sha")

        await publisher.create()

        payload = client.create_check_run.call_args[0][2]
        assert "Kenjutsu" in payload["name"]


# ---------------------------------------------------------------------------
# update_with_annotations()
# ---------------------------------------------------------------------------


class TestUpdateWithAnnotations:
    async def test_no_publishable_findings_skips_api_call(self) -> None:
        client = _make_client()
        publisher = CheckRunPublisher(client, owner="a", repo="r", head_sha="s")
        suppressed = _make_finding(publishability=Publishability.SUPPRESS)

        await publisher.update_with_annotations(check_run_id=1, findings=[suppressed])

        client.update_check_run.assert_not_called()

    async def test_single_batch_of_findings(self) -> None:
        client = _make_client()
        publisher = CheckRunPublisher(client, owner="a", repo="r", head_sha="s")
        findings = [_make_finding() for _ in range(3)]

        await publisher.update_with_annotations(check_run_id=1, findings=findings)

        client.update_check_run.assert_called_once()
        _owner, _repo, _id, payload = client.update_check_run.call_args[0]
        assert len(payload["output"]["annotations"]) == 3

    async def test_large_batch_splits_into_multiple_calls(self) -> None:
        client = _make_client()
        publisher = CheckRunPublisher(client, owner="a", repo="r", head_sha="s")
        count = ANNOTATION_BATCH_SIZE + 5
        findings = [_make_finding() for _ in range(count)]

        await publisher.update_with_annotations(check_run_id=1, findings=findings)

        assert client.update_check_run.call_count == 2
        first_batch = client.update_check_run.call_args_list[0][0][3]["output"]["annotations"]
        second_batch = client.update_check_run.call_args_list[1][0][3]["output"]["annotations"]
        assert len(first_batch) == ANNOTATION_BATCH_SIZE
        assert len(second_batch) == 5

    async def test_predictive_findings_excluded_from_annotations(self) -> None:
        client = _make_client()
        publisher = CheckRunPublisher(client, owner="a", repo="r", head_sha="s")
        defect = _make_finding(origin=Origin.LLM)
        predictive = _make_finding(origin=Origin.PREDICTIVE)

        await publisher.update_with_annotations(check_run_id=1, findings=[defect, predictive])

        client.update_check_run.assert_called_once()
        annotations = client.update_check_run.call_args[0][3]["output"]["annotations"]
        assert len(annotations) == 1


# ---------------------------------------------------------------------------
# complete()
# ---------------------------------------------------------------------------


class TestComplete:
    async def test_complete_calls_update_with_completed_status(self) -> None:
        client = _make_client()
        publisher = CheckRunPublisher(client, owner="a", repo="r", head_sha="s")

        await publisher.complete(
            check_run_id=1,
            findings=[],
            predictive_warnings=[],
            duration_seconds=5.0,
        )

        client.update_check_run.assert_called()
        payload = client.update_check_run.call_args[0][3]
        assert payload["status"] == "completed"
        assert "completed_at" in payload

    async def test_complete_no_findings_conclusion_is_success(self) -> None:
        client = _make_client()
        publisher = CheckRunPublisher(client, owner="a", repo="r", head_sha="s")

        await publisher.complete(check_run_id=1, findings=[], predictive_warnings=[], duration_seconds=1.0)

        payload = client.update_check_run.call_args[0][3]
        assert payload["conclusion"] == "success"

    async def test_complete_critical_finding_conclusion_is_failure(self) -> None:
        client = _make_client()
        publisher = CheckRunPublisher(client, owner="a", repo="r", head_sha="s")
        findings = [_make_finding(severity=Severity.CRITICAL)]

        await publisher.complete(check_run_id=1, findings=findings, predictive_warnings=[], duration_seconds=1.0)

        payload = client.update_check_run.call_args[0][3]
        assert payload["conclusion"] == "failure"

    async def test_complete_title_includes_stats(self) -> None:
        client = _make_client()
        publisher = CheckRunPublisher(client, owner="a", repo="r", head_sha="s")
        findings = [_make_finding() for _ in range(3)]

        await publisher.complete(check_run_id=1, findings=findings, predictive_warnings=[], duration_seconds=4.2)

        payload = client.update_check_run.call_args[0][3]
        title = payload["output"]["title"]
        assert "3" in title
        assert "4.2" in title

    async def test_complete_predictive_warnings_in_summary_only(self) -> None:
        client = _make_client()
        publisher = CheckRunPublisher(client, owner="a", repo="r", head_sha="s")
        pw = _make_finding(origin=Origin.PREDICTIVE, category=Category.CO_CHANGE, description="Files co-change")

        await publisher.complete(
            check_run_id=1,
            findings=[],
            predictive_warnings=[pw],
            duration_seconds=1.0,
        )

        payload = client.update_check_run.call_args[0][3]
        summary = payload["output"]["summary"]
        # Predictive warning appears in summary text
        assert "Files co-change" in summary
        # Completion PATCH sends no annotations — all annotations were streamed earlier
        assert "annotations" not in payload["output"]

    async def test_complete_sends_no_annotations(self) -> None:
        """complete() must not re-send annotations that were already streamed."""
        client = _make_client()
        publisher = CheckRunPublisher(client, owner="a", repo="r", head_sha="s")
        findings = [_make_finding() for _ in range(ANNOTATION_BATCH_SIZE + 10)]

        await publisher.complete(check_run_id=1, findings=findings, predictive_warnings=[], duration_seconds=2.0)

        completion_call = client.update_check_run.call_args_list[-1]
        payload = completion_call[0][3]
        assert payload["status"] == "completed"
        assert "annotations" not in payload["output"]


# ---------------------------------------------------------------------------
# Full workflow
# ---------------------------------------------------------------------------


class TestFullWorkflow:
    async def test_create_update_complete_workflow(self) -> None:
        """End-to-end: create → stream annotations → complete without re-sending annotations."""
        client = _make_client(check_run_id=77)
        publisher = CheckRunPublisher(client, owner="acme", repo="api", head_sha="deadbeef")

        # Step 1: create
        run_id = await publisher.create()
        assert run_id == 77

        # Step 2: stream findings as they arrive
        findings = [_make_finding(severity=Severity.WARNING) for _ in range(2)]
        await publisher.update_with_annotations(check_run_id=run_id, findings=findings)

        # Step 3: complete — pass findings for stats, no annotations re-sent
        pw = _make_finding(origin=Origin.PREDICTIVE, description="Likely missed test")
        await publisher.complete(
            check_run_id=run_id,
            findings=findings,
            predictive_warnings=[pw],
            duration_seconds=8.3,
        )

        # create called exactly once
        assert client.create_check_run.call_count == 1

        # update called twice: once for streaming annotations, once for completion
        assert client.update_check_run.call_count == 2

        # Final completion payload is correct
        final = client.update_check_run.call_args_list[-1][0][3]
        assert final["status"] == "completed"
        assert final["conclusion"] == "neutral"  # warnings → neutral
        assert "Likely missed test" in final["output"]["summary"]
        # Completion does not re-send annotations
        assert "annotations" not in final["output"]
