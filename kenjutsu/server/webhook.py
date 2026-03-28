"""GitHub webhook endpoint with HMAC-SHA256 verification and event persistence.

Design:
- HMAC verification happens synchronously before any DB work.
- The event record is written inside the request handler (fast INSERT).
- Heavy downstream work (review queue, installation tracking) is dispatched
  as a BackgroundTask so the 200 response is returned within 500 ms.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Request, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

logger = logging.getLogger(__name__)

router = APIRouter()

# ---------------------------------------------------------------------------
# Database session factory
# ---------------------------------------------------------------------------

_engine: Any = None
_session_factory: Any = None


def _get_engine() -> Any:
    global _engine
    if _engine is None:
        database_url = os.environ.get("DATABASE_URL", "")
        if not database_url:
            raise RuntimeError("DATABASE_URL environment variable is not set")
        _engine = create_async_engine(database_url, pool_pre_ping=True)
    return _engine


def _get_session_factory() -> async_sessionmaker[AsyncSession]:
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(_get_engine(), expire_on_commit=False)
    return _session_factory


async def get_db_session() -> Any:
    """FastAPI dependency that yields an async DB session."""
    factory = _get_session_factory()
    async with factory() as session:
        yield session


# ---------------------------------------------------------------------------
# HMAC verification
# ---------------------------------------------------------------------------


def verify_signature(payload_bytes: bytes, signature_header: str, secret: str) -> bool:
    """Return True iff the HMAC-SHA256 signature matches the payload.

    Args:
        payload_bytes: The raw request body bytes.
        signature_header: The value of the ``X-Hub-Signature-256`` header,
            expected to be ``sha256=<hex_digest>``.
        secret: The shared webhook secret used to compute the expected digest.

    Returns:
        ``True`` if signatures match, ``False`` otherwise (including when the
        header is missing or malformed).
    """
    if not signature_header or not signature_header.startswith("sha256="):
        return False
    expected_digest = signature_header.removeprefix("sha256=")
    actual_digest = hmac.new(secret.encode(), payload_bytes, hashlib.sha256).hexdigest()
    return hmac.compare_digest(actual_digest, expected_digest)


# ---------------------------------------------------------------------------
# Background event routing
# ---------------------------------------------------------------------------


async def _route_event(event_type: str, action: str | None, payload: dict[str, Any]) -> None:
    """Dispatch webhook events to the appropriate handler.

    Runs as a FastAPI BackgroundTask; errors are logged, not propagated.
    """
    from kenjutsu.server.debounce import debounce_manager

    try:
        if event_type == "pull_request" and action in {"opened", "synchronize", "reopened"}:
            pr_number = payload.get("number")
            repo = payload.get("repository", {}).get("full_name", "unknown")
            logger.info("Debouncing PR review: %s#%s (action=%s)", repo, pr_number, action)

            if pr_number is None:
                logger.warning("pull_request event missing PR number: %s", action)
                return

            pr_key = (repo, int(pr_number))

            async def _enqueue_review() -> None:
                logger.info("Enqueueing PR review: %s#%s", repo, pr_number)
                # TODO(DEM-160): enqueue review job

            debounce_manager.schedule(pr_key, _enqueue_review)

        elif event_type == "installation":
            github_id = payload.get("installation", {}).get("id")
            logger.info("Installation event: action=%s github_id=%s", action, github_id)
            # TODO(DEM-145): sync installation record
        else:
            logger.debug("Unhandled event: %s/%s", event_type, action)
    except Exception:
        logger.exception("Error routing event %s/%s", event_type, action)


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------


@router.post("/webhook", status_code=status.HTTP_200_OK)
async def receive_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    x_hub_signature_256: str | None = Header(default=None),
    x_github_event: str | None = Header(default=None),
    x_github_delivery: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db_session),
) -> dict[str, str]:
    """Receive a GitHub webhook, verify its signature, and persist the event.

    - Returns 401 if HMAC verification fails.
    - Returns 400 if required headers are missing.
    - Returns 409 if the delivery ID has already been processed (idempotency).
    - Returns 200 immediately; heavy work runs in a background task.
    """
    # 1. Validate required headers
    if not x_github_event:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing X-GitHub-Event header")
    if not x_github_delivery:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing X-GitHub-Delivery header")

    # 2. Read raw body
    payload_bytes = await request.body()

    # 3. Verify HMAC signature
    secret = os.environ.get("GITHUB_WEBHOOK_SECRET", "")
    if not secret:
        logger.error("GITHUB_WEBHOOK_SECRET is not configured")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Webhook secret not configured")

    if not verify_signature(payload_bytes, x_hub_signature_256 or "", secret):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid signature")

    # 4. Parse JSON payload
    try:
        payload: dict[str, Any] = json.loads(payload_bytes)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid JSON payload") from exc

    # 5. Resolve installation_id from payload
    from sqlalchemy import select  # local import to avoid circular deps at module load

    from kenjutsu.db.models import Installation, WebhookEvent

    github_installation_id: int | None = payload.get("installation", {}).get("id")
    if github_installation_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Payload missing installation.id",
        )

    result = await db.execute(select(Installation).where(Installation.github_installation_id == github_installation_id))
    installation = result.scalar_one_or_none()
    if installation is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown installation: {github_installation_id}",
        )

    # 6. Persist event (idempotent by delivery_id)
    event = WebhookEvent(
        delivery_id=x_github_delivery,
        installation_id=installation.id,
        event_type=x_github_event,
        payload_json=payload,
    )
    db.add(event)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        # Already processed — safe to return 200 (idempotency)
        logger.info("Duplicate delivery %s ignored", x_github_delivery)
        return {"status": "duplicate"}

    # 7. Dispatch heavy work asynchronously
    action: str | None = payload.get("action")
    background_tasks.add_task(_route_event, x_github_event, action, payload)

    return {"status": "accepted"}
