"""Supersession logic — ensures at most one canonical review per (repo_id, pr_number, head_sha).

Spec ref: v3 Sections 4.1, 4.4

These functions operate on a sequence of Review objects and return updated
results.  The caller is responsible for persisting state (in-memory for
tests, database rows in production).

Database contract (production):
  UNIQUE (repo_id, pr_number, head_sha) WHERE status NOT IN ('superseded', 'aborted')

This partial unique constraint enforces the invariant at the DB level.  The
functions here enforce the same invariant in application logic so it can be
tested without a running database.
"""

from __future__ import annotations

from kenjutsu.models.reviews import Review, ReviewStatus


def supersede_previous_reviews(
    reviews: list[Review],
    new_review_id: str,
    repo_id: str,
    pr_number: int,
) -> None:
    """Mark all prior canonical reviews for (repo_id, pr_number) as superseded.

    Mutates the reviews in-place — sets status to SUPERSEDED and records
    superseded_by pointing to new_review_id.

    Only reviews that are currently canonical (not already superseded or
    aborted) are updated.  The new review itself is never touched.

    Args:
        reviews:       Collection of all known reviews (mutable).
        new_review_id: ID of the review that supersedes the others.
        repo_id:       Repository identifier.
        pr_number:     Pull request number.
    """
    for review in reviews:
        if review.id == new_review_id:
            continue
        if review.repo_id != repo_id or review.pr_number != pr_number:
            continue
        if review.status.is_canonical():
            review.status = ReviewStatus.SUPERSEDED
            review.superseded_by = new_review_id


def ensure_unique_canonical(
    reviews: list[Review],
    repo_id: str,
    pr_number: int,
    head_sha: str,
) -> Review | None:
    """Return an existing canonical review for the exact (repo_id, pr_number, head_sha) triple.

    If a canonical review already exists for this triple the caller should
    skip creating a new one and return the existing review instead.

    Returns None when no canonical review exists, signalling that the caller
    should proceed with creating a new review.

    Args:
        reviews:   Collection of all known reviews.
        repo_id:   Repository identifier.
        pr_number: Pull request number.
        head_sha:  Exact commit SHA being reviewed.

    Returns:
        The existing canonical Review, or None.
    """
    for review in reviews:
        if (
            review.repo_id == repo_id
            and review.pr_number == pr_number
            and review.head_sha == head_sha
            and review.status.is_canonical()
        ):
            return review
    return None
