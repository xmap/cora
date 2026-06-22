"""Application-handler unit tests for the 13 Visit slices.

Consolidated coverage file: covers `register_visit`, `record_visit_arrival`,
`start_visit`, `hold_visit`, `resume_visit`, `complete_visit`,
`cancel_visit`, `abort_visit`, `void_visit`, `check_in_visit`,
`check_out_visit`, `take_control_of_surface`,
`release_control_of_surface` per the arch-fitness substring-match
rule. Pure-decider behavior is exercised in the per-slice files under
`tests/unit/trust/visit/`; here we pin the handler-level concerns:
idempotency wrapping, authz invocation, event-store append, envelope
shape, factory wiring.
"""

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest

from cora.infrastructure.adapters.in_memory_event_store import InMemoryEventStore
from cora.infrastructure.event_envelope import to_new_event
from cora.trust import UnauthorizedError
from cora.trust.aggregates.visit import (
    PresenceMode,
    Visit,
    VisitActorNotCheckedInError,
    VisitCheckedIn,
    VisitNotFoundError,
    VisitRegistered,
    VisitStatus,
    VisitType,
    event_type_name,
    fold,
    from_stored,
    to_payload,
)
from cora.trust.features import (
    abort_visit,
    cancel_visit,
    check_in_visit,
    check_out_visit,
    complete_visit,
    hold_visit,
    record_visit_arrival,
    register_visit,
    release_control_of_surface,
    resume_visit,
    start_visit,
    take_control_of_surface,
    void_visit,
)
from tests.unit._helpers import build_deps

_NOW = datetime(2026, 5, 27, 12, 0, 0, tzinfo=UTC)
_VISIT_ID = UUID("01900000-0000-7000-8000-00000000e001")
_POLICY_ID = UUID("01900000-0000-7000-8000-00000000e002")
_SURFACE_ID = UUID("01900000-0000-7000-8000-00000000e003")
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")
_GENESIS_EVENT_ID = UUID("01900000-0000-7000-8000-00000000e101")
_TRANSITION_EVENT_ID = UUID("01900000-0000-7000-8000-00000000e102")
_PLANNED_START = _NOW
_PLANNED_END = _NOW + timedelta(hours=8)


def _register_command() -> register_visit.RegisterVisit:
    return register_visit.RegisterVisit(
        visit_id=_VISIT_ID,
        policy_id=_POLICY_ID,
        surface_id=_SURFACE_ID,
        type=VisitType.USER,
        planned_start_at=_PLANNED_START,
        planned_end_at=_PLANNED_END,
    )


async def _seed_to(store: InMemoryEventStore, status: VisitStatus) -> None:
    """Append events to drive a Visit to the requested status."""
    from cora.trust.aggregates.visit import (
        VisitArrived,
        VisitEvent,
        VisitHeld,
        VisitStarted,
    )

    events_to_append: list[VisitEvent] = [
        VisitRegistered(
            visit_id=_VISIT_ID,
            policy_id=_POLICY_ID,
            surface_id=_SURFACE_ID,
            type=VisitType.USER.value,
            planned_start_at=_PLANNED_START,
            planned_end_at=_PLANNED_END,
            occurred_at=_NOW,
        )
    ]
    if status != VisitStatus.PLANNED:
        events_to_append.append(VisitArrived(visit_id=_VISIT_ID, occurred_at=_NOW))
    if status not in {VisitStatus.PLANNED, VisitStatus.ARRIVED}:
        events_to_append.append(VisitStarted(visit_id=_VISIT_ID, occurred_at=_NOW))
    if status == VisitStatus.ON_HOLD:
        events_to_append.append(VisitHeld(visit_id=_VISIT_ID, reason="beam dump", occurred_at=_NOW))

    version = 0
    for offset, ev in enumerate(events_to_append):
        current_version = version + offset
        await store.append(
            stream_type="Visit",
            stream_id=_VISIT_ID,
            expected_version=current_version,
            events=[
                to_new_event(
                    event_type=event_type_name(ev),
                    payload=to_payload(ev),
                    occurred_at=ev.occurred_at,
                    event_id=UUID(int=current_version + 1),
                    command_name="SeedCommand",
                    correlation_id=_CORRELATION_ID,
                    causation_id=None,
                    principal_id=_PRINCIPAL_ID,
                )
            ],
        )


# ---------------------------------------------------------------------------
# register_visit (genesis): the longhand handler path.
# ---------------------------------------------------------------------------


@pytest.mark.unit
async def test_register_visit_handler_returns_caller_supplied_id() -> None:
    """Genesis: caller supplies visit_id; handler returns it unchanged."""
    deps = build_deps(ids=[_GENESIS_EVENT_ID], now=_NOW)
    handler = register_visit.bind(deps)

    returned = await handler(
        _register_command(),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert returned == _VISIT_ID


@pytest.mark.unit
async def test_register_visit_handler_appends_visit_registered_to_store() -> None:
    store = InMemoryEventStore()
    deps = build_deps(ids=[_GENESIS_EVENT_ID], now=_NOW, event_store=store)
    handler = register_visit.bind(deps)

    await handler(
        _register_command(),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    events, version = await store.load("Visit", _VISIT_ID)
    assert version == 1
    assert len(events) == 1
    stored = events[0]
    assert stored.event_type == "VisitRegistered"
    assert stored.correlation_id == _CORRELATION_ID
    assert stored.principal_id == _PRINCIPAL_ID
    assert stored.metadata == {"command": "RegisterVisit"}
    folded = fold([from_stored(s) for s in events])
    assert folded is not None
    assert folded.status == VisitStatus.PLANNED
    assert folded.type == VisitType.USER


@pytest.mark.unit
async def test_register_visit_handler_raises_unauthorized_on_deny() -> None:
    deps = build_deps(ids=[_GENESIS_EVENT_ID], now=_NOW, deny=True)
    handler = register_visit.bind(deps)

    with pytest.raises(UnauthorizedError):
        await handler(
            _register_command(),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


# ---------------------------------------------------------------------------
# Lifecycle slices (factory-based): parametrized happy + not-found tests.
# ---------------------------------------------------------------------------


_LIFECYCLE_BIND_HAPPY: list[tuple[str, object, VisitStatus, VisitStatus]] = [
    (
        "record_visit_arrival",
        record_visit_arrival.RecordVisitArrival(visit_id=_VISIT_ID),
        VisitStatus.PLANNED,
        VisitStatus.ARRIVED,
    ),
    (
        "start_visit",
        start_visit.StartVisit(visit_id=_VISIT_ID),
        VisitStatus.ARRIVED,
        VisitStatus.IN_PROGRESS,
    ),
    (
        "hold_visit",
        hold_visit.HoldVisit(visit_id=_VISIT_ID, reason="beam dump"),
        VisitStatus.IN_PROGRESS,
        VisitStatus.ON_HOLD,
    ),
    (
        "resume_visit",
        resume_visit.ResumeVisit(visit_id=_VISIT_ID),
        VisitStatus.ON_HOLD,
        VisitStatus.IN_PROGRESS,
    ),
    (
        "complete_visit",
        complete_visit.CompleteVisit(visit_id=_VISIT_ID),
        VisitStatus.IN_PROGRESS,
        VisitStatus.COMPLETED,
    ),
    (
        "cancel_visit",
        cancel_visit.CancelVisit(visit_id=_VISIT_ID, reason="no-show"),
        VisitStatus.PLANNED,
        VisitStatus.CANCELLED,
    ),
    (
        "abort_visit",
        abort_visit.AbortVisit(visit_id=_VISIT_ID, reason="equipment fault"),
        VisitStatus.IN_PROGRESS,
        VisitStatus.ABORTED,
    ),
    (
        "void_visit",
        void_visit.VoidVisit(visit_id=_VISIT_ID, reason="duplicate"),
        VisitStatus.PLANNED,
        VisitStatus.VOIDED,
    ),
]


_BIND_FN = {
    "record_visit_arrival": record_visit_arrival.bind,
    "start_visit": start_visit.bind,
    "hold_visit": hold_visit.bind,
    "resume_visit": resume_visit.bind,
    "complete_visit": complete_visit.bind,
    "cancel_visit": cancel_visit.bind,
    "abort_visit": abort_visit.bind,
    "void_visit": void_visit.bind,
}


@pytest.mark.parametrize(
    ("slice_name", "command", "from_status", "expected_status"),
    _LIFECYCLE_BIND_HAPPY,
    ids=[t[0] for t in _LIFECYCLE_BIND_HAPPY],
)
@pytest.mark.unit
async def test_lifecycle_handler_advances_visit_to_expected_status(
    slice_name: str,
    command: object,
    from_status: VisitStatus,
    expected_status: VisitStatus,
) -> None:
    """All 8 lifecycle slices: seed to from_status, invoke handler, assert state."""
    store = InMemoryEventStore()
    await _seed_to(store, from_status)
    deps = build_deps(ids=[_TRANSITION_EVENT_ID], now=_NOW, event_store=store)
    handler = _BIND_FN[slice_name](deps)

    await handler(
        command,  # type: ignore[arg-type]
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    events, _ = await store.load("Visit", _VISIT_ID)
    folded: Visit | None = fold([from_stored(s) for s in events])
    assert folded is not None
    assert folded.status == expected_status


@pytest.mark.parametrize(
    ("slice_name", "command"),
    [(name, cmd) for (name, cmd, _from, _to) in _LIFECYCLE_BIND_HAPPY],
    ids=[t[0] for t in _LIFECYCLE_BIND_HAPPY],
)
@pytest.mark.unit
async def test_lifecycle_handler_raises_not_found_when_visit_absent(
    slice_name: str, command: object
) -> None:
    """All 8 lifecycle slices: empty store -> VisitNotFoundError."""
    store = InMemoryEventStore()
    deps = build_deps(ids=[_TRANSITION_EVENT_ID], now=_NOW, event_store=store)
    handler = _BIND_FN[slice_name](deps)

    with pytest.raises(VisitNotFoundError):
        await handler(
            command,  # type: ignore[arg-type]
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_hold_visit_handler_records_reason_via_factory_wiring() -> None:
    """Spot-check that the factory propagates the reason payload end-to-end."""
    store = InMemoryEventStore()
    await _seed_to(store, VisitStatus.IN_PROGRESS)
    deps = build_deps(ids=[_TRANSITION_EVENT_ID], now=_NOW, event_store=store)
    handler = hold_visit.bind(deps)

    await handler(
        hold_visit.HoldVisit(visit_id=_VISIT_ID, reason="cryostream alarm"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    events, _ = await store.load("Visit", _VISIT_ID)
    folded = fold([from_stored(s) for s in events])
    assert folded is not None
    assert folded.status == VisitStatus.ON_HOLD
    assert folded.last_status_reason == "cryostream alarm"


# ---------------------------------------------------------------------------
# Presence handlers: check_in_visit + check_out_visit.
# ---------------------------------------------------------------------------


@pytest.mark.unit
async def test_check_in_visit_handler_appends_visit_checked_in() -> None:
    store = InMemoryEventStore()
    await _seed_to(store, VisitStatus.ARRIVED)
    deps = build_deps(ids=[_TRANSITION_EVENT_ID], now=_NOW, event_store=store)
    handler = check_in_visit.bind(deps)
    actor_id = uuid4()
    await handler(
        check_in_visit.CheckInVisit(
            visit_id=_VISIT_ID, actor_id=actor_id, mode=PresenceMode.PHYSICAL
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    events, _ = await store.load("Visit", _VISIT_ID)
    folded = fold([from_stored(s) for s in events])
    assert folded is not None
    assert len(folded.presence_entries) == 1
    [entry] = folded.presence_entries
    assert entry.actor_id == actor_id
    assert entry.check_out_at is None


@pytest.mark.unit
async def test_check_in_visit_handler_raises_not_found_when_visit_absent() -> None:
    store = InMemoryEventStore()
    deps = build_deps(ids=[_TRANSITION_EVENT_ID], now=_NOW, event_store=store)
    handler = check_in_visit.bind(deps)
    with pytest.raises(VisitNotFoundError):
        await handler(
            check_in_visit.CheckInVisit(
                visit_id=_VISIT_ID, actor_id=uuid4(), mode=PresenceMode.PHYSICAL
            ),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_check_out_visit_handler_closes_open_entry_via_frozen_replace() -> None:
    """Seed a check-in then close: frozen-replace populates check_out_at."""
    store = InMemoryEventStore()
    await _seed_to(store, VisitStatus.ARRIVED)
    actor_id = uuid4()
    _, current_version = await store.load("Visit", _VISIT_ID)
    seed_event = VisitCheckedIn(
        visit_id=_VISIT_ID,
        actor_id=actor_id,
        mode=PresenceMode.PHYSICAL.value,
        occurred_at=_NOW,
    )
    await store.append(
        stream_type="Visit",
        stream_id=_VISIT_ID,
        expected_version=current_version,
        events=[
            to_new_event(
                event_type=event_type_name(seed_event),
                payload=to_payload(seed_event),
                occurred_at=seed_event.occurred_at,
                event_id=uuid4(),
                command_name="SeedCheckIn",
                correlation_id=_CORRELATION_ID,
                causation_id=None,
                principal_id=_PRINCIPAL_ID,
            )
        ],
    )
    deps = build_deps(ids=[_TRANSITION_EVENT_ID], now=_NOW, event_store=store)
    handler = check_out_visit.bind(deps)
    await handler(
        check_out_visit.CheckOutVisit(visit_id=_VISIT_ID, actor_id=actor_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    events, _ = await store.load("Visit", _VISIT_ID)
    folded = fold([from_stored(s) for s in events])
    assert folded is not None
    [entry] = folded.presence_entries
    assert entry.check_out_at is not None


@pytest.mark.unit
async def test_check_out_visit_handler_raises_when_actor_not_checked_in() -> None:
    store = InMemoryEventStore()
    await _seed_to(store, VisitStatus.IN_PROGRESS)
    deps = build_deps(ids=[_TRANSITION_EVENT_ID], now=_NOW, event_store=store)
    handler = check_out_visit.bind(deps)
    with pytest.raises(VisitActorNotCheckedInError):
        await handler(
            check_out_visit.CheckOutVisit(visit_id=_VISIT_ID, actor_id=uuid4()),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


# Pool-less unit kernel returns active_holder=None (Surface presumed free).
# That covers the free-surface path. Tests further down inject a stub pool
# to exercise the preload-then-reject + preload-then-allow paths without
# requiring a live Postgres.


@pytest.mark.unit
async def test_take_control_of_surface_handler_appends_event_on_free_surface() -> None:
    store = InMemoryEventStore()
    await _seed_to(store, VisitStatus.IN_PROGRESS)
    deps = build_deps(ids=[_TRANSITION_EVENT_ID], now=_NOW, event_store=store)
    handler = take_control_of_surface.bind(deps)
    await handler(
        take_control_of_surface.TakeControlOfSurface(visit_id=_VISIT_ID, surface_id=_SURFACE_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    events, _ = await store.load("Visit", _VISIT_ID)
    assert events[-1].event_type == "VisitSurfaceControlTaken"
    assert events[-1].payload["surface_id"] == str(_SURFACE_ID)
    assert events[-1].payload["visit_id"] == str(_VISIT_ID)


@pytest.mark.unit
async def test_take_control_of_surface_handler_raises_not_found_when_visit_absent() -> None:
    store = InMemoryEventStore()
    deps = build_deps(ids=[_TRANSITION_EVENT_ID], now=_NOW, event_store=store)
    handler = take_control_of_surface.bind(deps)
    with pytest.raises(VisitNotFoundError):
        await handler(
            take_control_of_surface.TakeControlOfSurface(
                visit_id=_VISIT_ID, surface_id=_SURFACE_ID
            ),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_take_control_of_surface_handler_denies_when_unauthorized() -> None:
    store = InMemoryEventStore()
    await _seed_to(store, VisitStatus.IN_PROGRESS)
    deps = build_deps(ids=[_TRANSITION_EVENT_ID], now=_NOW, event_store=store, deny=True)
    handler = take_control_of_surface.bind(deps)
    with pytest.raises(UnauthorizedError):
        await handler(
            take_control_of_surface.TakeControlOfSurface(
                visit_id=_VISIT_ID, surface_id=_SURFACE_ID
            ),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_release_control_of_surface_handler_raises_when_pool_says_free() -> None:
    """Pool-less unit kernel returns active_holder=None; release on a 'free'
    Surface must raise because the requesting Visit cannot be the holder.
    """
    from cora.trust.aggregates.visit import VisitCannotReleaseControlError

    store = InMemoryEventStore()
    await _seed_to(store, VisitStatus.IN_PROGRESS)
    deps = build_deps(ids=[_TRANSITION_EVENT_ID], now=_NOW, event_store=store)
    handler = release_control_of_surface.bind(deps)
    with pytest.raises(VisitCannotReleaseControlError):
        await handler(
            release_control_of_surface.ReleaseControlOfSurface(
                visit_id=_VISIT_ID, surface_id=_SURFACE_ID
            ),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_release_control_of_surface_handler_raises_not_found_when_visit_absent() -> None:
    store = InMemoryEventStore()
    deps = build_deps(ids=[_TRANSITION_EVENT_ID], now=_NOW, event_store=store)
    handler = release_control_of_surface.bind(deps)
    with pytest.raises(VisitNotFoundError):
        await handler(
            release_control_of_surface.ReleaseControlOfSurface(
                visit_id=_VISIT_ID, surface_id=_SURFACE_ID
            ),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


class _StubPool:
    """asyncpg.Pool stand-in returning one fixed row from `fetchrow`."""

    def __init__(self, row: dict[str, object] | None) -> None:
        self._row = row

    async def fetchrow(self, _sql: str, *_args: object) -> dict[str, object] | None:
        return self._row


@pytest.mark.unit
async def test_take_control_handler_rejects_when_pool_reports_unrelated_holder() -> None:
    from dataclasses import replace

    from cora.trust.aggregates.visit import VisitCannotTakeControlError

    store = InMemoryEventStore()
    await _seed_to(store, VisitStatus.IN_PROGRESS)
    pool = _StubPool({"visit_id": uuid4(), "since_at": _NOW})
    deps = replace(
        build_deps(ids=[_TRANSITION_EVENT_ID], now=_NOW, event_store=store),
        pool=pool,  # type: ignore[arg-type]
    )
    handler = take_control_of_surface.bind(deps)
    with pytest.raises(VisitCannotTakeControlError) as exc:
        await handler(
            take_control_of_surface.TakeControlOfSurface(
                visit_id=_VISIT_ID, surface_id=_SURFACE_ID
            ),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    assert exc.value.reason == "not_descendant"
    events, _ = await store.load("Visit", _VISIT_ID)
    assert not any(e.event_type == "VisitSurfaceControlTaken" for e in events)


@pytest.mark.unit
async def test_take_control_handler_allows_when_pool_reports_partof_parent_holder() -> None:
    from dataclasses import replace

    from cora.trust.aggregates.visit import VisitArrived, VisitEvent, VisitStarted

    parent_visit_id = UUID("01900000-0000-7000-8000-00000000e201")
    child_visit_id = UUID("01900000-0000-7000-8000-00000000e202")
    child_genesis_id = UUID("01900000-0000-7000-8000-00000000e203")
    child_arrived_id = UUID("01900000-0000-7000-8000-00000000e204")
    child_started_id = UUID("01900000-0000-7000-8000-00000000e205")
    child_took_id = UUID("01900000-0000-7000-8000-00000000e206")

    store = InMemoryEventStore()
    child_events: list[VisitEvent] = [
        VisitRegistered(
            visit_id=child_visit_id,
            policy_id=_POLICY_ID,
            surface_id=_SURFACE_ID,
            type=VisitType.COMMISSIONING.value,
            planned_start_at=_PLANNED_START,
            planned_end_at=_PLANNED_END,
            parent_id=parent_visit_id,
            occurred_at=_NOW,
        ),
        VisitArrived(visit_id=child_visit_id, occurred_at=_NOW),
        VisitStarted(visit_id=child_visit_id, occurred_at=_NOW),
    ]
    for offset, ev in enumerate(child_events):
        await store.append(
            stream_type="Visit",
            stream_id=child_visit_id,
            expected_version=offset,
            events=[
                to_new_event(
                    event_type=event_type_name(ev),
                    payload=to_payload(ev),
                    occurred_at=ev.occurred_at,
                    event_id=[child_genesis_id, child_arrived_id, child_started_id][offset],
                    command_name="SeedCommand",
                    correlation_id=_CORRELATION_ID,
                    causation_id=None,
                    principal_id=_PRINCIPAL_ID,
                )
            ],
        )
    pool = _StubPool({"visit_id": parent_visit_id, "since_at": _NOW})
    deps = replace(
        build_deps(ids=[child_took_id], now=_NOW, event_store=store),
        pool=pool,  # type: ignore[arg-type]
    )
    handler = take_control_of_surface.bind(deps)
    await handler(
        take_control_of_surface.TakeControlOfSurface(
            visit_id=child_visit_id, surface_id=_SURFACE_ID
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    events, _ = await store.load("Visit", child_visit_id)
    assert events[-1].event_type == "VisitSurfaceControlTaken"
    assert events[-1].payload["visit_id"] == str(child_visit_id)


@pytest.mark.unit
async def test_release_control_handler_appends_event_when_pool_reports_self_as_holder() -> None:
    """Pool returns this Visit as the current holder; release succeeds."""
    from dataclasses import replace

    store = InMemoryEventStore()
    await _seed_to(store, VisitStatus.IN_PROGRESS)
    pool = _StubPool({"visit_id": _VISIT_ID, "since_at": _NOW})
    deps = replace(
        build_deps(ids=[_TRANSITION_EVENT_ID], now=_NOW, event_store=store),
        pool=pool,  # type: ignore[arg-type]
    )
    handler = release_control_of_surface.bind(deps)
    await handler(
        release_control_of_surface.ReleaseControlOfSurface(
            visit_id=_VISIT_ID, surface_id=_SURFACE_ID
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    events, _ = await store.load("Visit", _VISIT_ID)
    assert events[-1].event_type == "VisitSurfaceControlReleased"
    assert events[-1].payload["visit_id"] == str(_VISIT_ID)
    assert events[-1].payload["surface_id"] == str(_SURFACE_ID)


@pytest.mark.unit
async def test_release_control_handler_rejects_when_pool_reports_other_holder() -> None:
    """Pool returns a DIFFERENT Visit as holder; release must reject."""
    from dataclasses import replace

    from cora.trust.aggregates.visit import VisitCannotReleaseControlError

    store = InMemoryEventStore()
    await _seed_to(store, VisitStatus.IN_PROGRESS)
    pool = _StubPool({"visit_id": uuid4(), "since_at": _NOW})
    deps = replace(
        build_deps(ids=[_TRANSITION_EVENT_ID], now=_NOW, event_store=store),
        pool=pool,  # type: ignore[arg-type]
    )
    handler = release_control_of_surface.bind(deps)
    with pytest.raises(VisitCannotReleaseControlError):
        await handler(
            release_control_of_surface.ReleaseControlOfSurface(
                visit_id=_VISIT_ID, surface_id=_SURFACE_ID
            ),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    events, _ = await store.load("Visit", _VISIT_ID)
    assert not any(e.event_type == "VisitSurfaceControlReleased" for e in events)
