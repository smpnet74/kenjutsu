"""Unit tests for kenjutsu.pipeline.sha_guard.

Covers all four acceptance criteria from DEM-148:
  1. Stale sha at entry → GuardResult.STALE (caller sets review to 'aborted')
  2. Stale sha at exit  → GuardResult.STALE (caller must not publish)
  3. GitHub API down    → GuardResult.API_ERROR (caller sets review to 'failed')
  4. Mid-review push simulated by two successive calls returning different shas

Tests inject a mock httpx.AsyncClient to avoid any live network calls.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from kenjutsu.pipeline.sha_guard import (
    GuardResult,
    PrRef,
    _sha_cache,
    check_sha_current,
    entry_guard,
    exit_guard,
)

_TOKEN = "ghp_test_token"
_OWNER = "acme"
_REPO = "myapp"
_PR = 42
_HEAD_SHA = "abc123def456"
_OTHER_SHA = "999000111222"


def _make_pr(sha: str = _HEAD_SHA) -> PrRef:
    return PrRef(repo_owner=_OWNER, repo_name=_REPO, pr_number=_PR, expected_head_sha=sha)


def _mock_response(sha: str, status_code: int = 200, etag: str | None = None) -> MagicMock:
    """Build a mock httpx.Response returning the given sha."""
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = status_code
    resp.json.return_value = {"head": {"sha": sha}}
    resp.headers = {"ETag": etag} if etag else {}
    return resp


def _mock_client(response: MagicMock) -> AsyncMock:
    client = AsyncMock(spec=httpx.AsyncClient)
    client.get = AsyncMock(return_value=response)
    return client


# ---------------------------------------------------------------------------
# Helpers — clear the module-level cache before each test
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def clear_cache() -> None:
    _sha_cache.clear()


# ---------------------------------------------------------------------------
# check_sha_current — happy path
# ---------------------------------------------------------------------------


class TestCheckShaCurrent:
    async def test_current_sha_returns_current(self) -> None:
        pr = _make_pr()
        client = _mock_client(_mock_response(_HEAD_SHA))
        result = await check_sha_current(pr, _TOKEN, client=client)
        assert result == GuardResult.CURRENT

    async def test_stale_sha_returns_stale(self) -> None:
        pr = _make_pr()
        client = _mock_client(_mock_response(_OTHER_SHA))
        result = await check_sha_current(pr, _TOKEN, client=client)
        assert result == GuardResult.STALE

    async def test_result_is_cached_for_ttl(self) -> None:
        pr = _make_pr()
        resp = _mock_response(_HEAD_SHA)
        client = _mock_client(resp)

        # First call hits GitHub
        r1 = await check_sha_current(pr, _TOKEN, client=client)
        assert r1 == GuardResult.CURRENT
        assert client.get.call_count == 1

        # Second call uses cache — no additional HTTP request
        r2 = await check_sha_current(pr, _TOKEN, client=client)
        assert r2 == GuardResult.CURRENT
        assert client.get.call_count == 1  # still just one call

    async def test_stale_sha_also_cached(self) -> None:
        pr = _make_pr()
        client = _mock_client(_mock_response(_OTHER_SHA))

        await check_sha_current(pr, _TOKEN, client=client)
        await check_sha_current(pr, _TOKEN, client=client)

        # Cache prevents second request even when stale
        assert client.get.call_count == 1

    async def test_304_not_modified_uses_cached_sha(self) -> None:
        pr = _make_pr()
        # Prime cache with current sha + etag
        first_resp = _mock_response(_HEAD_SHA, etag='"v1"')
        client = _mock_client(first_resp)
        await check_sha_current(pr, _TOKEN, client=client)

        # Expire the cache manually
        cache_key = (_OWNER, _REPO, _PR)
        sha, _, etag = _sha_cache[cache_key]
        _sha_cache[cache_key] = (sha, 0.0, etag)  # set fetched_at=0 to expire TTL

        # Second request returns 304
        not_modified = MagicMock(spec=httpx.Response)
        not_modified.status_code = 304
        not_modified.headers = {}
        client.get = AsyncMock(return_value=not_modified)

        result = await check_sha_current(pr, _TOKEN, client=client)
        assert result == GuardResult.CURRENT

    # ------------------------------------------------------------------
    # Failure modes
    # ------------------------------------------------------------------

    async def test_rate_limit_403_returns_api_error(self) -> None:
        pr = _make_pr()
        resp = MagicMock(spec=httpx.Response)
        resp.status_code = 403
        resp.headers = {}
        client = _mock_client(resp)
        result = await check_sha_current(pr, _TOKEN, client=client)
        assert result == GuardResult.API_ERROR

    async def test_rate_limit_429_returns_api_error(self) -> None:
        pr = _make_pr()
        resp = MagicMock(spec=httpx.Response)
        resp.status_code = 429
        resp.headers = {}
        client = _mock_client(resp)
        result = await check_sha_current(pr, _TOKEN, client=client)
        assert result == GuardResult.API_ERROR

    async def test_connection_error_retries_then_api_error(self) -> None:
        pr = _make_pr()
        client = AsyncMock(spec=httpx.AsyncClient)
        client.get = AsyncMock(side_effect=httpx.ConnectError("refused"))

        with patch("kenjutsu.pipeline.sha_guard.asyncio.sleep", new_callable=AsyncMock):
            result = await check_sha_current(pr, _TOKEN, client=client)

        assert result == GuardResult.API_ERROR
        assert client.get.call_count == 3  # three attempts

    async def test_timeout_retries_then_api_error(self) -> None:
        pr = _make_pr()
        client = AsyncMock(spec=httpx.AsyncClient)
        client.get = AsyncMock(side_effect=httpx.TimeoutException("timeout"))

        with patch("kenjutsu.pipeline.sha_guard.asyncio.sleep", new_callable=AsyncMock):
            result = await check_sha_current(pr, _TOKEN, client=client)

        assert result == GuardResult.API_ERROR
        assert client.get.call_count == 3

    async def test_server_error_retries(self) -> None:
        pr = _make_pr()
        server_err = MagicMock(spec=httpx.Response)
        server_err.status_code = 503
        server_err.headers = {}
        ok_resp = _mock_response(_HEAD_SHA)

        client = AsyncMock(spec=httpx.AsyncClient)
        client.get = AsyncMock(side_effect=[server_err, ok_resp])

        with patch("kenjutsu.pipeline.sha_guard.asyncio.sleep", new_callable=AsyncMock):
            result = await check_sha_current(pr, _TOKEN, client=client)

        assert result == GuardResult.CURRENT
        assert client.get.call_count == 2

    async def test_network_error_is_not_stale(self) -> None:
        """API_ERROR must never be mistaken for STALE — different caller actions."""
        pr = _make_pr()
        client = AsyncMock(spec=httpx.AsyncClient)
        client.get = AsyncMock(side_effect=httpx.NetworkError("network"))

        with patch("kenjutsu.pipeline.sha_guard.asyncio.sleep", new_callable=AsyncMock):
            result = await check_sha_current(pr, _TOKEN, client=client)

        assert result == GuardResult.API_ERROR
        assert result != GuardResult.STALE


# ---------------------------------------------------------------------------
# Acceptance criterion 1: Stale sha at entry → aborted, no processing
# ---------------------------------------------------------------------------


class TestEntryGuard:
    async def test_entry_current_sha(self) -> None:
        pr = _make_pr()
        client = _mock_client(_mock_response(_HEAD_SHA))
        result = await entry_guard(pr, _TOKEN, client=client)
        assert result == GuardResult.CURRENT

    async def test_entry_stale_sha(self) -> None:
        """Stale sha at entry — caller must set review to 'aborted'."""
        pr = _make_pr()
        client = _mock_client(_mock_response(_OTHER_SHA))
        result = await entry_guard(pr, _TOKEN, client=client)
        assert result == GuardResult.STALE

    async def test_entry_github_down(self) -> None:
        """GitHub API down at entry — caller must set review to 'failed', not 'aborted'."""
        pr = _make_pr()
        client = AsyncMock(spec=httpx.AsyncClient)
        client.get = AsyncMock(side_effect=httpx.ConnectError("refused"))

        with patch("kenjutsu.pipeline.sha_guard.asyncio.sleep", new_callable=AsyncMock):
            result = await entry_guard(pr, _TOKEN, client=client)

        assert result == GuardResult.API_ERROR
        assert result != GuardResult.STALE  # must not be confused with stale


# ---------------------------------------------------------------------------
# Acceptance criterion 2: Stale sha at exit → aborted, no publish
# ---------------------------------------------------------------------------


class TestExitGuard:
    async def test_exit_current_sha(self) -> None:
        pr = _make_pr()
        client = _mock_client(_mock_response(_HEAD_SHA))
        result = await exit_guard(pr, _TOKEN, client=client)
        assert result == GuardResult.CURRENT

    async def test_exit_stale_sha(self) -> None:
        """Stale sha at exit — caller must NOT publish findings."""
        pr = _make_pr()
        client = _mock_client(_mock_response(_OTHER_SHA))
        result = await exit_guard(pr, _TOKEN, client=client)
        assert result == GuardResult.STALE

    async def test_exit_evicts_cache(self) -> None:
        """exit_guard must ignore cache to get a fresh sha check before publish."""
        pr = _make_pr()

        # Prime cache with current sha
        prime_client = _mock_client(_mock_response(_HEAD_SHA))
        await check_sha_current(pr, _TOKEN, client=prime_client)
        assert prime_client.get.call_count == 1

        # Simulate push: GitHub now returns a new sha
        push_client = _mock_client(_mock_response(_OTHER_SHA))
        result = await exit_guard(pr, _TOKEN, client=push_client)

        # exit_guard must have made a fresh request despite the cache
        assert push_client.get.call_count == 1
        assert result == GuardResult.STALE

    async def test_exit_github_down(self) -> None:
        """GitHub API down at exit — caller must set review to 'failed', not 'aborted'."""
        pr = _make_pr()
        client = AsyncMock(spec=httpx.AsyncClient)
        client.get = AsyncMock(side_effect=httpx.ConnectError("refused"))

        with patch("kenjutsu.pipeline.sha_guard.asyncio.sleep", new_callable=AsyncMock):
            result = await exit_guard(pr, _TOKEN, client=client)

        assert result == GuardResult.API_ERROR


# ---------------------------------------------------------------------------
# Acceptance criterion 4: Simulated mid-review push
# ---------------------------------------------------------------------------


class TestMidReviewPush:
    async def test_entry_passes_exit_fails_on_push(self) -> None:
        """Simulate a push that arrives between entry and exit guard checks.

        entry_guard sees the original sha → CURRENT.
        A push happens (sha changes on GitHub).
        exit_guard (cache-busting) sees the new sha → STALE.
        """
        pr = _make_pr(sha=_HEAD_SHA)

        # Entry check: sha matches
        entry_client = _mock_client(_mock_response(_HEAD_SHA))
        entry_result = await entry_guard(pr, _TOKEN, client=entry_client)
        assert entry_result == GuardResult.CURRENT

        # Simulated push: GitHub now returns a new sha
        exit_client = _mock_client(_mock_response(_OTHER_SHA))
        exit_result = await exit_guard(pr, _TOKEN, client=exit_client)
        assert exit_result == GuardResult.STALE

    async def test_if_cached_after_entry_exit_still_detects_push(self) -> None:
        """Even if entry result is still in the 5s cache, exit_guard bypasses it."""
        pr = _make_pr(sha=_HEAD_SHA)

        # Entry populates cache
        entry_client = _mock_client(_mock_response(_HEAD_SHA, etag='"v1"'))
        await entry_guard(pr, _TOKEN, client=entry_client)

        # Cache is hot (TTL not expired), but a push happened
        exit_client = _mock_client(_mock_response(_OTHER_SHA))
        result = await exit_guard(pr, _TOKEN, client=exit_client)

        assert result == GuardResult.STALE
        assert exit_client.get.call_count == 1  # fresh request was made


# ---------------------------------------------------------------------------
# PrRef
# ---------------------------------------------------------------------------


class TestPrRef:
    def test_frozen_dataclass(self) -> None:
        pr = _make_pr()
        with pytest.raises((AttributeError, TypeError)):
            pr.expected_head_sha = "new_value"  # type: ignore[misc]

    def test_equality(self) -> None:
        assert _make_pr() == _make_pr()
        assert _make_pr(_HEAD_SHA) != _make_pr(_OTHER_SHA)
