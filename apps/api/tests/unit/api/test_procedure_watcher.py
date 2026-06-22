"""Tests for the ProcedureWatcher runtime (cora.api._procedure_watcher).

Covers the pure staleness rule (is_stalled) on both sides of the inclusive
boundary, plus a fakes-driven tick that exercises the drain -> flag Decision
loop for both watched statuses, the Running activity-recency fold (the
anti-false-flag guard), the Held no-fold path, the defensive status guard, the
Actor.active revocation gate, idempotency, and the disabled no-op.
"""

# white-box test of the runtime internals (private functions / constants)
# pyright: reportPrivateUsage=false

import asyncio
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest

from cora.agent.seed_procedure_watcher import (
    PROCEDURE_WATCHER_AGENT_ID,
    seed_procedure_watcher_agent,
)
from cora.api._procedure_watcher import (
    _derive_decision_id,
    is_stalled,
    procedure_watcher_lifespan,
)
from cora.decision.aggregates.decision import load_decision
from cora.infrastructure.adapters.in_memory_event_store import InMemoryEventStore
from cora.infrastructure.config import Settings
from cora.infrastructure.deps import make_inmemory_kernel
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.ports import AllowAllAuthorize, FakeClock, UUIDv7Generator
from cora.infrastructure.routing import NIL_SENTINEL_ID
from cora.operation.features.list_procedures import (
    ListProcedures,
    ProcedureListPage,
    ProcedureSummaryItem,
)
from cora.operation.ports import InMemoryProcedureActivityLookup
from cora.shared.identity import ActorId

_NOW = datetime(2026, 6, 22, 12, 0, 0, tzinfo=UTC)
_STALE_AFTER = 3600.0  # 1 hour
_OLD = _NOW - timedelta(hours=2)  # clearly stale at a 1-hour window
_RECENT = _NOW - timedelta(minutes=1)  # fresh
_STILL_STALE = _NOW - timedelta(minutes=90)  # newer than _OLD but still > window
_BOUNDARY = _NOW - timedelta(seconds=int(_STALE_AFTER))


# ---------- pure rule: is_stalled ----------


@pytest.mark.unit
def test_is_stalled_when_status_old() -> None:
    assert is_stalled(_OLD, _NOW, _STALE_AFTER) is True


@pytest.mark.unit
def test_is_not_stalled_when_status_recent() -> None:
    assert is_stalled(_RECENT, _NOW, _STALE_AFTER) is False


@pytest.mark.unit
def test_stalled_is_inclusive_at_boundary() -> None:
    """Elapsed == window FLAGS (inclusive >=); pins the `>`-vs-`>=` mutant."""
    assert is_stalled(_BOUNDARY, _NOW, _STALE_AFTER) is True


@pytest.mark.unit
def test_not_stalled_just_under_boundary() -> None:
    just_under = _NOW - timedelta(seconds=int(_STALE_AFTER) - 1)
    assert is_stalled(just_under, _NOW, _STALE_AFTER) is False


# ---------- tick: full loop with fakes ----------


def _kernel(*, enabled: bool = False, stale_after: float = _STALE_AFTER) -> Kernel:
    settings = Settings(  # type: ignore[call-arg]
        procedure_watcher_enabled=enabled,
        procedure_watcher_stale_after_seconds=stale_after,
    )
    return make_inmemory_kernel(
        settings=settings,
        clock=FakeClock(_NOW),
        id_generator=UUIDv7Generator(),
        authz=AllowAllAuthorize(),
    )


def _item(
    procedure_id: UUID,
    *,
    status: str = "Running",
    last_status_changed_at: datetime | None,
) -> ProcedureSummaryItem:
    return ProcedureSummaryItem(
        procedure_id=procedure_id,
        name="scan-01",
        kind="tomography",
        target_asset_ids=[uuid4()],
        parent_run_id=uuid4(),
        status=status,
        activity_logbook_id=uuid4(),
        registered_at=_OLD,
        last_status_changed_at=last_status_changed_at,
        last_status_reason=None,
        interrupted_at=None,
        iteration_count=0,
    )


def _make_list_procedures(items: list[ProcedureSummaryItem], *, honor_filter: bool = True):
    async def list_procedures(
        query: ListProcedures,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> ProcedureListPage:
        if honor_filter and query.status is not None:
            matching = [i for i in items if i.status == query.status]
        else:
            matching = list(items)
        return ProcedureListPage(items=matching, next_cursor=None)

    return list_procedures


@pytest.mark.unit
async def test_tick_flags_stale_running_with_no_activity() -> None:
    from cora.api._procedure_watcher import _watch_tick

    kernel = _kernel()
    await seed_procedure_watcher_agent(kernel)
    pid = uuid4()
    list_procedures = _make_list_procedures([_item(pid, last_status_changed_at=_OLD)])

    await _watch_tick(
        deps=kernel,
        list_procedures=list_procedures,
        activity_lookup=InMemoryProcedureActivityLookup(),
    )

    decision = await load_decision(kernel.event_store, _derive_decision_id(pid, _OLD))
    assert decision is not None
    assert decision.context.value == "ProcedureProgress"
    assert decision.choice.value == "Stall"
    assert decision.decided_by == ActorId(PROCEDURE_WATCHER_AGENT_ID)


@pytest.mark.unit
async def test_tick_flags_stale_held_without_folding_activity() -> None:
    """A Held conduct accepts no activity, so it is clocked on its status
    timestamp directly; a (defensively seeded) recent activity is ignored."""
    from cora.api._procedure_watcher import _watch_tick

    kernel = _kernel()
    await seed_procedure_watcher_agent(kernel)
    pid = uuid4()
    list_procedures = _make_list_procedures(
        [_item(pid, status="Held", last_status_changed_at=_OLD)]
    )
    lookup = InMemoryProcedureActivityLookup()
    lookup.register(procedure_id=pid, recorded_at=_RECENT)  # must NOT rescue a Held

    await _watch_tick(deps=kernel, list_procedures=list_procedures, activity_lookup=lookup)

    assert await load_decision(kernel.event_store, _derive_decision_id(pid, _OLD)) is not None


@pytest.mark.unit
async def test_tick_does_not_flag_running_with_recent_activity() -> None:
    """The anti-false-flag fold: a Running procedure that looks stale by its
    status timestamp but is actively logging activity is NOT flagged."""
    from cora.api._procedure_watcher import _watch_tick

    kernel = _kernel()
    await seed_procedure_watcher_agent(kernel)
    pid = uuid4()
    list_procedures = _make_list_procedures([_item(pid, last_status_changed_at=_OLD)])
    lookup = InMemoryProcedureActivityLookup()
    lookup.register(procedure_id=pid, recorded_at=_RECENT)

    await _watch_tick(deps=kernel, list_procedures=list_procedures, activity_lookup=lookup)

    assert await load_decision(kernel.event_store, _derive_decision_id(pid, _OLD)) is None
    assert await load_decision(kernel.event_store, _derive_decision_id(pid, _RECENT)) is None


@pytest.mark.unit
async def test_tick_flags_running_when_latest_activity_also_stale() -> None:
    """The fold folds in activity recency but still flags when even the newest
    activity is past the window; the episode keys on that folded timestamp."""
    from cora.api._procedure_watcher import _watch_tick

    kernel = _kernel()
    await seed_procedure_watcher_agent(kernel)
    pid = uuid4()
    list_procedures = _make_list_procedures([_item(pid, last_status_changed_at=_OLD)])
    lookup = InMemoryProcedureActivityLookup()
    lookup.register(procedure_id=pid, recorded_at=_STILL_STALE)  # newer than _OLD, still stale

    await _watch_tick(deps=kernel, list_procedures=list_procedures, activity_lookup=lookup)

    # Episode keys on the folded last_progress_at (the latest activity), not _OLD.
    assert (
        await load_decision(kernel.event_store, _derive_decision_id(pid, _STILL_STALE)) is not None
    )
    assert await load_decision(kernel.event_store, _derive_decision_id(pid, _OLD)) is None


@pytest.mark.unit
async def test_tick_skips_fresh_running() -> None:
    from cora.api._procedure_watcher import _watch_tick

    kernel = _kernel()
    await seed_procedure_watcher_agent(kernel)
    pid = uuid4()
    list_procedures = _make_list_procedures([_item(pid, last_status_changed_at=_RECENT)])

    await _watch_tick(
        deps=kernel,
        list_procedures=list_procedures,
        activity_lookup=InMemoryProcedureActivityLookup(),
    )

    assert await load_decision(kernel.event_store, _derive_decision_id(pid, _RECENT)) is None


async def _procedure_progress_decision_count(kernel: Kernel) -> int:
    """Count ProcedureProgress Decisions written to the event store."""
    store = kernel.event_store
    assert isinstance(store, InMemoryEventStore)
    count = 0
    for stream_type, stream_id in store._streams:
        if stream_type != "Decision":
            continue
        decision = await load_decision(store, stream_id)
        if decision is not None and decision.context.value == "ProcedureProgress":
            count += 1
    return count


@pytest.mark.unit
async def test_tick_does_not_flag_when_status_timestamp_missing() -> None:
    """cannot-tell -> defer: a row with no last_status_changed_at is skipped, so
    no ProcedureProgress Decision is written."""
    from cora.api._procedure_watcher import _watch_tick

    kernel = _kernel()
    await seed_procedure_watcher_agent(kernel)
    pid = uuid4()
    list_procedures = _make_list_procedures([_item(pid, last_status_changed_at=None)])

    await _watch_tick(
        deps=kernel,
        list_procedures=list_procedures,
        activity_lookup=InMemoryProcedureActivityLookup(),
    )

    assert await _procedure_progress_decision_count(kernel) == 0


@pytest.mark.unit
async def test_tick_skips_terminal_status_even_if_unfiltered() -> None:
    """Defensive guard: a non-watched status (Completed) is never flagged, even
    if the drain returned it. Pins the status check against a filter widening."""
    from cora.api._procedure_watcher import _watch_tick

    kernel = _kernel()
    await seed_procedure_watcher_agent(kernel)
    pid = uuid4()
    list_procedures = _make_list_procedures(
        [_item(pid, status="Completed", last_status_changed_at=_OLD)], honor_filter=False
    )

    await _watch_tick(
        deps=kernel,
        list_procedures=list_procedures,
        activity_lookup=InMemoryProcedureActivityLookup(),
    )

    assert await load_decision(kernel.event_store, _derive_decision_id(pid, _OLD)) is None


@pytest.mark.unit
async def test_record_decision_is_idempotent_on_repeated_episode() -> None:
    """Re-flagging the same stall episode is a ConcurrencyError no-op, not a crash."""
    from cora.api._procedure_watcher import _record_decision

    kernel = _kernel()
    pid = uuid4()
    await _record_decision(
        kernel, procedure_id=pid, status="Running", last_progress_at=_OLD, now=_NOW
    )
    await _record_decision(
        kernel, procedure_id=pid, status="Running", last_progress_at=_OLD, now=_NOW
    )
    assert await load_decision(kernel.event_store, _derive_decision_id(pid, _OLD)) is not None


@pytest.mark.unit
async def test_tick_drains_paginated_procedures() -> None:
    """The drain follows next_cursor across pages, so a stale procedure on a
    later page is still flagged (pins the cursor-advance against a mutant)."""
    from cora.api._procedure_watcher import _watch_tick

    kernel = _kernel()
    await seed_procedure_watcher_agent(kernel)
    page1_pid, page2_pid = uuid4(), uuid4()

    async def list_procedures(
        query: ListProcedures,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> ProcedureListPage:
        if query.status != "Running":
            return ProcedureListPage(items=[], next_cursor=None)
        if query.cursor is None:
            return ProcedureListPage(
                items=[_item(page1_pid, last_status_changed_at=_OLD)], next_cursor="page2"
            )
        return ProcedureListPage(
            items=[_item(page2_pid, last_status_changed_at=_OLD)], next_cursor=None
        )

    await _watch_tick(
        deps=kernel,
        list_procedures=list_procedures,
        activity_lookup=InMemoryProcedureActivityLookup(),
    )

    # The page-2 procedure is only reached if the cursor advance ran.
    assert await load_decision(kernel.event_store, _derive_decision_id(page2_pid, _OLD)) is not None


@pytest.mark.unit
async def test_tick_is_noop_when_watcher_actor_absent() -> None:
    """Revocation gate: with no seeded (active) ProcedureWatcher Actor, do nothing."""
    from cora.api._procedure_watcher import _watch_tick

    kernel = _kernel()  # NOT seeded
    pid = uuid4()
    list_procedures = _make_list_procedures([_item(pid, last_status_changed_at=_OLD)])

    await _watch_tick(
        deps=kernel,
        list_procedures=list_procedures,
        activity_lookup=InMemoryProcedureActivityLookup(),
    )

    assert await load_decision(kernel.event_store, _derive_decision_id(pid, _OLD)) is None


@pytest.mark.unit
async def test_tick_is_noop_when_watcher_actor_deactivated() -> None:
    """Kill switch: an operator deactivating the agent Actor stands the watcher
    down even while seeded. Pins the `not actor.active` disjunct of the gate."""
    from cora.access.features import deactivate_actor
    from cora.access.features.deactivate_actor import DeactivateActor
    from cora.api._procedure_watcher import _watch_tick

    kernel = _kernel()
    await seed_procedure_watcher_agent(kernel)
    await deactivate_actor.bind(kernel)(
        DeactivateActor(actor_id=PROCEDURE_WATCHER_AGENT_ID),
        principal_id=PROCEDURE_WATCHER_AGENT_ID,
        correlation_id=uuid4(),
    )
    pid = uuid4()
    list_procedures = _make_list_procedures([_item(pid, last_status_changed_at=_OLD)])

    await _watch_tick(
        deps=kernel,
        list_procedures=list_procedures,
        activity_lookup=InMemoryProcedureActivityLookup(),
    )

    assert await load_decision(kernel.event_store, _derive_decision_id(pid, _OLD)) is None


@pytest.mark.unit
def test_default_activity_lookup_is_in_memory_without_a_pool() -> None:
    """The production lookup selector (used when the lifespan is not handed an
    explicit activity_lookup) builds the in-memory stub when there is no pool,
    which is the path a pool-less deployment / the test kernel takes."""
    from cora.api._procedure_watcher import _default_activity_lookup

    kernel = _kernel()  # make_inmemory_kernel -> pool is None
    assert isinstance(_default_activity_lookup(kernel), InMemoryProcedureActivityLookup)


@pytest.mark.unit
async def test_lifespan_is_noop_when_disabled() -> None:
    """Default settings (procedure_watcher_enabled=False): clean no-op, no task."""
    kernel = _kernel()
    pid = uuid4()
    list_procedures = _make_list_procedures([_item(pid, last_status_changed_at=_OLD)])

    async with procedure_watcher_lifespan(kernel, list_procedures=list_procedures):
        pass

    assert await load_decision(kernel.event_store, _derive_decision_id(pid, _OLD)) is None


@pytest.mark.unit
async def test_lifespan_enabled_runs_the_loop_and_flags() -> None:
    """Enabled: the lifespan spawns the loop, which flags a stale procedure."""
    kernel = _kernel(enabled=True)
    await seed_procedure_watcher_agent(kernel)
    pid = uuid4()
    list_procedures = _make_list_procedures([_item(pid, last_status_changed_at=_OLD)])

    async with procedure_watcher_lifespan(
        kernel,
        list_procedures=list_procedures,
        activity_lookup=InMemoryProcedureActivityLookup(),
        interval_seconds=0.01,
    ):
        await asyncio.sleep(0.1)

    assert await load_decision(kernel.event_store, _derive_decision_id(pid, _OLD)) is not None


@pytest.mark.unit
async def test_loop_survives_a_failing_tick() -> None:
    """A tick that raises is logged and the loop keeps going; lifespan exits cleanly."""
    kernel = _kernel(enabled=True)
    await seed_procedure_watcher_agent(kernel)

    async def failing_list_procedures(
        query: ListProcedures,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> ProcedureListPage:
        raise RuntimeError("list_procedures boom")

    async with procedure_watcher_lifespan(
        kernel,
        list_procedures=failing_list_procedures,
        activity_lookup=InMemoryProcedureActivityLookup(),
        interval_seconds=0.01,
    ):
        await asyncio.sleep(0.05)


@pytest.mark.unit
def test_procedure_watcher_tick_seconds_rejects_sub_floor() -> None:
    with pytest.raises(ValueError, match="procedure_watcher_tick_seconds"):
        Settings(procedure_watcher_tick_seconds=0.05)  # type: ignore[call-arg]


@pytest.mark.unit
def test_procedure_watcher_stale_after_rejects_non_positive() -> None:
    with pytest.raises(ValueError, match="procedure_watcher_stale_after_seconds"):
        Settings(procedure_watcher_stale_after_seconds=0.0)  # type: ignore[call-arg]


@pytest.mark.unit
def test_procedure_watcher_settings_accept_valid() -> None:
    settings = Settings(  # type: ignore[call-arg]
        procedure_watcher_tick_seconds=120.0,
        procedure_watcher_stale_after_seconds=7200.0,
    )
    assert settings.procedure_watcher_tick_seconds == 120.0
    assert settings.procedure_watcher_stale_after_seconds == 7200.0
