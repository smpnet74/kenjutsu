"""DBOS step and workflow wrappers for the PR review pipeline.

Thin adapter layer — each function is a one-liner that delegates to
the corresponding business logic function in logic.py. This is the only
file that imports DBOS. If DBOS is replaced, only this file changes.

Architecture reference: kenjutsu-architecture-v3.md §3.6
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from dbos import DBOS

if TYPE_CHECKING:
    from kenjutsu.models.findings import Finding

from kenjutsu.pipeline.logic import (
    get_structural_context,
    process_diff,
    publish,
    run_deterministic,
    run_llm_review,
    score_evidence,
    sha_guard,
    update_review_status,
)
from kenjutsu.pipeline.types import PrMetadata, ReviewRequest, ReviewResult, ReviewStatus, StructuralContext


@DBOS.step()
async def step_sha_guard(pr: PrMetadata) -> bool:
    return await sha_guard(pr)


@DBOS.step()
async def step_process_diff(pr: PrMetadata) -> ReviewRequest:
    return await process_diff(pr)


@DBOS.step()
async def step_structural_context(req: ReviewRequest) -> StructuralContext:
    return await get_structural_context(req)


@DBOS.step()
async def step_deterministic(req: ReviewRequest, ctx: StructuralContext) -> list[Finding]:
    return await run_deterministic(req, ctx)


@DBOS.step()
async def step_llm_review(
    req: ReviewRequest,
    ctx: StructuralContext,
    det: list[Finding],
) -> list[Finding]:
    return await run_llm_review(req, ctx, det)


@DBOS.step()
async def step_score(findings: list[Finding], ctx: StructuralContext) -> list[Finding]:
    return await score_evidence(findings, ctx)


@DBOS.step()
async def step_publish(findings: list[Finding], pr: PrMetadata) -> ReviewResult:
    return await publish(findings, pr)


@DBOS.step()
async def step_update_status(review_id: str, status: ReviewStatus) -> None:
    """Persist a review status transition. Checkpointed so retries are idempotent."""
    await update_review_status(review_id, status)


async def _run_review_pipeline(pr: PrMetadata, review_id: str) -> ReviewResult:
    """Workflow body — all sequencing logic lives here.

    Called by the DBOS workflow wrapper and directly in unit tests.
    Each step reference is a module-level name so it can be patched in tests.

    Status transitions emitted:
      sha_checking → (aborted | processing_diff) → extracting_context
      → running_deterministic → running_llm → scoring_evidence
      → publishing → (superseded | complete)

    Superseded: a second sha_guard before publishing catches mid-review
    pushes. If the SHA changed, the review is marked superseded and not
    published.
    """
    # Step 1: SHA guard — abort immediately if already stale.
    await step_update_status(review_id, ReviewStatus.SHA_CHECKING)
    if not await step_sha_guard(pr):
        await step_update_status(review_id, ReviewStatus.ABORTED)
        return ReviewResult(status="aborted", reason="stale_sha")

    # Step 2: Parse diff and extend with AST context.
    await step_update_status(review_id, ReviewStatus.PROCESSING_DIFF)
    req = await step_process_diff(pr)

    # Step 3: Extract structural context (call graph, co-changes).
    await step_update_status(review_id, ReviewStatus.EXTRACTING_CONTEXT)
    ctx = await step_structural_context(req)

    # Step 4: Deterministic analysis (AST-grep rules).
    await step_update_status(review_id, ReviewStatus.RUNNING_DETERMINISTIC)
    det = await step_deterministic(req, ctx)

    # Step 5: LLM review.
    await step_update_status(review_id, ReviewStatus.RUNNING_LLM)
    llm = await step_llm_review(req, ctx, det)

    # Step 6: Evidence scoring and filtering.
    await step_update_status(review_id, ReviewStatus.SCORING_EVIDENCE)
    scored = await step_score(det + llm, ctx)

    # Step 7: Final SHA re-check before publishing.
    # Catches the case where a new push arrived while we were processing.
    await step_update_status(review_id, ReviewStatus.PUBLISHING)
    if not await step_sha_guard(pr):
        await step_update_status(review_id, ReviewStatus.SUPERSEDED)
        return ReviewResult(status="superseded", reason="sha_changed_before_publish")

    result = await step_publish(scored, pr)
    await step_update_status(review_id, ReviewStatus.COMPLETE)
    return result


@DBOS.workflow()
async def review_pr(pr: PrMetadata, review_id: str = "") -> ReviewResult:
    """End-to-end durable PR review workflow.

    Each step is checkpointed: if the process restarts mid-review,
    DBOS resumes from the last completed step rather than re-running
    expensive operations.
    """
    return await _run_review_pipeline(pr, review_id)
