"""Business logic for the PR review pipeline.

Plain async functions — zero framework imports. Each function takes
typed input and returns typed output. The orchestration layer (steps.py)
wraps these with DBOS durability; business logic never touches DBOS.

All implementations are stubs for Phase 1 (DEM-159). Real logic
is added in DEM-160 (Review Workflow Pipeline).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from kenjutsu.pipeline.types import PrMetadata, ReviewRequest, ReviewResult, StructuralContext

if TYPE_CHECKING:
    from kenjutsu.models.findings import Finding


async def sha_guard(pr: PrMetadata) -> bool:
    """Return True if the PR head SHA is still current.

    Stub: always returns True. DEM-160 implements the GitHub API check.
    """
    return True


async def process_diff(pr: PrMetadata) -> ReviewRequest:
    """Parse the PR diff and extend hunks with AST context.

    Stub: returns an empty ReviewRequest. DEM-160 implements mirror
    access and tree-sitter parsing.
    """
    return ReviewRequest(pr_metadata=pr, diff_patches=[])


async def get_structural_context(req: ReviewRequest) -> StructuralContext:
    """Extract structural context (call graph, symbols) from the repo mirror.

    Stub: returns empty context. DEM-160 implements tree-sitter graph extraction.
    """
    return StructuralContext(
        repo_id=req.pr_metadata.repo_id,
        head_sha=req.pr_metadata.head_sha,
    )


async def run_deterministic(req: ReviewRequest, ctx: StructuralContext) -> list[Finding]:
    """Run AST-based deterministic analysis rules.

    Stub: returns no findings. DEM-160 implements ast-grep rule evaluation.
    """
    return []


async def run_llm_review(
    req: ReviewRequest,
    ctx: StructuralContext,
    det: list[Finding],
) -> list[Finding]:
    """Run LLM-based review using structural context and deterministic pre-pass.

    Stub: returns no findings. DEM-160 implements LiteLLM integration.
    """
    return []


async def score_evidence(findings: list[Finding], ctx: StructuralContext) -> list[Finding]:
    """Score and filter findings by evidence quality.

    Stub: passes findings through unchanged. DEM-160 implements
    structural confirmation and self-reflection scoring.
    """
    return list(findings)


async def publish(findings: list[Finding], pr: PrMetadata) -> ReviewResult:
    """Publish findings to GitHub, guarded by a final SHA check.

    Stub: reports published with zero findings. DEM-160 implements
    the SHA re-check and GitHub review submission.
    """
    return ReviewResult(status="published", finding_count=len(findings))
