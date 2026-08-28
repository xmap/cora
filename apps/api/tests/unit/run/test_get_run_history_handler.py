"""Unit tests for the `get_run_history` query handler.

The highest-value test here (`test_handler_two_transitions_in_one_tick_both_appear`)
pins the whole slice's reason for existing: two state changes to the same
run inside one 2-second live-push tick must both survive with their own
exact timestamps, which a current-state poll (`get_run` / `list_runs`)
cannot promise.
"""

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest

from cora.infrastructure.adapters.in_memory_event_store import InMemoryEventStore
from cora.infrastructure.event_envelope import to_new_event
from cora.run import RunHandlers, UnauthorizedError, wire_run
from cora.run.adapters.in_memory_run_observation_trail import InMemoryRunObservationTrail
from cora.run.aggregates.run.entries import InMemoryObservationStore, Observation
from cora.run.aggregates.run.events import RunHeld, RunStarted, event_type_name, to_payload
from cora.run.features import get_run_history
from cora.run.features.get_run_history import GetRunHistory
from tests.unit._helpers import RecordingAuthorize, build_deps

_NOW = datetime(2026, 5, 11, 12, 0, 0, tzinfo=UTC)
_OBSERVATION_LIMIT = 2000
"""Mirrors `get_run_history.handler._OBSERVATION_LIMIT`. Kept as a local
constant rather than importing the private module attribute."""
_RUN_ID = UUID("01900000-0000-7000-8000-00000000fe01")
_PLAN_ID = UUID("01900000-0000-7000-8000-00000000fe02")
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")


async def _seed_started(
    store: InMemoryEventStore, run_id: UUID, *, plan_id: UUID, occurred_at: datetime
) -> None:
    event = RunStarted(
        run_id=run_id,
        name="32-ID FlyScan",
        plan_id=plan_id,
        subject_id=None,
        occurred_at=occurred_at,
    )
    new_event = to_new_event(
        event_type=event_type_name(event),
        payload=to_payload(event),
        occurred_at=occurred_at,
        event_id=uuid4(),
        command_name="StartRun",
        correlation_id=_CORRELATION_ID,
        principal_id=uuid4(),
    )
    await store.append(stream_type="Run", stream_id=run_id, expected_version=0, events=[new_event])


async def _seed_held(
    store: InMemoryEventStore, run_id: UUID, *, expected_version: int, occurred_at: datetime
) -> None:
    event = RunHeld(run_id=run_id, occurred_at=occurred_at)
    new_event = to_new_event(
        event_type=event_type_name(event),
        payload=to_payload(event),
        occurred_at=occurred_at,
        event_id=uuid4(),
        command_name="HoldRun",
        correlation_id=_CORRELATION_ID,
        principal_id=uuid4(),
    )
    await store.append(
        stream_type="Run",
        stream_id=run_id,
        expected_version=expected_version,
        events=[new_event],
    )


def _observation(
    *, run_id: UUID, channel_name: str, value: float, occurred_at: datetime
) -> Observation:
    return Observation(
        event_id=uuid4(),
        run_id=run_id,
        logbook_id=uuid4(),
        actor_id=uuid4(),
        command_name="AppendObservations",
        channel_name=channel_name,
        value=value,
        categorical_value=None,
        units=None,
        sampling_procedure="monitor",
        sampled_at=occurred_at,
        occurred_at=occurred_at,
        correlation_id=_CORRELATION_ID,
        causation_id=None,
        is_simulated=False,
    )


@pytest.mark.unit
async def test_handler_returns_events_and_observations_for_known_run() -> None:
    store = InMemoryEventStore()
    await _seed_started(store, _RUN_ID, plan_id=_PLAN_ID, occurred_at=_NOW)
    obs_store = InMemoryObservationStore()
    await obs_store.append(
        [_observation(run_id=_RUN_ID, channel_name="images", value=1.0, occurred_at=_NOW)]
    )
    deps = build_deps(ids=[_RUN_ID], now=_NOW, event_store=store)
    handler = get_run_history.bind(deps, observation_trail=InMemoryRunObservationTrail(obs_store))

    view = await handler(
        GetRunHistory(run_id=_RUN_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    assert view is not None
    assert view.run_id == _RUN_ID
    assert view.name == "32-ID FlyScan"
    assert view.status == "Running"
    assert len(view.events) == 1
    assert view.events[0].event_type == "RunStarted"
    assert len(view.observations) == 1
    assert view.observations[0].channel_name == "images"
    assert view.observations_truncated is False


@pytest.mark.unit
async def test_handler_two_transitions_in_one_tick_both_appear() -> None:
    """RunStarted and RunHeld, 400ms apart -- both must appear with their
    own distinct timestamps. This is the assertion that fails if this
    slice is ever "optimized" back into a repeated current-state poll."""
    store = InMemoryEventStore()
    started_at = _NOW
    held_at = _NOW + timedelta(milliseconds=400)
    await _seed_started(store, _RUN_ID, plan_id=_PLAN_ID, occurred_at=started_at)
    await _seed_held(store, _RUN_ID, expected_version=1, occurred_at=held_at)
    deps = build_deps(ids=[_RUN_ID], now=_NOW, event_store=store)
    handler = get_run_history.bind(
        deps, observation_trail=InMemoryRunObservationTrail(InMemoryObservationStore())
    )

    view = await handler(
        GetRunHistory(run_id=_RUN_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    assert view is not None
    assert [e.event_type for e in view.events] == ["RunStarted", "RunHeld"]
    assert view.events[0].occurred_at == started_at
    assert view.events[1].occurred_at == held_at
    assert view.events[0].occurred_at != view.events[1].occurred_at
    assert view.status == "Held"


@pytest.mark.unit
async def test_handler_returns_none_for_unknown_run() -> None:
    deps = build_deps(ids=[_RUN_ID], now=_NOW)
    handler = get_run_history.bind(
        deps, observation_trail=InMemoryRunObservationTrail(InMemoryObservationStore())
    )

    view = await handler(
        GetRunHistory(run_id=uuid4()),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    assert view is None


@pytest.mark.unit
async def test_handler_observations_truncated_true_over_limit() -> None:
    store = InMemoryEventStore()
    await _seed_started(store, _RUN_ID, plan_id=_PLAN_ID, occurred_at=_NOW)
    obs_store = InMemoryObservationStore()
    await obs_store.append(
        [
            _observation(
                run_id=_RUN_ID,
                channel_name="images",
                value=float(i),
                occurred_at=_NOW + timedelta(seconds=i),
            )
            for i in range(_OBSERVATION_LIMIT + 1)
        ]
    )
    deps = build_deps(ids=[_RUN_ID], now=_NOW, event_store=store)
    handler = get_run_history.bind(deps, observation_trail=InMemoryRunObservationTrail(obs_store))

    view = await handler(
        GetRunHistory(run_id=_RUN_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    assert view is not None
    assert view.observations_truncated is True
    assert len(view.observations) == _OBSERVATION_LIMIT


@pytest.mark.unit
async def test_handler_observations_not_truncated_at_exactly_limit() -> None:
    store = InMemoryEventStore()
    await _seed_started(store, _RUN_ID, plan_id=_PLAN_ID, occurred_at=_NOW)
    obs_store = InMemoryObservationStore()
    await obs_store.append(
        [
            _observation(
                run_id=_RUN_ID,
                channel_name="images",
                value=float(i),
                occurred_at=_NOW + timedelta(seconds=i),
            )
            for i in range(_OBSERVATION_LIMIT)
        ]
    )
    deps = build_deps(ids=[_RUN_ID], now=_NOW, event_store=store)
    handler = get_run_history.bind(deps, observation_trail=InMemoryRunObservationTrail(obs_store))

    view = await handler(
        GetRunHistory(run_id=_RUN_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    assert view is not None
    assert view.observations_truncated is False
    assert len(view.observations) == _OBSERVATION_LIMIT


@pytest.mark.unit
async def test_handler_authorizes_with_query_name_and_default_conduit() -> None:
    tracking = RecordingAuthorize()
    deps = build_deps(ids=[_RUN_ID], now=_NOW, authz=tracking)
    handler = get_run_history.bind(
        deps, observation_trail=InMemoryRunObservationTrail(InMemoryObservationStore())
    )

    await handler(
        GetRunHistory(run_id=uuid4()),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    assert tracking.calls == [(_PRINCIPAL_ID, "GetRunHistory", UUID(int=0), UUID(int=0))]


@pytest.mark.unit
async def test_handler_raises_unauthorized_on_deny() -> None:
    deps = build_deps(ids=[_RUN_ID], now=_NOW, deny=True)
    handler = get_run_history.bind(
        deps, observation_trail=InMemoryRunObservationTrail(InMemoryObservationStore())
    )

    with pytest.raises(UnauthorizedError) as exc_info:
        await handler(
            GetRunHistory(run_id=uuid4()),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    assert exc_info.value.reason == "denied for test"


@pytest.mark.unit
def test_wire_run_includes_get_run_history() -> None:
    deps = build_deps(ids=[_RUN_ID], now=_NOW)
    handlers = wire_run(deps)
    assert isinstance(handlers, RunHandlers)
    assert callable(handlers.get_run_history)
