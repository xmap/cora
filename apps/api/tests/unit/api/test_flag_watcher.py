"""Unit tests for the shared flag-only-watcher scaffold (cora.api._flag_watcher).

The per-agent behavior (envelope, drain, fold, gates) is covered by each
watcher's own suite, which exercises record_watcher_decision / is_stalled /
derive_watcher_decision_id through the watchers. This module pins the scaffold
contracts those suites do not reach: the loop's CancelledError propagation, the
read-unauthorized edge-trigger (a blinded watchdog warns loudly once per episode
and recovers, not a buried traceback), and the startup read-grant probe.
"""

import asyncio
from datetime import UTC, datetime
from uuid import UUID

import pytest
import structlog

from cora.api._flag_watcher import (
    WatcherReadUnauthorizedError,
    flag_watcher_lifespan,
    probe_read_grant,
)
from cora.infrastructure.config import Settings
from cora.infrastructure.deps import make_inmemory_kernel
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.ports import Allow, AllowAllAuthorize, Deny, FakeClock, UUIDv7Generator

_NOW = datetime(2026, 6, 22, 12, 0, 0, tzinfo=UTC)
_AGENT = UUID("01900000-0000-7000-8000-0000cab10010")


class _DenyingAuthorize:
    """Authorize stub that Denies every check (the production-misconfig case)."""

    async def authorize(
        self,
        *,
        principal_id: UUID,
        command_name: str,
        conduit_id: UUID,
        surface_id: UUID,
    ) -> Deny:
        return Deny(reason=f"{principal_id} not granted {command_name}")


def _kernel(authz: object) -> Kernel:
    return make_inmemory_kernel(
        settings=Settings(),  # type: ignore[call-arg]
        clock=FakeClock(_NOW),
        id_generator=UUIDv7Generator(),
        authz=authz,  # type: ignore[arg-type]
    )


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


@pytest.mark.unit
async def test_loop_warns_once_per_read_denial_episode_then_recovers() -> None:
    """A read-denial is surfaced as a distinct, edge-triggered warning (once per
    episode, not per tick) and a recovery is logged when reads resume -- not a
    crash and not a generic tick_failed traceback."""
    state = {"calls": 0}
    recovered = asyncio.Event()

    async def tick() -> None:
        state["calls"] += 1
        if state["calls"] <= 2:  # two denied ticks in one episode
            raise WatcherReadUnauthorizedError(
                query_name="ListThings", principal_id=_AGENT, reason="not granted"
            )
        recovered.set()  # third tick onward: reads succeed (grant restored)

    with structlog.testing.capture_logs() as logs:
        async with flag_watcher_lifespan(
            enabled=True,
            default_tick_seconds=0.01,
            log_prefix="test_watcher",
            task_name="test-watcher",
            tick=tick,
        ):
            await asyncio.wait_for(recovered.wait(), timeout=1.0)
            await asyncio.sleep(0.02)  # let the loop log the recovery after the tick returns

    events = [e.get("event") for e in logs]
    # Edge-trigger: warned exactly once across the two-tick denial episode...
    assert events.count("test_watcher.read_unauthorized") == 1
    # ...and never as a generic tick_failed traceback.
    assert "test_watcher.tick_failed" not in events
    # ...and a recovery was logged when the grant came back.
    assert "test_watcher.read_authorized_recovered" in events


@pytest.mark.unit
async def test_probe_read_grant_warns_and_does_not_raise_under_deny_when_not_strict() -> None:
    """Non-strict startup probe: a denied grant logs read_unauthorized_at_startup
    and lets boot proceed (the watcher will warn at runtime too)."""
    kernel = _kernel(_DenyingAuthorize())
    with structlog.testing.capture_logs() as logs:
        await probe_read_grant(
            kernel, agent_id=_AGENT, read_command="ListThings", log_prefix="tw", strict=False
        )
    assert "tw.read_unauthorized_at_startup" in [e.get("event") for e in logs]


@pytest.mark.unit
async def test_probe_read_grant_raises_under_deny_when_strict() -> None:
    """Strict startup probe: a denied grant refuses boot (raises)."""
    kernel = _kernel(_DenyingAuthorize())
    with pytest.raises(WatcherReadUnauthorizedError) as exc:
        await probe_read_grant(
            kernel, agent_id=_AGENT, read_command="ListThings", log_prefix="tw", strict=True
        )
    assert exc.value.query_name == "ListThings"


@pytest.mark.unit
async def test_probe_read_grant_is_noop_under_permissive_authz() -> None:
    """Under AllowAllAuthorize (dev/test) the probe never warns or raises."""
    kernel = _kernel(AllowAllAuthorize())
    with structlog.testing.capture_logs() as logs:
        await probe_read_grant(
            kernel, agent_id=_AGENT, read_command="ListThings", log_prefix="tw", strict=True
        )
    assert "tw.read_unauthorized_at_startup" not in [e.get("event") for e in logs]


@pytest.mark.unit
def test_allow_and_deny_value_shapes() -> None:
    """Guards the probe's isinstance(decision, Deny) branch contract."""
    assert isinstance(Deny(reason="x"), Deny)
    assert not isinstance(Allow(), Deny)
