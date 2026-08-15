"""Unit tests for the `record_witnessed_run_outcome` application handler.

Mirror of `test_complete_run_handler.py` shape: update-style, strict-not-
idempotent, append-once-on-success. Every seeded Run is Witnessed, since
the applicability guard (`RunNotWitnessedError`) refuses a Conducted one
regardless of status.
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.infrastructure.adapters.in_memory_event_store import InMemoryEventStore
from cora.infrastructure.event_envelope import to_new_event
from cora.run import RunHandlers, UnauthorizedError, wire_run
from cora.run.aggregates.run import (
    ConductMode,
    RunCannotAbortError,
    RunCannotCompleteError,
    RunNotFoundError,
    RunNotWitnessedError,
)
from cora.run.aggregates.run.events import (
    RunCompleted,
    RunStarted,
    event_type_name,
    to_payload,
)
from cora.run.features import record_witnessed_run_outcome
from cora.run.features.record_witnessed_run_outcome import RecordWitnessedRunOutcome
from cora.shared.capture_phase import CapturePhase
from tests.unit._helpers import build_deps

_NOW = datetime(2026, 8, 15, 12, 0, 0, tzinfo=UTC)
_RUN_ID = UUID("01900000-0000-7000-8000-00000000fd01")
_OUTCOME_EVENT_ID = UUID("01900000-0000-7000-8000-00000000fd02")
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")
_MONITOR_SOURCE_ID = UUID("01900000-0000-7000-8000-000072756e01")


async def _seed_witnessed_run_started(
    store: InMemoryEventStore,
    run_id: UUID,
    *,
    conduct_mode: ConductMode = ConductMode.WITNESSED,
) -> None:
    event = RunStarted(
        run_id=run_id,
        name="Witnessed capture 2bmb-tomoscan",
        plan_id=uuid4(),
        subject_id=None,
        conduct_mode=conduct_mode,
        occurred_at=_NOW,
    )
    new_event = to_new_event(
        event_type=event_type_name(event),
        payload=to_payload(event),
        occurred_at=_NOW,
        event_id=uuid4(),
        command_name="RecordWitnessedRun",
        correlation_id=_CORRELATION_ID,
        principal_id=uuid4(),
    )
    await store.append(stream_type="Run", stream_id=run_id, expected_version=0, events=[new_event])


async def _seed_witnessed_run_completed(store: InMemoryEventStore, run_id: UUID) -> None:
    await _seed_witnessed_run_started(store, run_id)
    completed = RunCompleted(run_id=run_id, occurred_at=_NOW, observed_at=None)
    new_event = to_new_event(
        event_type=event_type_name(completed),
        payload=to_payload(completed),
        occurred_at=_NOW,
        event_id=uuid4(),
        command_name="RecordWitnessedRunOutcome",
        correlation_id=_CORRELATION_ID,
        principal_id=uuid4(),
    )
    await store.append(stream_type="Run", stream_id=run_id, expected_version=1, events=[new_event])


def _command(**overrides: object) -> RecordWitnessedRunOutcome:
    defaults: dict[str, object] = {
        "run_id": _RUN_ID,
        "capture_code": "2bmb-tomoscan",
        "observed_phase": CapturePhase.ENDED,
        "observed_at": _NOW,
        "monitor_source_id": _MONITOR_SOURCE_ID,
        "trigger": "Monitor",
        "capture_progress_snapshot": None,
    }
    defaults.update(overrides)
    return RecordWitnessedRunOutcome(**defaults)  # type: ignore[arg-type]


@pytest.mark.unit
async def test_handler_returns_none_on_success() -> None:
    store = InMemoryEventStore()
    await _seed_witnessed_run_started(store, _RUN_ID)
    deps = build_deps(ids=[_OUTCOME_EVENT_ID], now=_NOW, event_store=store)

    result = await record_witnessed_run_outcome.bind(deps)(
        _command(),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert result is None


@pytest.mark.unit
async def test_handler_appends_run_completed_for_ended_phase() -> None:
    store = InMemoryEventStore()
    await _seed_witnessed_run_started(store, _RUN_ID)
    deps = build_deps(ids=[_OUTCOME_EVENT_ID], now=_NOW, event_store=store)

    await record_witnessed_run_outcome.bind(deps)(
        _command(observed_phase=CapturePhase.ENDED),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    events, version = await store.load("Run", _RUN_ID)
    assert version == 2
    assert [e.event_type for e in events] == ["RunStarted", "RunCompleted"]
    outcome = events[1]
    assert outcome.event_id == _OUTCOME_EVENT_ID
    assert outcome.metadata == {"command": "RecordWitnessedRunOutcome"}


@pytest.mark.unit
async def test_handler_appends_run_aborted_for_aborted_phase() -> None:
    store = InMemoryEventStore()
    await _seed_witnessed_run_started(store, _RUN_ID)
    deps = build_deps(ids=[_OUTCOME_EVENT_ID], now=_NOW, event_store=store)

    await record_witnessed_run_outcome.bind(deps)(
        _command(observed_phase=CapturePhase.ABORTED),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    events, _ = await store.load("Run", _RUN_ID)
    assert [e.event_type for e in events] == ["RunStarted", "RunAborted"]


@pytest.mark.unit
async def test_handler_raises_run_not_found_when_run_does_not_exist() -> None:
    deps = build_deps(ids=[_OUTCOME_EVENT_ID], now=_NOW)
    handler = record_witnessed_run_outcome.bind(deps)

    with pytest.raises(RunNotFoundError):
        await handler(
            _command(),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_handler_raises_not_witnessed_for_a_conducted_run() -> None:
    store = InMemoryEventStore()
    await _seed_witnessed_run_started(store, _RUN_ID, conduct_mode=ConductMode.CONDUCTED)
    deps = build_deps(ids=[_OUTCOME_EVENT_ID], now=_NOW, event_store=store)

    with pytest.raises(RunNotWitnessedError):
        await record_witnessed_run_outcome.bind(deps)(
            _command(),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_handler_raises_cannot_complete_when_already_completed() -> None:
    """Strict-not-idempotent: re-recording the outcome raises."""
    store = InMemoryEventStore()
    await _seed_witnessed_run_completed(store, _RUN_ID)
    deps = build_deps(ids=[_OUTCOME_EVENT_ID], now=_NOW, event_store=store)

    with pytest.raises(RunCannotCompleteError):
        await record_witnessed_run_outcome.bind(deps)(
            _command(observed_phase=CapturePhase.ENDED),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_handler_raises_cannot_abort_when_already_completed() -> None:
    store = InMemoryEventStore()
    await _seed_witnessed_run_completed(store, _RUN_ID)
    deps = build_deps(ids=[_OUTCOME_EVENT_ID], now=_NOW, event_store=store)

    with pytest.raises(RunCannotAbortError):
        await record_witnessed_run_outcome.bind(deps)(
            _command(observed_phase=CapturePhase.ABORTED),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_handler_raises_unauthorized_on_deny() -> None:
    store = InMemoryEventStore()
    await _seed_witnessed_run_started(store, _RUN_ID)
    deny_deps = build_deps(ids=[_OUTCOME_EVENT_ID], now=_NOW, event_store=store, deny=True)

    with pytest.raises(UnauthorizedError) as exc_info:
        await record_witnessed_run_outcome.bind(deny_deps)(
            _command(),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    assert exc_info.value.reason == "denied for test"


@pytest.mark.unit
async def test_handler_propagates_causation_id_to_appended_event() -> None:
    causation = UUID("01900000-0000-7000-8000-0000000000bb")
    store = InMemoryEventStore()
    await _seed_witnessed_run_started(store, _RUN_ID)
    deps = build_deps(ids=[_OUTCOME_EVENT_ID], now=_NOW, event_store=store)

    await record_witnessed_run_outcome.bind(deps)(
        _command(),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
        causation_id=causation,
    )

    events, _ = await store.load("Run", _RUN_ID)
    assert events[1].causation_id == causation


@pytest.mark.unit
def test_wire_run_includes_record_witnessed_run_outcome() -> None:
    deps = build_deps(ids=[_OUTCOME_EVENT_ID], now=_NOW)
    handlers = wire_run(deps)
    assert isinstance(handlers, RunHandlers)
    assert callable(handlers.record_witnessed_run_outcome)
