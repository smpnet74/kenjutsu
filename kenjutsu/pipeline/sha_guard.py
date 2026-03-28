"""Sha guard: prevent publishing findings against an outdated commit.

Spec ref: v3 Section 4.2, Pipeline Steps 2 and 8.

Hard rule: Never publish findings against an outdated head_sha.

Two guards bracket the review pipeline:
  - entry_guard (Step 2): check before any processing begins
  - exit_guard  (Step 8): check again before publishing findings

GitHub API failures use retry-with-backoff (3 attempts). If still down,
the review is marked 'failed', NOT 'aborted'. Only a sha mismatch => 'aborted'.

Rate limit mitigation: conditional requests (If-None-Match etag) + 5s TTL cache
on the PR head sha to reduce repeated API calls within a single review run.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from enum import StrEnum

import httpx

_GITHUB_API_BASE = "https://api.github.com"
_REQUEST_TIMEOUT = 10.0
_MAX_RETRIES = 3
_RETRY_BASE_DELAY = 1.0
_SHA_CACHE_TTL = 5.0  # seconds

# {(repo_owner, repo_name, pr_number): (sha, fetched_at, etag)}
_sha_cache: dict[tuple[str, str, int], tuple[str, float, str | None]] = {}


class GuardResult(StrEnum):
    """Outcome of a sha guard check."""

    CURRENT = "current"  # sha matches — safe to proceed / publish
    STALE = "stale"  # sha mismatch — review must be aborted
    API_ERROR = "api_error"  # GitHub unreachable — review must be failed


@dataclass(frozen=True)
class PrRef:
    """Minimal PR reference needed for sha validation."""

    repo_owner: str
    repo_name: str
    pr_number: int
    expected_head_sha: str


def _cache_key(pr: PrRef) -> tuple[str, str, int]:
    return (pr.repo_owner, pr.repo_name, pr.pr_number)


def _get_cached(pr: PrRef) -> tuple[str, str | None] | None:
    """Return (sha, etag) from cache if still fresh, else None."""
    entry = _sha_cache.get(_cache_key(pr))
    if entry is None:
        return None
    sha, fetched_at, etag = entry
    if time.monotonic() - fetched_at < _SHA_CACHE_TTL:
        return sha, etag
    return None


def _set_cached(pr: PrRef, sha: str, etag: str | None) -> None:
    _sha_cache[_cache_key(pr)] = (sha, time.monotonic(), etag)


def _evict_cached(pr: PrRef) -> None:
    _sha_cache.pop(_cache_key(pr), None)


async def check_sha_current(
    pr: PrRef,
    github_token: str,
    *,
    client: httpx.AsyncClient | None = None,
) -> GuardResult:
    """Fetch the current PR head SHA from GitHub and compare to expected.

    Returns:
        CURRENT  — sha matches, proceed.
        STALE    — sha mismatch, abort the review.
        API_ERROR — GitHub unreachable after retries, fail the review.

    Uses an in-process TTL cache and If-None-Match conditional requests
    to stay within GitHub rate limits during high-volume review runs.
    """
    # Serve from cache when fresh — avoids redundant API calls
    cached = _get_cached(pr)
    if cached is not None:
        cached_sha, _ = cached
        return GuardResult.CURRENT if cached_sha == pr.expected_head_sha else GuardResult.STALE

    url = f"{_GITHUB_API_BASE}/repos/{pr.repo_owner}/{pr.repo_name}/pulls/{pr.pr_number}"
    headers: dict[str, str] = {
        "Authorization": f"Bearer {github_token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    # Include stale etag for conditional request even after TTL expiry
    stale_entry = _sha_cache.get(_cache_key(pr))
    if stale_entry is not None:
        _, _, etag = stale_entry
        if etag:
            headers["If-None-Match"] = etag

    own_client = client is None
    if own_client:
        client = httpx.AsyncClient()

    try:
        for attempt in range(_MAX_RETRIES):
            try:
                response = await client.get(url, headers=headers, timeout=_REQUEST_TIMEOUT)

                if response.status_code == 200:
                    data = response.json()
                    current_sha: str = data["head"]["sha"]
                    etag = response.headers.get("ETag")
                    _set_cached(pr, current_sha, etag)
                    return GuardResult.CURRENT if current_sha == pr.expected_head_sha else GuardResult.STALE

                if response.status_code == 304:
                    # Not modified — cached sha is still current
                    if stale_entry is None:
                        return GuardResult.API_ERROR
                    old_sha, _, old_etag = stale_entry
                    _set_cached(pr, old_sha, old_etag)
                    return GuardResult.CURRENT if old_sha == pr.expected_head_sha else GuardResult.STALE

                if response.status_code in {403, 429}:
                    # Rate limited — treat as API error; do not abort on rate limit
                    return GuardResult.API_ERROR

                # 4xx (not rate limit) or 5xx — retry on server errors, fail on client errors
                if response.status_code >= 500 and attempt < _MAX_RETRIES - 1:
                    await asyncio.sleep(_RETRY_BASE_DELAY * (2**attempt))
                    continue

                return GuardResult.API_ERROR

            except (httpx.TimeoutException, httpx.ConnectError, httpx.NetworkError):
                if attempt < _MAX_RETRIES - 1:
                    await asyncio.sleep(_RETRY_BASE_DELAY * (2**attempt))

        return GuardResult.API_ERROR
    finally:
        if own_client:
            await client.aclose()


async def entry_guard(
    pr: PrRef,
    github_token: str,
    *,
    client: httpx.AsyncClient | None = None,
) -> GuardResult:
    """Step 2: verify sha is current before starting review processing.

    Called immediately after a review is dequeued. If the result is STALE,
    the caller must set the review status to 'aborted' and return early.
    If the result is API_ERROR, the caller must set status to 'failed'.
    """
    return await check_sha_current(pr, github_token, client=client)


async def exit_guard(
    pr: PrRef,
    github_token: str,
    *,
    client: httpx.AsyncClient | None = None,
) -> GuardResult:
    """Step 8: re-verify sha before publishing findings.

    Called after LLM review + evidence scoring, immediately before publish.
    Always performs a fresh API check — the TTL cache is evicted first so
    we never publish against a cached (potentially stale) sha.

    If the result is STALE, the caller must set review status to 'aborted'
    and must NOT publish any findings.
    """
    _evict_cached(pr)
    return await check_sha_current(pr, github_token, client=client)
