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
)
from kenjutsu.pipeline.types import PrMetadata, ReviewRequest, ReviewResult, StructuralContext


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


@DBOS.workflow()
async def review_pr(pr: PrMetadata) -> ReviewResult:
    """End-to-end durable PR review workflow.

    Each step is checkpointed: if the process restarts mid-review,
    DBOS resumes from the last completed step rather than re-running
    expensive operations.
    """
    if not await step_sha_guard(pr):
        return ReviewResult(status="aborted", reason="stale_sha")

    req = await step_process_diff(pr)
    ctx = await step_structural_context(req)
    det = await step_deterministic(req, ctx)
    llm = await step_llm_review(req, ctx, det)
    scored = await step_score(det + llm, ctx)
    return await step_publish(scored, pr)
