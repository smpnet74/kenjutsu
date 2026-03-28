"""Queue management for multi-tenant review processing.

All classes are plain Python/asyncio — no DBOS imports (arch spec §3.6).

Provides:
- GlobalQueue: configurable global concurrency limit
- TenantQueue: per-tenant concurrency cap
- RateLimiter: sliding-window rate limiter (per-tenant or global LLM)
- SupersessionRegistry: stale-work cancellation via cancel events
- CostTracker: per-tenant cost cap with alert (80%) and hard stop (100%)
"""

from __future__ import annotations

import asyncio
import time
from collections import deque
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Callable

# ---------------------------------------------------------------------------
# ReviewKey — supersession identity
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ReviewKey:
    """Unique identity for a review: (repo_id, pr_number).

    At most one canonical in-flight review per key; a new registration
    supersedes the previous one automatically.
    """

    repo_id: str
    pr_number: int


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class RateLimitedError(Exception):
    """Raised when a rate limiter's call budget is exhausted for the current window."""


# ---------------------------------------------------------------------------
# GlobalQueue — configurable global concurrency limit
# ---------------------------------------------------------------------------


class GlobalQueue:
    """Asyncio semaphore-backed global concurrency limit.

    Usage::

        queue = GlobalQueue(max_concurrency=10)
        async with queue:
            await do_work()
    """

    def __init__(self, max_concurrency: int) -> None:
        self.max_concurrency = max_concurrency
        self._semaphore = asyncio.Semaphore(max_concurrency)

    async def __aenter__(self) -> GlobalQueue:
        await self._semaphore.acquire()
        return self

    async def __aexit__(self, exc_type: object, exc: object, tb: object) -> None:
        self._semaphore.release()


# ---------------------------------------------------------------------------
# TenantQueue — per-tenant concurrency cap
# ---------------------------------------------------------------------------


class TenantQueue:
    """Per-tenant concurrency cap using one semaphore per tenant.

    Usage::

        tq = TenantQueue(max_concurrency=3)
        async with tq.for_tenant("acme"):
            await do_tenant_work()
    """

    def __init__(self, max_concurrency: int) -> None:
        self._max_concurrency = max_concurrency
        self._semaphores: dict[str, asyncio.Semaphore] = {}

    def _semaphore_for(self, tenant_id: str) -> asyncio.Semaphore:
        if tenant_id not in self._semaphores:
            self._semaphores[tenant_id] = asyncio.Semaphore(self._max_concurrency)
        return self._semaphores[tenant_id]

    @asynccontextmanager
    async def for_tenant(self, tenant_id: str) -> AsyncIterator[None]:
        sem = self._semaphore_for(tenant_id)
        await sem.acquire()
        try:
            yield
        finally:
            sem.release()


# ---------------------------------------------------------------------------
# RateLimiter — sliding-window rate limiter
# ---------------------------------------------------------------------------


class RateLimiter:
    """Sliding-window rate limiter.

    Tracks call timestamps in a deque. Calls that exceed ``calls`` within
    the current ``period`` raise :exc:`RateLimitExceeded`.

    The optional ``_now`` callable injects a fake clock for unit tests.

    Usage::

        limiter = RateLimiter(calls=100, period=60.0)
        await limiter.acquire()   # raises RateLimitExceeded if over budget
    """

    def __init__(
        self,
        calls: int,
        period: float,
        *,
        _now: Callable[[], float] | None = None,
    ) -> None:
        self._calls = calls
        self._period = period
        self._timestamps: deque[float] = deque()
        self._lock = asyncio.Lock()
        self._now: Callable[[], float] = _now or time.monotonic

    async def acquire(self) -> None:
        async with self._lock:
            now = self._now()
            cutoff = now - self._period
            # Evict timestamps outside the current window
            while self._timestamps and self._timestamps[0] <= cutoff:
                self._timestamps.popleft()

            if len(self._timestamps) >= self._calls:
                raise RateLimitedError(f"Rate limit of {self._calls} calls per {self._period}s exceeded")

            self._timestamps.append(now)


# ---------------------------------------------------------------------------
# SupersessionRegistry — stale-work cancellation
# ---------------------------------------------------------------------------


class SupersessionRegistry:
    """Tracks in-flight reviews and cancels superseded ones.

    When a new review is registered for the same :class:`ReviewKey`, the
    previous review's cancel event is set so it can abort early.

    Usage::

        reg = SupersessionRegistry()
        cancel_event = reg.register(key)
        # ... in the review coroutine, poll cancel_event.is_set() ...
        reg.complete(key)  # clean up when done
    """

    def __init__(self) -> None:
        self._events: dict[ReviewKey, asyncio.Event] = {}
        self._superseded: set[ReviewKey] = set()

    def register(self, key: ReviewKey) -> asyncio.Event:
        """Register a review; supersede any prior review with the same key."""
        if key in self._events:
            self._events[key].set()  # signal the prior review to abort
            self._superseded.add(key)

        new_event = asyncio.Event()
        self._events[key] = new_event
        return new_event

    def complete(self, key: ReviewKey) -> None:
        """Mark a review as finished and remove it from the registry."""
        self._events.pop(key, None)
        self._superseded.discard(key)

    def is_cancelled(self, key: ReviewKey) -> bool:
        """Return True if a supersession has occurred for this key since the last complete().

        The active (superseding) review should check its own cancel event directly,
        not rely on this method — this is intended for polling from outside the coroutine.
        """
        return key in self._superseded


# ---------------------------------------------------------------------------
# CostTracker — per-tenant cost cap
# ---------------------------------------------------------------------------


@dataclass
class CostStatus:
    """Snapshot of a tenant's cost position."""

    tenant_id: str
    current_cost: float
    cap: float
    alert_triggered: bool
    hard_stop: bool


@dataclass
class CostTracker:
    """Per-tenant cost tracking with configurable cap.

    Alert fires at 80% of cap; hard stop fires at 100%.

    Usage::

        tracker = CostTracker()
        tracker.set_cap("acme", cap=500.0)
        status = tracker.record_cost("acme", 10.50)
        if status.hard_stop:
            raise CostCapExceeded(status.tenant_id)
    """

    _soft_threshold: float = field(default=0.8, init=False)
    _costs: dict[str, float] = field(default_factory=dict, init=False)
    _caps: dict[str, float] = field(default_factory=dict, init=False)

    def set_cap(self, tenant_id: str, cap: float) -> None:
        """Set the cost cap for a tenant."""
        self._caps[tenant_id] = cap

    def record_cost(self, tenant_id: str, cost: float) -> CostStatus:
        """Add ``cost`` to the tenant's running total and return status."""
        self._costs[tenant_id] = self._costs.get(tenant_id, 0.0) + cost
        return self.check(tenant_id)

    def check(self, tenant_id: str) -> CostStatus:
        """Return the current cost status for a tenant."""
        current = self._costs.get(tenant_id, 0.0)
        cap = self._caps.get(tenant_id, float("inf"))

        if cap == float("inf"):
            return CostStatus(
                tenant_id=tenant_id,
                current_cost=current,
                cap=cap,
                alert_triggered=False,
                hard_stop=False,
            )

        ratio = current / cap
        return CostStatus(
            tenant_id=tenant_id,
            current_cost=current,
            cap=cap,
            alert_triggered=ratio >= self._soft_threshold,
            hard_stop=ratio >= 1.0,
        )
