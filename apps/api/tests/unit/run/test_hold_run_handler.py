"""Unit tests for the `hold_run` application handler."""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.infrastructure.adapters.in_memory_event_store import InMemoryEventStore
from cora.infrastructure.event_envelope import to_new_event
from cora.run import RunHandlers, UnauthorizedError, wire_run
from cora.run.aggregates.run import (
    HOLD_CAUSE_OPERATOR,
    RunCannotHoldError,
    RunNotFoundError,
    derive_claim_id,
)
from cora.run.aggregates.run.events import (
    RunHeld,
    RunStarted,
    event_type_name,
    to_payload,
)
from cora.run.features import hold_run
from cora.run.features.hold_run import HoldRun
from tests.unit._helpers import build_deps

_NOW = datetime(2026, 5, 11, 12, 0, 0, tzinfo=UTC)
_RUN_ID = UUID("01900000-0000-7000-8000-00000000fb01")
_HELD_EVENT_ID = UUID("01900000-0000-7000-8000-00000000fb02")
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


async def _seed_run_held(
    store: InMemoryEventStore, run_id: UUID, *, cause: str | None = None
) -> None:
    """Seed a Run held by `cause`; `None` seeds a legacy claimless hold."""
    await _seed_run_started(store, run_id)
    held = RunHeld(
        run_id=run_id,
        occurred_at=_NOW,
        claim_id=derive_claim_id(run_id, cause) if cause is not None else None,
        cause=cause,
    )
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


@pytest.mark.unit
async def test_handler_returns_none_on_success() -> None:
    store = InMemoryEventStore()
    await _seed_run_started(store, _RUN_ID)
    deps = build_deps(ids=[_HELD_EVENT_ID], now=_NOW, event_store=store)

    result = await hold_run.bind(deps)(
        HoldRun(run_id=_RUN_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert result is None


@pytest.mark.unit
async def test_handler_appends_run_held_event() -> None:
    store = InMemoryEventStore()
    await _seed_run_started(store, _RUN_ID)
    deps = build_deps(ids=[_HELD_EVENT_ID], now=_NOW, event_store=store)

    await hold_run.bind(deps)(
        HoldRun(run_id=_RUN_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    events, version = await store.load("Run", _RUN_ID)
    assert version == 2
    assert [e.event_type for e in events] == ["RunStarted", "RunHeld"]
    held = events[1]
    assert held.event_id == _HELD_EVENT_ID
    assert held.metadata == {"command": "HoldRun"}


@pytest.mark.unit
async def test_handler_raises_run_not_found_when_run_does_not_exist() -> None:
    deps = build_deps(ids=[_HELD_EVENT_ID], now=_NOW)
    handler = hold_run.bind(deps)

    with pytest.raises(RunNotFoundError):
        await handler(
            HoldRun(run_id=_RUN_ID),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_handler_raises_cannot_hold_when_this_cause_already_holds() -> None:
    """Alternation is per claim: the same concern cannot hold twice."""
    store = InMemoryEventStore()
    await _seed_run_held(store, _RUN_ID, cause=HOLD_CAUSE_OPERATOR)
    deps = build_deps(ids=[_HELD_EVENT_ID], now=_NOW, event_store=store)

    with pytest.raises(RunCannotHoldError):
        await hold_run.bind(deps)(
            HoldRun(run_id=_RUN_ID),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_handler_raises_unauthorized_on_deny() -> None:
    store = InMemoryEventStore()
    await _seed_run_started(store, _RUN_ID)
    deny_deps = build_deps(ids=[_HELD_EVENT_ID], now=_NOW, event_store=store, deny=True)

    with pytest.raises(UnauthorizedError) as exc_info:
        await hold_run.bind(deny_deps)(
            HoldRun(run_id=_RUN_ID),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    assert exc_info.value.reason == "denied for test"


@pytest.mark.unit
async def test_handler_propagates_causation_id_to_appended_event() -> None:
    causation = UUID("01900000-0000-7000-8000-0000000000bb")
    store = InMemoryEventStore()
    await _seed_run_started(store, _RUN_ID)
    deps = build_deps(ids=[_HELD_EVENT_ID], now=_NOW, event_store=store)

    await hold_run.bind(deps)(
        HoldRun(run_id=_RUN_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
        causation_id=causation,
    )

    events, _ = await store.load("Run", _RUN_ID)
    assert events[1].causation_id == causation


@pytest.mark.unit
def test_wire_run_includes_hold_run() -> None:
    deps = build_deps(ids=[_HELD_EVENT_ID], now=_NOW)
    handlers = wire_run(deps)
    assert isinstance(handlers, RunHandlers)
    assert callable(handlers.hold_run)
