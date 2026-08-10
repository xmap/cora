"""Tests for the Enclosure permit monitor runtime (`_monitor.py`).

`record_observation` is pinned deterministically against a real event
store (maps an observation to an EnclosurePermitObserved transition,
status-change-only idempotency, unknown-code no-op). The retry loop +
lifespan are covered for the empty-config no-op path and for a
fake-observer drive that records one observation end to end. The
startup-race fix (module docstring "Startup race") is covered
separately: `startup_ready` semantics on the loop, and the lifespan's
bounded wait plus its still-yields-on-timeout fallback.

The permit probe trail (module docstring "Permit probe trail",
[[project_enclosure_permit_probe_design]]) is covered separately below:
every mapped observation writes a probe row before any transition is
attempted; a probe-only observation (`observed_status=None`) writes a
row but never touches the event store and never settles startup
readiness; a probe-store failure never suppresses a real transition.
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
from cora.enclosure.aggregates.enclosure import (
    InMemoryPermitProbeStore,
    PermitProbe,
    PostgresPermitProbeStore,
    ReachTier,
)
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


def _obs(
    name: str,
    status: str | None,
    *,
    pv: str = "S02BM-PSS:StaA:SecureM",
    reach_tier: ReachTier = ReachTier.RELAYED,
) -> EnclosureObservation:
    return EnclosureObservation(
        enclosure_code=name,
        observed_status=status,
        reach_tier=reach_tier,
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

    await record_observation(deps, _obs(name, "Permitted"), name_to_id, InMemoryPermitProbeStore())

    events = await _permit_events(deps, name_to_id[name])
    assert len(events) == 1
    assert events[0].payload["from_status"] == "Unknown"
    assert events[0].payload["to_status"] == "Permitted"


@pytest.mark.integration
async def test_record_observation_same_status_writes_probes_but_no_second_event(
    db_pool: asyncpg.Pool,
) -> None:
    name = f"hutch-idem-{uuid4().hex[:8]}"
    deps = _deps_with(db_pool, permit_pvs={name: "pv"})
    name_to_id = await seed_enclosures(deps)
    probe_store = InMemoryPermitProbeStore()

    await record_observation(deps, _obs(name, "Permitted"), name_to_id, probe_store)
    await record_observation(deps, _obs(name, "Permitted"), name_to_id, probe_store)

    # The decider's status-change-only short-circuit still absorbs the
    # second observation on the transition path...
    assert len(await _permit_events(deps, name_to_id[name])) == 1
    # ...but the probe trail is not the event stream: a probe row is
    # written per observation regardless of whether it caused a
    # transition, which is the entire point of this slice.
    assert len(probe_store.all()) == 2


@pytest.mark.integration
async def test_record_observation_unknown_code_writes_no_probe_or_event(
    db_pool: asyncpg.Pool,
) -> None:
    name = f"hutch-known-{uuid4().hex[:8]}"
    deps = _deps_with(db_pool, permit_pvs={name: "pv"})
    name_to_id = await seed_enclosures(deps)
    probe_store = InMemoryPermitProbeStore()

    # observation for a code that was never seeded -> skipped, no raise,
    # and no probe row: an unmapped code cannot be attributed to an
    # enclosure at all.
    await record_observation(deps, _obs("not-a-hutch", "Permitted"), name_to_id, probe_store)
    assert await _permit_events(deps, name_to_id[name]) == []
    assert probe_store.all() == []


@pytest.mark.unit
async def test_run_monitor_empty_map_returns_immediately() -> None:
    await run_enclosure_permit_monitor(
        observer=_FakeObserver([]),
        kernel=cast("Kernel", None),
        name_to_id={},
        probe_store=InMemoryPermitProbeStore(),
    )


@pytest.mark.unit
async def test_lifespan_empty_map_is_noop() -> None:
    async with enclosure_permit_monitor_lifespan(
        observer=_FakeObserver([]),
        kernel=cast("Kernel", None),
        name_to_id={},
        probe_store=InMemoryPermitProbeStore(),
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
            probe_store=InMemoryPermitProbeStore(),
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
async def test_record_observation_bad_status_writes_probe_but_no_event() -> None:
    name = "hutch-bad"
    probe_store = InMemoryPermitProbeStore()
    # Unparseable status still writes the probe row (reach happened, the
    # value just could not be classified), but never reaches the event
    # store: EnclosurePermitStatus("Garbage") raises before kernel.event_store
    # would ever be touched. `_ProbeOnlyKernel` exposes only `id_generator`,
    # so an event-store access would AttributeError rather than pass silently.
    await record_observation(
        cast("Kernel", _ProbeOnlyKernel()), _obs(name, "Garbage"), {name: uuid4()}, probe_store
    )
    rows = probe_store.all()
    assert len(rows) == 1
    assert rows[0].status_claimed is True


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
            probe_store=InMemoryPermitProbeStore(),
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
            probe_store=InMemoryPermitProbeStore(),
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
            probe_store=InMemoryPermitProbeStore(),
            reconnect_delay_seconds=0.0,
        )


@pytest.mark.unit
async def test_lifespan_nonempty_starts_and_cancels_monitor_task() -> None:
    async with enclosure_permit_monitor_lifespan(
        observer=_FakeObserver([]),
        kernel=cast("Kernel", None),
        name_to_id={"hutch-lifespan": uuid4()},
        probe_store=InMemoryPermitProbeStore(),
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
            kernel=cast("Kernel", _ProbeOnlyKernel()),
            name_to_id={code_a: uuid4(), code_b: uuid4()},
            probe_store=InMemoryPermitProbeStore(),
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
async def test_run_monitor_startup_ready_not_set_when_pass_yields_nothing() -> None:
    # An empty scope (observer.observe ends without yielding anything) does
    # NOT settle startup_ready: no code was ever heard from, so falsely
    # reporting readiness here would let boot serve requests for an
    # enclosure whose permit status this process never confirmed. The
    # caller's own bounded wait (enclosure_permit_monitor_lifespan) is what
    # eventually gives up on a deployment that cannot connect at all.
    ready = asyncio.Event()
    task = asyncio.create_task(
        run_enclosure_permit_monitor(
            observer=_FakeObserver([]),
            kernel=cast("Kernel", None),
            name_to_id={"hutch-empty": uuid4()},
            probe_store=InMemoryPermitProbeStore(),
            reconnect_delay_seconds=3600.0,
            startup_ready=ready,
        )
    )
    try:
        await asyncio.sleep(0.05)  # let at least one empty pass complete
        assert not ready.is_set()
    finally:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task


@pytest.mark.unit
async def test_run_monitor_startup_ready_not_set_on_total_iteration_failure() -> None:
    # The observer raising outright, before ever yielding an observation,
    # must NOT settle startup_ready either: no code was heard from, so
    # settling here would be the same false-readiness bug as the
    # empty-pass case above. The caller's bounded wait is what eventually
    # gives up on this deployment.
    ready = asyncio.Event()
    observer = _BoomObserver()
    task = asyncio.create_task(
        run_enclosure_permit_monitor(
            observer=observer,
            kernel=cast("Kernel", None),
            name_to_id={"hutch-iter-fail": uuid4()},
            probe_store=InMemoryPermitProbeStore(),
            reconnect_delay_seconds=3600.0,
            startup_ready=ready,
        )
    )
    try:
        await asyncio.wait_for(observer.observe_started.wait(), timeout=2.0)
        await asyncio.sleep(0.05)
        assert not ready.is_set()
    finally:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task


@pytest.mark.unit
async def test_run_monitor_startup_ready_not_settled_by_probe_only_observation() -> None:
    # F1 regression: a probe-only observation (observed_status=None, the
    # shape a poll tick produces) must NOT settle startup readiness for its
    # code. Settling here would let boot serve a stale permit_status this
    # process never confirmed, exactly the window PR #642 closed.
    name = "hutch-probe-only"
    ready = asyncio.Event()
    task = asyncio.create_task(
        run_enclosure_permit_monitor(
            observer=_FakeObserver([_obs(name, None)]),
            kernel=cast("Kernel", _ProbeOnlyKernel()),
            name_to_id={name: uuid4()},
            probe_store=InMemoryPermitProbeStore(),
            reconnect_delay_seconds=3600.0,
            startup_ready=ready,
        )
    )
    try:
        await asyncio.sleep(0.05)
        assert not ready.is_set()
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
        kernel=cast("Kernel", _ProbeOnlyKernel()),
        name_to_id={name: uuid4()},
        probe_store=InMemoryPermitProbeStore(),
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
            probe_store=InMemoryPermitProbeStore(),
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
            probe_store=InMemoryPermitProbeStore(),
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
        probe_store=InMemoryPermitProbeStore(),
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
        probe_store=InMemoryPermitProbeStore(),
        enclosure_projection_registry=registry,
        startup_timeout_seconds=5.0,
    ):
        row = await db_pool.fetchrow(
            "SELECT permit_status FROM proj_enclosure_summary WHERE enclosure_id = $1",
            enclosure_id,
        )
        assert row is not None
        assert row["permit_status"] == "Permitted"


# --- Permit probe trail ------------------------------------------------


@pytest.mark.integration
async def test_record_observation_writes_a_probe_row_to_postgres(db_pool: asyncpg.Pool) -> None:
    name = f"hutch-probe-pg-{uuid4().hex[:8]}"
    deps = _deps_with(db_pool, permit_pvs={name: "pv"})
    name_to_id = await seed_enclosures(deps)
    probe_store = PostgresPermitProbeStore(db_pool)

    await record_observation(deps, _obs(name, "Permitted"), name_to_id, probe_store)

    row = await db_pool.fetchrow(
        "SELECT enclosure_id, source_kind, source_id, reach_tier, status_claimed "
        "FROM entries_enclosure_permit_probes WHERE enclosure_id = $1",
        name_to_id[name],
    )
    assert row is not None
    assert row["reach_tier"] == ReachTier.RELAYED.value
    assert row["status_claimed"] is True
    assert row["source_kind"] == "EpicsPv"


@pytest.mark.unit
async def test_probe_only_observation_writes_row_but_no_event() -> None:
    # A probe-only observation (observed_status=None, the shape a poll tick
    # produces) writes a probe row but never attempts a permit transition:
    # `_ProbeOnlyKernel` exposes only `id_generator`, so any event-store
    # access would AttributeError rather than silently succeed.
    name = "hutch-probe-only-record"
    probe_store = InMemoryPermitProbeStore()
    await record_observation(
        cast("Kernel", _ProbeOnlyKernel()),
        _obs(name, None, reach_tier=ReachTier.UNREACHED),
        {name: uuid4()},
        probe_store,
    )
    rows = probe_store.all()
    assert len(rows) == 1
    assert rows[0].status_claimed is False
    assert rows[0].reach_tier is ReachTier.UNREACHED


@pytest.mark.unit
async def test_record_observation_skips_probe_write_when_schema_degraded() -> None:
    # A degraded boot's event store is read-only (EventWritesDisabledError
    # on append), so a probe row would assert reach for a process that
    # cannot actually record what it observed. The correct signal is a
    # gap in the trail, not a row. `_DegradedSchemaKernel` exposes ONLY
    # `schema_posture`, so touching `id_generator` (part of building the
    # probe row) would AttributeError if the skip fired too late.
    name = "hutch-degraded"
    probe_store = InMemoryPermitProbeStore()
    with structlog.testing.capture_logs() as logs:
        await record_observation(
            cast("Kernel", _DegradedSchemaKernel()),
            _obs(name, None),
            {name: uuid4()},
            probe_store,
        )
    assert probe_store.all() == []
    events = [e.get("event") for e in logs]
    assert "enclosure_monitor.probe_skipped_degraded_schema" in events


@pytest.mark.integration
async def test_probe_store_failure_never_suppresses_the_permit_transition(
    db_pool: asyncpg.Pool,
) -> None:
    # The load-bearing lock (R6): a probe-store failure is a bookkeeping
    # problem, not a safety problem, and must never take down the real
    # transition. Driven against a real Postgres kernel so the assertion
    # is "the transition actually landed", not merely "was attempted".
    name = f"hutch-probe-fails-{uuid4().hex[:8]}"
    deps = _deps_with(db_pool, permit_pvs={name: "pv"})
    name_to_id = await seed_enclosures(deps)

    with structlog.testing.capture_logs() as logs:
        await record_observation(
            deps, _obs(name, "Permitted"), name_to_id, _RaisingPermitProbeStore()
        )

    events = await _permit_events(deps, name_to_id[name])
    assert len(events) == 1
    assert events[0].payload["to_status"] == "Permitted"
    log_events = [e.get("event") for e in logs]
    assert "enclosure_monitor.probe_write_failed" in log_events


@pytest.mark.unit
async def test_run_monitor_writes_no_probe_rows_when_observer_yields_nothing() -> None:
    # The anti-hook, stated in the module and design-lock docstrings: a
    # probe row must come from evidence about the substrate, never from
    # the loop's own liveness. An observer producing nothing, across
    # several reconnect passes, must produce zero probe rows.
    probe_store = InMemoryPermitProbeStore()
    task = asyncio.create_task(
        run_enclosure_permit_monitor(
            observer=_FakeObserver([]),
            kernel=cast("Kernel", None),
            name_to_id={"hutch-inert": uuid4()},
            probe_store=probe_store,
            reconnect_delay_seconds=0.01,
        )
    )
    try:
        await asyncio.sleep(0.1)  # several reconnect passes at this cadence
        assert probe_store.all() == []
    finally:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task


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
    """Kernel double exposing a non-None `pool` sentinel, plus a matched
    `schema_posture` (the record_observation probe-write gate touches it
    on every call) and `id_generator` (the observation this kernel is
    driven with is status-bearing, so the probe write is attempted).

    Only used with a monkeypatched `drain_projections`, which never touches
    `pool` for real; `pool` just needs to satisfy the lifespan's
    `kernel.pool is not None` gate before reaching the drain call.
    """

    def __init__(self) -> None:
        self.pool = object()
        self.schema_posture = "matched"
        self.id_generator = _FixedIdGenerator()


class _ProbeOnlyKernel:
    """Kernel double exposing only `schema_posture` and `id_generator`.

    Used to prove a code path never reaches `kernel.event_store`: that
    access would AttributeError here rather than silently succeeding.
    """

    def __init__(self) -> None:
        self.schema_posture = "matched"
        self.id_generator = _FixedIdGenerator()


class _DegradedSchemaKernel:
    """Kernel double exposing only `schema_posture="degraded"`.

    Touching `id_generator` or `event_store` would mean the degraded-boot
    probe-write skip fired too late (or not at all).
    """

    schema_posture = "degraded"


class _FixedIdGenerator:
    def new_id(self) -> UUID:
        return uuid4()


class _RaisingPermitProbeStore:
    """`PermitProbeStore` double whose append always raises (R6 pin)."""

    async def append(self, rows: list[PermitProbe]) -> None:
        raise RuntimeError("probe store boom")


class _RaisingLoadKernel:
    """Kernel double whose event-store load raises, to drive the per-record branch."""

    def __init__(self) -> None:
        self.load_attempted = asyncio.Event()
        self.event_store = self
        self.schema_posture = "matched"
        self.id_generator = _FixedIdGenerator()

    async def load(self, *, stream_type: str, stream_id: UUID) -> object:
        self.load_attempted.set()
        raise RuntimeError("load boom")


class _CancelOnLoadKernel:
    """Kernel double whose load raises CancelledError, modelling shutdown mid-record."""

    def __init__(self) -> None:
        self.event_store = self
        self.schema_posture = "matched"
        self.id_generator = _FixedIdGenerator()

    async def load(self, *, stream_type: str, stream_id: UUID) -> object:
        raise asyncio.CancelledError
