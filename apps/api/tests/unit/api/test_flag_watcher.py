"""Unit tests for the shared flag-only-watcher scaffold (cora.api._flag_watcher).

The per-agent behavior (envelope, drain, fold, gates) is covered by each
watcher's own suite, which exercises record_watcher_decision / is_stalled /
derive_watcher_decision_id through the watchers. This module pins the one
scaffold contract those suites do not reach: the loop re-raises CancelledError so
a lifespan exit actually stops an in-flight tick rather than swallowing the
cancellation and hanging shutdown.
"""

import asyncio

import pytest

from cora.api._flag_watcher import flag_watcher_lifespan


@pytest.mark.unit
async def test_in_flight_tick_is_cancelled_on_lifespan_exit() -> None:
    """Exiting the lifespan while a tick is blocked cancels it cleanly: the loop
    propagates CancelledError so task teardown completes without hanging."""
    started = asyncio.Event()
    released = False

    async def tick() -> None:
        nonlocal released
        started.set()
        await asyncio.Event().wait()  # block forever until cancelled
        released = True  # unreachable: cancellation interrupts the wait

    async with flag_watcher_lifespan(
        enabled=True,
        default_tick_seconds=0.01,
        log_prefix="test_watcher",
        task_name="test-watcher",
        tick=tick,
    ):
        await asyncio.wait_for(started.wait(), timeout=1.0)

    # Reaching here means the context exited without hanging on the blocked tick.
    assert released is False
