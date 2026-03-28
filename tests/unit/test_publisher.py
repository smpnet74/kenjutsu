"""Unit tests for the PendingReviewPublisher.

Covers:
- Severity badge rendering
- Suggestion block formatting
- Redaction (REDACT_AND_PUBLISH does not leak evidence_sources)
- Publishability filtering
- Comment payload structure (single-line vs multi-line findings)
- Severity-based ordering
- Near-limit filtering (only critical findings when rate-limited)
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from kenjutsu.models import Category, Confidence, Finding, Origin, Publishability, Severity
from kenjutsu.publisher import SEVERITY_BADGES, PendingReviewPublisher, RateLimitExceededError


def _finding(**overrides: object) -> Finding:
    defaults: dict[str, object] = {
        "file_path": "src/auth.py",
        "line_start": 10,
        "line_end": 10,
        "origin": Origin.LLM,
        "confidence": Confidence.HIGH,
        "severity": Severity.WARNING,
        "category": Category.BUG,
        "publishability": Publishability.PUBLISH,
        "description": "Potential null dereference",
    }
    defaults.update(overrides)
    return Finding(**defaults)  # type: ignore[arg-type]


def _publisher(rate_limit_remaining: int | None = None) -> tuple[PendingReviewPublisher, MagicMock]:
    """Return a publisher wired to a mock httpx.Client and a canned success response."""
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.json.return_value = {"id": 1, "state": "PENDING"}
    mock_response.raise_for_status.return_value = None

    if rate_limit_remaining is not None:
        mock_response.headers = {"X-RateLimit-Remaining": str(rate_limit_remaining)}
    else:
        mock_response.headers = {}

    mock_client.post.return_value = mock_response

    pub = PendingReviewPublisher(
        token="ghp_test",
        owner="acme",
        repo="kenjutsu",
        pull_number=42,
        client=mock_client,
    )
    return pub, mock_client


# ---------------------------------------------------------------------------
# Severity badges
# ---------------------------------------------------------------------------


class TestSeverityBadges:
    def test_critical_badge(self) -> None:
        assert "🔴" in SEVERITY_BADGES[Severity.CRITICAL]
        assert "critical" in SEVERITY_BADGES[Severity.CRITICAL]

    def test_warning_badge(self) -> None:
        assert "🟡" in SEVERITY_BADGES[Severity.WARNING]
        assert "warning" in SEVERITY_BADGES[Severity.WARNING]

    def test_suggestion_badge(self) -> None:
        assert "💡" in SEVERITY_BADGES[Severity.SUGGESTION]
        assert "suggestion" in SEVERITY_BADGES[Severity.SUGGESTION]

    def test_all_severities_covered(self) -> None:
        assert set(SEVERITY_BADGES.keys()) == set(Severity)


# ---------------------------------------------------------------------------
# Comment body formatting
# ---------------------------------------------------------------------------


class TestFormatCommentBody:
    def setup_method(self) -> None:
        self.pub, _ = _publisher()

    def test_critical_badge_in_body(self) -> None:
        f = _finding(severity=Severity.CRITICAL)
        body = self.pub.format_comment_body(f)
        assert "🔴" in body
        assert "critical" in body

    def test_warning_badge_in_body(self) -> None:
        f = _finding(severity=Severity.WARNING)
        body = self.pub.format_comment_body(f)
        assert "🟡" in body
        assert "warning" in body

    def test_suggestion_badge_in_body(self) -> None:
        f = _finding(severity=Severity.SUGGESTION)
        body = self.pub.format_comment_body(f)
        assert "💡" in body
        assert "suggestion" in body

    def test_description_included(self) -> None:
        f = _finding(description="Use parameterised queries to avoid SQL injection")
        body = self.pub.format_comment_body(f)
        assert "Use parameterised queries" in body

    def test_no_suggestion_block_when_none(self) -> None:
        f = _finding(suggestion=None)
        body = self.pub.format_comment_body(f)
        assert "```suggestion" not in body

    def test_suggestion_block_rendered(self) -> None:
        f = _finding(suggestion="return user.get('email', '')")
        body = self.pub.format_comment_body(f)
        assert "```suggestion" in body
        assert "return user.get('email', '')" in body
        assert body.strip().endswith("```")

    def test_redact_and_publish_omits_evidence_sources(self) -> None:
        """evidence_sources must not appear in the published comment body."""
        f = _finding(
            publishability=Publishability.REDACT_AND_PUBLISH,
            description="Hardcoded credential detected",
            evidence_sources=["ast_grep:hardcoded_secret", "graph:taint_path"],
        )
        body = self.pub.format_comment_body(f)
        assert "ast_grep" not in body
        assert "graph:taint_path" not in body
        assert "Hardcoded credential detected" in body

    def test_publish_includes_description(self) -> None:
        f = _finding(publishability=Publishability.PUBLISH, description="Null check missing")
        body = self.pub.format_comment_body(f)
        assert "Null check missing" in body


# ---------------------------------------------------------------------------
# Publishability filtering
# ---------------------------------------------------------------------------


class TestPublishabilityFiltering:
    def setup_method(self) -> None:
        self.pub, self.mock_client = _publisher(rate_limit_remaining=100)

    def _call_publish(self, *findings: Finding) -> None:
        self.pub.publish(list(findings))

    def _captured_comments(self) -> list[dict]:  # type: ignore[type-arg]
        payload = self.mock_client.post.call_args[1]["json"]
        return payload["comments"]  # type: ignore[no-any-return]

    def test_publish_finding_included(self) -> None:
        f = _finding(publishability=Publishability.PUBLISH)
        self._call_publish(f)
        assert len(self._captured_comments()) == 1

    def test_redact_and_publish_included(self) -> None:
        f = _finding(publishability=Publishability.REDACT_AND_PUBLISH)
        self._call_publish(f)
        assert len(self._captured_comments()) == 1

    def test_suppress_excluded(self) -> None:
        f = _finding(publishability=Publishability.SUPPRESS)
        self._call_publish(f)
        assert len(self._captured_comments()) == 0

    def test_audit_only_excluded(self) -> None:
        f = _finding(publishability=Publishability.AUDIT_ONLY)
        self._call_publish(f)
        assert len(self._captured_comments()) == 0

    def test_mixed_findings_filtered(self) -> None:
        findings = [
            _finding(publishability=Publishability.PUBLISH, line_start=1, line_end=1),
            _finding(publishability=Publishability.SUPPRESS, line_start=2, line_end=2),
            _finding(publishability=Publishability.AUDIT_ONLY, line_start=3, line_end=3),
            _finding(publishability=Publishability.REDACT_AND_PUBLISH, line_start=4, line_end=4),
        ]
        self._call_publish(*findings)
        assert len(self._captured_comments()) == 2


# ---------------------------------------------------------------------------
# Comment payload structure
# ---------------------------------------------------------------------------


class TestCommentPayload:
    def setup_method(self) -> None:
        self.pub, self.mock_client = _publisher(rate_limit_remaining=100)

    def _captured_comments(self) -> list[dict]:  # type: ignore[type-arg]
        payload = self.mock_client.post.call_args[1]["json"]
        return payload["comments"]  # type: ignore[no-any-return]

    def test_single_line_uses_line_only(self) -> None:
        f = _finding(line_start=42, line_end=42)
        self.pub.publish([f])
        comment = self._captured_comments()[0]
        assert comment["line"] == 42
        assert "start_line" not in comment

    def test_multi_line_includes_start_line(self) -> None:
        f = _finding(line_start=10, line_end=20)
        self.pub.publish([f])
        comment = self._captured_comments()[0]
        assert comment["start_line"] == 10
        assert comment["line"] == 20

    def test_file_path_in_comment(self) -> None:
        f = _finding(file_path="kenjutsu/publisher/pending_review.py")
        self.pub.publish([f])
        comment = self._captured_comments()[0]
        assert comment["path"] == "kenjutsu/publisher/pending_review.py"

    def test_side_is_right(self) -> None:
        f = _finding()
        self.pub.publish([f])
        comment = self._captured_comments()[0]
        assert comment["side"] == "RIGHT"


# ---------------------------------------------------------------------------
# Severity ordering
# ---------------------------------------------------------------------------


class TestSeverityOrdering:
    def setup_method(self) -> None:
        self.pub, self.mock_client = _publisher(rate_limit_remaining=100)

    def _captured_comments(self) -> list[dict]:  # type: ignore[type-arg]
        payload = self.mock_client.post.call_args[1]["json"]
        return payload["comments"]  # type: ignore[no-any-return]

    def test_critical_before_warning_before_suggestion(self) -> None:
        findings = [
            _finding(severity=Severity.SUGGESTION, line_start=3, line_end=3),
            _finding(severity=Severity.CRITICAL, line_start=1, line_end=1),
            _finding(severity=Severity.WARNING, line_start=2, line_end=2),
        ]
        self.pub.publish(findings)
        comments = self._captured_comments()
        bodies = [c["body"] for c in comments]
        assert "🔴" in bodies[0]
        assert "🟡" in bodies[1]
        assert "💡" in bodies[2]


# ---------------------------------------------------------------------------
# Rate limit behaviour
# ---------------------------------------------------------------------------


class TestRateLimitBehaviour:
    def _publisher_with_limit(self, remaining: int) -> tuple[PendingReviewPublisher, MagicMock]:
        return _publisher(rate_limit_remaining=remaining)

    def _captured_comments(self, mock_client: MagicMock) -> list[dict]:  # type: ignore[type-arg]
        payload = mock_client.post.call_args[1]["json"]
        return payload["comments"]  # type: ignore[no-any-return]

    def test_healthy_limit_publishes_all(self) -> None:
        pub, mc = self._publisher_with_limit(100)
        findings = [
            _finding(severity=Severity.CRITICAL, line_start=1, line_end=1),
            _finding(severity=Severity.WARNING, line_start=2, line_end=2),
            _finding(severity=Severity.SUGGESTION, line_start=3, line_end=3),
        ]
        pub.publish(findings)
        assert len(self._captured_comments(mc)) == 3

    def test_near_limit_only_critical_published(self) -> None:
        pub, mc = self._publisher_with_limit(100)
        # Simulate a first call that returns low remaining
        first_response = MagicMock()
        first_response.json.return_value = {"id": 99}
        first_response.raise_for_status.return_value = None
        first_response.headers = {"X-RateLimit-Remaining": "5"}  # below floor
        mc.post.return_value = first_response

        with pytest.raises(RateLimitExceededError):
            pub.publish([_finding(severity=Severity.WARNING)])

        # Second publish: rate_limit_remaining is now 5, only critical included
        second_response = MagicMock()
        second_response.json.return_value = {"id": 100}
        second_response.raise_for_status.return_value = None
        second_response.headers = {"X-RateLimit-Remaining": "4"}
        mc.post.return_value = second_response

        with pytest.raises(RateLimitExceededError):
            pub.publish(
                [
                    _finding(severity=Severity.CRITICAL, line_start=1, line_end=1),
                    _finding(severity=Severity.WARNING, line_start=2, line_end=2),
                ]
            )

        # Only the critical finding should have been sent
        assert len(self._captured_comments(mc)) == 1
        assert "🔴" in self._captured_comments(mc)[0]["body"]

    def test_rate_limit_remaining_property_updated_after_call(self) -> None:
        pub, _ = _publisher(rate_limit_remaining=80)
        pub.publish([_finding()])
        assert pub.rate_limit_remaining == 80

    def test_rate_limit_remaining_none_before_first_call(self) -> None:
        pub, _ = _publisher(rate_limit_remaining=None)
        assert pub.rate_limit_remaining is None

    def test_raises_rate_limit_exceeded_after_publish(self) -> None:
        pub, _ = _publisher(rate_limit_remaining=5)
        with pytest.raises(RateLimitExceededError, match="rate limit"):
            pub.publish([_finding()])
