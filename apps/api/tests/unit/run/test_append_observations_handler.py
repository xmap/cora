"""Unit tests for the `append_observations` application handler.

Mirrors `test_append_inferences_handler.py` shape.
Adds the per-entry validation tests specific to Observation (channel_name,
NaN/Inf value, sampling_procedure) and the terminal-status guard
(RunObservationLogbookClosedError).
"""

from collections.abc import Callable
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.infrastructure.adapters.in_memory_event_store import InMemoryEventStore
from cora.infrastructure.event_envelope import to_new_event
from cora.run.aggregates.run import (
    InMemoryObservationStore,
    InvalidChannelNameError,
    InvalidObservationValueError,
    InvalidSamplingProcedureError,
    RunNotFoundError,
    RunObservationLogbookClosedError,
)
from cora.run.aggregates.run.events import (
    RunAborted,
    RunCompleted,
    RunHeld,
    RunStarted,
    RunStopped,
    RunTruncated,
    event_type_name,
    to_payload,
)
from cora.run.errors import UnauthorizedError
from cora.run.features import append_observations
from cora.run.features.append_observations import (
    AppendObservations,
    ObservationInput,
)
from tests.unit._helpers import build_deps

_NOW = datetime(2026, 5, 14, 12, 0, 0, tzinfo=UTC)
_RUN_ID = UUID("01900000-0000-7000-8000-00000000f5b1")
_LOGBOOK_ID = UUID("01900000-0000-7000-8000-00000000f5b2")
_LOGBOOK_OPEN_EVENT_ID = UUID("01900000-0000-7000-8000-00000000f5b3")
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")


def _entry(**overrides: object) -> ObservationInput:
    base: dict[str, object] = {
        "event_id": uuid4(),
        "channel_name": "T_sample",
        "value": 295.1,
        "sampled_at": _NOW,
        "sampling_procedure": "baseline",
    }
    base.update(overrides)
    return ObservationInput(**base)  # type: ignore[arg-type]


async def _seed_run_started(store: InMemoryEventStore, run_id: UUID) -> None:
    event = RunStarted(
        run_id=run_id,
        name="32-ID FlyScan",
        plan_id=uuid4(),
        subject_id=uuid4(),
        occurred_at=_NOW,
    )
    new_event = to_new_event(
        event_type=event_type_name(event),
        payload=to_payload(event),
        occurred_at=_NOW,
        event_id=uuid4(),
        command_name="StartRun",
        correlation_id=_CORRELATION_ID,
        principal_id=uuid4(),
    )
    await store.append(stream_type="Run", stream_id=run_id, expected_version=0, events=[new_event])


async def _seed_run_held(store: InMemoryEventStore, run_id: UUID) -> None:
    await _seed_run_started(store, run_id)
    held = RunHeld(run_id=run_id, occurred_at=_NOW)
    new_event = to_new_event(
        event_type=event_type_name(held),
        payload=to_payload(held),
        occurred_at=_NOW,
        event_id=uuid4(),
        command_name="HoldRun",
        correlation_id=_CORRELATION_ID,
        principal_id=uuid4(),
    )
    await store.append(stream_type="Run", stream_id=run_id, expected_version=1, events=[new_event])


async def _seed_run_terminated(
    store: InMemoryEventStore,
    run_id: UUID,
    terminal_event: RunCompleted | RunAborted | RunStopped | RunTruncated,
    command_name: str,
) -> None:
    await _seed_run_started(store, run_id)
    new_event = to_new_event(
        event_type=event_type_name(terminal_event),
        payload=to_payload(terminal_event),
        occurred_at=_NOW,
        event_id=uuid4(),
        command_name=command_name,
        correlation_id=_CORRELATION_ID,
        principal_id=uuid4(),
    )
    await store.append(stream_type="Run", stream_id=run_id, expected_version=1, events=[new_event])


# ---------- Happy path: lazy open on first append ----------


@pytest.mark.unit
async def test_handler_emits_logbook_opened_on_first_append() -> None:
    """First append on a Run with no observation logbook emits
    RunObservationLogbookOpened to the Run stream + appends the entry."""
    event_store = InMemoryEventStore()
    await _seed_run_started(event_store, _RUN_ID)
    observation_store = InMemoryObservationStore()
    deps = build_deps(ids=[_LOGBOOK_ID, _LOGBOOK_OPEN_EVENT_ID], now=_NOW, event_store=event_store)

    count = await append_observations.bind(deps, observation_store=observation_store)(
        AppendObservations(run_id=_RUN_ID, entries=(_entry(),)),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert count == 1

    # Run stream now has 2 events: started + logbook opened.
    stored, version = await event_store.load("Run", _RUN_ID)
    assert version == 2
    assert [e.event_type for e in stored] == ["RunStarted", "RunObservationLogbookOpened"]
    assert stored[1].event_id == _LOGBOOK_OPEN_EVENT_ID

    # Reading store has the appended entry with the open's logbook_id.
    rows = observation_store.all()
    assert len(rows) == 1
    assert rows[0].run_id == _RUN_ID
    assert rows[0].logbook_id == _LOGBOOK_ID


@pytest.mark.unit
async def test_handler_skips_open_when_logbook_already_present() -> None:
    """Second append (observation logbook already open) appends without
    re-emitting RunObservationLogbookOpened."""
    event_store = InMemoryEventStore()
    await _seed_run_started(event_store, _RUN_ID)
    observation_store = InMemoryObservationStore()
    deps_first = build_deps(
        ids=[_LOGBOOK_ID, _LOGBOOK_OPEN_EVENT_ID], now=_NOW, event_store=event_store
    )
    await append_observations.bind(deps_first, observation_store=observation_store)(
        AppendObservations(run_id=_RUN_ID, entries=(_entry(),)),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    # Second call with fresh deps (fresh id_generator).
    deps_second = build_deps(
        ids=[uuid4(), uuid4(), uuid4(), uuid4()],
        now=_NOW,
        event_store=event_store,
    )
    count = await append_observations.bind(deps_second, observation_store=observation_store)(
        AppendObservations(run_id=_RUN_ID, entries=(_entry(),)),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert count == 1

    # Run stream still only has 2 events (no second open).
    stored, version = await event_store.load("Run", _RUN_ID)
    assert version == 2
    assert [e.event_type for e in stored] == ["RunStarted", "RunObservationLogbookOpened"]

    # Both entries land with the SAME logbook_id.
    rows = observation_store.all()
    assert len(rows) == 2
    assert rows[0].logbook_id == rows[1].logbook_id == _LOGBOOK_ID


@pytest.mark.unit
async def test_handler_appends_during_held_status() -> None:
    """Held is a non-terminal pause state; observations still accepted."""
    event_store = InMemoryEventStore()
    await _seed_run_held(event_store, _RUN_ID)
    observation_store = InMemoryObservationStore()
    deps = build_deps(ids=[_LOGBOOK_ID, _LOGBOOK_OPEN_EVENT_ID], now=_NOW, event_store=event_store)
    count = await append_observations.bind(deps, observation_store=observation_store)(
        AppendObservations(run_id=_RUN_ID, entries=(_entry(),)),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert count == 1
    assert len(observation_store.all()) == 1


# ---------- Batch ----------


@pytest.mark.unit
async def test_handler_appends_batch_in_one_call() -> None:
    """Batch of N entries lands as N rows + ONE logbook open."""
    event_store = InMemoryEventStore()
    await _seed_run_started(event_store, _RUN_ID)
    observation_store = InMemoryObservationStore()
    deps = build_deps(ids=[_LOGBOOK_ID, _LOGBOOK_OPEN_EVENT_ID], now=_NOW, event_store=event_store)

    entries = (
        _entry(channel_name="T_sample"),
        _entry(channel_name="motor_x"),
        _entry(channel_name="ring_current"),
    )
    count = await append_observations.bind(deps, observation_store=observation_store)(
        AppendObservations(run_id=_RUN_ID, entries=entries),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert count == 3
    assert len(observation_store.all()) == 3
    # Only one RunObservationLogbookOpened for the whole batch.
    stored, _ = await event_store.load("Run", _RUN_ID)
    open_events = [e for e in stored if e.event_type == "RunObservationLogbookOpened"]
    assert len(open_events) == 1


# ---------- Per-entry validation ----------


@pytest.mark.unit
async def test_handler_rejects_invalid_channel_name() -> None:
    event_store = InMemoryEventStore()
    await _seed_run_started(event_store, _RUN_ID)
    observation_store = InMemoryObservationStore()
    deps = build_deps(ids=[_LOGBOOK_ID, _LOGBOOK_OPEN_EVENT_ID], now=_NOW, event_store=event_store)
    with pytest.raises(InvalidChannelNameError):
        await append_observations.bind(deps, observation_store=observation_store)(
            AppendObservations(run_id=_RUN_ID, entries=(_entry(channel_name="   "),)),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    # No logbook open + no rows on validation failure.
    _, version = await event_store.load("Run", _RUN_ID)
    assert version == 1
    assert observation_store.all() == []


@pytest.mark.unit
@pytest.mark.parametrize("bad_value", [float("nan"), float("inf"), float("-inf")])
async def test_handler_rejects_nan_and_infinity(bad_value: float) -> None:
    event_store = InMemoryEventStore()
    await _seed_run_started(event_store, _RUN_ID)
    observation_store = InMemoryObservationStore()
    deps = build_deps(ids=[_LOGBOOK_ID, _LOGBOOK_OPEN_EVENT_ID], now=_NOW, event_store=event_store)
    with pytest.raises(InvalidObservationValueError):
        await append_observations.bind(deps, observation_store=observation_store)(
            AppendObservations(run_id=_RUN_ID, entries=(_entry(value=bad_value),)),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    assert observation_store.all() == []


@pytest.mark.unit
async def test_handler_rejects_unknown_sampling_procedure() -> None:
    event_store = InMemoryEventStore()
    await _seed_run_started(event_store, _RUN_ID)
    observation_store = InMemoryObservationStore()
    deps = build_deps(ids=[_LOGBOOK_ID, _LOGBOOK_OPEN_EVENT_ID], now=_NOW, event_store=event_store)
    with pytest.raises(InvalidSamplingProcedureError):
        await append_observations.bind(deps, observation_store=observation_store)(
            AppendObservations(
                run_id=_RUN_ID,
                entries=(_entry(sampling_procedure="histogram"),),
            ),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    assert observation_store.all() == []


# ---------- Terminal-status guard (RunObservationLogbookClosedError) ----------


def _make_completed(rid: UUID) -> RunCompleted:
    return RunCompleted(run_id=rid, occurred_at=_NOW)


def _make_aborted(rid: UUID) -> RunAborted:
    return RunAborted(run_id=rid, reason="emergency", occurred_at=_NOW)


def _make_stopped(rid: UUID) -> RunStopped:
    return RunStopped(run_id=rid, reason="stop", occurred_at=_NOW)


def _make_truncated(rid: UUID) -> RunTruncated:
    return RunTruncated(run_id=rid, reason="crash", interrupted_at=None, occurred_at=_NOW)


_TerminalFactory = Callable[[UUID], RunCompleted | RunAborted | RunStopped | RunTruncated]


@pytest.mark.unit
@pytest.mark.parametrize(
    "terminal_factory, command_name",
    [
        (_make_completed, "CompleteRun"),
        (_make_aborted, "AbortRun"),
        (_make_stopped, "StopRun"),
        (_make_truncated, "TruncateRun"),
    ],
)
async def test_handler_rejects_when_run_in_terminal_status(
    terminal_factory: _TerminalFactory, command_name: str
) -> None:
    """Run.status terminal implicitly closes the observation logbook."""
    event_store = InMemoryEventStore()
    await _seed_run_terminated(
        event_store,
        _RUN_ID,
        terminal_factory(_RUN_ID),
        command_name,
    )
    observation_store = InMemoryObservationStore()
    deps = build_deps(ids=[_LOGBOOK_ID, _LOGBOOK_OPEN_EVENT_ID], now=_NOW, event_store=event_store)
    with pytest.raises(RunObservationLogbookClosedError):
        await append_observations.bind(deps, observation_store=observation_store)(
            AppendObservations(run_id=_RUN_ID, entries=(_entry(),)),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    assert observation_store.all() == []


# ---------- 404 ----------


@pytest.mark.unit
async def test_handler_raises_run_not_found_for_unknown_id() -> None:
    deps = build_deps(ids=[_LOGBOOK_ID, _LOGBOOK_OPEN_EVENT_ID], now=_NOW)
    observation_store = InMemoryObservationStore()
    with pytest.raises(RunNotFoundError) as exc_info:
        await append_observations.bind(deps, observation_store=observation_store)(
            AppendObservations(run_id=uuid4(), entries=(_entry(),)),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    assert "not found" in str(exc_info.value).lower()
    assert observation_store.all() == []


# ---------- Authz ----------


@pytest.mark.unit
async def test_handler_raises_unauthorized_on_deny() -> None:
    event_store = InMemoryEventStore()
    await _seed_run_started(event_store, _RUN_ID)
    observation_store = InMemoryObservationStore()
    deps = build_deps(
        ids=[_LOGBOOK_ID, _LOGBOOK_OPEN_EVENT_ID],
        now=_NOW,
        event_store=event_store,
        deny=True,
    )
    with pytest.raises(UnauthorizedError):
        await append_observations.bind(deps, observation_store=observation_store)(
            AppendObservations(run_id=_RUN_ID, entries=(_entry(),)),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    # No logbook open + no rows when authz denies.
    _, version = await event_store.load("Run", _RUN_ID)
    assert version == 1
    assert observation_store.all() == []


# ---------- Envelope threading ----------


@pytest.mark.unit
async def test_handler_threads_correlation_id_into_entries() -> None:
    event_store = InMemoryEventStore()
    await _seed_run_started(event_store, _RUN_ID)
    observation_store = InMemoryObservationStore()
    deps = build_deps(ids=[_LOGBOOK_ID, _LOGBOOK_OPEN_EVENT_ID], now=_NOW, event_store=event_store)
    await append_observations.bind(deps, observation_store=observation_store)(
        AppendObservations(run_id=_RUN_ID, entries=(_entry(), _entry())),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    for row in observation_store.all():
        assert row.correlation_id == _CORRELATION_ID


@pytest.mark.unit
async def test_handler_threads_causation_id_into_entries() -> None:
    causation = UUID("01900000-0000-7000-8000-0000000000bb")
    event_store = InMemoryEventStore()
    await _seed_run_started(event_store, _RUN_ID)
    observation_store = InMemoryObservationStore()
    deps = build_deps(ids=[_LOGBOOK_ID, _LOGBOOK_OPEN_EVENT_ID], now=_NOW, event_store=event_store)
    await append_observations.bind(deps, observation_store=observation_store)(
        AppendObservations(run_id=_RUN_ID, entries=(_entry(),)),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
        causation_id=causation,
    )
    rows = observation_store.all()
    assert rows[0].causation_id == causation


@pytest.mark.unit
async def test_handler_threads_principal_id_into_actor_id() -> None:
    """actor_id on the row equals the principal who issued the
    command (PII-vault posture: the actor identity is the audit
    surface; the entry payload doesn't carry a separate actor field)."""
    event_store = InMemoryEventStore()
    await _seed_run_started(event_store, _RUN_ID)
    observation_store = InMemoryObservationStore()
    deps = build_deps(ids=[_LOGBOOK_ID, _LOGBOOK_OPEN_EVENT_ID], now=_NOW, event_store=event_store)
    await append_observations.bind(deps, observation_store=observation_store)(
        AppendObservations(run_id=_RUN_ID, entries=(_entry(),)),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    rows = observation_store.all()
    assert rows[0].actor_id == _PRINCIPAL_ID


# ---------- is_simulated provenance threading ----------


@pytest.mark.unit
async def test_handler_threads_is_simulated_into_row_defaulting_real() -> None:
    """The producer's is_simulated flag reaches the stored row; it
    defaults to False (real) when omitted and is preserved when set."""
    event_store = InMemoryEventStore()
    await _seed_run_started(event_store, _RUN_ID)
    observation_store = InMemoryObservationStore()
    deps = build_deps(ids=[_LOGBOOK_ID, _LOGBOOK_OPEN_EVENT_ID], now=_NOW, event_store=event_store)
    await append_observations.bind(deps, observation_store=observation_store)(
        AppendObservations(
            run_id=_RUN_ID,
            entries=(
                _entry(channel_name="real_default"),
                _entry(channel_name="sim_explicit", is_simulated=True),
            ),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    rows = observation_store.all()
    real_row = next(r for r in rows if r.channel_name == "real_default")
    sim_row = next(r for r in rows if r.channel_name == "sim_explicit")
    assert real_row.is_simulated is False
    assert sim_row.is_simulated is True


# ---------- occurred_at fallback ----------


@pytest.mark.unit
async def test_handler_defaults_occurred_at_to_clock_when_omitted() -> None:
    """Producer omits `occurred_at`; handler stamps deps.clock.now()."""
    event_store = InMemoryEventStore()
    await _seed_run_started(event_store, _RUN_ID)
    observation_store = InMemoryObservationStore()
    deps = build_deps(ids=[_LOGBOOK_ID, _LOGBOOK_OPEN_EVENT_ID], now=_NOW, event_store=event_store)
    await append_observations.bind(deps, observation_store=observation_store)(
        AppendObservations(run_id=_RUN_ID, entries=(_entry(occurred_at=None),)),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    rows = observation_store.all()
    assert rows[0].occurred_at == _NOW


@pytest.mark.unit
async def test_handler_preserves_explicit_occurred_at() -> None:
    """Producer-supplied `occurred_at` is kept verbatim (DAQ adapter
    case: external ingest-time clock)."""
    custom = datetime(2026, 5, 14, 9, 0, 0, tzinfo=UTC)
    event_store = InMemoryEventStore()
    await _seed_run_started(event_store, _RUN_ID)
    observation_store = InMemoryObservationStore()
    deps = build_deps(ids=[_LOGBOOK_ID, _LOGBOOK_OPEN_EVENT_ID], now=_NOW, event_store=event_store)
    await append_observations.bind(deps, observation_store=observation_store)(
        AppendObservations(run_id=_RUN_ID, entries=(_entry(occurred_at=custom),)),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    rows = observation_store.all()
    assert rows[0].occurred_at == custom


# ---------- Concurrent first-write race (post-gate-review P1) ----------


@pytest.mark.unit
async def test_handler_retries_on_concurrent_logbook_open_race() -> None:
    """Two parallel first-appends both try to emit RunObservationLogbookOpened;
    the second loses on optimistic concurrency. The handler retries from
    load, the second pass sees the logbook now open + skips the open
    step. Models the documented self-healing behavior. Mirrors 8c-b's
    `test_handler_retries_on_concurrent_logbook_open_race`."""
    from cora.infrastructure.ports.event_store import ConcurrencyError, NewEvent
    from cora.run.aggregates.run import (
        LOGBOOK_KIND_OBSERVATION,
        OBSERVATION_LOGBOOK_SCHEMA,
        RunObservationLogbookOpened,
    )

    event_store = InMemoryEventStore()
    await _seed_run_started(event_store, _RUN_ID)
    observation_store = InMemoryObservationStore()

    real_append = event_store.append
    real_load = event_store.load
    concurrent_logbook_id = UUID("01900000-0000-7000-8000-0000000099aa")
    raced_open_event_id = UUID("01900000-0000-7000-8000-0000000099bb")
    fired = {"yes": False}

    async def racing_append(
        stream_type: str,
        stream_id: UUID,
        expected_version: int,
        events: list[NewEvent],
    ) -> int:
        if not fired["yes"] and any(e.event_type == "RunObservationLogbookOpened" for e in events):
            fired["yes"] = True
            # Simulate the conflicting writer landing first.
            conflict_event = RunObservationLogbookOpened(
                run_id=stream_id,
                logbook_id=concurrent_logbook_id,
                kind=LOGBOOK_KIND_OBSERVATION,
                schema=OBSERVATION_LOGBOOK_SCHEMA,
                occurred_at=_NOW,
            )
            new_event = to_new_event(
                event_type=event_type_name(conflict_event),
                payload=to_payload(conflict_event),
                occurred_at=_NOW,
                event_id=raced_open_event_id,
                command_name="ConcurrentWriter",
                correlation_id=_CORRELATION_ID,
                principal_id=uuid4(),
            )
            await real_append(stream_type, stream_id, expected_version, [new_event])
            raise ConcurrencyError(
                stream_type=stream_type,
                stream_id=stream_id,
                expected=expected_version,
                actual=expected_version + 1,
            )
        return await real_append(stream_type, stream_id, expected_version, events)

    event_store.append = racing_append  # type: ignore[method-assign]
    event_store.load = real_load  # type: ignore[method-assign]

    deps = build_deps(
        ids=[_LOGBOOK_ID, _LOGBOOK_OPEN_EVENT_ID, uuid4(), uuid4()],
        now=_NOW,
        event_store=event_store,
    )
    count = await append_observations.bind(deps, observation_store=observation_store)(
        AppendObservations(run_id=_RUN_ID, entries=(_entry(),)),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert count == 1
    rows = observation_store.all()
    assert len(rows) == 1
    # The retry's reload saw the conflicting writer's logbook id and used IT,
    # not the originally-allocated one.
    assert rows[0].logbook_id == concurrent_logbook_id


# ---------- sampled_at independence (post-gate-review P2) ----------


@pytest.mark.unit
async def test_handler_preserves_distinct_sampled_at_per_entry() -> None:
    """Each entry's sampled_at survives the row build independent of
    occurred_at. Pin at the handler boundary because the row factory
    is where conflation could silently happen."""
    event_store = InMemoryEventStore()
    await _seed_run_started(event_store, _RUN_ID)
    observation_store = InMemoryObservationStore()
    deps = build_deps(ids=[_LOGBOOK_ID, _LOGBOOK_OPEN_EVENT_ID], now=_NOW, event_store=event_store)

    sampled_a = datetime(2026, 5, 14, 11, 59, 50, tzinfo=UTC)
    sampled_b = datetime(2026, 5, 14, 11, 59, 51, tzinfo=UTC)
    await append_observations.bind(deps, observation_store=observation_store)(
        AppendObservations(
            run_id=_RUN_ID,
            entries=(
                _entry(sampled_at=sampled_a, channel_name="a"),
                _entry(sampled_at=sampled_b, channel_name="b"),
            ),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    rows = observation_store.all()
    row_a = next(r for r in rows if r.channel_name == "a")
    row_b = next(r for r in rows if r.channel_name == "b")
    assert row_a.sampled_at == sampled_a
    assert row_b.sampled_at == sampled_b
    assert row_a.sampled_at != row_a.occurred_at
    assert row_b.sampled_at != row_b.occurred_at


# ---------- 'monitor' accepted (sampling_procedure extension) ----------


@pytest.mark.unit
async def test_handler_accepts_monitor_sampling_procedure() -> None:
    """The closed enum was extended to admit 'monitor' alongside
    'baseline'. Replaces the earlier 'rejects-monitor' guard test;
    monitor is now a first-class procedure value (Bluesky monitor
    stream pattern: sub-Hz time-series during the run)."""
    event_store = InMemoryEventStore()
    await _seed_run_started(event_store, _RUN_ID)
    observation_store = InMemoryObservationStore()
    deps = build_deps(ids=[_LOGBOOK_ID, _LOGBOOK_OPEN_EVENT_ID], now=_NOW, event_store=event_store)
    count = await append_observations.bind(deps, observation_store=observation_store)(
        AppendObservations(
            run_id=_RUN_ID,
            entries=(_entry(sampling_procedure="monitor"),),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert count == 1
    assert observation_store.all()[0].sampling_procedure == "monitor"


# ---------- Polymorphic mixed-procedure (6f-5c — the design earns its keep) ----------


@pytest.mark.unit
async def test_handler_writes_baseline_and_monitor_to_same_run_logbook() -> None:
    """The whole point of the polymorphic-with-discriminator design:
    a single Run holds BOTH baseline and monitor observations, side-by-
    side, in the same `entries_run_observations` table, sharing the same
    observation_logbook_id. No table split, no separate slice, no
    discriminator gymnastics — just rows that differ by the
    `sampling_procedure` column.

    Realistic scenario: Run start posts a baseline snapshot of all
    channels; the DAQ adapter then streams monitor observations for
    sample temperature throughout the Run; Run end posts another
    baseline snapshot. All three writes hit the same logbook."""
    event_store = InMemoryEventStore()
    await _seed_run_started(event_store, _RUN_ID)
    observation_store = InMemoryObservationStore()
    deps = build_deps(ids=[_LOGBOOK_ID, _LOGBOOK_OPEN_EVENT_ID], now=_NOW, event_store=event_store)

    # Run-start baseline: temperature snapshot.
    await append_observations.bind(deps, observation_store=observation_store)(
        AppendObservations(
            run_id=_RUN_ID,
            entries=(
                _entry(
                    channel_name="T_sample",
                    value=295.1,
                    sampling_procedure="baseline",
                ),
            ),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    # Mid-run monitor stream: three samples drifting.
    deps_monitor = build_deps(ids=[uuid4() for _ in range(4)], now=_NOW, event_store=event_store)
    await append_observations.bind(deps_monitor, observation_store=observation_store)(
        AppendObservations(
            run_id=_RUN_ID,
            entries=(
                _entry(
                    channel_name="T_sample",
                    value=294.8,
                    sampling_procedure="monitor",
                    sampled_at=datetime(2026, 5, 14, 12, 0, 30, tzinfo=UTC),
                ),
                _entry(
                    channel_name="T_sample",
                    value=295.0,
                    sampling_procedure="monitor",
                    sampled_at=datetime(2026, 5, 14, 12, 1, 0, tzinfo=UTC),
                ),
                _entry(
                    channel_name="T_sample",
                    value=295.2,
                    sampling_procedure="monitor",
                    sampled_at=datetime(2026, 5, 14, 12, 1, 30, tzinfo=UTC),
                ),
            ),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    # Run-end baseline: temperature snapshot again.
    deps_end = build_deps(ids=[uuid4() for _ in range(2)], now=_NOW, event_store=event_store)
    await append_observations.bind(deps_end, observation_store=observation_store)(
        AppendObservations(
            run_id=_RUN_ID,
            entries=(
                _entry(
                    channel_name="T_sample",
                    value=295.4,
                    sampling_procedure="baseline",
                ),
            ),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    rows = observation_store.all()
    assert len(rows) == 5

    # All rows share the same logbook (no per-procedure split).
    logbook_ids = {r.logbook_id for r in rows}
    assert logbook_ids == {_LOGBOOK_ID}

    # All rows share the same Run (no per-procedure aggregate split).
    assert {r.run_id for r in rows} == {_RUN_ID}

    # Procedure split: 2 baseline (start + end), 3 monitor (mid-run).
    by_procedure: dict[str, list[float]] = {"baseline": [], "monitor": []}
    for r in rows:
        by_procedure[r.sampling_procedure].append(r.value)
    assert sorted(by_procedure["baseline"]) == [295.1, 295.4]
    assert sorted(by_procedure["monitor"]) == [294.8, 295.0, 295.2]

    # The Run stream still has just one logbook-open event (lazy
    # open survives across procedure kinds).
    stored, version = await event_store.load("Run", _RUN_ID)
    assert version == 2  # RunStarted + RunObservationLogbookOpened
    assert [e.event_type for e in stored] == ["RunStarted", "RunObservationLogbookOpened"]


# ---------- Wire surface ----------


@pytest.mark.unit
def test_wire_run_includes_append_run_observations() -> None:
    from cora.run import RunHandlers, wire_run

    deps = build_deps(ids=[_LOGBOOK_ID, _LOGBOOK_OPEN_EVENT_ID], now=_NOW)
    handlers = wire_run(deps)
    assert isinstance(handlers, RunHandlers)
    assert callable(handlers.append_observations)
