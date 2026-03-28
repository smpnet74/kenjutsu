"""Debounce logic for PR review triggering on rapid-fire synchronize events.

When GitHub sends multiple ``synchronize`` webhooks for the same PR (e.g. a
developer pushes several fixup commits in quick succession), we want only the
most recent push to trigger a review.  This module provides a
:class:`DebounceManager` that:

1. Resets a per-PR quiet-period timer on every incoming event.
2. Cancels any in-flight review task when a new event arrives — the old
   review is superseded.
3. Fires the review coroutine only after the configured quiet period has
   elapsed without another push.

Usage::

    from kenjutsu.server.debounce import debounce_manager

    debounce_manager.schedule(("owner/repo", 42), lambda: enqueue_review(payload))

The module-level :data:`debounce_manager` singleton is pre-configured from
``KENJUTSU_DEBOUNCE_SECONDS`` (default ``30``).
"""

from __future__ import annotations

import asyncio
import logging
import os
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Callable, Coroutine

logger = logging.getLogger(__name__)

PRKey = tuple[str, int]  # (repo_full_name, pr_number)


class DebounceManager:
    """Debounce PR review triggering on rapid-fire ``synchronize`` events.

    Each PR is identified by a :data:`PRKey` of ``(repo_full_name, pr_number)``.
    The manager maintains two internal dicts:

    - ``_pending``:   timer handles that have not yet fired.
    - ``_in_flight``: asyncio tasks that are currently running a review.

    When :meth:`schedule` is called for a key that already has a pending timer,
    the old timer is cancelled and a new one is started (timer reset).  If a
    review task is already in flight for that key, it is cancelled before the
    new timer is registered.
    """

    def __init__(self, quiet_period: float = 30.0) -> None:
        """
        Args:
            quiet_period: Seconds to wait for additional events before
                triggering the review.  Range 30-60 s is recommended.
        """
        self._quiet_period = quiet_period
        self._pending: dict[PRKey, asyncio.TimerHandle] = {}
        self._in_flight: dict[PRKey, asyncio.Task[Any]] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def schedule(
        self,
        pr_key: PRKey,
        coro_factory: Callable[[], Coroutine[Any, Any, None]],
    ) -> None:
        """Schedule a review for *pr_key* after the quiet period.

        Any existing pending timer or in-flight review for the same key is
        cancelled before the new timer is registered.

        Args:
            pr_key: ``(repo_full_name, pr_number)`` identifying the PR.
            coro_factory: Zero-argument callable that returns the coroutine
                to run when the quiet period expires.
        """
        self._cancel_pending(pr_key)
        self._cancel_in_flight(pr_key)

        loop = asyncio.get_running_loop()
        handle = loop.call_later(
            self._quiet_period,
            self._fire,
            pr_key,
            coro_factory,
        )
        self._pending[pr_key] = handle
        logger.debug("Debounce scheduled: %s (quiet_period=%.1fs)", pr_key, self._quiet_period)

    def cancel(self, pr_key: PRKey) -> bool:
        """Explicitly cancel any pending timer or in-flight task for *pr_key*.

        Returns:
            ``True`` if anything was cancelled, ``False`` if nothing was
            pending for this key.
        """
        cancelled_pending = self._cancel_pending(pr_key)
        cancelled_in_flight = self._cancel_in_flight(pr_key)
        return cancelled_pending or cancelled_in_flight

    @property
    def pending_keys(self) -> frozenset[PRKey]:
        """PR keys that have a pending (not-yet-fired) debounce timer."""
        return frozenset(self._pending)

    @property
    def in_flight_keys(self) -> frozenset[PRKey]:
        """PR keys whose review coroutine is currently executing."""
        return frozenset(self._in_flight)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _cancel_pending(self, pr_key: PRKey) -> bool:
        handle = self._pending.pop(pr_key, None)
        if handle is not None:
            handle.cancel()
            logger.debug("Debounce timer reset: %s", pr_key)
            return True
        return False

    def _cancel_in_flight(self, pr_key: PRKey) -> bool:
        task = self._in_flight.pop(pr_key, None)
        if task is not None:
            task.cancel()
            logger.info("In-flight review superseded: %s", pr_key)
            return True
        return False

    def _fire(
        self,
        pr_key: PRKey,
        coro_factory: Callable[[], Coroutine[Any, Any, None]],
    ) -> None:
        """Called by the event loop after the quiet period expires."""
        self._pending.pop(pr_key, None)
        loop = asyncio.get_running_loop()
        task = loop.create_task(self._run(pr_key, coro_factory))
        self._in_flight[pr_key] = task

    async def _run(
        self,
        pr_key: PRKey,
        coro_factory: Callable[[], Coroutine[Any, Any, None]],
    ) -> None:
        """Execute the review coroutine and clean up the in-flight slot."""
        try:
            await coro_factory()
        except asyncio.CancelledError:
            logger.info("Review task cancelled (superseded): %s", pr_key)
            raise
        except Exception:
            logger.exception("Review task failed: %s", pr_key)
        finally:
            self._in_flight.pop(pr_key, None)


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

debounce_manager: DebounceManager = DebounceManager(
    quiet_period=float(os.environ.get("KENJUTSU_DEBOUNCE_SECONDS", "30")),
)
