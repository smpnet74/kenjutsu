"""Unit tests for DebounceManager.

All tests use a very short quiet_period (TINY seconds) so the event loop can
advance naturally without artificial sleeps that would make the suite slow.

Coverage targets:
- Timer fires after the quiet period has elapsed
- Timer resets when a second schedule() arrives before the period elapses
- Explicit cancel() prevents firing
- In-flight task is cancelled and marked superseded by a new schedule()
- pending_keys / in_flight_keys snapshots are immutable frozensets
- Module-level singleton exists and is configured
"""

from __future__ import annotations

import asyncio

from kenjutsu.server.debounce import DebounceManager, PRKey

# 20 ms: fast enough for a test run, slow enough to be deterministic.
TINY: float = 0.02

PR_A: PRKey = ("owner/repo", 1)
PR_B: PRKey = ("owner/repo", 2)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_factory(called: list[PRKey], key: PRKey):  # type: ignore[return]
    """Return a coro_factory that appends *key* to *called* when it runs."""

    async def _review() -> None:
        called.append(key)

    return _review


# ---------------------------------------------------------------------------
# Schedule and fire
# ---------------------------------------------------------------------------


class TestScheduleAndFire:
    async def test_timer_fires_after_quiet_period(self) -> None:
        called: list[PRKey] = []
        mgr = DebounceManager(quiet_period=TINY)

        mgr.schedule(PR_A, make_factory(called, PR_A))
        assert PR_A in mgr.pending_keys

        await asyncio.sleep(TINY * 4)

        assert PR_A not in mgr.pending_keys
        assert called == [PR_A]

    async def test_timer_reset_fires_only_once(self) -> None:
        called: list[PRKey] = []
        mgr = DebounceManager(quiet_period=TINY)

        mgr.schedule(PR_A, make_factory(called, PR_A))
        await asyncio.sleep(TINY * 0.4)  # before period elapses

        mgr.schedule(PR_A, make_factory(called, PR_A))  # reset
        await asyncio.sleep(TINY * 0.4)  # still before the reset period

        assert called == [], "fired too early — timer was not properly reset"

        await asyncio.sleep(TINY * 4)
        assert called == [PR_A], "should have fired exactly once after reset"

    async def test_multiple_prs_are_independent(self) -> None:
        called: list[PRKey] = []
        mgr = DebounceManager(quiet_period=TINY)

        mgr.schedule(PR_A, make_factory(called, PR_A))
        mgr.schedule(PR_B, make_factory(called, PR_B))
        assert PR_A in mgr.pending_keys
        assert PR_B in mgr.pending_keys

        await asyncio.sleep(TINY * 4)

        assert set(called) == {PR_A, PR_B}

    async def test_pending_key_removed_after_fire(self) -> None:
        mgr = DebounceManager(quiet_period=TINY)
        mgr.schedule(PR_A, make_factory([], PR_A))
        await asyncio.sleep(TINY * 4)
        assert PR_A not in mgr.pending_keys


# ---------------------------------------------------------------------------
# Cancellation
# ---------------------------------------------------------------------------


class TestCancellation:
    async def test_explicit_cancel_prevents_fire(self) -> None:
        called: list[PRKey] = []
        mgr = DebounceManager(quiet_period=TINY)

        mgr.schedule(PR_A, make_factory(called, PR_A))
        result = mgr.cancel(PR_A)
        assert result is True

        await asyncio.sleep(TINY * 4)
        assert called == []

    async def test_cancel_returns_false_when_nothing_pending(self) -> None:
        mgr = DebounceManager(quiet_period=TINY)
        assert mgr.cancel(PR_A) is False

    async def test_cancel_only_affects_target_pr(self) -> None:
        called: list[PRKey] = []
        mgr = DebounceManager(quiet_period=TINY)

        mgr.schedule(PR_A, make_factory(called, PR_A))
        mgr.schedule(PR_B, make_factory(called, PR_B))
        mgr.cancel(PR_A)

        await asyncio.sleep(TINY * 4)
        assert called == [PR_B]

    async def test_new_schedule_cancels_in_flight_task(self) -> None:
        blocked = asyncio.Event()
        superseded: list[bool] = []

        async def _slow_review() -> None:
            try:
                await blocked.wait()
            except asyncio.CancelledError:
                superseded.append(True)
                raise

        async def _fast_review() -> None:
            pass

        mgr = DebounceManager(quiet_period=TINY)
        mgr.schedule(PR_A, _slow_review)

        # Let the slow review start running (timer fires, task created).
        await asyncio.sleep(TINY * 4)
        assert PR_A in mgr.in_flight_keys

        # A new push arrives — should cancel the in-flight task synchronously.
        mgr.schedule(PR_A, _fast_review)
        assert PR_A not in mgr.in_flight_keys  # removed from dict immediately

        # Allow the CancelledError to propagate through the blocked coroutine.
        await asyncio.sleep(0)
        await asyncio.sleep(0)
        assert superseded == [True]

    async def test_cancel_returns_true_for_in_flight_task(self) -> None:
        blocked = asyncio.Event()

        async def _slow_review() -> None:
            await blocked.wait()

        mgr = DebounceManager(quiet_period=TINY)
        mgr.schedule(PR_A, _slow_review)
        await asyncio.sleep(TINY * 4)
        assert PR_A in mgr.in_flight_keys

        result = mgr.cancel(PR_A)
        assert result is True
        assert PR_A not in mgr.in_flight_keys


# ---------------------------------------------------------------------------
# State snapshots
# ---------------------------------------------------------------------------


class TestStateSnapshots:
    async def test_pending_keys_is_frozenset(self) -> None:
        mgr = DebounceManager(quiet_period=100.0)
        mgr.schedule(PR_A, make_factory([], PR_A))
        keys = mgr.pending_keys
        assert isinstance(keys, frozenset)
        # Cancelling after the snapshot must not affect the captured frozenset.
        mgr.cancel(PR_A)
        assert PR_A in keys
        assert PR_A not in mgr.pending_keys

    async def test_in_flight_keys_is_frozenset(self) -> None:
        mgr = DebounceManager(quiet_period=TINY)
        blocked = asyncio.Event()

        async def _blocker() -> None:
            await blocked.wait()

        mgr.schedule(PR_A, _blocker)
        await asyncio.sleep(TINY * 4)
        keys = mgr.in_flight_keys
        assert isinstance(keys, frozenset)
        assert PR_A in keys


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------


class TestModuleSingleton:
    def test_singleton_is_debounce_manager_instance(self) -> None:
        from kenjutsu.server.debounce import debounce_manager

        assert isinstance(debounce_manager, DebounceManager)

    def test_singleton_has_positive_quiet_period(self) -> None:
        from kenjutsu.server.debounce import debounce_manager

        assert debounce_manager._quiet_period > 0


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------


class TestErrorHandling:
    async def test_exception_in_review_does_not_propagate(self) -> None:
        async def _bad_review() -> None:
            msg = "intentional test error"
            raise ValueError(msg)

        mgr = DebounceManager(quiet_period=TINY)
        mgr.schedule(PR_A, _bad_review)
        # Should not raise; exception is logged inside _run.
        await asyncio.sleep(TINY * 4)
        assert PR_A not in mgr.in_flight_keys

    async def test_in_flight_key_removed_after_task_completes(self) -> None:
        called: list[bool] = []

        async def _review() -> None:
            called.append(True)

        mgr = DebounceManager(quiet_period=TINY)
        mgr.schedule(PR_A, _review)
        await asyncio.sleep(TINY * 4)
        assert PR_A not in mgr.in_flight_keys
        assert called == [True]
