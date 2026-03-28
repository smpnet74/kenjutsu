"""Type models for the PR review pipeline.

These are the typed interfaces shared between business logic and the
orchestration layer. All steps take and return these types — making
the pipeline's data flow explicit and testable without any framework.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel


class ReviewStatus(StrEnum):
    """Status values for a review record, updated at each pipeline step."""

    QUEUED = "queued"
    SHA_CHECKING = "sha_checking"
    PROCESSING_DIFF = "processing_diff"
    EXTRACTING_CONTEXT = "extracting_context"
    RUNNING_DETERMINISTIC = "running_deterministic"
    RUNNING_LLM = "running_llm"
    SCORING_EVIDENCE = "scoring_evidence"
    PUBLISHING = "publishing"
    COMPLETE = "complete"
    FAILED = "failed"
    SUPERSEDED = "superseded"
    ABORTED = "aborted"


class PrMetadata(BaseModel):
    """Identifying metadata for a pull request review job."""

    repo_id: str
    pr_number: int
    base_sha: str
    head_sha: str
    repo_url: str


class ReviewRequest(BaseModel):
    """Parsed diff and context ready for analysis steps."""

    pr_metadata: PrMetadata
    diff_patches: list[str]


class StructuralContext(BaseModel):
    """Structural information extracted from the repo mirror."""

    repo_id: str
    head_sha: str
    referenced_symbols: list[str] = []
    call_graph_edges: list[tuple[str, str]] = []


class ReviewResult(BaseModel):
    """Final outcome of a review workflow run."""

    status: str
    reason: str | None = None
    finding_count: int = 0
