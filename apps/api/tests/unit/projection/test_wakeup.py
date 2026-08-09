"""Unit tests for the projection wake-up sources.

`PollOnlyWakeup` is covered end to end here. `ListenNotifyWakeup` needs
a real Postgres LISTEN connection for its notify path, which lives in
the integration suite, but its CONNECTION-BUDGET invariant does not:
one instance is shared by every projection and must hold exactly one
pool connection no matter how many advance loops call `wait()` at
once. A fake pool pins that here, in the fast lane, because the
integration test uses a single consumer and so cannot see the race.
"""

import asyncio
from typing import Any

import pytest

from cora.infrastructure.projection.wakeup import (
    NOTIFY_CHANNEL,
    ListenNotifyWakeup,
    PollOnlyWakeup,
)


@pytest.mark.unit
async def test_poll_only_wakeup_sleeps_for_timeout() -> None:
    wakeup = PollOnlyWakeup()
    loop = asyncio.get_event_loop()

    start = loop.time()
    await wakeup.wait(0.15)
    elapsed = loop.time() - start

    # Allow generous slack for CI variance; the floor matters more
    # than the ceiling.
    assert 0.10 <= elapsed <= 0.50


@pytest.mark.unit
async def test_poll_only_wakeup_close_is_safe_to_call_repeatedly() -> None:
    wakeup = PollOnlyWakeup()
    await wakeup.close()
    await wakeup.close()  # idempotent


@pytest.mark.unit
async def test_poll_only_wakeup_responds_to_cancellation() -> None:
    """The worker cancels the wait task on shutdown; PollOnlyWakeup
    must propagate cancellation cleanly."""
    wakeup = PollOnlyWakeup()
    task = asyncio.create_task(wakeup.wait(60.0))
    await asyncio.sleep(0.05)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task


class _FakeConnection:
    """Stands in for an asyncpg pool connection proxy."""

    def __init__(self, conn_id: int) -> None:
        self.conn_id = conn_id
        self.listen_channels: list[str] = []
        self.closed = False

    def is_closed(self) -> bool:
        return self.closed

    async def add_listener(self, channel: str, _callback: object) -> None:
        # Yield control so a concurrent caller can interleave here. Without
        # the lock under test, this is exactly where the losers of the race
        # would pile onto a connection already in use.
        await asyncio.sleep(0)
        self.listen_channels.append(channel)

    async def remove_listener(self, channel: str, _callback: object) -> None:
        self.listen_channels.remove(channel)


class _FakePool:
    """Counts acquisitions so a connection leak is directly observable."""

    def __init__(self) -> None:
        self.acquired: list[_FakeConnection] = []
        self.released: list[_FakeConnection] = []

    async def acquire(self) -> _FakeConnection:
        await asyncio.sleep(0)  # make the acquire a real suspension point
        conn = _FakeConnection(len(self.acquired))
        self.acquired.append(conn)
        return conn

    async def release(self, conn: _FakeConnection) -> None:
        self.released.append(conn)


def _wakeup(pool: _FakePool) -> ListenNotifyWakeup:
    return ListenNotifyWakeup(pool)  # type: ignore[arg-type]


@pytest.mark.unit
async def test_concurrent_waits_acquire_exactly_one_connection() -> None:
    """Every projection shares one instance, so `wait()` races itself.

    The regression this pins: on the 2-BM pilot, 40 projections racing
    here left six connections parked on LISTEN out of a pool of ten,
    because each racer overwrote `self._conn` and only the last was
    ever released.
    """
    pool = _FakePool()
    wakeup = _wakeup(pool)

    await asyncio.gather(*(wakeup.wait(0.01) for _ in range(40)))

    assert len(pool.acquired) == 1
    assert pool.acquired[0].listen_channels == [NOTIFY_CHANNEL]


@pytest.mark.unit
async def test_concurrent_waits_register_one_listener_only() -> None:
    """A duplicate `add_listener` on one connection is the InterfaceError source."""
    pool = _FakePool()
    wakeup = _wakeup(pool)

    await asyncio.gather(*(wakeup.wait(0.01) for _ in range(20)))

    assert [c.listen_channels for c in pool.acquired] == [[NOTIFY_CHANNEL]]


@pytest.mark.unit
async def test_second_wait_reuses_the_established_listener() -> None:
    pool = _FakePool()
    wakeup = _wakeup(pool)

    await wakeup.wait(0.01)
    await wakeup.wait(0.01)
    await wakeup.wait(0.01)

    assert len(pool.acquired) == 1


@pytest.mark.unit
async def test_closed_listener_connection_is_reacquired() -> None:
    """A dropped listener must not leave the worker permanently deaf."""
    pool = _FakePool()
    wakeup = _wakeup(pool)

    await wakeup.wait(0.01)
    pool.acquired[0].closed = True
    await wakeup.wait(0.01)

    assert len(pool.acquired) == 2
    assert pool.acquired[1].listen_channels == [NOTIFY_CHANNEL]


@pytest.mark.unit
async def test_notify_wakes_the_waiter_before_the_timeout() -> None:
    """The latency win the LISTEN connection exists for."""
    pool = _FakePool()
    wakeup = _wakeup(pool)
    await wakeup.wait(0.01)  # establish the listener

    loop = asyncio.get_event_loop()
    start = loop.time()
    task = asyncio.create_task(wakeup.wait(30.0))
    await asyncio.sleep(0.02)
    notify: Any = wakeup._on_notify  # pyright: ignore[reportPrivateUsage]
    notify(None, 0, NOTIFY_CHANNEL, "")
    await task

    assert loop.time() - start < 5.0


@pytest.mark.unit
async def test_close_releases_the_listen_connection() -> None:
    pool = _FakePool()
    wakeup = _wakeup(pool)
    await wakeup.wait(0.01)

    await wakeup.close()

    assert pool.released == [pool.acquired[0]]
    assert pool.acquired[0].listen_channels == []
