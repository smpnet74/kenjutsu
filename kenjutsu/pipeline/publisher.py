"""Idempotent GitHub PR review publisher.

Pipeline Step 8 — spec v3 § 4.5.

Publishes findings as GitHub PR review comments. Retrying is safe: if a
review/comment was already created its stored ID is used to update the
existing object rather than posting a duplicate.

Deletion recovery: if GitHub returns 404 on an update (the review or
comment was deleted externally) the publisher falls back to creating a
fresh object and logs a warning.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import httpx
from sqlalchemy import select

from kenjutsu.db.models import Finding, Repo, Review
from kenjutsu.models.findings import Publishability

if TYPE_CHECKING:
    from uuid import UUID

    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

GITHUB_API_BASE = "https://api.github.com"

# Publishability values that should result in a comment on the PR
_PUBLISHABLE = {Publishability.PUBLISH, Publishability.REDACT_AND_PUBLISH}


def _auth_headers(token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def _finding_comment_body(finding: Finding) -> str:
    """Build the markdown comment body for a single finding.

    REDACT_AND_PUBLISH findings have description, suggestion, and fingerprint
    replaced with [REDACTED] to prevent leaking sensitive data into PR threads.
    """
    is_redacted = finding.publishability == Publishability.REDACT_AND_PUBLISH.value

    severity_icon = {
        "critical": "🔴",
        "warning": "🟡",
        "suggestion": "🔵",
    }.get(finding.severity, "⚪")

    description = "[REDACTED]" if is_redacted else finding.description

    lines = [
        f"{severity_icon} **{finding.severity.upper()}** [{finding.category}] — {description}",
    ]
    if not is_redacted and finding.suggestion:
        lines.append("")
        lines.append(f"**Suggestion:** {finding.suggestion}")
    lines.append("")

    fingerprint = "[REDACTED]" if is_redacted else f"`{finding.fingerprint}`"
    lines.append(
        f"*origin: {finding.origin} · confidence: {finding.confidence} · fingerprint: {fingerprint}*"
    )
    return "\n".join(lines)


async def _create_review(
    client: httpx.AsyncClient,
    owner: str,
    repo: str,
    pr_number: int,
    head_sha: str,
    token: str,
) -> int:
    """Create a new GitHub pull request review (PENDING, no body).

    Returns the new review ID.
    """
    url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}/pulls/{pr_number}/reviews"
    payload: dict[str, object] = {
        "commit_id": head_sha,
        "event": "COMMENT",
        "body": "Kenjutsu automated review",
        "comments": [],
    }
    resp = await client.post(url, json=payload, headers=_auth_headers(token))
    resp.raise_for_status()
    data = resp.json()
    review_id: int = data["id"]
    logger.info("Created GitHub review %d for %s/%s PR#%d", review_id, owner, repo, pr_number)
    return review_id


async def _update_review(
    client: httpx.AsyncClient,
    owner: str,
    repo: str,
    pr_number: int,
    review_id: int,
    token: str,
) -> bool:
    """Update an existing GitHub PR review body.

    Returns True on success, False if the review no longer exists (404).
    """
    url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}/pulls/{pr_number}/reviews/{review_id}"
    payload = {"body": "Kenjutsu automated review"}
    resp = await client.put(url, json=payload, headers=_auth_headers(token))
    if resp.status_code == 404:
        logger.warning(
            "GitHub review %d on %s/%s PR#%d no longer exists — will recreate",
            review_id,
            owner,
            repo,
            pr_number,
        )
        return False
    resp.raise_for_status()
    return True


async def _create_comment(
    client: httpx.AsyncClient,
    owner: str,
    repo: str,
    pr_number: int,
    commit_id: str,
    finding: Finding,
    token: str,
) -> int:
    """Create an inline PR review comment for a finding.

    Returns the new comment ID.
    """
    url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}/pulls/{pr_number}/comments"
    payload: dict[str, object] = {
        "body": _finding_comment_body(finding),
        "commit_id": commit_id,
        "path": finding.file_path,
        "line": finding.line_end,
        "side": "RIGHT",
    }
    resp = await client.post(url, json=payload, headers=_auth_headers(token))
    resp.raise_for_status()
    data = resp.json()
    comment_id: int = data["id"]
    logger.debug("Created comment %d for finding %s", comment_id, finding.id)
    return comment_id


async def _update_comment(
    client: httpx.AsyncClient,
    owner: str,
    repo: str,
    comment_id: int,
    finding: Finding,
    token: str,
) -> bool:
    """Update an existing inline PR review comment.

    Returns True on success, False if the comment no longer exists (404).
    """
    url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}/pulls/comments/{comment_id}"
    payload = {"body": _finding_comment_body(finding)}
    resp = await client.patch(url, json=payload, headers=_auth_headers(token))
    if resp.status_code == 404:
        logger.warning(
            "GitHub comment %d on %s/%s no longer exists — will recreate",
            comment_id,
            owner,
            repo,
        )
        return False
    resp.raise_for_status()
    return True


async def publish_review(
    session: AsyncSession,
    review_id: UUID,
    installation_id: UUID,
    github_token: str,
) -> None:
    """Publish or update a GitHub PR review idempotently.

    On first call: creates a GitHub PR review and inline comments, then
    stores the returned IDs in the DB so a retry can update rather than
    duplicate.

    On retry: uses stored IDs to update existing objects. If GitHub
    returns 404 (externally deleted) falls back to creating fresh objects
    and logs a warning.

    Args:
        session: Async SQLAlchemy session. Caller is responsible for
            committing or rolling back.
        review_id: Primary key of the Review row to publish.
        installation_id: Tenant identifier. All DB queries are scoped to
            this installation to enforce tenant boundaries.
        github_token: GitHub personal access token or installation token
            with pull_requests write permission.

    Raises:
        ValueError: review_id not found, repo not found, or head SHA
            mismatch (PR was force-pushed since analysis).
        httpx.HTTPStatusError: GitHub API returned a non-recoverable error.
    """
    # ------------------------------------------------------------------
    # 1. Load review and its publishable findings — scoped by installation_id
    # ------------------------------------------------------------------
    review_result = await session.execute(
        select(Review)
        .join(Repo, Review.repo_id == Repo.id)
        .where(Review.id == review_id, Repo.installation_id == installation_id)
    )
    review_row = review_result.scalar_one_or_none()
    if review_row is None:
        raise ValueError(f"Review {review_id} not found")

    repo_result = await session.execute(
        select(Repo).where(Repo.id == review_row.repo_id, Repo.installation_id == installation_id)
    )
    repo_row = repo_result.scalar_one_or_none()
    if repo_row is None:
        raise ValueError(f"Repo {review_row.repo_id} not found")

    owner, repo_name = repo_row.full_name.split("/", 1)
    pr_number: int = review_row.pr_number
    head_sha: str = review_row.head_sha

    result = await session.execute(select(Finding).where(Finding.review_id == review_id))
    all_findings: list[Finding] = list(result.scalars().all())

    publishable_findings = [f for f in all_findings if f.publishability in {p.value for p in _PUBLISHABLE}]

    # github_comment_ids is stored as {str(finding_id): comment_id}
    comment_id_map: dict[str, int] = dict(review_row.github_comment_ids or {})

    async with httpx.AsyncClient(timeout=30.0) as client:
        # ------------------------------------------------------------------
        # 2. SHA guard — abort if the PR was force-pushed since analysis
        # ------------------------------------------------------------------
        pr_resp = await client.get(
            f"{GITHUB_API_BASE}/repos/{owner}/{repo_name}/pulls/{pr_number}",
            headers=_auth_headers(github_token),
        )
        pr_resp.raise_for_status()
        current_sha: str = pr_resp.json()["head"]["sha"]
        if current_sha != head_sha:
            logger.warning(
                "PR %s/%s #%d head SHA changed from %s to %s — aborting publish",
                owner,
                repo_name,
                pr_number,
                head_sha,
                current_sha,
            )
            raise ValueError(
                f"Head SHA mismatch for PR #{pr_number}: expected {head_sha}, got {current_sha}"
            )

        # ------------------------------------------------------------------
        # 3. Ensure the GitHub review exists
        # ------------------------------------------------------------------
        github_review_id: int | None = review_row.github_review_id

        if github_review_id is None:
            # First publish — create the review
            github_review_id = await _create_review(client, owner, repo_name, pr_number, head_sha, github_token)
            review_row.github_review_id = github_review_id
            await session.flush()  # checkpoint before next network call
        else:
            # Retry — update the existing review; recreate if deleted
            updated = await _update_review(client, owner, repo_name, pr_number, github_review_id, github_token)
            if not updated:
                # Review was deleted externally — create a fresh one
                github_review_id = await _create_review(client, owner, repo_name, pr_number, head_sha, github_token)
                review_row.github_review_id = github_review_id
                # All previous comment IDs are now stale — clear them so
                # every finding gets a fresh comment below
                comment_id_map = {}
                await session.flush()  # checkpoint before next network call

        # ------------------------------------------------------------------
        # 4. Create or update inline comments for each publishable finding
        # ------------------------------------------------------------------
        for finding in publishable_findings:
            finding_key = str(finding.id)
            existing_comment_id = comment_id_map.get(finding_key) or finding.github_comment_id

            if existing_comment_id is None:
                # First publish for this finding
                new_comment_id = await _create_comment(
                    client, owner, repo_name, pr_number, head_sha, finding, github_token
                )
                finding.github_comment_id = new_comment_id
                finding.published = True
                comment_id_map[finding_key] = new_comment_id
                review_row.github_comment_ids = dict(comment_id_map)
                await session.flush()  # checkpoint after each new comment ID
            else:
                # Retry — update existing comment; recreate if deleted
                updated = await _update_comment(client, owner, repo_name, existing_comment_id, finding, github_token)
                if not updated:
                    new_comment_id = await _create_comment(
                        client, owner, repo_name, pr_number, head_sha, finding, github_token
                    )
                    finding.github_comment_id = new_comment_id
                    comment_id_map[finding_key] = new_comment_id
                    review_row.github_comment_ids = dict(comment_id_map)
                    await session.flush()  # checkpoint after recreated comment ID
                finding.published = True

    # ------------------------------------------------------------------
    # 5. Persist final publishing state — caller commits the session
    # ------------------------------------------------------------------
    review_row.github_comment_ids = comment_id_map

    logger.info(
        "Published review %s → GitHub review %d (%d comments)",
        review_id,
        review_row.github_review_id,
        len(comment_id_map),
    )
