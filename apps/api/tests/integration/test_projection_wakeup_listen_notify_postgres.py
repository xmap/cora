"""Integration tests for `ListenNotifyWakeup` against real Postgres.

This is the production wake-up source — `Settings.projection_use_listen_notify`
defaults to True, so every deploy without an explicit override runs on
this implementation. `PollOnlyWakeup` is covered by unit tests in
`tests/unit/projection/test_wakeup.py`.

Pins each reachable behavioral edge:
  - wait() returns immediately on pg_notify (latency well below timeout)
  - wait() returns on timeout when no NOTIFY arrives
  - close() before any wait() is a no-op (lazy acquisition)
  - close() is idempotent
  - second wait() reuses the same listener connection (early-return path)

The `is_closed() == True` branches in `_ensure_listening` (line 97) and
`close` (line 127) are unreachable under asyncpg's `PoolConnectionProxy`
semantics: when the underlying backend dies, the pool auto-releases the
proxy, and `is_closed()` then raises `InterfaceError` rather than
returning True. The outer worker retry loop is what actually recovers
from listener disconnects — see [[project_phase_plan]] for the
defer/clean-up follow-up.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false, reportPrivateUsage=false, reportOptionalMemberAccess=false, reportAttributeAccessIssue=false

import asyncio

import asyncpg
import pytest

from cora.infrastructure.projection.wakeup import NOTIFY_CHANNEL, ListenNotifyWakeup


async def _send_notify(pool: asyncpg.Pool, payload: str = "test") -> None:
    """Fire a NOTIFY on the events channel from a non-listener connection.

    asyncpg's `execute` runs in autocommit when not inside a `.transaction()`
    block, so NOTIFY is delivered at the implicit COMMIT immediately after.
    """
    async with pool.acquire() as conn:
        await conn.execute(f"NOTIFY {NOTIFY_CHANNEL}, '{payload}'")


# Hang guards, not timing assertions: the test's conclusion comes from
# `_event`, so these only need to be comfortably larger than any
# plausible contention delay and comfortably under the 60s per-test cap.
_WAIT_TIMEOUT_S = 20.0
_READY_DEADLINE_S = 20.0


@pytest.mark.integration
async def test_wait_returns_immediately_on_notify(db_pool: asyncpg.Pool) -> None:
    """`wait()` is woken by the NOTIFY, not by its own timeout expiring.

    Both halves used to be wall-clock guesses: a fixed 50ms sleep hoping
    `add_listener` had completed, and an `elapsed < 1.0` assertion standing in
    for "it was the notify". Under `-n 4` both are unsound, and the first is
    silently so: a NOTIFY sent before the listener registers is delivered to
    nobody and dropped, so the test fails on the timeout it was trying to rule
    out. Now readiness is awaited on the flag `_ensure_listening` sets, and the
    conclusion is drawn from `_event`, which `wait()` clears before waiting and
    `_on_notify` sets. Set means the notify woke it; clear means the timeout did.
    """
    wakeup = ListenNotifyWakeup(db_pool)
    loop = asyncio.get_event_loop()
    try:
        wait_task = asyncio.create_task(wakeup.wait(_WAIT_TIMEOUT_S))

        registered_by = loop.time() + _READY_DEADLINE_S
        while not wakeup._listening:
            assert loop.time() < registered_by, (
                "listener never registered; a NOTIFY now would be dropped and the "
                "test would fail on wait()'s timeout rather than on delivery"
            )
            await asyncio.sleep(0.01)

        await _send_notify(db_pool, "wakeup-test")
        await asyncio.wait_for(wait_task, timeout=_WAIT_TIMEOUT_S)

        assert wakeup._event.is_set(), (
            "wait() returned with the event clear, so it fell through its own "
            "timeout instead of being woken by the NOTIFY"
        )
    finally:
        await wakeup.close()


@pytest.mark.integration
async def test_wait_returns_on_timeout_when_no_notify(db_pool: asyncpg.Pool) -> None:
    wakeup = ListenNotifyWakeup(db_pool)
    loop = asyncio.get_event_loop()
    try:
        start = loop.time()
        await wakeup.wait(0.15)
        elapsed = loop.time() - start
        assert 0.10 <= elapsed <= 0.60
    finally:
        await wakeup.close()


@pytest.mark.integration
async def test_close_before_first_wait_is_safe(db_pool: asyncpg.Pool) -> None:
    """Lazy acquisition: no connection is held until the first wait()."""
    wakeup = ListenNotifyWakeup(db_pool)
    await wakeup.close()
    assert wakeup._conn is None


@pytest.mark.integration
async def test_close_is_idempotent(db_pool: asyncpg.Pool) -> None:
    wakeup = ListenNotifyWakeup(db_pool)
    try:
        await wakeup.wait(0.05)
    finally:
        await wakeup.close()
        await wakeup.close()  # second call hits the conn-is-None early return


@pytest.mark.integration
async def test_second_wait_reuses_listener_connection(db_pool: asyncpg.Pool) -> None:
    """The already-listening fast path skips re-acquisition.

    Pins the `_listening and conn and not is_closed -> return` short-
    circuit at the top of `_ensure_listening`. Without it the listener
    would re-register on every wait, leaking connections under the
    worker's normal busy-loop.
    """
    wakeup = ListenNotifyWakeup(db_pool)
    try:
        await wakeup.wait(0.05)
        conn_after_first = wakeup._conn
        assert conn_after_first is not None

        await wakeup.wait(0.05)
        assert wakeup._conn is conn_after_first  # same proxy instance
    finally:
        await wakeup.close()
