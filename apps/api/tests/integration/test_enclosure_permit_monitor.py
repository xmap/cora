"""Tests for the Enclosure permit monitor runtime (`_monitor.py`).

`record_observation` is pinned deterministically against a real event
store (maps an observation to an EnclosurePermitObserved transition,
status-change-only idempotency, unknown-code no-op). The retry loop +
lifespan are covered for the empty-config no-op path and for a
fake-observer drive that records one observation end to end. The
startup-race fix (module docstring "Startup race") is covered
separately: `startup_ready` semantics on the loop, and the lifespan's
bounded wait plus its still-yields-on-timeout fallback.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

import asyncio
import contextlib
import dataclasses
from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from typing import cast
from uuid import UUID, uuid4

import asyncpg
import pytest
import structlog.testing

from cora.enclosure import register_enclosure_projections, seed_enclosures
from cora.enclosure._monitor import (
    enclosure_permit_monitor_lifespan,
    record_observation,
    run_enclosure_permit_monitor,
)
from cora.enclosure.adapters import PostgresEnclosureLookup
from cora.enclosure.ports.enclosure_observer import (
    EnclosureObservation,
    EnclosureObserverScope,
)
from cora.infrastructure.config import Settings
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.ports.event_store import StoredEvent
from cora.infrastructure.projection import ProjectionDrainTimeoutError, ProjectionRegistry
from tests.integration._helpers import build_postgres_deps

_T = datetime(2026, 6, 17, 12, 0, 0, tzinfo=UTC)


def _deps_with(db_pool: asyncpg.Pool, *, permit_pvs: dict[str, str]) -> Kernel:
    deps = build_postgres_deps(db_pool, now=_T, ids=[uuid4() for _ in range(12)])
    return dataclasses.replace(
        deps,
        settings=Settings(app_env="test", enclosure_permit_pvs=permit_pvs),  # type: ignore[call-arg]
        enclosure_lookup=PostgresEnclosureLookup(db_pool),
    )


def _obs(name: str, status: str, *, pv: str = "S02BM-PSS:StaA:SecureM") -> EnclosureObservation:
    return EnclosureObservation(
        enclosure_code=name,
        observed_status=status,
        observed_at=_T,
        source_kind="EpicsPv",
        source_id=pv,
    )


async def _permit_events(deps: Kernel, enclosure_id: UUID) -> list[StoredEvent]:
    events, _ = await deps.event_store.load(stream_type="Enclosure", stream_id=enclosure_id)
    return [e for e in events if e.event_type == "EnclosurePermitObserved"]


@pytest.mark.integration
async def test_record_observation_writes_permit_observed(db_pool: asyncpg.Pool) -> None:
    name = f"hutch-rec-{uuid4().hex[:8]}"
    deps = _deps_with(db_pool, permit_pvs={name: "pv"})
    name_to_id = await seed_enclosures(deps)

    await record_observation(deps, _obs(name, "Permitted"), name_to_id)

    events = await _permit_events(deps, name_to_id[name])
    assert len(events) == 1
    assert events[0].payload["from_status"] == "Unknown"
    assert events[0].payload["to_status"] == "Permitted"


@pytest.mark.integration
async def test_record_observation_same_status_is_noop(db_pool: asyncpg.Pool) -> None:
    name = f"hutch-idem-{uuid4().hex[:8]}"
    deps = _deps_with(db_pool, permit_pvs={name: "pv"})
    name_to_id = await seed_enclosures(deps)

    await record_observation(deps, _obs(name, "Permitted"), name_to_id)
    await record_observation(deps, _obs(name, "Permitted"), name_to_id)

    assert len(await _permit_events(deps, name_to_id[name])) == 1


@pytest.mark.integration
async def test_record_observation_unknown_code_is_noop(db_pool: asyncpg.Pool) -> None:
    name = f"hutch-known-{uuid4().hex[:8]}"
    deps = _deps_with(db_pool, permit_pvs={name: "pv"})
    name_to_id = await seed_enclosures(deps)

    # observation for a code that was never seeded -> skipped, no raise
    await record_observation(deps, _obs("not-a-hutch", "Permitted"), name_to_id)
    assert await _permit_events(deps, name_to_id[name]) == []


@pytest.mark.unit
async def test_run_monitor_empty_map_returns_immediately() -> None:
    await run_enclosure_permit_monitor(
        observer=_FakeObserver([]), kernel=cast("Kernel", None), name_to_id={}
    )


@pytest.mark.unit
async def test_lifespan_empty_map_is_noop() -> None:
    async with enclosure_permit_monitor_lifespan(
        observer=_FakeObserver([]), kernel=cast("Kernel", None), name_to_id={}
    ):
        pass  # yields without starting a task; kernel/observer untouched


@pytest.mark.integration
async def test_loop_records_observation_from_observer(db_pool: asyncpg.Pool) -> None:
    name = f"hutch-loop-{uuid4().hex[:8]}"
    deps = _deps_with(db_pool, permit_pvs={name: "pv"})
    name_to_id = await seed_enclosures(deps)
    enclosure_id = name_to_id[name]

    observer = _FakeObserver([_obs(name, "Permitted")])
    task = asyncio.create_task(
        run_enclosure_permit_monitor(
            observer=observer,
            kernel=deps,
            name_to_id=name_to_id,
            reconnect_delay_seconds=3600.0,  # one pass, then idle (test cancels)
        )
    )
    try:
        for _ in range(200):
            if await _permit_events(deps, enclosure_id):
                break
            await asyncio.sleep(0.01)
        else:  # pragma: no cover - failure path
            raise AssertionError("monitor did not record the observation")
    finally:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task

    events = await _permit_events(deps, enclosure_id)
    assert len(events) == 1
    assert events[0].payload["to_status"] == "Permitted"


@pytest.mark.unit
async def test_record_observation_bad_status_is_noop() -> None:
    name = "hutch-bad"
    # Unparseable status flattens to a no-op before any event-store access,
    # so a None kernel is never touched.
    await record_observation(cast("Kernel", None), _obs(name, "Garbage"), {name: uuid4()})


@pytest.mark.unit
async def test_loop_logs_and_survives_record_failure() -> None:
    name = "hutch-rec-fail"
    kernel = _RaisingLoadKernel()
    observer = _FakeObserver([_obs(name, "Permitted")])
    task = asyncio.create_task(
        run_enclosure_permit_monitor(
            observer=observer,
            kernel=cast("Kernel", kernel),
            name_to_id={name: uuid4()},
            reconnect_delay_seconds=3600.0,
        )
    )
    try:
        await asyncio.wait_for(kernel.load_attempted.wait(), timeout=2.0)
        await asyncio.sleep(0)
        assert not task.done()  # the record error was swallowed; loop survives
    finally:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task


@pytest.mark.unit
async def test_loop_logs_and_survives_observer_iteration_failure() -> None:
    observer = _BoomObserver()
    task = asyncio.create_task(
        run_enclosure_permit_monitor(
            observer=observer,
            kernel=cast("Kernel", None),
            name_to_id={"hutch-iter-fail": uuid4()},
            reconnect_delay_seconds=3600.0,
        )
    )
    try:
        await asyncio.wait_for(observer.observe_started.wait(), timeout=2.0)
        await asyncio.sleep(0)
        assert not task.done()  # the iteration error was swallowed; loop survives
    finally:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task


@pytest.mark.unit
async def test_loop_cancellation_during_record_propagates() -> None:
    name = "hutch-cancel"
    observer = _FakeObserver([_obs(name, "Permitted")])
    with pytest.raises(asyncio.CancelledError):
        await run_enclosure_permit_monitor(
            observer=observer,
            kernel=cast("Kernel", _CancelOnLoadKernel()),
            name_to_id={name: uuid4()},
            reconnect_delay_seconds=0.0,
        )


@pytest.mark.unit
async def test_lifespan_nonempty_starts_and_cancels_monitor_task() -> None:
    async with enclosure_permit_monitor_lifespan(
        observer=_FakeObserver([]),
        kernel=cast("Kernel", None),
        name_to_id={"hutch-lifespan": uuid4()},
    ):
        await asyncio.sleep(0)  # let the background task start and park on reconnect
    # context exit cancels the task cleanly: no hang, no error surfaced


@pytest.mark.unit
async def test_run_monitor_startup_ready_waits_for_every_configured_code() -> None:
    code_a, code_b = "hutch-a", "hutch-b"
    release = asyncio.Event()
    observer = _StaggeredObserver(_obs(code_a, "Garbage"), _obs(code_b, "Garbage"), release)
    ready = asyncio.Event()
    task = asyncio.create_task(
        run_enclosure_permit_monitor(
            observer=observer,
            kernel=cast("Kernel", None),
            name_to_id={code_a: uuid4(), code_b: uuid4()},
            reconnect_delay_seconds=3600.0,
            startup_ready=ready,
        )
    )
    try:
        await asyncio.wait_for(observer.first_yielded.wait(), timeout=2.0)
        assert not ready.is_set()  # code_b has not answered yet
        release.set()
        await asyncio.wait_for(ready.wait(), timeout=2.0)
    finally:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task


@pytest.mark.unit
async def test_run_monitor_startup_ready_set_when_pass_yields_nothing() -> None:
    # An empty scope (observer.observe ends without yielding) still settles:
    # startup_ready must not wait forever for a monitor that has nothing to say.
    ready = asyncio.Event()
    task = asyncio.create_task(
        run_enclosure_permit_monitor(
            observer=_FakeObserver([]),
            kernel=cast("Kernel", None),
            name_to_id={"hutch-empty": uuid4()},
            reconnect_delay_seconds=3600.0,
            startup_ready=ready,
        )
    )
    try:
        await asyncio.wait_for(ready.wait(), timeout=2.0)
    finally:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task


@pytest.mark.unit
async def test_run_monitor_startup_ready_set_on_iteration_failure() -> None:
    # The observer raising outright (e.g. an immediate connect failure the
    # observer itself could not turn into an Unknown) must still settle
    # startup_ready, not hang it until the timeout on every reconnect pass.
    ready = asyncio.Event()
    observer = _BoomObserver()
    task = asyncio.create_task(
        run_enclosure_permit_monitor(
            observer=observer,
            kernel=cast("Kernel", None),
            name_to_id={"hutch-iter-fail": uuid4()},
            reconnect_delay_seconds=3600.0,
            startup_ready=ready,
        )
    )
    try:
        await asyncio.wait_for(ready.wait(), timeout=2.0)
    finally:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task


@pytest.mark.unit
async def test_lifespan_yields_once_ready_without_waiting_full_timeout() -> None:
    # startup_timeout_seconds is set absurdly high; if the wait blocked for
    # the full duration this test would hang past pytest-timeout instead of
    # completing, so reaching the assertion proves readiness unblocked it.
    name = "hutch-lifespan-ready"
    async with enclosure_permit_monitor_lifespan(
        observer=_FakeObserver([_obs(name, "Garbage")]),
        kernel=cast("Kernel", None),
        name_to_id={name: uuid4()},
        startup_timeout_seconds=3600.0,
    ):
        pass


@pytest.mark.unit
async def test_lifespan_gives_up_after_timeout_and_still_yields() -> None:
    entered = False
    with structlog.testing.capture_logs() as logs:
        async with enclosure_permit_monitor_lifespan(
            observer=_HangingObserver(),
            kernel=cast("Kernel", None),
            name_to_id={"hutch-hang": uuid4()},
            startup_timeout_seconds=0.05,
        ):
            entered = True
    assert entered  # boot proceeds even though the monitor never settled
    events = [e.get("event") for e in logs]
    assert "enclosure_monitor.startup_timeout" in events


@pytest.mark.unit
async def test_lifespan_gives_up_after_drain_timeout_and_still_yields(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # A slow projection catch-up must degrade the same way as a slow PV: log
    # and proceed, never abort boot. `drain_projections` is monkeypatched
    # (rather than driven against a real slow drain) so this stays a fast
    # unit test pinning the CATCH, not drain_projections' own timeout logic.
    async def _raising_drain(*_args: object, **_kwargs: object) -> None:
        raise ProjectionDrainTimeoutError(
            deadline_seconds=5.0,
            subscribed_heads={"proj_enclosure_summary": 1},
            bookmarks={"proj_enclosure_summary": 0},
        )

    monkeypatch.setattr("cora.enclosure._monitor.drain_projections", _raising_drain)

    name = "hutch-drain-timeout"
    entered = False
    with structlog.testing.capture_logs() as logs:
        async with enclosure_permit_monitor_lifespan(
            observer=_FakeObserver([_obs(name, "Garbage")]),
            kernel=cast("Kernel", _PoolOnlyKernel()),
            name_to_id={name: uuid4()},
            enclosure_projection_registry=ProjectionRegistry(),
            startup_timeout_seconds=5.0,
        ):
            entered = True
    assert entered  # boot proceeds even though the projection drain timed out
    events = [e.get("event") for e in logs]
    assert "enclosure_monitor.projection_drain_timeout" in events


@pytest.mark.unit
async def test_lifespan_cancelled_during_startup_wait_still_cleans_up_task() -> None:
    # Regression: entering the context manager used to create the background
    # task, then await the startup wait with no enclosing try/finally, so a
    # cancellation delivered during that wait (before __aenter__ ever
    # returns) skipped cleanup entirely and leaked the task.
    cm = enclosure_permit_monitor_lifespan(
        observer=_HangingObserver(),
        kernel=cast("Kernel", None),
        name_to_id={"hutch-cancel-startup": uuid4()},
        startup_timeout_seconds=3600.0,  # only our cancellation should end this
    )
    entering = asyncio.ensure_future(cm.__aenter__())
    await asyncio.sleep(0)  # let it reach the startup wait
    entering.cancel()
    with pytest.raises(asyncio.CancelledError):
        await entering
    await asyncio.sleep(0)  # let the finally's task.cancel()/await settle
    leaked = [
        t
        for t in asyncio.all_tasks()
        if t.get_name() == "enclosure-permit-monitor" and not t.done()
    ]
    assert not leaked


@pytest.mark.integration
async def test_lifespan_drains_projection_before_yielding(db_pool: asyncpg.Pool) -> None:
    # startup_ready proves the event was appended, not that permit_status
    # itself is caught up; this pins the second half of the fix, that the
    # projection is drained before the context manager body ever runs.
    name = f"hutch-drain-{uuid4().hex[:8]}"
    deps = _deps_with(db_pool, permit_pvs={name: "pv"})
    name_to_id = await seed_enclosures(deps)
    enclosure_id = name_to_id[name]

    registry = ProjectionRegistry()
    register_enclosure_projections(registry, deps)

    async with enclosure_permit_monitor_lifespan(
        observer=_FakeObserver([_obs(name, "Permitted")]),
        kernel=deps,
        name_to_id=name_to_id,
        enclosure_projection_registry=registry,
        startup_timeout_seconds=5.0,
    ):
        row = await db_pool.fetchrow(
            "SELECT permit_status FROM proj_enclosure_summary WHERE enclosure_id = $1",
            enclosure_id,
        )
        assert row is not None
        assert row["permit_status"] == "Permitted"


class _FakeObserver:
    """Yields a fixed observation sequence once, then ends the stream."""

    def __init__(self, observations: list[EnclosureObservation]) -> None:
        self._observations = observations

    def observe(self, scope: EnclosureObserverScope) -> AsyncGenerator[EnclosureObservation]:
        return self._drain()

    async def _drain(self) -> AsyncGenerator[EnclosureObservation]:
        for observation in self._observations:
            yield observation


class _BoomObserver:
    """Raises mid-iteration so the loop's outer resilience branch fires."""

    def __init__(self) -> None:
        self.observe_started = asyncio.Event()

    def observe(self, scope: EnclosureObserverScope) -> AsyncGenerator[EnclosureObservation]:
        return self._drain()

    async def _drain(self) -> AsyncGenerator[EnclosureObservation]:
        self.observe_started.set()
        raise RuntimeError("observer boom")
        yield  # pragma: no cover - unreachable, marks this body an async generator


class _StaggeredObserver:
    """Yields one observation, then gates the second behind `release`.

    `first_yielded` fires once the consumer has resumed this generator to
    ask for the second item, which only happens after the consumer has
    finished processing the first (including any `startup_ready` bookkeeping).
    """

    def __init__(
        self,
        first: EnclosureObservation,
        second: EnclosureObservation,
        release: asyncio.Event,
    ) -> None:
        self._first = first
        self._second = second
        self._release = release
        self.first_yielded = asyncio.Event()

    def observe(self, scope: EnclosureObserverScope) -> AsyncGenerator[EnclosureObservation]:
        return self._drain()

    async def _drain(self) -> AsyncGenerator[EnclosureObservation]:
        yield self._first
        self.first_yielded.set()
        await self._release.wait()
        yield self._second


class _HangingObserver:
    """Never yields and never ends.

    Real adapters (`EpicsCaControlPort`) always bound a connect attempt and
    resolve to a real `Unknown` observation, so this is not a faithful model
    of an unreachable PV; it exercises the lifespan's `TimeoutError` fallback
    in the abstract, for whatever future observer or bug might not settle.
    """

    def observe(self, scope: EnclosureObserverScope) -> AsyncGenerator[EnclosureObservation]:
        return self._drain()

    async def _drain(self) -> AsyncGenerator[EnclosureObservation]:
        await asyncio.Event().wait()  # never released
        yield _obs("unreachable", "Garbage")  # pragma: no cover - dead code, never released


class _PoolOnlyKernel:
    """Kernel double exposing a non-None `pool` sentinel, nothing else.

    Only used with a monkeypatched `drain_projections`, which never touches
    `pool` for real; this just needs to satisfy the lifespan's
    `kernel.pool is not None` gate before reaching the drain call.
    """

    def __init__(self) -> None:
        self.pool = object()


class _RaisingLoadKernel:
    """Kernel double whose event-store load raises, to drive the per-record branch."""

    def __init__(self) -> None:
        self.load_attempted = asyncio.Event()
        self.event_store = self

    async def load(self, *, stream_type: str, stream_id: UUID) -> object:
        self.load_attempted.set()
        raise RuntimeError("load boom")


class _CancelOnLoadKernel:
    """Kernel double whose load raises CancelledError, modelling shutdown mid-record."""

    def __init__(self) -> None:
        self.event_store = self

    async def load(self, *, stream_type: str, stream_id: UUID) -> object:
        raise asyncio.CancelledError
