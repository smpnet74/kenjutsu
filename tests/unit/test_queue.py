"""Unit tests for queue management (DEM-161 — 1.5c).

All tests are DBOS-free and use only asyncio primitives.
"""

from __future__ import annotations

import asyncio

import pytest

from kenjutsu.pipeline.queue import (
    CostTracker,
    GlobalQueue,
    RateLimiter,
    ReviewKey,
    SupersessionRegistry,
    TenantQueue,
)

# ---------------------------------------------------------------------------
# ReviewKey
# ---------------------------------------------------------------------------


class TestReviewKey:
    def test_equality_by_value(self) -> None:
        assert ReviewKey(repo_id="r1", pr_number=42) == ReviewKey(repo_id="r1", pr_number=42)

    def test_inequality_on_different_pr(self) -> None:
        assert ReviewKey(repo_id="r1", pr_number=42) != ReviewKey(repo_id="r1", pr_number=43)

    def test_hashable_for_dict_keys(self) -> None:
        d: dict[ReviewKey, str] = {}
        d[ReviewKey(repo_id="r1", pr_number=1)] = "a"
        d[ReviewKey(repo_id="r1", pr_number=2)] = "b"
        assert len(d) == 2


# ---------------------------------------------------------------------------
# GlobalQueue — configurable concurrency limit
# ---------------------------------------------------------------------------


class TestGlobalQueue:
    @pytest.mark.asyncio
    async def test_allows_up_to_max_concurrency(self) -> None:
        """At most max_concurrency tasks may hold the queue simultaneously."""
        queue = GlobalQueue(max_concurrency=2)
        inside: list[int] = []
        hold = asyncio.Event()

        async def task(n: int) -> None:
            async with queue:
                inside.append(n)
                await hold.wait()
                inside.remove(n)

        t1 = asyncio.create_task(task(1))
        t2 = asyncio.create_task(task(2))
        await asyncio.sleep(0)  # let tasks reach hold.wait()
        await asyncio.sleep(0)
        assert len(inside) == 2

        t3 = asyncio.create_task(task(3))
        await asyncio.sleep(0)  # t3 should be blocked waiting for a slot
        assert 3 not in inside  # t3 has not entered yet

        hold.set()  # release all
        await asyncio.gather(t1, t2, t3)

    @pytest.mark.asyncio
    async def test_slot_released_after_context_exit(self) -> None:
        queue = GlobalQueue(max_concurrency=1)
        async with queue:
            pass
        # If slot was released we can acquire again immediately
        acquired = False
        async with queue:
            acquired = True
        assert acquired

    def test_max_concurrency_stored(self) -> None:
        queue = GlobalQueue(max_concurrency=5)
        assert queue.max_concurrency == 5


# ---------------------------------------------------------------------------
# TenantQueue — per-tenant concurrency cap
# ---------------------------------------------------------------------------


class TestTenantQueue:
    @pytest.mark.asyncio
    async def test_per_tenant_limit_enforced(self) -> None:
        tq = TenantQueue(max_concurrency=1)
        inside: list[str] = []
        hold = asyncio.Event()

        async def task(tenant: str) -> None:
            async with tq.for_tenant(tenant):
                inside.append(tenant)
                await hold.wait()
                inside.remove(tenant)

        t1 = asyncio.create_task(task("acme"))
        await asyncio.sleep(0)
        await asyncio.sleep(0)
        assert inside == ["acme"]

        t2 = asyncio.create_task(task("acme"))
        await asyncio.sleep(0)
        assert inside == ["acme"]  # t2 still blocked

        hold.set()
        await asyncio.gather(t1, t2)

    @pytest.mark.asyncio
    async def test_different_tenants_do_not_block_each_other(self) -> None:
        tq = TenantQueue(max_concurrency=1)
        inside: list[str] = []
        hold = asyncio.Event()

        async def task(tenant: str) -> None:
            async with tq.for_tenant(tenant):
                inside.append(tenant)
                await hold.wait()
                inside.remove(tenant)

        t1 = asyncio.create_task(task("acme"))
        t2 = asyncio.create_task(task("beta"))
        await asyncio.sleep(0)
        await asyncio.sleep(0)
        assert set(inside) == {"acme", "beta"}

        hold.set()
        await asyncio.gather(t1, t2)

    @pytest.mark.asyncio
    async def test_tenant_semaphore_created_on_demand(self) -> None:
        tq = TenantQueue(max_concurrency=2)
        async with tq.for_tenant("new-tenant"):
            pass  # should not raise


# ---------------------------------------------------------------------------
# RateLimiter — sliding-window token bucket
# ---------------------------------------------------------------------------


class TestRateLimiter:
    @pytest.mark.asyncio
    async def test_first_calls_within_limit_do_not_wait(self) -> None:
        """calls <= rate_limit in fresh window should pass immediately."""
        fake_time = [0.0]

        def _now() -> float:
            return fake_time[0]

        limiter = RateLimiter(calls=3, period=1.0, _now=_now)
        delays: list[float] = []

        for _ in range(3):
            t0 = fake_time[0]
            await limiter.acquire()
            delays.append(fake_time[0] - t0)

        assert all(d < 0.01 for d in delays)

    @pytest.mark.asyncio
    async def test_exceeding_rate_raises_rate_limited(self) -> None:
        """Exceeding the call rate raises RateLimitedError."""
        from kenjutsu.pipeline.queue import RateLimitedError

        fake_time = [0.0]

        def _now() -> float:
            return fake_time[0]

        limiter = RateLimiter(calls=2, period=1.0, _now=_now)
        await limiter.acquire()
        await limiter.acquire()

        with pytest.raises(RateLimitedError):
            await limiter.acquire()  # 3rd call in same window

    @pytest.mark.asyncio
    async def test_window_resets_after_period(self) -> None:
        fake_time = [0.0]

        def _now() -> float:
            return fake_time[0]

        limiter = RateLimiter(calls=2, period=1.0, _now=_now)
        await limiter.acquire()
        await limiter.acquire()

        fake_time[0] = 1.1  # advance past period
        await limiter.acquire()  # should succeed, window reset


# ---------------------------------------------------------------------------
# SupersessionRegistry — stale-work cancellation
# ---------------------------------------------------------------------------


class TestSupersessionRegistry:
    def test_register_returns_cancel_event(self) -> None:
        reg = SupersessionRegistry()
        key = ReviewKey(repo_id="r1", pr_number=1)
        event = reg.register(key)
        assert not event.is_set()

    def test_second_register_cancels_first(self) -> None:
        reg = SupersessionRegistry()
        key = ReviewKey(repo_id="r1", pr_number=1)
        first_event = reg.register(key)
        reg.register(key)  # supersedes first
        assert first_event.is_set()

    def test_second_register_new_event_not_cancelled(self) -> None:
        reg = SupersessionRegistry()
        key = ReviewKey(repo_id="r1", pr_number=1)
        reg.register(key)
        second_event = reg.register(key)
        assert not second_event.is_set()

    def test_different_keys_independent(self) -> None:
        reg = SupersessionRegistry()
        k1 = ReviewKey(repo_id="r1", pr_number=1)
        k2 = ReviewKey(repo_id="r1", pr_number=2)
        e1 = reg.register(k1)
        e2 = reg.register(k2)
        assert not e1.is_set()
        assert not e2.is_set()

    def test_complete_removes_key(self) -> None:
        reg = SupersessionRegistry()
        key = ReviewKey(repo_id="r1", pr_number=1)
        reg.register(key)
        reg.complete(key)
        # Registering again after complete should not be cancelled
        new_event = reg.register(key)
        assert not new_event.is_set()

    def test_is_cancelled_true_after_supersession(self) -> None:
        reg = SupersessionRegistry()
        key = ReviewKey(repo_id="r1", pr_number=1)
        reg.register(key)
        reg.register(key)  # supersedes
        assert reg.is_cancelled(key)

    def test_is_cancelled_false_for_active_review(self) -> None:
        reg = SupersessionRegistry()
        key = ReviewKey(repo_id="r1", pr_number=1)
        reg.register(key)
        assert not reg.is_cancelled(key)


# ---------------------------------------------------------------------------
# CostTracker — per-tenant cost caps
# ---------------------------------------------------------------------------


class TestCostTracker:
    def test_no_cap_never_stops(self) -> None:
        tracker = CostTracker()
        status = tracker.record_cost("tenant-a", 9999.0)
        assert not status.hard_stop
        assert not status.alert_triggered

    def test_below_alert_threshold(self) -> None:
        tracker = CostTracker()
        tracker.set_cap("tenant-a", cap=100.0)
        status = tracker.record_cost("tenant-a", 79.0)
        assert not status.alert_triggered
        assert not status.hard_stop

    def test_alert_at_80_percent(self) -> None:
        tracker = CostTracker()
        tracker.set_cap("tenant-a", cap=100.0)
        status = tracker.record_cost("tenant-a", 80.0)
        assert status.alert_triggered
        assert not status.hard_stop

    def test_hard_stop_at_100_percent(self) -> None:
        tracker = CostTracker()
        tracker.set_cap("tenant-a", cap=100.0)
        status = tracker.record_cost("tenant-a", 100.0)
        assert status.hard_stop

    def test_hard_stop_over_100_percent(self) -> None:
        tracker = CostTracker()
        tracker.set_cap("tenant-a", cap=100.0)
        status = tracker.record_cost("tenant-a", 150.0)
        assert status.hard_stop

    def test_costs_accumulate(self) -> None:
        tracker = CostTracker()
        tracker.set_cap("tenant-a", cap=100.0)
        tracker.record_cost("tenant-a", 50.0)
        status = tracker.record_cost("tenant-a", 35.0)
        assert status.alert_triggered
        assert not status.hard_stop

    def test_tenants_are_independent(self) -> None:
        tracker = CostTracker()
        tracker.set_cap("tenant-a", cap=100.0)
        tracker.set_cap("tenant-b", cap=100.0)
        tracker.record_cost("tenant-a", 99.0)
        status_b = tracker.record_cost("tenant-b", 10.0)
        assert not status_b.alert_triggered

    def test_check_returns_current_status(self) -> None:
        tracker = CostTracker()
        tracker.set_cap("tenant-a", cap=100.0)
        tracker.record_cost("tenant-a", 85.0)
        status = tracker.check("tenant-a")
        assert status.current_cost == 85.0
        assert status.alert_triggered

    def test_cost_status_fields(self) -> None:
        tracker = CostTracker()
        tracker.set_cap("tenant-a", cap=200.0)
        status = tracker.record_cost("tenant-a", 50.0)
        assert status.tenant_id == "tenant-a"
        assert status.current_cost == 50.0
        assert status.cap == 200.0


# ---------------------------------------------------------------------------
# No DBOS imports in queue module
# ---------------------------------------------------------------------------


def test_queue_module_has_no_dbos_imports() -> None:
    """Business logic must stay framework-free (arch spec §3.6).

    Checks for actual import statements, not doc-comment mentions.
    """
    import pathlib
    import re

    queue_path = pathlib.Path(__file__).parent.parent.parent / "kenjutsu" / "pipeline" / "queue.py"
    source = queue_path.read_text()
    # Detect 'import dbos' or 'from dbos' — doc comments mentioning DBOS are fine
    dbos_import = re.search(r"^\s*(import|from)\s+dbos", source, re.IGNORECASE | re.MULTILINE)
    assert dbos_import is None, f"queue.py must not import DBOS; found: {dbos_import}"
