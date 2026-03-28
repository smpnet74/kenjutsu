"""Integration tests for PendingReviewPublisher against a mocked GitHub API.

These tests verify the full publish() path including:
- Correct HTTP method and URL construction
- Request payload shape (event, body, comments array)
- Atomic submission (single POST for all findings)
- Suppressed findings absent from payload
- Rate-limit header propagation and RateLimitExceeded signal
- Empty-findings edge case (review still posted, no comments)
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from kenjutsu.models import Category, Confidence, Finding, Origin, Publishability, Severity
from kenjutsu.publisher import PendingReviewPublisher, RateLimitExceededError
from kenjutsu.publisher.pending_review import GITHUB_API_BASE, RATE_LIMIT_FLOOR

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _finding(**overrides: object) -> Finding:
    defaults: dict[str, object] = {
        "file_path": "src/main.py",
        "line_start": 5,
        "line_end": 5,
        "origin": Origin.LLM,
        "confidence": Confidence.HIGH,
        "severity": Severity.WARNING,
        "category": Category.BUG,
        "publishability": Publishability.PUBLISH,
        "description": "Missing input validation",
    }
    defaults.update(overrides)
    return Finding(**defaults)  # type: ignore[arg-type]


def _mock_response(
    review_id: int = 1,
    state: str = "PENDING",
    rate_limit_remaining: int = 100,
) -> MagicMock:
    response = MagicMock()
    response.json.return_value = {"id": review_id, "state": state}
    response.raise_for_status.return_value = None
    response.headers = {"X-RateLimit-Remaining": str(rate_limit_remaining)}
    return response


def _make_publisher(
    response: MagicMock | None = None,
    rate_limit_remaining: int = 100,
) -> tuple[PendingReviewPublisher, MagicMock]:
    mock_client = MagicMock()
    mock_client.post.return_value = response or _mock_response(rate_limit_remaining=rate_limit_remaining)
    publisher = PendingReviewPublisher(
        token="ghp_integration_test",
        owner="acme",
        repo="kenjutsu",
        pull_number=7,
        client=mock_client,
    )
    return publisher, mock_client


# ---------------------------------------------------------------------------
# HTTP contract
# ---------------------------------------------------------------------------


class TestHTTPContract:
    def test_posts_to_correct_url(self) -> None:
        pub, mc = _make_publisher()
        pub.publish([_finding()])
        expected_url = f"{GITHUB_API_BASE}/repos/acme/kenjutsu/pulls/7/reviews"
        mc.post.assert_called_once()
        actual_url = mc.post.call_args[0][0]
        assert actual_url == expected_url

    def test_single_post_for_multiple_findings(self) -> None:
        """All comments must be submitted in exactly one API call."""
        pub, mc = _make_publisher()
        findings = [_finding(line_start=i, line_end=i) for i in range(1, 6)]
        pub.publish(findings)
        assert mc.post.call_count == 1

    def test_event_is_comment(self) -> None:
        pub, mc = _make_publisher()
        pub.publish([_finding()])
        payload = mc.post.call_args[1]["json"]
        assert payload["event"] == "COMMENT"

    def test_custom_body_passed_through(self) -> None:
        pub, mc = _make_publisher()
        pub.publish([_finding()], body="Kenjutsu automated review")
        payload = mc.post.call_args[1]["json"]
        assert payload["body"] == "Kenjutsu automated review"

    def test_empty_findings_posts_empty_comments(self) -> None:
        pub, mc = _make_publisher()
        pub.publish([])
        payload = mc.post.call_args[1]["json"]
        assert payload["comments"] == []

    def test_returns_github_review_object(self) -> None:
        response = _mock_response(review_id=42, state="PENDING")
        pub, _ = _make_publisher(response=response)
        result = pub.publish([_finding()])
        assert result["id"] == 42
        assert result["state"] == "PENDING"


# ---------------------------------------------------------------------------
# Filtering — suppressed findings must not appear in payload
# ---------------------------------------------------------------------------


class TestFilteringIntegration:
    def _payload_comments(self, mock_client: MagicMock) -> list[dict]:  # type: ignore[type-arg]
        return mock_client.post.call_args[1]["json"]["comments"]  # type: ignore[no-any-return]

    def test_suppressed_finding_absent(self) -> None:
        pub, mc = _make_publisher()
        pub.publish(
            [
                _finding(publishability=Publishability.SUPPRESS, line_start=1, line_end=1),
                _finding(publishability=Publishability.PUBLISH, line_start=2, line_end=2),
            ]
        )
        comments = self._payload_comments(mc)
        assert len(comments) == 1

    def test_audit_only_finding_absent(self) -> None:
        pub, mc = _make_publisher()
        pub.publish(
            [
                _finding(publishability=Publishability.AUDIT_ONLY, line_start=1, line_end=1),
            ]
        )
        comments = self._payload_comments(mc)
        assert len(comments) == 0

    def test_all_publishable_types_present(self) -> None:
        pub, mc = _make_publisher()
        pub.publish(
            [
                _finding(publishability=Publishability.PUBLISH, line_start=1, line_end=1),
                _finding(publishability=Publishability.REDACT_AND_PUBLISH, line_start=2, line_end=2),
            ]
        )
        assert len(self._payload_comments(mc)) == 2


# ---------------------------------------------------------------------------
# Rate limit header propagation
# ---------------------------------------------------------------------------


class TestRateLimitIntegration:
    def test_rate_limit_remaining_updated_after_publish(self) -> None:
        pub, _ = _make_publisher(rate_limit_remaining=75)
        pub.publish([_finding()])
        assert pub.rate_limit_remaining == 75

    def test_rate_limit_exceeded_raised_when_near_floor(self) -> None:
        floor_minus_one = RATE_LIMIT_FLOOR - 1
        pub, _ = _make_publisher(rate_limit_remaining=floor_minus_one)
        with pytest.raises(RateLimitExceededError):
            pub.publish([_finding()])

    def test_no_exception_when_above_floor(self) -> None:
        pub, _ = _make_publisher(rate_limit_remaining=RATE_LIMIT_FLOOR)
        # Should not raise — floor is exclusive lower bound
        pub.publish([_finding()])

    def test_near_limit_only_critical_in_payload(self) -> None:
        """When already near the limit, only critical findings are sent."""
        pub, mc = _make_publisher(rate_limit_remaining=100)

        # First call brings remaining below floor
        low_response = _mock_response(rate_limit_remaining=RATE_LIMIT_FLOOR - 1)
        mc.post.return_value = low_response

        with pytest.raises(RateLimitExceededError):
            pub.publish([_finding(severity=Severity.CRITICAL, line_start=1, line_end=1)])

        # On the next call the publisher should filter to critical-only
        mc.post.return_value = low_response
        with pytest.raises(RateLimitExceededError):
            pub.publish(
                [
                    _finding(severity=Severity.CRITICAL, line_start=10, line_end=10),
                    _finding(severity=Severity.WARNING, line_start=11, line_end=11),
                    _finding(severity=Severity.SUGGESTION, line_start=12, line_end=12),
                ]
            )

        last_payload = mc.post.call_args[1]["json"]
        assert len(last_payload["comments"]) == 1
        assert "🔴" in last_payload["comments"][0]["body"]

    def test_missing_rate_limit_header_no_exception(self) -> None:
        response = _mock_response()
        response.headers = {}  # no rate-limit header
        pub, _ = _make_publisher(response=response)
        result = pub.publish([_finding()])  # should not raise
        assert result["id"] == 1
        assert pub.rate_limit_remaining is None


# ---------------------------------------------------------------------------
# Redaction — evidence sources must not appear in published comment
# ---------------------------------------------------------------------------


class TestRedactionIntegration:
    def test_evidence_sources_not_in_comment_body(self) -> None:
        pub, mc = _make_publisher()
        f = _finding(
            publishability=Publishability.REDACT_AND_PUBLISH,
            description="SQL injection risk",
            evidence_sources=["ast_grep:sql_injection", "graph:user_input_to_db"],
        )
        pub.publish([f])
        payload = mc.post.call_args[1]["json"]
        body = payload["comments"][0]["body"]
        assert "ast_grep" not in body
        assert "graph:user_input_to_db" not in body
        assert "SQL injection risk" in body
