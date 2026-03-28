"""Integration tests for DBOS step wrappers.

Verifies that step_* functions in steps.py correctly delegate to
business logic when executed through the DBOS runtime. Uses SQLite
as the DBOS system database — no external services required.
"""

from __future__ import annotations

import pytest

# Import steps module before DBOS is initialized so decorators register.
import kenjutsu.pipeline.steps  # noqa: F401
from kenjutsu.pipeline.steps import (
    review_pr,
    step_process_diff,
    step_publish,
    step_score,
    step_sha_guard,
    step_structural_context,
)
from kenjutsu.pipeline.types import PrMetadata, ReviewRequest, ReviewResult, StructuralContext


@pytest.fixture()
def _dbos(dbos_instance):
    """Alias for dbos_instance — provides a live DBOS runtime per test."""
    return dbos_instance


@pytest.fixture
def pr() -> PrMetadata:
    return PrMetadata(
        repo_id="org/repo",
        pr_number=1,
        base_sha="aaa111",
        head_sha="bbb222",
        repo_url="https://github.com/org/repo",
    )


class TestStepDelegation:
    """Each step wrapper must delegate to the corresponding logic function."""

    async def test_step_sha_guard_returns_true(self, _dbos: object, pr: PrMetadata) -> None:
        result = await step_sha_guard(pr)
        assert result is True

    async def test_step_process_diff_returns_review_request(self, _dbos: object, pr: PrMetadata) -> None:
        result = await step_process_diff(pr)
        assert isinstance(result, ReviewRequest)
        assert result.pr_metadata == pr

    async def test_step_structural_context_returns_context(self, _dbos: object, pr: PrMetadata) -> None:
        req = ReviewRequest(pr_metadata=pr, diff_patches=[])
        result = await step_structural_context(req)
        assert isinstance(result, StructuralContext)
        assert result.repo_id == pr.repo_id
        assert result.head_sha == pr.head_sha

    async def test_step_score_passes_findings_through(self, _dbos: object, pr: PrMetadata) -> None:
        ctx = StructuralContext(repo_id=pr.repo_id, head_sha=pr.head_sha)
        result = await step_score([], ctx)
        assert result == []

    async def test_step_publish_returns_review_result(self, _dbos: object, pr: PrMetadata) -> None:
        result = await step_publish([], pr)
        assert isinstance(result, ReviewResult)
        assert result.status == "published"
        assert result.finding_count == 0


class TestReviewPrWorkflow:
    """Full workflow should execute all steps and return a ReviewResult."""

    async def test_workflow_returns_review_result(self, _dbos: object, pr: PrMetadata) -> None:
        result = await review_pr(pr)
        assert isinstance(result, ReviewResult)

    async def test_workflow_publishes_by_default(self, _dbos: object, pr: PrMetadata) -> None:
        # Stub sha_guard always returns True, so we expect "published" not "aborted"
        pr2 = PrMetadata(
            repo_id="org/repo",
            pr_number=2,
            base_sha="ccc333",
            head_sha="ddd444",
            repo_url="https://github.com/org/repo",
        )
        result = await review_pr(pr2)
        assert result.status == "published"
