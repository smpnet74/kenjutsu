"""GitHub Check Run publisher for Kenjutsu review results.

Lifecycle:
  1. create()                  — open an in_progress Check Run
  2. update_with_annotations() — stream findings as they arrive (≤50 per call)
  3. complete()                — close with conclusion, title, and summary
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Protocol

from kenjutsu.models.findings import Finding, Origin, Publishability, Severity

ANNOTATION_BATCH_SIZE = 50

_SEVERITY_TO_LEVEL: dict[Severity, str] = {
    Severity.CRITICAL: "failure",
    Severity.WARNING: "warning",
    Severity.SUGGESTION: "notice",
}


# ---------------------------------------------------------------------------
# Client protocol — injectable for testing
# ---------------------------------------------------------------------------


class CheckRunClient(Protocol):
    """Minimal GitHub API surface needed by CheckRunPublisher."""

    async def create_check_run(self, owner: str, repo: str, payload: dict) -> dict:  # pragma: no cover
        ...

    async def update_check_run(  # pragma: no cover
        self, owner: str, repo: str, check_run_id: int, payload: dict
    ) -> dict: ...


# ---------------------------------------------------------------------------
# Pure helpers (exported for unit testing)
# ---------------------------------------------------------------------------


def _is_inline_publishable(finding: Finding) -> bool:
    """Return True only for defect findings that belong as inline annotations."""
    if finding.origin == Origin.PREDICTIVE:
        return False
    return finding.publishability in (Publishability.PUBLISH, Publishability.REDACT_AND_PUBLISH)


def _finding_to_annotation(finding: Finding) -> dict:
    message = finding.description
    if finding.suggestion:
        message = f"{finding.description}\n\nSuggestion: {finding.suggestion}"
    return {
        "path": finding.file_path,
        "start_line": finding.line_start,
        "end_line": finding.line_end,
        "annotation_level": _SEVERITY_TO_LEVEL.get(finding.severity, "notice"),
        "message": message,
    }


def _batch_annotations(annotations: list[dict]) -> list[list[dict]]:
    """Split annotation list into chunks of at most ANNOTATION_BATCH_SIZE."""
    return [annotations[i : i + ANNOTATION_BATCH_SIZE] for i in range(0, len(annotations), ANNOTATION_BATCH_SIZE)]


def _build_title(findings: list[Finding], duration_seconds: float) -> str:
    count = sum(1 for f in findings if _is_inline_publishable(f))
    return f"Kenjutsu: {count} finding(s) ({duration_seconds:.1f}s)"


def _build_summary(
    findings: list[Finding],
    predictive_warnings: list[Finding],
    duration_seconds: float,
) -> str:
    inline = [f for f in findings if _is_inline_publishable(f)]
    critical = sum(1 for f in inline if f.severity == Severity.CRITICAL)
    warnings = sum(1 for f in inline if f.severity == Severity.WARNING)
    suggestions = sum(1 for f in inline if f.severity == Severity.SUGGESTION)

    lines = [
        f"**Kenjutsu Review complete** — {len(inline)} finding(s) in {duration_seconds:.1f}s",
        "",
        "| Severity | Count |",
        "|----------|-------|",
        f"| Critical | {critical} |",
        f"| Warning  | {warnings} |",
        f"| Suggestion | {suggestions} |",
    ]

    if predictive_warnings:
        lines += [
            "",
            "## Predictions",
            "",
            "_These are statistical signals, not confirmed defects._",
            "",
        ]
        for pw in predictive_warnings:
            lines.append(f"- **{pw.category}**: {pw.description}")

    return "\n".join(lines)


def _determine_conclusion(findings: list[Finding]) -> str:
    inline = [f for f in findings if _is_inline_publishable(f)]
    if any(f.severity == Severity.CRITICAL for f in inline):
        return "failure"
    if inline:
        return "neutral"
    return "success"


# ---------------------------------------------------------------------------
# Publisher
# ---------------------------------------------------------------------------


class CheckRunPublisher:
    """Publishes Kenjutsu review results as GitHub Check Runs.

    Inject any object implementing CheckRunClient — real httpx wrapper in
    production, AsyncMock in tests.
    """

    def __init__(self, client: CheckRunClient, owner: str, repo: str, head_sha: str) -> None:
        self._client = client
        self._owner = owner
        self._repo = repo
        self._head_sha = head_sha

    async def create(self, name: str = "Kenjutsu Review") -> int:
        """Open an in_progress Check Run. Returns the GitHub check_run_id."""
        payload = {
            "name": name,
            "head_sha": self._head_sha,
            "status": "in_progress",
            "started_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        }
        result = await self._client.create_check_run(self._owner, self._repo, payload)
        return result["id"]

    async def update_with_annotations(self, check_run_id: int, findings: list[Finding]) -> None:
        """Stream publishable findings as annotations (≤50 per API call)."""
        annotations = [_finding_to_annotation(f) for f in findings if _is_inline_publishable(f)]
        if not annotations:
            return
        for batch in _batch_annotations(annotations):
            await self._client.update_check_run(
                self._owner,
                self._repo,
                check_run_id,
                {"output": {"title": "Kenjutsu Review", "summary": "Review in progress…", "annotations": batch}},
            )

    async def complete(
        self,
        check_run_id: int,
        findings: list[Finding],
        predictive_warnings: list[Finding],
        duration_seconds: float,
    ) -> None:
        """Close the Check Run with final conclusion, title, and summary.

        Annotations must have been streamed beforehand via update_with_annotations().
        The completion PATCH sets only the final status, conclusion, and output
        text — it does not re-send annotations to avoid duplicates on GitHub.
        """
        payload: dict = {
            "status": "completed",
            "conclusion": _determine_conclusion(findings),
            "completed_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "output": {
                "title": _build_title(findings, duration_seconds),
                "summary": _build_summary(findings, predictive_warnings, duration_seconds),
            },
        }
        await self._client.update_check_run(self._owner, self._repo, check_run_id, payload)
