"""Unit tests for the idempotent GitHub review publisher.

All GitHub API calls and DB session interactions are fully mocked so these
tests run without a live database or network.
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from kenjutsu.pipeline.publisher import _finding_comment_body, publish_review

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_review(
    review_id: uuid.UUID | None = None,
    repo_id: uuid.UUID | None = None,
    github_review_id: int | None = None,
    github_comment_ids: dict | None = None,
) -> MagicMock:
    review = MagicMock()
    review.id = review_id or uuid.uuid4()
    review.repo_id = repo_id or uuid.uuid4()
    review.pr_number = 42
    review.head_sha = "abc123"
    review.github_review_id = github_review_id
    review.github_comment_ids = github_comment_ids
    return review


def _make_repo(full_name: str = "acme/myrepo") -> MagicMock:
    repo = MagicMock()
    repo.full_name = full_name
    return repo


def _make_finding(
    finding_id: uuid.UUID | None = None,
    publishability: str = "publish",
    github_comment_id: int | None = None,
) -> MagicMock:
    f = MagicMock()
    f.id = finding_id or uuid.uuid4()
    f.publishability = publishability
    f.github_comment_id = github_comment_id
    f.file_path = "src/auth.py"
    f.line_end = 10
    f.line_start = 10
    f.severity = "warning"
    f.category = "bug"
    f.description = "A test finding"
    f.suggestion = None
    f.origin = "llm"
    f.confidence = "high"
    f.fingerprint = "deadbeef12345678"
    f.published = False
    return f


def _make_response(status_code: int = 200, json_data: dict | None = None) -> MagicMock:
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = status_code
    resp.json.return_value = json_data or {}
    if status_code >= 400:
        resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            f"HTTP {status_code}", request=MagicMock(), response=resp
        )
    else:
        resp.raise_for_status.return_value = None
    return resp


# ---------------------------------------------------------------------------
# Tests: _finding_comment_body
# ---------------------------------------------------------------------------


class TestFindingCommentBody:
    def test_includes_description(self) -> None:
        finding = _make_finding()
        body = _finding_comment_body(finding)
        assert "A test finding" in body

    def test_includes_severity(self) -> None:
        finding = _make_finding()
        body = _finding_comment_body(finding)
        assert "WARNING" in body

    def test_includes_suggestion_when_present(self) -> None:
        finding = _make_finding()
        finding.suggestion = "Use a safer API"
        body = _finding_comment_body(finding)
        assert "Use a safer API" in body

    def test_no_suggestion_section_when_absent(self) -> None:
        finding = _make_finding()
        finding.suggestion = None
        body = _finding_comment_body(finding)
        assert "Suggestion" not in body

    def test_includes_fingerprint(self) -> None:
        finding = _make_finding()
        body = _finding_comment_body(finding)
        assert "deadbeef12345678" in body

    def test_critical_icon(self) -> None:
        finding = _make_finding()
        finding.severity = "critical"
        body = _finding_comment_body(finding)
        assert "🔴" in body


# ---------------------------------------------------------------------------
# Tests: publish_review — first publish (no stored IDs)
# ---------------------------------------------------------------------------


class TestPublishReviewFirstPublish:
    @pytest.fixture
    def review_id(self) -> uuid.UUID:
        return uuid.uuid4()

    @pytest.fixture
    def finding_id(self) -> uuid.UUID:
        return uuid.uuid4()

    @pytest.fixture
    def review(self, review_id: uuid.UUID) -> MagicMock:
        return _make_review(review_id=review_id)

    @pytest.fixture
    def repo(self) -> MagicMock:
        return _make_repo()

    @pytest.fixture
    def finding(self, finding_id: uuid.UUID, review_id: uuid.UUID) -> MagicMock:
        f = _make_finding(finding_id=finding_id)
        f.review_id = review_id
        return f

    async def _run(
        self,
        session: AsyncMock,
        review: MagicMock,
        repo: MagicMock,
        finding: MagicMock,
        client_mock: MagicMock,
    ) -> None:
        session.get = AsyncMock(side_effect=[review, repo])
        scalars_mock = MagicMock()
        scalars_mock.all.return_value = [finding]
        execute_result = MagicMock()
        execute_result.scalars.return_value = scalars_mock
        session.execute = AsyncMock(return_value=execute_result)

        with patch("kenjutsu.pipeline.publisher.httpx.AsyncClient") as mock_client_cls:
            mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=client_mock)
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            await publish_review(session, review.id, "gh_token_test")

    @pytest.mark.asyncio
    async def test_creates_review_on_first_publish(
        self, review: MagicMock, repo: MagicMock, finding: MagicMock, review_id: uuid.UUID
    ) -> None:
        session = AsyncMock()
        client = MagicMock()

        create_review_resp = _make_response(200, {"id": 9001})
        create_comment_resp = _make_response(200, {"id": 1234})

        client.post = AsyncMock(side_effect=[create_review_resp, create_comment_resp])
        client.put = AsyncMock()
        client.patch = AsyncMock()

        await self._run(session, review, repo, finding, client)

        # Should POST to reviews endpoint once
        assert client.post.call_count == 2  # one review + one comment
        first_call_url = client.post.call_args_list[0].args[0]
        assert "/pulls/42/reviews" in first_call_url

    @pytest.mark.asyncio
    async def test_stores_github_review_id(self, review: MagicMock, repo: MagicMock, finding: MagicMock) -> None:
        session = AsyncMock()
        client = MagicMock()

        client.post = AsyncMock(
            side_effect=[
                _make_response(200, {"id": 9001}),
                _make_response(200, {"id": 1234}),
            ]
        )
        client.put = AsyncMock()
        client.patch = AsyncMock()

        await self._run(session, review, repo, finding, client)

        assert review.github_review_id == 9001

    @pytest.mark.asyncio
    async def test_stores_comment_id_on_finding(self, review: MagicMock, repo: MagicMock, finding: MagicMock) -> None:
        session = AsyncMock()
        client = MagicMock()

        client.post = AsyncMock(
            side_effect=[
                _make_response(200, {"id": 9001}),
                _make_response(200, {"id": 5678}),
            ]
        )
        client.put = AsyncMock()
        client.patch = AsyncMock()

        await self._run(session, review, repo, finding, client)

        assert finding.github_comment_id == 5678
        assert finding.published is True

    @pytest.mark.asyncio
    async def test_persists_comment_id_map(self, review: MagicMock, repo: MagicMock, finding: MagicMock) -> None:
        session = AsyncMock()
        client = MagicMock()

        client.post = AsyncMock(
            side_effect=[
                _make_response(200, {"id": 9001}),
                _make_response(200, {"id": 5678}),
            ]
        )
        client.put = AsyncMock()
        client.patch = AsyncMock()

        await self._run(session, review, repo, finding, client)

        expected_key = str(finding.id)
        assert review.github_comment_ids[expected_key] == 5678

    @pytest.mark.asyncio
    async def test_suppressed_finding_not_published(self, review: MagicMock, repo: MagicMock) -> None:
        session = AsyncMock()
        client = MagicMock()

        suppressed = _make_finding(publishability="suppress")
        suppressed.review_id = review.id

        create_review_resp = _make_response(200, {"id": 9001})
        client.post = AsyncMock(return_value=create_review_resp)
        client.put = AsyncMock()
        client.patch = AsyncMock()

        session.get = AsyncMock(side_effect=[review, repo])
        scalars_mock = MagicMock()
        scalars_mock.all.return_value = [suppressed]
        execute_result = MagicMock()
        execute_result.scalars.return_value = scalars_mock
        session.execute = AsyncMock(return_value=execute_result)

        with patch("kenjutsu.pipeline.publisher.httpx.AsyncClient") as mock_client_cls:
            mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=client)
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            await publish_review(session, review.id, "gh_token_test")

        # Only the review POST, no comment POST
        assert client.post.call_count == 1
        assert suppressed.published is False


# ---------------------------------------------------------------------------
# Tests: publish_review — retry (IDs already stored)
# ---------------------------------------------------------------------------


class TestPublishReviewRetry:
    @pytest.mark.asyncio
    async def test_updates_existing_review_on_retry(self) -> None:
        review_id = uuid.uuid4()
        finding_id = uuid.uuid4()

        review = _make_review(review_id=review_id, github_review_id=9001)
        repo = _make_repo()
        finding = _make_finding(finding_id=finding_id, github_comment_id=5678)
        finding.review_id = review_id

        session = AsyncMock()
        session.get = AsyncMock(side_effect=[review, repo])
        scalars_mock = MagicMock()
        scalars_mock.all.return_value = [finding]
        execute_result = MagicMock()
        execute_result.scalars.return_value = scalars_mock
        session.execute = AsyncMock(return_value=execute_result)

        client = MagicMock()
        update_review_resp = _make_response(200, {"id": 9001})
        update_comment_resp = _make_response(200, {"id": 5678})
        client.put = AsyncMock(return_value=update_review_resp)
        client.patch = AsyncMock(return_value=update_comment_resp)
        client.post = AsyncMock()

        with patch("kenjutsu.pipeline.publisher.httpx.AsyncClient") as mock_client_cls:
            mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=client)
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            await publish_review(session, review_id, "gh_token_test")

        # Should PUT (update) the review, not POST
        assert client.put.call_count == 1
        put_url = client.put.call_args.args[0]
        assert "/reviews/9001" in put_url

        # Should PATCH (update) the comment, not POST
        assert client.patch.call_count == 1
        patch_url = client.patch.call_args.args[0]
        assert "/pulls/comments/5678" in patch_url

        # No new review or comment created
        assert client.post.call_count == 0

    @pytest.mark.asyncio
    async def test_no_duplicate_comments_on_retry(self) -> None:
        """Retrying must not create additional comments when existing ones succeed."""
        review_id = uuid.uuid4()
        finding_id = uuid.uuid4()

        review = _make_review(
            review_id=review_id,
            github_review_id=9001,
            github_comment_ids={str(finding_id): 5678},
        )
        repo = _make_repo()
        finding = _make_finding(finding_id=finding_id, github_comment_id=5678)
        finding.review_id = review_id

        session = AsyncMock()
        session.get = AsyncMock(side_effect=[review, repo])
        scalars_mock = MagicMock()
        scalars_mock.all.return_value = [finding]
        execute_result = MagicMock()
        execute_result.scalars.return_value = scalars_mock
        session.execute = AsyncMock(return_value=execute_result)

        client = MagicMock()
        client.put = AsyncMock(return_value=_make_response(200, {"id": 9001}))
        client.patch = AsyncMock(return_value=_make_response(200, {"id": 5678}))
        client.post = AsyncMock()

        with patch("kenjutsu.pipeline.publisher.httpx.AsyncClient") as mock_client_cls:
            mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=client)
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            await publish_review(session, review_id, "gh_token_test")

        assert client.post.call_count == 0


# ---------------------------------------------------------------------------
# Tests: publish_review — 404 recovery
# ---------------------------------------------------------------------------


class TestPublishReviewRecovery:
    @pytest.mark.asyncio
    async def test_recreates_review_after_404(self) -> None:
        """If GitHub review is deleted (404 on PUT), a new one is created."""
        review_id = uuid.uuid4()
        finding_id = uuid.uuid4()

        review = _make_review(review_id=review_id, github_review_id=9001)
        repo = _make_repo()
        finding = _make_finding(finding_id=finding_id)
        finding.review_id = review_id

        session = AsyncMock()
        session.get = AsyncMock(side_effect=[review, repo])
        scalars_mock = MagicMock()
        scalars_mock.all.return_value = [finding]
        execute_result = MagicMock()
        execute_result.scalars.return_value = scalars_mock
        session.execute = AsyncMock(return_value=execute_result)

        client = MagicMock()
        # PUT returns 404 (review deleted)
        not_found_resp = _make_response(404)
        not_found_resp.raise_for_status.return_value = None  # 404 handled gracefully
        client.put = AsyncMock(return_value=not_found_resp)
        # POST creates a fresh review and comment
        client.post = AsyncMock(
            side_effect=[
                _make_response(200, {"id": 9999}),
                _make_response(200, {"id": 1111}),
            ]
        )
        client.patch = AsyncMock()

        with patch("kenjutsu.pipeline.publisher.httpx.AsyncClient") as mock_client_cls:
            mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=client)
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            await publish_review(session, review_id, "gh_token_test")

        # New review was created
        assert review.github_review_id == 9999
        # New comment was created (no PATCH since comment_id_map was cleared)
        assert client.post.call_count == 2
        assert client.patch.call_count == 0

    @pytest.mark.asyncio
    async def test_recreates_comment_after_404(self) -> None:
        """If a comment is deleted (404 on PATCH), a new one is created."""
        review_id = uuid.uuid4()
        finding_id = uuid.uuid4()

        review = _make_review(review_id=review_id, github_review_id=9001)
        repo = _make_repo()
        finding = _make_finding(finding_id=finding_id, github_comment_id=5678)
        finding.review_id = review_id

        session = AsyncMock()
        session.get = AsyncMock(side_effect=[review, repo])
        scalars_mock = MagicMock()
        scalars_mock.all.return_value = [finding]
        execute_result = MagicMock()
        execute_result.scalars.return_value = scalars_mock
        session.execute = AsyncMock(return_value=execute_result)

        client = MagicMock()
        client.put = AsyncMock(return_value=_make_response(200, {"id": 9001}))
        # PATCH returns 404 (comment deleted)
        not_found_resp = _make_response(404)
        not_found_resp.raise_for_status.return_value = None
        client.patch = AsyncMock(return_value=not_found_resp)
        # POST creates a fresh comment
        client.post = AsyncMock(return_value=_make_response(200, {"id": 2222}))

        with patch("kenjutsu.pipeline.publisher.httpx.AsyncClient") as mock_client_cls:
            mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=client)
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            await publish_review(session, review_id, "gh_token_test")

        # New comment created
        assert finding.github_comment_id == 2222
        assert finding.published is True

    @pytest.mark.asyncio
    async def test_raises_value_error_for_missing_review(self) -> None:
        session = AsyncMock()
        session.get = AsyncMock(return_value=None)

        with pytest.raises(ValueError, match="not found"):
            await publish_review(session, uuid.uuid4(), "gh_token_test")

    @pytest.mark.asyncio
    async def test_raises_value_error_for_missing_repo(self) -> None:
        review = _make_review()
        session = AsyncMock()
        session.get = AsyncMock(side_effect=[review, None])

        with pytest.raises(ValueError, match="not found"):
            await publish_review(session, review.id, "gh_token_test")
