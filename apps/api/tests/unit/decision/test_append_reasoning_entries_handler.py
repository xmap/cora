"""Unit tests for the `append_reasoning_entries` application handler.

Mirrors register_decision handler tests + adds the lazy-open and
batch behaviors specific to 8c-b.
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.decision import DecisionHandlers, UnauthorizedError, wire_decision
from cora.decision.aggregates.decision import (
    DECISION_REASONING_OPERATION_CHAT,
    LOGBOOK_KIND_REASONING,
    DecisionNotFoundError,
    InMemoryReasoningStore,
    fold,
    from_stored,
    load_decision,
)
from cora.decision.aggregates.decision.events import (
    DecisionRegistered,
    event_type_name,
    to_payload,
)
from cora.decision.features import append_reasoning_entries
from cora.decision.features.append_reasoning_entries import (
    AppendReasoningEntries,
    ReasoningEntryInput,
)
from cora.infrastructure.adapters.in_memory_event_store import InMemoryEventStore
from cora.infrastructure.event_envelope import to_new_event
from cora.shared.identity import ActorId
from tests.unit._helpers import build_deps

_NOW = datetime(2026, 5, 12, 12, 0, 0, tzinfo=UTC)
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")
_DECISION_ID = UUID("01900000-0000-7000-8000-000000008c01")
_LOGBOOK_ID = UUID("01900000-0000-7000-8000-000000008c02")
_LOGBOOK_OPEN_EVENT_ID = UUID("01900000-0000-7000-8000-000000008c03")


def _entry(**overrides: object) -> ReasoningEntryInput:
    base: dict[str, object] = {
        "event_id": uuid4(),
        "occurred_at": _NOW,
        "operation_name": DECISION_REASONING_OPERATION_CHAT,
        "provider_name": "anthropic",
        "request_model": "claude-opus-4-7",
    }
    base.update(overrides)
    return ReasoningEntryInput(**base)  # type: ignore[arg-type]


async def _seed_decision(store: InMemoryEventStore, decision_id: UUID) -> None:
    event = DecisionRegistered(
        decision_id=decision_id,
        decided_by=ActorId(uuid4()),
        context="RecipeApproval",
        choice="Approved",
        parent_id=None,
        override_kind=None,
        rule=None,
        reasoning=None,
        confidence=None,
        confidence_source=None,
        alternatives=(),
        inputs=None,
        reasoning_signature=None,
        occurred_at=_NOW,
    )
    new_event = to_new_event(
        event_type=event_type_name(event),
        payload=to_payload(event),
        occurred_at=_NOW,
        event_id=uuid4(),
        command_name="RegisterDecision",
        correlation_id=_CORRELATION_ID,
        principal_id=uuid4(),
    )
    await store.append(
        stream_type="Decision", stream_id=decision_id, expected_version=0, events=[new_event]
    )


# ---------- Happy path: lazy open on first append ----------


@pytest.mark.unit
async def test_handler_emits_logbook_opened_on_first_append() -> None:
    """First append on a Decision with no reasoning logbook emits
    DecisionLogbookOpened to the Decision stream + appends the entry."""
    event_store = InMemoryEventStore()
    await _seed_decision(event_store, _DECISION_ID)
    reasoning_store = InMemoryReasoningStore()
    deps = build_deps(ids=[_LOGBOOK_ID, _LOGBOOK_OPEN_EVENT_ID], now=_NOW, event_store=event_store)

    count = await append_reasoning_entries.bind(deps, reasoning_store=reasoning_store)(
        AppendReasoningEntries(decision_id=_DECISION_ID, entries=(_entry(),)),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert count == 1

    # Decision stream now has 2 events: registered + logbook opened.
    stored, version = await event_store.load("Decision", _DECISION_ID)
    assert version == 2
    assert [e.event_type for e in stored] == ["DecisionRegistered", "DecisionLogbookOpened"]
    assert stored[1].event_id == _LOGBOOK_OPEN_EVENT_ID

    # Reasoning store has the appended entry with the open's logbook_id.
    rows = reasoning_store.all()
    assert len(rows) == 1
    assert rows[0].decision_id == _DECISION_ID
    assert rows[0].logbook_id == _LOGBOOK_ID


@pytest.mark.unit
async def test_handler_skips_open_when_logbook_already_present() -> None:
    """Second append (reasoning logbook already open) appends without
    re-emitting DecisionLogbookOpened."""
    event_store = InMemoryEventStore()
    await _seed_decision(event_store, _DECISION_ID)
    reasoning_store = InMemoryReasoningStore()
    deps_first = build_deps(
        ids=[_LOGBOOK_ID, _LOGBOOK_OPEN_EVENT_ID], now=_NOW, event_store=event_store
    )
    await append_reasoning_entries.bind(deps_first, reasoning_store=reasoning_store)(
        AppendReasoningEntries(decision_id=_DECISION_ID, entries=(_entry(),)),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    # Second call with a fresh deps (fresh id_generator).
    deps_second = build_deps(
        ids=[_LOGBOOK_ID, _LOGBOOK_OPEN_EVENT_ID, uuid4(), uuid4()],
        now=_NOW,
        event_store=event_store,
    )
    count = await append_reasoning_entries.bind(deps_second, reasoning_store=reasoning_store)(
        AppendReasoningEntries(decision_id=_DECISION_ID, entries=(_entry(),)),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert count == 1

    # Decision stream still only has 2 events (no second open).
    stored, version = await event_store.load("Decision", _DECISION_ID)
    assert version == 2
    assert [e.event_type for e in stored] == ["DecisionRegistered", "DecisionLogbookOpened"]

    # Both entries land with the SAME logbook_id.
    rows = reasoning_store.all()
    assert len(rows) == 2
    assert rows[0].logbook_id == rows[1].logbook_id == _LOGBOOK_ID


# ---------- Batch ----------


@pytest.mark.unit
async def test_handler_appends_batch_in_one_call() -> None:
    """Batch of N entries lands as N rows + ONE logbook open."""
    event_store = InMemoryEventStore()
    await _seed_decision(event_store, _DECISION_ID)
    reasoning_store = InMemoryReasoningStore()
    deps = build_deps(ids=[_LOGBOOK_ID, _LOGBOOK_OPEN_EVENT_ID], now=_NOW, event_store=event_store)

    entries = (_entry(), _entry(), _entry())
    count = await append_reasoning_entries.bind(deps, reasoning_store=reasoning_store)(
        AppendReasoningEntries(decision_id=_DECISION_ID, entries=entries),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert count == 3
    assert len(reasoning_store.all()) == 3
    # Only one DecisionLogbookOpened event for the whole batch.
    stored, _ = await event_store.load("Decision", _DECISION_ID)
    open_events = [e for e in stored if e.event_type == "DecisionLogbookOpened"]
    assert len(open_events) == 1


@pytest.mark.unit
async def test_handler_dedups_silently_on_repeated_event_id() -> None:
    """Producer retry with the same event_id is a silent no-op
    (first write wins via InMemoryReasoningStore.setdefault)."""
    event_store = InMemoryEventStore()
    await _seed_decision(event_store, _DECISION_ID)
    reasoning_store = InMemoryReasoningStore()
    shared_event_id = uuid4()
    entry_first = _entry(event_id=shared_event_id, request_model="claude-opus-4-7")
    entry_second = _entry(event_id=shared_event_id, request_model="claude-sonnet-4-6")

    deps = build_deps(ids=[_LOGBOOK_ID, _LOGBOOK_OPEN_EVENT_ID], now=_NOW, event_store=event_store)
    await append_reasoning_entries.bind(deps, reasoning_store=reasoning_store)(
        AppendReasoningEntries(decision_id=_DECISION_ID, entries=(entry_first,)),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    deps2 = build_deps(
        ids=[_LOGBOOK_ID, _LOGBOOK_OPEN_EVENT_ID, uuid4(), uuid4()],
        now=_NOW,
        event_store=event_store,
    )
    await append_reasoning_entries.bind(deps2, reasoning_store=reasoning_store)(
        AppendReasoningEntries(decision_id=_DECISION_ID, entries=(entry_second,)),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    rows = reasoning_store.all()
    assert len(rows) == 1
    # First write wins; second was deduped silently.
    assert rows[0].request_model == "claude-opus-4-7"


# ---------- Envelope threading ----------


@pytest.mark.unit
async def test_handler_threads_correlation_id_into_entries() -> None:
    """Each row's correlation_id matches the envelope's correlation_id."""
    event_store = InMemoryEventStore()
    await _seed_decision(event_store, _DECISION_ID)
    reasoning_store = InMemoryReasoningStore()
    deps = build_deps(ids=[_LOGBOOK_ID, _LOGBOOK_OPEN_EVENT_ID], now=_NOW, event_store=event_store)
    await append_reasoning_entries.bind(deps, reasoning_store=reasoning_store)(
        AppendReasoningEntries(decision_id=_DECISION_ID, entries=(_entry(), _entry())),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    for row in reasoning_store.all():
        assert row.correlation_id == _CORRELATION_ID


@pytest.mark.unit
async def test_handler_threads_causation_id_into_entries() -> None:
    causation = UUID("01900000-0000-7000-8000-0000000000bb")
    event_store = InMemoryEventStore()
    await _seed_decision(event_store, _DECISION_ID)
    reasoning_store = InMemoryReasoningStore()
    deps = build_deps(ids=[_LOGBOOK_ID, _LOGBOOK_OPEN_EVENT_ID], now=_NOW, event_store=event_store)
    await append_reasoning_entries.bind(deps, reasoning_store=reasoning_store)(
        AppendReasoningEntries(decision_id=_DECISION_ID, entries=(_entry(),)),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
        causation_id=causation,
    )
    rows = reasoning_store.all()
    assert rows[0].causation_id == causation


# ---------- 404 ----------


@pytest.mark.unit
async def test_handler_raises_decision_not_found_for_unknown_id() -> None:
    deps = build_deps(ids=[_LOGBOOK_ID, _LOGBOOK_OPEN_EVENT_ID], now=_NOW)
    reasoning_store = InMemoryReasoningStore()
    with pytest.raises(DecisionNotFoundError) as exc_info:
        await append_reasoning_entries.bind(deps, reasoning_store=reasoning_store)(
            AppendReasoningEntries(decision_id=uuid4(), entries=(_entry(),)),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    assert "not found" in str(exc_info.value).lower()
    assert reasoning_store.all() == []


# ---------- Authz ----------


@pytest.mark.unit
async def test_handler_retries_on_concurrent_logbook_open_race() -> None:
    """Two parallel first-appends both try to emit DecisionLogbookOpened;
    the second loses on optimistic concurrency. The handler retries from
    load, the second pass sees the logbook now open + skips the open
    step. Models the documented self-healing behavior."""
    from cora.infrastructure.ports.event_store import ConcurrencyError, NewEvent

    event_store = InMemoryEventStore()
    await _seed_decision(event_store, _DECISION_ID)
    reasoning_store = InMemoryReasoningStore()

    # Wrap the event_store: on the first .append() call, simulate a
    # concurrent writer winning the race by appending DecisionLogbookOpened
    # ourselves with a different logbook_id, then raising ConcurrencyError.
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
        if not fired["yes"] and any(e.event_type == "DecisionLogbookOpened" for e in events):
            fired["yes"] = True
            # Simulate the conflicting writer landing first.
            from cora.decision.aggregates.decision import DecisionLogbookOpened
            from cora.decision.aggregates.decision import (
                event_type_name as agg_event_type_name,
            )
            from cora.decision.aggregates.decision import to_payload as agg_to_payload

            conflict_event = DecisionLogbookOpened(
                decision_id=stream_id,
                logbook_id=concurrent_logbook_id,
                kind=LOGBOOK_KIND_REASONING,
                schema=__import__(
                    "cora.decision.aggregates.decision",
                    fromlist=["REASONING_LOGBOOK_SCHEMA"],
                ).REASONING_LOGBOOK_SCHEMA,
                occurred_at=_NOW,
            )
            new_event = to_new_event(
                event_type=agg_event_type_name(conflict_event),
                payload=agg_to_payload(conflict_event),
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
    count = await append_reasoning_entries.bind(deps, reasoning_store=reasoning_store)(
        AppendReasoningEntries(decision_id=_DECISION_ID, entries=(_entry(),)),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    # Entry was appended despite the race.
    assert count == 1
    rows = reasoning_store.all()
    assert len(rows) == 1
    # The retry's reload saw the conflicting writer's logbook id and used IT,
    # not the originally-allocated one.
    assert rows[0].logbook_id == concurrent_logbook_id


@pytest.mark.unit
async def test_handler_raises_unauthorized_on_deny() -> None:
    event_store = InMemoryEventStore()
    await _seed_decision(event_store, _DECISION_ID)
    reasoning_store = InMemoryReasoningStore()
    deps = build_deps(
        ids=[_LOGBOOK_ID, _LOGBOOK_OPEN_EVENT_ID], now=_NOW, event_store=event_store, deny=True
    )
    with pytest.raises(UnauthorizedError) as exc_info:
        await append_reasoning_entries.bind(deps, reasoning_store=reasoning_store)(
            AppendReasoningEntries(decision_id=_DECISION_ID, entries=(_entry(),)),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    assert exc_info.value.reason == "denied for test"
    assert reasoning_store.all() == []


# ---------- Decision aggregate state reflects logbook ----------


@pytest.mark.unit
async def test_decision_state_after_append_carries_reasoning_logbook() -> None:
    """The Decision aggregate's logbooks dict gets the new entry
    after the lazy open lands; subsequent `load_decision` reads it."""
    event_store = InMemoryEventStore()
    await _seed_decision(event_store, _DECISION_ID)
    reasoning_store = InMemoryReasoningStore()
    deps = build_deps(ids=[_LOGBOOK_ID, _LOGBOOK_OPEN_EVENT_ID], now=_NOW, event_store=event_store)
    await append_reasoning_entries.bind(deps, reasoning_store=reasoning_store)(
        AppendReasoningEntries(decision_id=_DECISION_ID, entries=(_entry(),)),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    state = await load_decision(event_store, _DECISION_ID)
    assert state is not None
    assert state.logbooks == {LOGBOOK_KIND_REASONING: _LOGBOOK_ID}


# ---------- Wire bundle ----------


@pytest.mark.unit
def test_wire_decision_includes_append_reasoning_entries() -> None:
    deps = build_deps(ids=[uuid4()], now=_NOW)
    handlers = wire_decision(deps)
    assert isinstance(handlers, DecisionHandlers)
    assert callable(handlers.append_reasoning_entries)


# ---------- Forward-compat: load + fold via from_stored ----------


@pytest.mark.unit
async def test_decision_logbook_opened_round_trips_through_event_store() -> None:
    """The DecisionLogbookOpened event written via to_payload reads
    back via from_stored (load_decision exercises this fully)."""
    event_store = InMemoryEventStore()
    await _seed_decision(event_store, _DECISION_ID)
    reasoning_store = InMemoryReasoningStore()
    deps = build_deps(ids=[_LOGBOOK_ID, _LOGBOOK_OPEN_EVENT_ID], now=_NOW, event_store=event_store)
    await append_reasoning_entries.bind(deps, reasoning_store=reasoning_store)(
        AppendReasoningEntries(decision_id=_DECISION_ID, entries=(_entry(),)),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    stored, _ = await event_store.load("Decision", _DECISION_ID)
    events = [from_stored(s) for s in stored]
    state = fold(events)
    assert state is not None
    assert LOGBOOK_KIND_REASONING in state.logbooks
