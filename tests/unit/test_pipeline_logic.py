"""Unit tests for pipeline business logic functions.

Verifies that logic.py has no DBOS dependency and that each function
returns the correct type. All tests run in < 1 second with zero I/O.
"""

from __future__ import annotations

import importlib
import inspect

import pytest

from kenjutsu.models.findings import Category, Confidence, Finding, Origin, Publishability, Severity
from kenjutsu.pipeline.logic import (
    get_structural_context,
    process_diff,
    publish,
    run_deterministic,
    run_llm_review,
    score_evidence,
    sha_guard,
)
from kenjutsu.pipeline.types import PrMetadata, ReviewRequest, ReviewResult, StructuralContext


@pytest.fixture
def pr() -> PrMetadata:
    return PrMetadata(
        repo_id="org/repo",
        pr_number=42,
        base_sha="abc123",
        head_sha="def456",
        repo_url="https://github.com/org/repo",
    )


@pytest.fixture
def review_request(pr: PrMetadata) -> ReviewRequest:
    return ReviewRequest(pr_metadata=pr, diff_patches=[])


@pytest.fixture
def ctx(pr: PrMetadata) -> StructuralContext:
    return StructuralContext(repo_id=pr.repo_id, head_sha=pr.head_sha)


@pytest.fixture
def finding() -> Finding:
    return Finding(
        file_path="src/auth.py",
        line_start=10,
        line_end=10,
        origin=Origin.DETERMINISTIC,
        confidence=Confidence.HIGH,
        severity=Severity.WARNING,
        category=Category.BUG,
        publishability=Publishability.PUBLISH,
        description="Example finding",
    )


class TestNoDbosDependency:
    """Business logic must not import DBOS — framework-free by design."""

    def test_logic_module_has_no_dbos_import(self) -> None:
        import kenjutsu.pipeline.logic as logic_mod

        source_file = inspect.getfile(logic_mod)
        with open(source_file) as f:
            source = f.read()
        # Check for actual import statements, not just mentions in docstrings
        has_dbos_import = any(line.strip().startswith(("import dbos", "from dbos")) for line in source.splitlines())
        assert not has_dbos_import, "logic.py must not import DBOS"

    def test_logic_module_importable_without_dbos(self) -> None:
        # If this import succeeds, logic.py has no mandatory DBOS boot sequence
        mod = importlib.import_module("kenjutsu.pipeline.logic")
        assert mod is not None


class TestShaGuard:
    async def test_returns_bool(self, pr: PrMetadata) -> None:
        result = await sha_guard(pr)
        assert isinstance(result, bool)

    async def test_stub_returns_true(self, pr: PrMetadata) -> None:
        assert await sha_guard(pr) is True


class TestProcessDiff:
    async def test_returns_review_request(self, pr: PrMetadata) -> None:
        result = await process_diff(pr)
        assert isinstance(result, ReviewRequest)

    async def test_preserves_pr_metadata(self, pr: PrMetadata) -> None:
        result = await process_diff(pr)
        assert result.pr_metadata == pr

    async def test_stub_returns_empty_patches(self, pr: PrMetadata) -> None:
        result = await process_diff(pr)
        assert result.diff_patches == []


class TestGetStructuralContext:
    async def test_returns_structural_context(self, review_request: ReviewRequest) -> None:
        result = await get_structural_context(review_request)
        assert isinstance(result, StructuralContext)

    async def test_carries_repo_id_and_sha(self, review_request: ReviewRequest) -> None:
        result = await get_structural_context(review_request)
        assert result.repo_id == review_request.pr_metadata.repo_id
        assert result.head_sha == review_request.pr_metadata.head_sha

    async def test_stub_returns_empty_context(self, review_request: ReviewRequest) -> None:
        result = await get_structural_context(review_request)
        assert result.referenced_symbols == []
        assert result.call_graph_edges == []


class TestRunDeterministic:
    async def test_returns_list(self, review_request: ReviewRequest, ctx: StructuralContext) -> None:
        result = await run_deterministic(review_request, ctx)
        assert isinstance(result, list)

    async def test_stub_returns_no_findings(self, review_request: ReviewRequest, ctx: StructuralContext) -> None:
        assert await run_deterministic(review_request, ctx) == []


class TestRunLlmReview:
    async def test_returns_list(
        self,
        review_request: ReviewRequest,
        ctx: StructuralContext,
        finding: Finding,
    ) -> None:
        result = await run_llm_review(review_request, ctx, [finding])
        assert isinstance(result, list)

    async def test_stub_returns_no_findings(
        self,
        review_request: ReviewRequest,
        ctx: StructuralContext,
    ) -> None:
        assert await run_llm_review(review_request, ctx, []) == []


class TestScoreEvidence:
    async def test_returns_list(self, finding: Finding, ctx: StructuralContext) -> None:
        result = await score_evidence([finding], ctx)
        assert isinstance(result, list)

    async def test_stub_passes_findings_through(self, finding: Finding, ctx: StructuralContext) -> None:
        result = await score_evidence([finding], ctx)
        assert result == [finding]

    async def test_empty_findings_returns_empty(self, ctx: StructuralContext) -> None:
        assert await score_evidence([], ctx) == []


class TestPublish:
    async def test_returns_review_result(self, pr: PrMetadata) -> None:
        result = await publish([], pr)
        assert isinstance(result, ReviewResult)

    async def test_status_is_published(self, pr: PrMetadata) -> None:
        result = await publish([], pr)
        assert result.status == "published"

    async def test_finding_count_matches_input(self, pr: PrMetadata, finding: Finding) -> None:
        result = await publish([finding, finding], pr)
        assert result.finding_count == 2

    async def test_empty_findings_count_is_zero(self, pr: PrMetadata) -> None:
        result = await publish([], pr)
        assert result.finding_count == 0
