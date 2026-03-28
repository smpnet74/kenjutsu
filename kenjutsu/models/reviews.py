"""Review model — tracks the lifecycle of a single PR review run."""

from __future__ import annotations

from enum import StrEnum


class ReviewStatus(StrEnum):
    """Lifecycle status for a PR review."""

    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETE = "complete"
    FAILED = "failed"
    ABORTED = "aborted"
    SUPERSEDED = "superseded"

    def is_canonical(self) -> bool:
        """True if the review is still a live/canonical result (not superseded, aborted, or failed)."""
        return self not in (ReviewStatus.SUPERSEDED, ReviewStatus.ABORTED, ReviewStatus.FAILED)


class Review:
    """Represents one review run for a specific PR commit.

    In production this maps to a database row.  For Phase 1 tests it is
    used as a plain in-memory object — no ORM dependency required.
    """

    def __init__(
        self,
        id: str,
        repo_id: str,
        pr_number: int,
        head_sha: str,
        status: ReviewStatus = ReviewStatus.QUEUED,
        superseded_by: str | None = None,
    ) -> None:
        self.id = id
        self.repo_id = repo_id
        self.pr_number = pr_number
        self.head_sha = head_sha
        self.status = status
        self.superseded_by = superseded_by

    def __repr__(self) -> str:
        return (
            f"Review(id={self.id!r}, repo_id={self.repo_id!r}, "
            f"pr_number={self.pr_number}, head_sha={self.head_sha!r}, "
            f"status={self.status!r}, superseded_by={self.superseded_by!r})"
        )
