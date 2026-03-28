"""Unit tests for GitHub App authentication (JWT generation and token caching)."""

from __future__ import annotations

import time
from unittest.mock import AsyncMock, MagicMock

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from kenjutsu.github.auth import GitHubAppAuth, _parse_github_expiry

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _generate_rsa_private_key_pem() -> str:
    """Generate a fresh RSA-2048 key for testing (no real credentials)."""
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
    )
    return private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.TraditionalOpenSSL,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode()


@pytest.fixture(scope="module")
def rsa_private_key_pem() -> str:
    return _generate_rsa_private_key_pem()


@pytest.fixture()
def auth(rsa_private_key_pem: str) -> GitHubAppAuth:
    return GitHubAppAuth(app_id=12345, private_key_pem=rsa_private_key_pem)


# ---------------------------------------------------------------------------
# JWT generation
# ---------------------------------------------------------------------------


class TestGenerateJwt:
    def test_returns_string(self, auth: GitHubAppAuth) -> None:
        token = auth.generate_jwt()
        assert isinstance(token, str)
        assert len(token) > 0

    def test_algorithm_is_rs256(self, auth: GitHubAppAuth) -> None:
        token = auth.generate_jwt()
        header = jwt.get_unverified_header(token)
        assert header["alg"] == "RS256"

    def test_payload_has_required_claims(self, auth: GitHubAppAuth, rsa_private_key_pem: str) -> None:
        from cryptography.hazmat.primitives.serialization import load_pem_private_key

        private_key = load_pem_private_key(rsa_private_key_pem.encode(), password=None)
        public_key = private_key.public_key()

        token = auth.generate_jwt()
        payload = jwt.decode(token, public_key, algorithms=["RS256"])

        assert payload["iss"] == "12345"
        assert "iat" in payload
        assert "exp" in payload

    def test_iat_is_slightly_in_past(self, auth: GitHubAppAuth) -> None:
        before = int(time.time())
        token = auth.generate_jwt()
        payload = jwt.decode(token, options={"verify_signature": False})
        # iat should be ~60s before now to handle clock skew
        assert payload["iat"] <= before - 50

    def test_expiry_is_ten_minutes(self, auth: GitHubAppAuth) -> None:
        before = int(time.time())
        token = auth.generate_jwt()
        payload = jwt.decode(token, options={"verify_signature": False})
        # exp should be roughly now + 600s (10 min), allow ±10s tolerance
        assert abs(payload["exp"] - (before + 600)) <= 10

    def test_different_app_ids_produce_different_issuers(self, rsa_private_key_pem: str) -> None:
        auth_a = GitHubAppAuth(app_id=111, private_key_pem=rsa_private_key_pem)
        auth_b = GitHubAppAuth(app_id=222, private_key_pem=rsa_private_key_pem)
        payload_a = jwt.decode(auth_a.generate_jwt(), options={"verify_signature": False})
        payload_b = jwt.decode(auth_b.generate_jwt(), options={"verify_signature": False})
        assert payload_a["iss"] != payload_b["iss"]


# ---------------------------------------------------------------------------
# Token caching
# ---------------------------------------------------------------------------


def _make_token_response(token: str, offset_seconds: int = 3600) -> MagicMock:
    """Build a fake httpx response for an installation token request."""
    import datetime

    expires_at = (datetime.datetime.now(tz=datetime.UTC) + datetime.timedelta(seconds=offset_seconds)).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {"token": token, "expires_at": expires_at}
    return mock_response


class TestGetInstallationToken:
    @pytest.mark.asyncio
    async def test_fetches_token_on_first_call(self, auth: GitHubAppAuth) -> None:
        mock_client = AsyncMock()
        mock_client.post.return_value = _make_token_response("ghs_first")
        auth.http_client = mock_client

        token = await auth.get_installation_token(installation_id=99)
        assert token == "ghs_first"
        mock_client.post.assert_called_once()

    @pytest.mark.asyncio
    async def test_returns_cached_token_on_second_call(self, auth: GitHubAppAuth) -> None:
        mock_client = AsyncMock()
        mock_client.post.return_value = _make_token_response("ghs_cached")
        auth.http_client = mock_client
        auth._token_cache.clear()

        await auth.get_installation_token(installation_id=55)
        await auth.get_installation_token(installation_id=55)

        # Should have only hit the API once
        assert mock_client.post.call_count == 1

    @pytest.mark.asyncio
    async def test_refreshes_token_near_expiry(self, auth: GitHubAppAuth) -> None:
        """Token with <600s remaining should trigger a new fetch."""
        mock_client = AsyncMock()
        mock_client.post.return_value = _make_token_response("ghs_refreshed")
        auth.http_client = mock_client
        auth._token_cache.clear()

        # Pre-populate cache with a token that expires in 300s (below the 600s threshold)
        from kenjutsu.github.auth import _CachedToken

        auth._token_cache[77] = _CachedToken(token="ghs_old", expires_at=time.time() + 300)

        token = await auth.get_installation_token(installation_id=77)
        assert token == "ghs_refreshed"
        mock_client.post.assert_called_once()

    @pytest.mark.asyncio
    async def test_does_not_refresh_token_with_plenty_of_time(self, auth: GitHubAppAuth) -> None:
        """Token with >600s remaining should NOT trigger a new fetch."""
        mock_client = AsyncMock()
        mock_client.post.return_value = _make_token_response("ghs_unused")
        auth.http_client = mock_client
        auth._token_cache.clear()

        from kenjutsu.github.auth import _CachedToken

        # 1800s remaining — well above the 600s threshold
        auth._token_cache[88] = _CachedToken(token="ghs_still_valid", expires_at=time.time() + 1800)

        token = await auth.get_installation_token(installation_id=88)
        assert token == "ghs_still_valid"
        mock_client.post.assert_not_called()

    @pytest.mark.asyncio
    async def test_different_installations_cached_independently(self, auth: GitHubAppAuth) -> None:
        mock_client = AsyncMock()
        mock_client.post.side_effect = [
            _make_token_response("ghs_inst_1"),
            _make_token_response("ghs_inst_2"),
        ]
        auth.http_client = mock_client
        auth._token_cache.clear()

        token_a = await auth.get_installation_token(installation_id=1)
        token_b = await auth.get_installation_token(installation_id=2)

        assert token_a == "ghs_inst_1"
        assert token_b == "ghs_inst_2"
        assert mock_client.post.call_count == 2

    @pytest.mark.asyncio
    async def test_raises_on_http_error(self, auth: GitHubAppAuth) -> None:
        import httpx

        mock_client = AsyncMock()
        error_response = MagicMock()
        error_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "401 Unauthorized",
            request=MagicMock(),
            response=MagicMock(),
        )
        mock_client.post.return_value = error_response
        auth.http_client = mock_client
        auth._token_cache.clear()

        with pytest.raises(httpx.HTTPStatusError):
            await auth.get_installation_token(installation_id=999)


# ---------------------------------------------------------------------------
# Expiry parsing helper
# ---------------------------------------------------------------------------


class TestParseGithubExpiry:
    def test_parses_iso8601_utc(self) -> None:
        result = _parse_github_expiry("2025-01-01T12:00:00Z", fallback_ttl=3600)
        import datetime

        expected = datetime.datetime(2025, 1, 1, 12, 0, 0, tzinfo=datetime.UTC).timestamp()
        assert abs(result - expected) < 1

    def test_falls_back_on_none(self) -> None:
        before = time.time()
        result = _parse_github_expiry(None, fallback_ttl=3600)
        assert abs(result - (before + 3600)) < 2

    def test_falls_back_on_malformed_string(self) -> None:
        before = time.time()
        result = _parse_github_expiry("not-a-date", fallback_ttl=1800)
        assert abs(result - (before + 1800)) < 2
