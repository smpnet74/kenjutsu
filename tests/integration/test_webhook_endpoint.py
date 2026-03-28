"""Integration tests for the POST /webhook endpoint.

Split into two layers:

1. HMAC / HTTP contract tests — no database required.  These use FastAPI's
   dependency-override mechanism to inject a mock DB session, verifying that
   the endpoint returns the correct HTTP status codes for all request variants
   without requiring DATABASE_URL.

2. DB persistence test — skipped unless a real ``DATABASE_URL`` is available
   in the environment.  Verifies that a valid delivery is written to
   ``webhook_events`` exactly once (idempotency).
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from kenjutsu.app import app
from kenjutsu.server.webhook import get_db_session

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SECRET = "integration-test-secret"
DELIVERY_ID = "abc-123-delivery"
EVENT_TYPE = "pull_request"

SAMPLE_PAYLOAD: dict[str, Any] = {
    "action": "opened",
    "number": 42,
    "installation": {"id": 99},
    "repository": {"full_name": "acme/repo"},
}


def _sign(payload: bytes, secret: str) -> str:
    digest = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


def _headers(
    payload: bytes,
    *,
    event: str = EVENT_TYPE,
    delivery: str = DELIVERY_ID,
    secret: str = SECRET,
) -> dict[str, str]:
    return {
        "X-Hub-Signature-256": _sign(payload, secret),
        "X-GitHub-Event": event,
        "X-GitHub-Delivery": delivery,
        "Content-Type": "application/json",
    }


# ---------------------------------------------------------------------------
# Mock DB session helpers
# ---------------------------------------------------------------------------


def _mock_installation(github_id: int = 99) -> MagicMock:
    inst = MagicMock()
    inst.id = "00000000-0000-0000-0000-000000000001"
    inst.github_installation_id = github_id
    return inst


def _build_mock_db_session(installation: MagicMock | None) -> AsyncMock:
    """Return an AsyncMock that behaves like an AsyncSession."""
    db = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = installation
    db.execute = AsyncMock(return_value=result)
    db.add = MagicMock()
    db.commit = AsyncMock()
    db.rollback = AsyncMock()
    return db


def _override_db(installation: MagicMock | None = None) -> None:
    """Install a FastAPI dependency override for get_db_session."""
    if installation is None:
        installation = _mock_installation()
    mock_session = _build_mock_db_session(installation)

    async def _fake_session() -> AsyncGenerator[AsyncMock, None]:
        yield mock_session

    app.dependency_overrides[get_db_session] = _fake_session


def _clear_db_override() -> None:
    app.dependency_overrides.pop(get_db_session, None)


# ---------------------------------------------------------------------------
# HTTP contract tests (no real DB needed)
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


@pytest.fixture(autouse=True)
def _reset_dependency_overrides() -> None:  # type: ignore[return]
    """Ensure dependency overrides are cleaned up after each test."""
    yield  # type: ignore[misc]
    _clear_db_override()


@pytest.mark.asyncio
class TestWebhookHMACContract:
    """Verify that the endpoint enforces HMAC and returns correct status codes."""

    async def test_valid_request_returns_200(self, client: AsyncClient) -> None:
        _override_db()
        payload = json.dumps(SAMPLE_PAYLOAD).encode()
        with patch.dict(os.environ, {"GITHUB_WEBHOOK_SECRET": SECRET}):
            resp = await client.post("/webhook", content=payload, headers=_headers(payload))
        assert resp.status_code == 200
        assert resp.json()["status"] == "accepted"

    async def test_invalid_signature_returns_401(self, client: AsyncClient) -> None:
        _override_db()
        payload = json.dumps(SAMPLE_PAYLOAD).encode()
        hdrs = _headers(payload, secret="wrong-secret")
        with patch.dict(os.environ, {"GITHUB_WEBHOOK_SECRET": SECRET}):
            resp = await client.post("/webhook", content=payload, headers=hdrs)
        assert resp.status_code == 401

    async def test_missing_event_header_returns_400(self, client: AsyncClient) -> None:
        _override_db()
        payload = json.dumps(SAMPLE_PAYLOAD).encode()
        hdrs = _headers(payload)
        del hdrs["X-GitHub-Event"]
        with patch.dict(os.environ, {"GITHUB_WEBHOOK_SECRET": SECRET}):
            resp = await client.post("/webhook", content=payload, headers=hdrs)
        assert resp.status_code == 400

    async def test_missing_delivery_header_returns_400(self, client: AsyncClient) -> None:
        _override_db()
        payload = json.dumps(SAMPLE_PAYLOAD).encode()
        hdrs = _headers(payload)
        del hdrs["X-GitHub-Delivery"]
        with patch.dict(os.environ, {"GITHUB_WEBHOOK_SECRET": SECRET}):
            resp = await client.post("/webhook", content=payload, headers=hdrs)
        assert resp.status_code == 400

    async def test_tampered_payload_returns_401(self, client: AsyncClient) -> None:
        _override_db()
        payload = json.dumps(SAMPLE_PAYLOAD).encode()
        hdrs = _headers(payload)
        tampered = payload + b" garbage"
        with patch.dict(os.environ, {"GITHUB_WEBHOOK_SECRET": SECRET}):
            resp = await client.post("/webhook", content=tampered, headers=hdrs)
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# DB persistence test (requires DATABASE_URL)
# ---------------------------------------------------------------------------

_DB_AVAILABLE = bool(os.environ.get("DATABASE_URL"))


@pytest.mark.skipif(not _DB_AVAILABLE, reason="DATABASE_URL not set")
@pytest.mark.asyncio
async def test_webhook_persisted_to_db() -> None:
    """End-to-end: POST /webhook → row in webhook_events (idempotent)."""
    from sqlalchemy import select, text
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    from kenjutsu.db.models import Base, Installation, WebhookEvent

    engine = create_async_engine(os.environ["DATABASE_URL"])
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Seed an installation row
    async with factory() as session:
        inst = Installation(
            github_installation_id=SAMPLE_PAYLOAD["installation"]["id"],
            account_login="acme",
            account_type="Organization",
        )
        session.add(inst)
        await session.commit()
        await session.refresh(inst)

    # Patch engine in webhook module
    from kenjutsu.server import webhook as wh_module

    wh_module._engine = engine
    wh_module._session_factory = factory

    delivery = "unique-delivery-e2e-001"
    payload = json.dumps(SAMPLE_PAYLOAD).encode()
    hdrs = _headers(payload, delivery=delivery)

    _clear_db_override()  # use real DB for this test

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        with patch.dict(os.environ, {"GITHUB_WEBHOOK_SECRET": SECRET}):
            resp = await c.post("/webhook", content=payload, headers=hdrs)
    assert resp.status_code == 200, resp.text

    # Verify persistence
    async with factory() as session:
        result = await session.execute(select(WebhookEvent).where(WebhookEvent.delivery_id == delivery))
        event = result.scalar_one_or_none()
        assert event is not None
        assert event.event_type == EVENT_TYPE
        assert event.processed is False

    # Idempotency: second POST with same delivery_id must not raise
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        with patch.dict(os.environ, {"GITHUB_WEBHOOK_SECRET": SECRET}):
            resp2 = await c.post("/webhook", content=payload, headers=hdrs)
    assert resp2.status_code == 200
    assert resp2.json()["status"] == "duplicate"

    # Cleanup
    async with engine.begin() as conn:
        await conn.execute(text("DROP TABLE webhook_events, installations CASCADE"))
    await engine.dispose()
