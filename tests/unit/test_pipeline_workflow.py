"""Unit tests for the review pipeline workflow sequencing.

Covers:
- Happy path: all steps called in order, COMPLETE status emitted.
- SHA guard failure at start: workflow aborts with status ABORTED.
- SHA guard failure before publish (superseded): workflow returns superseded.
- Status transitions: correct ReviewStatus values emitted at each boundary.
- update_review_status has no DBOS dependency (logic boundary invariant).

These tests call _run_review_pipeline (the plain async body) with all step_*
functions patched as AsyncMocks. DBOS is never initialized — this is the unit
boundary. The DBOS runtime is covered by integration tests.
"""

from __future__ import annotations

import inspect
from unittest.mock import AsyncMock, patch

import pytest

from kenjutsu.pipeline.logic import (
    sha_guard,
    update_review_status,
)
from kenjutsu.pipeline.types import PrMetadata, ReviewRequest, ReviewResult, ReviewStatus, StructuralContext


@pytest.fixture
def pr() -> PrMetadata:
    return PrMetadata(
        repo_id="org/repo",
        pr_number=7,
        base_sha="aaa111",
        head_sha="bbb222",
        repo_url="https://github.com/org/repo",
    )


# ---------------------------------------------------------------------------
# update_review_status — logic boundary invariant
# ---------------------------------------------------------------------------


class TestUpdateReviewStatusLogicBoundary:
    """update_review_status must not import DBOS — it's a logic function."""

    def test_no_dbos_import(self) -> None:
        import kenjutsu.pipeline.logic as mod

        source = inspect.getsource(mod)
        dbos_imports = [ln for ln in source.splitlines() if ln.strip().startswith(("import dbos", "from dbos"))]
        assert not dbos_imports, "logic.py must not import DBOS"

    async def test_is_coroutine(self) -> None:
        import asyncio

        result = update_review_status("rev-1", ReviewStatus.QUEUED)
        assert asyncio.iscoroutine(result)
        await result  # no-op stub — must not raise

    async def test_accepts_all_status_values(self) -> None:
        for status in ReviewStatus:
            await update_review_status("rev-x", status)  # must not raise


# ---------------------------------------------------------------------------
# sha_guard logic
# ---------------------------------------------------------------------------


class TestShaGuard:
    async def test_returns_true_by_default(self, pr: PrMetadata) -> None:
        result = await sha_guard(pr)
        assert result is True


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_mocks(sha_guard_returns: list[bool] | None = None) -> dict[str, AsyncMock]:
    """Return AsyncMock replacements for all step_* functions used by _run_review_pipeline."""
    sha_side: list[bool] = sha_guard_returns if sha_guard_returns is not None else [True, True]
    pr_inner = PrMetadata(repo_id="r", pr_number=1, base_sha="a", head_sha="b", repo_url="u")
    req_inner = ReviewRequest(pr_metadata=pr_inner, diff_patches=[])
    ctx_inner = StructuralContext(repo_id="r", head_sha="b")

    return {
        "step_sha_guard": AsyncMock(side_effect=sha_side),
        "step_process_diff": AsyncMock(return_value=req_inner),
        "step_structural_context": AsyncMock(return_value=ctx_inner),
        "step_deterministic": AsyncMock(return_value=[]),
        "step_llm_review": AsyncMock(return_value=[]),
        "step_score": AsyncMock(return_value=[]),
        "step_publish": AsyncMock(return_value=ReviewResult(status="published", finding_count=0)),
        "step_update_status": AsyncMock(return_value=None),
    }


async def _run(pr: PrMetadata, mocks: dict[str, AsyncMock], review_id: str = "rev-test") -> ReviewResult:
    """Patch all step_* names in the steps module and call _run_review_pipeline."""
    from kenjutsu.pipeline.steps import _run_review_pipeline

    patches = [patch(f"kenjutsu.pipeline.steps.{name}", mock) for name, mock in mocks.items()]
    for p in patches:
        p.start()
    try:
        return await _run_review_pipeline(pr, review_id)
    finally:
        for p in patches:
            p.stop()


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


class TestWorkflowHappyPath:
    async def test_returns_review_result(self, pr: PrMetadata) -> None:
        mocks = _make_mocks()
        result = await _run(pr, mocks, review_id="rev-happy")
        assert isinstance(result, ReviewResult)
        assert result.status == "published"

    async def test_sha_guard_called_twice(self, pr: PrMetadata) -> None:
        """SHA is checked before processing AND before publishing."""
        mocks = _make_mocks()
        await _run(pr, mocks, review_id="rev-dbl-sha")
        assert mocks["step_sha_guard"].call_count == 2

    async def test_all_processing_steps_called(self, pr: PrMetadata) -> None:
        mocks = _make_mocks()
        await _run(pr, mocks, review_id="rev-all-steps")
        mocks["step_process_diff"].assert_called_once()
        mocks["step_structural_context"].assert_called_once()
        mocks["step_deterministic"].assert_called_once()
        mocks["step_llm_review"].assert_called_once()
        mocks["step_score"].assert_called_once()
        mocks["step_publish"].assert_called_once()

    async def test_status_transitions_complete_path(self, pr: PrMetadata) -> None:
        """Status updates must follow the canonical order for a successful review."""
        mocks = _make_mocks()
        await _run(pr, mocks, review_id="rev-status")
        status_calls = [c.args[1] for c in mocks["step_update_status"].call_args_list]
        assert status_calls == [
            ReviewStatus.SHA_CHECKING,
            ReviewStatus.PROCESSING_DIFF,
            ReviewStatus.EXTRACTING_CONTEXT,
            ReviewStatus.RUNNING_DETERMINISTIC,
            ReviewStatus.RUNNING_LLM,
            ReviewStatus.SCORING_EVIDENCE,
            ReviewStatus.PUBLISHING,
            ReviewStatus.COMPLETE,
        ]

    async def test_review_id_passed_to_all_status_updates(self, pr: PrMetadata) -> None:
        mocks = _make_mocks()
        await _run(pr, mocks, review_id="my-review-id")
        for c in mocks["step_update_status"].call_args_list:
            assert c.args[0] == "my-review-id"


# ---------------------------------------------------------------------------
# SHA guard failure at start → aborted
# ---------------------------------------------------------------------------


class TestWorkflowShaGuardFailAtStart:
    async def test_returns_aborted_result(self, pr: PrMetadata) -> None:
        mocks = _make_mocks(sha_guard_returns=[False])
        result = await _run(pr, mocks, review_id="rev-abort")
        assert result.status == "aborted"
        assert result.reason == "stale_sha"

    async def test_no_processing_steps_called_on_abort(self, pr: PrMetadata) -> None:
        mocks = _make_mocks(sha_guard_returns=[False])
        await _run(pr, mocks, review_id="rev-abort-skip")
        mocks["step_process_diff"].assert_not_called()
        mocks["step_structural_context"].assert_not_called()
        mocks["step_deterministic"].assert_not_called()
        mocks["step_llm_review"].assert_not_called()
        mocks["step_score"].assert_not_called()
        mocks["step_publish"].assert_not_called()

    async def test_status_transitions_abort_path(self, pr: PrMetadata) -> None:
        mocks = _make_mocks(sha_guard_returns=[False])
        await _run(pr, mocks, review_id="rev-abort-status")
        status_calls = [c.args[1] for c in mocks["step_update_status"].call_args_list]
        assert status_calls == [ReviewStatus.SHA_CHECKING, ReviewStatus.ABORTED]


# ---------------------------------------------------------------------------
# Superseded — SHA changes while processing
# ---------------------------------------------------------------------------


class TestWorkflowSuperseded:
    async def test_returns_superseded_result(self, pr: PrMetadata) -> None:
        """Second SHA guard (before publish) returns False → superseded."""
        mocks = _make_mocks(sha_guard_returns=[True, False])
        result = await _run(pr, mocks, review_id="rev-superseded")
        assert result.status == "superseded"
        assert result.reason == "sha_changed_before_publish"

    async def test_publish_not_called_when_superseded(self, pr: PrMetadata) -> None:
        mocks = _make_mocks(sha_guard_returns=[True, False])
        await _run(pr, mocks, review_id="rev-sup-nopub")
        mocks["step_publish"].assert_not_called()

    async def test_processing_steps_complete_before_supersession(self, pr: PrMetadata) -> None:
        """All analysis steps run; only publish is skipped when superseded."""
        mocks = _make_mocks(sha_guard_returns=[True, False])
        await _run(pr, mocks, review_id="rev-sup-full")
        mocks["step_process_diff"].assert_called_once()
        mocks["step_structural_context"].assert_called_once()
        mocks["step_deterministic"].assert_called_once()
        mocks["step_llm_review"].assert_called_once()
        mocks["step_score"].assert_called_once()

    async def test_status_transitions_superseded_path(self, pr: PrMetadata) -> None:
        mocks = _make_mocks(sha_guard_returns=[True, False])
        await _run(pr, mocks, review_id="rev-sup-status")
        status_calls = [c.args[1] for c in mocks["step_update_status"].call_args_list]
        assert status_calls == [
            ReviewStatus.SHA_CHECKING,
            ReviewStatus.PROCESSING_DIFF,
            ReviewStatus.EXTRACTING_CONTEXT,
            ReviewStatus.RUNNING_DETERMINISTIC,
            ReviewStatus.RUNNING_LLM,
            ReviewStatus.SCORING_EVIDENCE,
            ReviewStatus.PUBLISHING,
            ReviewStatus.SUPERSEDED,
        ]


# ---------------------------------------------------------------------------
# Default review_id
# ---------------------------------------------------------------------------


class TestWorkflowDefaultReviewId:
    async def test_empty_review_id_is_accepted(self, pr: PrMetadata) -> None:
        """review_id defaults to '' — callers without a DB ID still work."""
        mocks = _make_mocks()
        result = await _run(pr, mocks, review_id="")
        assert isinstance(result, ReviewResult)
