"""GitHub App authentication: JWT generation and installation access token flow."""

from __future__ import annotations

import time
from dataclasses import dataclass, field

import httpx
import jwt

# Installation tokens are valid for 1 hour; refresh before expiry.
_TOKEN_TTL_SECONDS = 3600
_TOKEN_REFRESH_BEFORE_EXPIRY_SECONDS = 600  # refresh at 50 min (600s before expiry)

# GitHub App JWTs are valid for up to 10 minutes.
_JWT_TTL_SECONDS = 600


@dataclass
class _CachedToken:
    token: str
    expires_at: float  # unix timestamp


@dataclass
class GitHubAppAuth:
    """Handles GitHub App authentication.

    Generates RS256 JWTs for GitHub App API calls and exchanges them for
    installation access tokens. Tokens are cached and refreshed before expiry.

    Args:
        app_id: The GitHub App's numeric ID.
        private_key_pem: The RSA private key in PEM format (contents, not path).
        http_client: Optional httpx.AsyncClient for token requests. If None, a
            temporary client is created per request. Pass a shared client in
            production to reuse connections.
    """

    app_id: int
    private_key_pem: str
    http_client: httpx.AsyncClient | None = field(default=None, repr=False)

    _token_cache: dict[int, _CachedToken] = field(default_factory=dict, init=False, repr=False)

    def generate_jwt(self) -> str:
        """Generate a signed RS256 JWT for GitHub App API authentication.

        The JWT is valid for up to 10 minutes. GitHub requires the issued-at
        time (iat) to be set slightly in the past to account for clock skew.

        Returns:
            Signed JWT string.
        """
        now = int(time.time())
        payload = {
            "iat": now - 60,  # 60s in the past to handle clock skew
            "exp": now + _JWT_TTL_SECONDS,
            "iss": str(self.app_id),
        }
        return jwt.encode(payload, self.private_key_pem, algorithm="RS256")

    async def get_installation_token(self, installation_id: int) -> str:
        """Return a valid installation access token, fetching a new one if needed.

        Tokens are cached for their lifetime and refreshed when less than
        `_TOKEN_REFRESH_BEFORE_EXPIRY_SECONDS` remain (i.e. at the 50-minute mark).

        Args:
            installation_id: The GitHub App installation ID for the target org/repo.

        Returns:
            A valid installation access token string.

        Raises:
            httpx.HTTPStatusError: If the GitHub API returns a non-2xx response.
        """
        cached = self._token_cache.get(installation_id)
        if cached is not None:
            remaining = cached.expires_at - time.time()
            if remaining > _TOKEN_REFRESH_BEFORE_EXPIRY_SECONDS:
                return cached.token

        token = await self._fetch_installation_token(installation_id)
        return token

    async def _fetch_installation_token(self, installation_id: int) -> str:
        """Fetch a fresh installation access token from GitHub and cache it.

        Args:
            installation_id: The GitHub App installation ID.

        Returns:
            A freshly issued installation access token.

        Raises:
            httpx.HTTPStatusError: If the GitHub API returns a non-2xx response.
        """
        app_jwt = self.generate_jwt()
        headers = {
            "Authorization": f"Bearer {app_jwt}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        url = f"https://api.github.com/app/installations/{installation_id}/access_tokens"

        if self.http_client is not None:
            response = await self.http_client.post(url, headers=headers)
        else:
            async with httpx.AsyncClient() as client:
                response = await client.post(url, headers=headers)

        response.raise_for_status()
        data = response.json()

        token: str = data["token"]
        # GitHub returns expires_at as ISO 8601; store as unix timestamp for easy comparison.
        # If parsing fails, fall back to TTL from now.
        expires_at = _parse_github_expiry(data.get("expires_at"), fallback_ttl=_TOKEN_TTL_SECONDS)

        self._token_cache[installation_id] = _CachedToken(token=token, expires_at=expires_at)
        return token


def _parse_github_expiry(expires_at_str: str | None, fallback_ttl: int) -> float:
    """Parse GitHub's expires_at ISO 8601 timestamp to a unix timestamp.

    Args:
        expires_at_str: ISO 8601 datetime string from GitHub (e.g. "2024-01-01T00:00:00Z").
        fallback_ttl: Seconds from now to use if parsing fails.

    Returns:
        Unix timestamp (float) when the token expires.
    """
    if expires_at_str is not None:
        try:
            import datetime

            dt = datetime.datetime.fromisoformat(expires_at_str.replace("Z", "+00:00"))
            return dt.replace(tzinfo=datetime.UTC).timestamp()
        except (ValueError, AttributeError):
            pass
    return time.time() + fallback_ttl
