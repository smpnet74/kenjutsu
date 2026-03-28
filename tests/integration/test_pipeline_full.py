"""Integration tests — full review_pr pipeline through the DBOS runtime.

Each test exercises the complete review_pr workflow (or targeted sub-steps)
through a live DBOS instance backed by SQLite. Business logic stubs are
used; no GitHub API or database connections are required.

Status-transition sequencing is covered by unit tests (test_pipeline_workflow.py).
These tests focus on DBOS runtime correctness: end-to-end outcomes, SHA
guard abort/superseded paths, and step_update_status round-trips.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

# Register step decorators before DBOS launches.
import kenjutsu.pipeline.steps  # noqa: F401
from kenjutsu.pipeline.steps import (
    review_pr,
    step_update_status,
)
from kenjutsu.pipeline.types import PrMetadata, ReviewResult, ReviewStatus


@pytest.fixture()
def _dbos(dbos_instance: object) -> object:
    """Live DBOS runtime (SQLite) per test."""
    return dbos_instance


@pytest.fixture
def pr() -> PrMetadata:
    return PrMetadata(
        repo_id="int/repo",
        pr_number=99,
        base_sha="ccc333",
        head_sha="ddd444",
        repo_url="https://github.com/int/repo",
    )


# ---------------------------------------------------------------------------
# step_update_status through DBOS
# ---------------------------------------------------------------------------


class TestStepUpdateStatus:
    async def test_executes_without_error(self, _dbos: object) -> None:
        await step_update_status("rev-int-1", ReviewStatus.QUEUED)

    async def test_all_status_values_accepted(self, _dbos: object) -> None:
        for status in ReviewStatus:
            await step_update_status("rev-int-2", status)


# ---------------------------------------------------------------------------
# Happy path — stubs return empty findings
# ---------------------------------------------------------------------------


class TestFullPipelineHappyPath:
    async def test_workflow_returns_review_result(self, _dbos: object, pr: PrMetadata) -> None:
        result = await review_pr(pr, review_id="int-happy")
        assert isinstance(result, ReviewResult)

    async def test_workflow_published_status(self, _dbos: object, pr: PrMetadata) -> None:
        result = await review_pr(pr, review_id="int-published")
        assert result.status == "published"

    async def test_workflow_zero_findings_from_stubs(self, _dbos: object, pr: PrMetadata) -> None:
        result = await review_pr(pr, review_id="int-zero")
        assert result.finding_count == 0

    async def test_workflow_accepts_empty_review_id(self, _dbos: object, pr: PrMetadata) -> None:
        result = await review_pr(pr)  # review_id defaults to ""
        assert isinstance(result, ReviewResult)


# ---------------------------------------------------------------------------
# SHA guard failure at start → aborted
# ---------------------------------------------------------------------------


class TestFullPipelineShaGuardFailAtStart:
    async def test_returns_aborted(self, _dbos: object, pr: PrMetadata) -> None:
        with patch("kenjutsu.pipeline.steps.sha_guard", AsyncMock(return_value=False)):
            result = await review_pr(pr, review_id="int-abort")
        assert result.status == "aborted"
        assert result.reason == "stale_sha"

    async def test_publish_not_called_on_abort(self, _dbos: object, pr: PrMetadata) -> None:
        publish_mock = AsyncMock(return_value=ReviewResult(status="published", finding_count=0))
        with (
            patch("kenjutsu.pipeline.steps.sha_guard", AsyncMock(return_value=False)),
            patch("kenjutsu.pipeline.steps.publish", publish_mock),
        ):
            await review_pr(pr, review_id="int-abort-nopub")
        publish_mock.assert_not_called()


# ---------------------------------------------------------------------------
# Superseded — SHA changes before publish
# ---------------------------------------------------------------------------


class TestFullPipelineSuperseded:
    async def test_returns_superseded(self, _dbos: object, pr: PrMetadata) -> None:
        sha_mock = AsyncMock(side_effect=[True, False])
        with patch("kenjutsu.pipeline.steps.sha_guard", sha_mock):
            result = await review_pr(pr, review_id="int-sup")
        assert result.status == "superseded"
        assert result.reason == "sha_changed_before_publish"

    async def test_publish_not_called_when_superseded(self, _dbos: object, pr: PrMetadata) -> None:
        publish_mock = AsyncMock(return_value=ReviewResult(status="published", finding_count=0))
        sha_mock = AsyncMock(side_effect=[True, False])
        with (
            patch("kenjutsu.pipeline.steps.sha_guard", sha_mock),
            patch("kenjutsu.pipeline.steps.publish", publish_mock),
        ):
            await review_pr(pr, review_id="int-sup-nopub")
        publish_mock.assert_not_called()
