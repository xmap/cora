"""Unit tests for the `abort_run` application handler.

Mirror of `test_version_plan_handler.py` for the string-payload
shape (run_id + reason). Strict-not-idempotent, append-once-on-
success.
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.infrastructure.adapters.in_memory_event_store import InMemoryEventStore
from cora.infrastructure.event_envelope import to_new_event
from cora.run import RunHandlers, UnauthorizedError, wire_run
from cora.run.aggregates.run import (
    InvalidRunAbortReasonError,
    RunCannotAbortError,
    RunNotFoundError,
)
from cora.run.aggregates.run.events import (
    RunAborted,
    RunStarted,
    event_type_name,
    to_payload,
)
from cora.run.features import abort_run
from cora.run.features.abort_run import AbortRun
from tests.unit._helpers import build_deps

_NOW = datetime(2026, 5, 11, 12, 0, 0, tzinfo=UTC)
_RUN_ID = UUID("01900000-0000-7000-8000-00000000fa01")
_ABORTED_EVENT_ID = UUID("01900000-0000-7000-8000-00000000fa02")
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")


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


async def _seed_run_aborted(store: InMemoryEventStore, run_id: UUID) -> None:
    await _seed_run_started(store, run_id)
    aborted = RunAborted(run_id=run_id, reason="prior abort", occurred_at=_NOW)
    new_event = to_new_event(
        event_type=event_type_name(aborted),
        payload=to_payload(aborted),
        occurred_at=_NOW,
        event_id=uuid4(),
        command_name="AbortRun",
        correlation_id=_CORRELATION_ID,
        principal_id=uuid4(),
    )
    await store.append(stream_type="Run", stream_id=run_id, expected_version=1, events=[new_event])


@pytest.mark.unit
async def test_handler_returns_none_on_success() -> None:
    store = InMemoryEventStore()
    await _seed_run_started(store, _RUN_ID)
    deps = build_deps(ids=[_ABORTED_EVENT_ID], now=_NOW, event_store=store)

    result = await abort_run.bind(deps)(
        AbortRun(
            run_id=_RUN_ID,
            reason="detector overheating",
            justification="operator: aborting for test",
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert result is None


@pytest.mark.unit
async def test_handler_appends_run_aborted_event_with_trimmed_reason() -> None:
    store = InMemoryEventStore()
    await _seed_run_started(store, _RUN_ID)
    deps = build_deps(ids=[_ABORTED_EVENT_ID], now=_NOW, event_store=store)

    await abort_run.bind(deps)(
        AbortRun(
            run_id=_RUN_ID,
            reason="  beam dump unscheduled  ",
            justification="operator: aborting for test",
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    events, version = await store.load("Run", _RUN_ID)
    assert version == 2
    assert [e.event_type for e in events] == ["RunStarted", "RunAborted"]
    aborted = events[1]
    assert aborted.event_id == _ABORTED_EVENT_ID
    assert aborted.metadata == {"command": "AbortRun"}
    assert aborted.payload["reason"] == "beam dump unscheduled"


@pytest.mark.unit
async def test_handler_raises_run_not_found_when_run_does_not_exist() -> None:
    deps = build_deps(ids=[_ABORTED_EVENT_ID], now=_NOW)
    handler = abort_run.bind(deps)

    with pytest.raises(RunNotFoundError):
        await handler(
            AbortRun(
                run_id=_RUN_ID,
                reason="X",
                justification="operator: aborting for test",
            ),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_handler_raises_invalid_reason_for_whitespace_only() -> None:
    store = InMemoryEventStore()
    await _seed_run_started(store, _RUN_ID)
    deps = build_deps(ids=[_ABORTED_EVENT_ID], now=_NOW, event_store=store)

    with pytest.raises(InvalidRunAbortReasonError):
        await abort_run.bind(deps)(
            AbortRun(
                run_id=_RUN_ID,
                reason="   ",
                justification="operator: aborting for test",
            ),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_handler_raises_cannot_abort_when_already_aborted() -> None:
    """Strict-not-idempotent: re-aborting raises."""
    store = InMemoryEventStore()
    await _seed_run_aborted(store, _RUN_ID)
    deps = build_deps(ids=[_ABORTED_EVENT_ID], now=_NOW, event_store=store)

    with pytest.raises(RunCannotAbortError):
        await abort_run.bind(deps)(
            AbortRun(
                run_id=_RUN_ID,
                reason="X",
                justification="operator: aborting for test",
            ),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_handler_raises_unauthorized_on_deny() -> None:
    store = InMemoryEventStore()
    await _seed_run_started(store, _RUN_ID)
    deny_deps = build_deps(ids=[_ABORTED_EVENT_ID], now=_NOW, event_store=store, deny=True)

    with pytest.raises(UnauthorizedError) as exc_info:
        await abort_run.bind(deny_deps)(
            AbortRun(
                run_id=_RUN_ID,
                reason="X",
                justification="operator: aborting for test",
            ),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    assert exc_info.value.reason == "denied for test"


@pytest.mark.unit
async def test_handler_propagates_causation_id_to_appended_event() -> None:
    causation = UUID("01900000-0000-7000-8000-0000000000bb")
    store = InMemoryEventStore()
    await _seed_run_started(store, _RUN_ID)
    deps = build_deps(ids=[_ABORTED_EVENT_ID], now=_NOW, event_store=store)

    await abort_run.bind(deps)(
        AbortRun(
            run_id=_RUN_ID,
            reason="X",
            justification="operator: aborting for test",
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
        causation_id=causation,
    )

    events, _ = await store.load("Run", _RUN_ID)
    assert events[1].causation_id == causation


@pytest.mark.unit
def test_wire_run_includes_abort_run() -> None:
    deps = build_deps(ids=[_ABORTED_EVENT_ID], now=_NOW)
    handlers = wire_run(deps)
    assert isinstance(handlers, RunHandlers)
    assert callable(handlers.abort_run)
