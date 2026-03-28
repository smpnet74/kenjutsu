"""Pending review publisher — publishes findings as a single GitHub PR review.

Uses the pending-review pattern: all inline comments are accumulated locally
and submitted atomically in one API call.  This ensures reviewers see a single
notification rather than a flood of individual comments.

Rate limit awareness:
  - Tracks X-RateLimit-Remaining after each call.
  - When remaining falls below RATE_LIMIT_FLOOR, only CRITICAL findings are
    included in subsequent publishes.
  - Raises RateLimitExceeded after a successful publish if remaining is low,
    so callers can implement back-off before the next review.

Redaction:
  - PUBLISH: full description published as-is.
  - REDACT_AND_PUBLISH: description published but evidence_sources are omitted,
    preventing any internal signal traces from leaking into public comments.
  - SUPPRESS / AUDIT_ONLY: finding is skipped entirely.
"""

from __future__ import annotations

from typing import Final

import httpx

from kenjutsu.models import Finding, Publishability, Severity

# Severity badges rendered in inline comment bodies.
SEVERITY_BADGES: Final[dict[Severity, str]] = {
    Severity.CRITICAL: "🔴 **critical**",
    Severity.WARNING: "🟡 **warning**",
    Severity.SUGGESTION: "💡 **suggestion**",
}

# Do not attempt further publishes when fewer than this many API calls remain.
RATE_LIMIT_FLOOR: Final[int] = 20

# Severity ordering used to prioritise findings when rate-limited.
_SEVERITY_ORDER: Final[dict[Severity, int]] = {
    Severity.CRITICAL: 0,
    Severity.WARNING: 1,
    Severity.SUGGESTION: 2,
}

GITHUB_API_BASE: Final[str] = "https://api.github.com"


class RateLimitExceededError(Exception):
    """Raised after a publish when the GitHub rate limit is nearly exhausted."""


class PendingReviewPublisher:
    """Publishes a batch of findings as a single GitHub PR review.

    Parameters
    ----------
    token:
        GitHub token with ``pull_requests: write`` permission.
    owner:
        Repository owner (user or org).
    repo:
        Repository name.
    pull_number:
        PR number to review.
    client:
        Optional pre-configured ``httpx.Client``.  Provide a mock client in
        tests to avoid hitting the live GitHub API.
    """

    def __init__(
        self,
        token: str,
        owner: str,
        repo: str,
        pull_number: int,
        client: httpx.Client | None = None,
    ) -> None:
        self._owner = owner
        self._repo = repo
        self._pull_number = pull_number
        self._rate_limit_remaining: int | None = None
        self._client = client or httpx.Client(
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def rate_limit_remaining(self) -> int | None:
        """GitHub rate limit remaining as of the last API response, or None."""
        return self._rate_limit_remaining

    def format_comment_body(self, finding: Finding) -> str:
        """Format a single finding into a GitHub inline comment body.

        Applies the severity badge, finding description, and (optionally) a
        GitHub suggestion block.  When publishability is REDACT_AND_PUBLISH the
        evidence_sources list is omitted to avoid leaking internal signal traces.
        """
        badge = SEVERITY_BADGES[finding.severity]
        body = f"{badge}\n\n{finding.description}"

        if finding.suggestion:
            body += f"\n\n```suggestion\n{finding.suggestion}\n```"

        return body

    def publish(self, findings: list[Finding], body: str = "") -> dict:  # type: ignore[type-arg]
        """Submit all publishable findings as a single PR review.

        Findings are sorted by severity (critical first) before submission.
        When the publisher is near the GitHub rate limit only CRITICAL findings
        are included.

        Parameters
        ----------
        findings:
            Full list of findings for this review.  Non-publishable findings
            (SUPPRESS, AUDIT_ONLY) are silently skipped.
        body:
            Optional top-level review body text.

        Returns
        -------
        dict
            The review object returned by the GitHub API.

        Raises
        ------
        RateLimitExceeded
            After a successful publish if X-RateLimit-Remaining drops below
            RATE_LIMIT_FLOOR, signalling the caller to back off.
        httpx.HTTPStatusError
            For non-2xx responses from GitHub.
        """
        publishable = [f for f in findings if self._is_publishable(f)]
        publishable.sort(key=lambda f: _SEVERITY_ORDER[f.severity])

        if self._near_rate_limit():
            publishable = [f for f in publishable if f.severity == Severity.CRITICAL]

        comments = [self._build_comment(f) for f in publishable]

        url = f"{GITHUB_API_BASE}/repos/{self._owner}/{self._repo}/pulls/{self._pull_number}/reviews"
        payload: dict = {"body": body, "event": "COMMENT", "comments": comments}  # type: ignore[type-arg]

        response = self._client.post(url, json=payload)
        self._record_rate_limit(response)
        response.raise_for_status()

        if self._near_rate_limit():
            raise RateLimitExceededError(f"GitHub rate limit nearly exhausted: {self._rate_limit_remaining} remaining")

        return response.json()  # type: ignore[no-any-return]

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _is_publishable(self, finding: Finding) -> bool:
        return finding.publishability in (
            Publishability.PUBLISH,
            Publishability.REDACT_AND_PUBLISH,
        )

    def _near_rate_limit(self) -> bool:
        return self._rate_limit_remaining is not None and self._rate_limit_remaining < RATE_LIMIT_FLOOR

    def _record_rate_limit(self, response: httpx.Response) -> None:
        raw = response.headers.get("X-RateLimit-Remaining")
        if raw is not None:
            self._rate_limit_remaining = int(raw)

    def _build_comment(self, finding: Finding) -> dict:  # type: ignore[type-arg]
        """Build a GitHub review comment dict for one finding."""
        comment: dict = {  # type: ignore[type-arg]
            "path": finding.file_path,
            "body": self.format_comment_body(finding),
            "side": "RIGHT",
        }
        if finding.line_start == finding.line_end:
            comment["line"] = finding.line_end
        else:
            comment["start_line"] = finding.line_start
            comment["start_side"] = "RIGHT"
            comment["line"] = finding.line_end
        return comment
