"""Tests for supersession pipeline logic."""

from kenjutsu.models.reviews import Review, ReviewStatus
from kenjutsu.pipeline.supersession import ensure_unique_canonical, supersede_previous_reviews


def _review(
    id: str,
    head_sha: str = "abc123",
    repo_id: str = "org/repo",
    pr_number: int = 42,
    status: ReviewStatus = ReviewStatus.COMPLETE,
    superseded_by: str | None = None,
) -> Review:
    return Review(
        id=id,
        repo_id=repo_id,
        pr_number=pr_number,
        head_sha=head_sha,
        status=status,
        superseded_by=superseded_by,
    )


class TestSupsedePreviousReviews:
    def test_marks_prior_complete_review_as_superseded(self) -> None:
        old = _review("r1", head_sha="sha1", status=ReviewStatus.COMPLETE)
        new = _review("r2", head_sha="sha2", status=ReviewStatus.IN_PROGRESS)
        reviews = [old, new]
        supersede_previous_reviews(reviews, new_review_id="r2", repo_id="org/repo", pr_number=42)
        assert old.status == ReviewStatus.SUPERSEDED
        assert old.superseded_by == "r2"

    def test_sets_superseded_by_on_all_canonical_prior_reviews(self) -> None:
        r1 = _review("r1", head_sha="sha1", status=ReviewStatus.COMPLETE)
        r2 = _review("r2", head_sha="sha2", status=ReviewStatus.IN_PROGRESS)
        r3 = _review("r3", head_sha="sha3", status=ReviewStatus.QUEUED)
        new = _review("r4", head_sha="sha4", status=ReviewStatus.QUEUED)
        reviews = [r1, r2, r3, new]
        supersede_previous_reviews(reviews, new_review_id="r4", repo_id="org/repo", pr_number=42)
        assert r1.status == ReviewStatus.SUPERSEDED and r1.superseded_by == "r4"
        assert r2.status == ReviewStatus.SUPERSEDED and r2.superseded_by == "r4"
        assert r3.status == ReviewStatus.SUPERSEDED and r3.superseded_by == "r4"

    def test_does_not_touch_new_review_itself(self) -> None:
        new = _review("r1", head_sha="sha1", status=ReviewStatus.QUEUED)
        reviews = [new]
        supersede_previous_reviews(reviews, new_review_id="r1", repo_id="org/repo", pr_number=42)
        assert new.status == ReviewStatus.QUEUED
        assert new.superseded_by is None

    def test_skips_already_superseded_reviews(self) -> None:
        old = _review("r1", head_sha="sha1", status=ReviewStatus.SUPERSEDED, superseded_by="r-prev")
        new = _review("r2", head_sha="sha2", status=ReviewStatus.QUEUED)
        reviews = [old, new]
        supersede_previous_reviews(reviews, new_review_id="r2", repo_id="org/repo", pr_number=42)
        # superseded_by must not be overwritten
        assert old.superseded_by == "r-prev"

    def test_skips_aborted_reviews(self) -> None:
        aborted = _review("r1", head_sha="sha1", status=ReviewStatus.ABORTED)
        new = _review("r2", head_sha="sha2", status=ReviewStatus.QUEUED)
        reviews = [aborted, new]
        supersede_previous_reviews(reviews, new_review_id="r2", repo_id="org/repo", pr_number=42)
        assert aborted.status == ReviewStatus.ABORTED

    def test_only_affects_same_pr(self) -> None:
        other_pr = _review("r1", head_sha="sha1", pr_number=99, status=ReviewStatus.COMPLETE)
        new = _review("r2", head_sha="sha2", pr_number=42, status=ReviewStatus.QUEUED)
        reviews = [other_pr, new]
        supersede_previous_reviews(reviews, new_review_id="r2", repo_id="org/repo", pr_number=42)
        assert other_pr.status == ReviewStatus.COMPLETE

    def test_only_affects_same_repo(self) -> None:
        other_repo = _review("r1", repo_id="other/repo", status=ReviewStatus.COMPLETE)
        new = _review("r2", repo_id="org/repo", status=ReviewStatus.QUEUED)
        reviews = [other_repo, new]
        supersede_previous_reviews(reviews, new_review_id="r2", repo_id="org/repo", pr_number=42)
        assert other_repo.status == ReviewStatus.COMPLETE

    def test_empty_list_is_a_noop(self) -> None:
        supersede_previous_reviews([], new_review_id="r1", repo_id="org/repo", pr_number=42)


class TestEnsureUniqueCanonical:
    def test_returns_existing_canonical_review(self) -> None:
        existing = _review("r1", head_sha="sha1", status=ReviewStatus.COMPLETE)
        result = ensure_unique_canonical([existing], repo_id="org/repo", pr_number=42, head_sha="sha1")
        assert result is existing

    def test_returns_none_when_no_canonical_exists(self) -> None:
        result = ensure_unique_canonical([], repo_id="org/repo", pr_number=42, head_sha="sha1")
        assert result is None

    def test_ignores_superseded_review_for_same_triple(self) -> None:
        superseded = _review("r1", head_sha="sha1", status=ReviewStatus.SUPERSEDED)
        result = ensure_unique_canonical([superseded], repo_id="org/repo", pr_number=42, head_sha="sha1")
        assert result is None

    def test_ignores_aborted_review_for_same_triple(self) -> None:
        aborted = _review("r1", head_sha="sha1", status=ReviewStatus.ABORTED)
        result = ensure_unique_canonical([aborted], repo_id="org/repo", pr_number=42, head_sha="sha1")
        assert result is None

    def test_does_not_match_different_sha(self) -> None:
        existing = _review("r1", head_sha="sha1", status=ReviewStatus.COMPLETE)
        result = ensure_unique_canonical([existing], repo_id="org/repo", pr_number=42, head_sha="sha2")
        assert result is None

    def test_does_not_match_different_pr(self) -> None:
        existing = _review("r1", head_sha="sha1", pr_number=1, status=ReviewStatus.COMPLETE)
        result = ensure_unique_canonical([existing], repo_id="org/repo", pr_number=99, head_sha="sha1")
        assert result is None

    def test_does_not_match_different_repo(self) -> None:
        existing = _review("r1", repo_id="other/repo", head_sha="sha1", status=ReviewStatus.COMPLETE)
        result = ensure_unique_canonical([existing], repo_id="org/repo", pr_number=42, head_sha="sha1")
        assert result is None

    def test_returns_in_progress_review_as_canonical(self) -> None:
        in_progress = _review("r1", head_sha="sha1", status=ReviewStatus.IN_PROGRESS)
        result = ensure_unique_canonical([in_progress], repo_id="org/repo", pr_number=42, head_sha="sha1")
        assert result is in_progress

    def test_force_push_scenario(self) -> None:
        """Force push: old sha superseded, new sha has no canonical yet."""
        old = _review("r1", head_sha="sha1", status=ReviewStatus.SUPERSEDED, superseded_by="r2")
        result = ensure_unique_canonical([old], repo_id="org/repo", pr_number=42, head_sha="sha2")
        assert result is None

    def test_multiple_rapid_pushes_only_latest_canonical(self) -> None:
        """Only the latest sha should have a canonical review."""
        r1 = _review("r1", head_sha="sha1", status=ReviewStatus.SUPERSEDED, superseded_by="r2")
        r2 = _review("r2", head_sha="sha2", status=ReviewStatus.SUPERSEDED, superseded_by="r3")
        r3 = _review("r3", head_sha="sha3", status=ReviewStatus.QUEUED)
        reviews = [r1, r2, r3]
        assert ensure_unique_canonical(reviews, repo_id="org/repo", pr_number=42, head_sha="sha1") is None
        assert ensure_unique_canonical(reviews, repo_id="org/repo", pr_number=42, head_sha="sha2") is None
        assert ensure_unique_canonical(reviews, repo_id="org/repo", pr_number=42, head_sha="sha3") is r3
