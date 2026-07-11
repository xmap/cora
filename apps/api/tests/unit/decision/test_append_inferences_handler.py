"""Unit tests for the `append_inferences` application handler.

Mirrors register_decision handler tests + adds the lazy-open and
batch behaviors specific to 8c-b.
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.decision import DecisionHandlers, UnauthorizedError, wire_decision
from cora.decision.aggregates.decision import (
    DECISION_REASONING_OPERATION_CHAT,
    LOGBOOK_KIND_INFERENCE,
    DecisionNotFoundError,
    InMemoryInferenceStore,
    fold,
    from_stored,
    load_decision,
)
from cora.decision.aggregates.decision.events import (
    DecisionRegistered,
    event_type_name,
    to_payload,
)
from cora.decision.errors import InferenceAgentMismatchError
from cora.decision.features import append_inferences
from cora.decision.features.append_inferences import (
    AppendInferences,
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
    inference_store = InMemoryInferenceStore()
    deps = build_deps(ids=[_LOGBOOK_ID, _LOGBOOK_OPEN_EVENT_ID], now=_NOW, event_store=event_store)

    count = await append_inferences.bind(deps, inference_store=inference_store)(
        AppendInferences(decision_id=_DECISION_ID, entries=(_entry(),)),
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
    rows = inference_store.all()
    assert len(rows) == 1
    assert rows[0].decision_id == _DECISION_ID
    assert rows[0].logbook_id == _LOGBOOK_ID


@pytest.mark.unit
async def test_handler_skips_open_when_logbook_already_present() -> None:
    """Second append (reasoning logbook already open) appends without
    re-emitting DecisionLogbookOpened."""
    event_store = InMemoryEventStore()
    await _seed_decision(event_store, _DECISION_ID)
    inference_store = InMemoryInferenceStore()
    deps_first = build_deps(
        ids=[_LOGBOOK_ID, _LOGBOOK_OPEN_EVENT_ID], now=_NOW, event_store=event_store
    )
    await append_inferences.bind(deps_first, inference_store=inference_store)(
        AppendInferences(decision_id=_DECISION_ID, entries=(_entry(),)),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    # Second call with a fresh deps (fresh id_generator).
    deps_second = build_deps(
        ids=[_LOGBOOK_ID, _LOGBOOK_OPEN_EVENT_ID, uuid4(), uuid4()],
        now=_NOW,
        event_store=event_store,
    )
    count = await append_inferences.bind(deps_second, inference_store=inference_store)(
        AppendInferences(decision_id=_DECISION_ID, entries=(_entry(),)),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert count == 1

    # Decision stream still only has 2 events (no second open).
    stored, version = await event_store.load("Decision", _DECISION_ID)
    assert version == 2
    assert [e.event_type for e in stored] == ["DecisionRegistered", "DecisionLogbookOpened"]

    # Both entries land with the SAME logbook_id.
    rows = inference_store.all()
    assert len(rows) == 2
    assert rows[0].logbook_id == rows[1].logbook_id == _LOGBOOK_ID


# ---------- Batch ----------


@pytest.mark.unit
async def test_handler_appends_batch_in_one_call() -> None:
    """Batch of N entries lands as N rows + ONE logbook open."""
    event_store = InMemoryEventStore()
    await _seed_decision(event_store, _DECISION_ID)
    inference_store = InMemoryInferenceStore()
    deps = build_deps(ids=[_LOGBOOK_ID, _LOGBOOK_OPEN_EVENT_ID], now=_NOW, event_store=event_store)

    entries = (_entry(), _entry(), _entry())
    count = await append_inferences.bind(deps, inference_store=inference_store)(
        AppendInferences(decision_id=_DECISION_ID, entries=entries),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert count == 3
    assert len(inference_store.all()) == 3
    # Only one DecisionLogbookOpened event for the whole batch.
    stored, _ = await event_store.load("Decision", _DECISION_ID)
    open_events = [e for e in stored if e.event_type == "DecisionLogbookOpened"]
    assert len(open_events) == 1


@pytest.mark.unit
async def test_handler_dedups_silently_on_repeated_event_id() -> None:
    """Producer retry with the same event_id is a silent no-op
    (first write wins via InMemoryInferenceStore.setdefault)."""
    event_store = InMemoryEventStore()
    await _seed_decision(event_store, _DECISION_ID)
    inference_store = InMemoryInferenceStore()
    shared_event_id = uuid4()
    entry_first = _entry(event_id=shared_event_id, request_model="claude-opus-4-7")
    entry_second = _entry(event_id=shared_event_id, request_model="claude-sonnet-4-6")

    deps = build_deps(ids=[_LOGBOOK_ID, _LOGBOOK_OPEN_EVENT_ID], now=_NOW, event_store=event_store)
    await append_inferences.bind(deps, inference_store=inference_store)(
        AppendInferences(decision_id=_DECISION_ID, entries=(entry_first,)),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    deps2 = build_deps(
        ids=[_LOGBOOK_ID, _LOGBOOK_OPEN_EVENT_ID, uuid4(), uuid4()],
        now=_NOW,
        event_store=event_store,
    )
    await append_inferences.bind(deps2, inference_store=inference_store)(
        AppendInferences(decision_id=_DECISION_ID, entries=(entry_second,)),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    rows = inference_store.all()
    assert len(rows) == 1
    # First write wins; second was deduped silently.
    assert rows[0].request_model == "claude-opus-4-7"


# ---------- Envelope threading ----------


@pytest.mark.unit
async def test_handler_threads_correlation_id_into_entries() -> None:
    """Each row's correlation_id matches the envelope's correlation_id."""
    event_store = InMemoryEventStore()
    await _seed_decision(event_store, _DECISION_ID)
    inference_store = InMemoryInferenceStore()
    deps = build_deps(ids=[_LOGBOOK_ID, _LOGBOOK_OPEN_EVENT_ID], now=_NOW, event_store=event_store)
    await append_inferences.bind(deps, inference_store=inference_store)(
        AppendInferences(decision_id=_DECISION_ID, entries=(_entry(), _entry())),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    for row in inference_store.all():
        assert row.correlation_id == _CORRELATION_ID


@pytest.mark.unit
async def test_handler_threads_causation_id_into_entries() -> None:
    causation = UUID("01900000-0000-7000-8000-0000000000bb")
    event_store = InMemoryEventStore()
    await _seed_decision(event_store, _DECISION_ID)
    inference_store = InMemoryInferenceStore()
    deps = build_deps(ids=[_LOGBOOK_ID, _LOGBOOK_OPEN_EVENT_ID], now=_NOW, event_store=event_store)
    await append_inferences.bind(deps, inference_store=inference_store)(
        AppendInferences(decision_id=_DECISION_ID, entries=(_entry(),)),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
        causation_id=causation,
    )
    rows = inference_store.all()
    assert rows[0].causation_id == causation


# ---------- 404 ----------


@pytest.mark.unit
async def test_handler_raises_decision_not_found_for_unknown_id() -> None:
    deps = build_deps(ids=[_LOGBOOK_ID, _LOGBOOK_OPEN_EVENT_ID], now=_NOW)
    inference_store = InMemoryInferenceStore()
    with pytest.raises(DecisionNotFoundError) as exc_info:
        await append_inferences.bind(deps, inference_store=inference_store)(
            AppendInferences(decision_id=uuid4(), entries=(_entry(),)),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    assert "not found" in str(exc_info.value).lower()
    assert inference_store.all() == []


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
    inference_store = InMemoryInferenceStore()

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
                kind=LOGBOOK_KIND_INFERENCE,
                schema=__import__(
                    "cora.decision.aggregates.decision",
                    fromlist=["INFERENCE_LOGBOOK_SCHEMA"],
                ).INFERENCE_LOGBOOK_SCHEMA,
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
    count = await append_inferences.bind(deps, inference_store=inference_store)(
        AppendInferences(decision_id=_DECISION_ID, entries=(_entry(),)),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    # Entry was appended despite the race.
    assert count == 1
    rows = inference_store.all()
    assert len(rows) == 1
    # The retry's reload saw the conflicting writer's logbook id and used IT,
    # not the originally-allocated one.
    assert rows[0].logbook_id == concurrent_logbook_id


@pytest.mark.unit
async def test_handler_raises_unauthorized_on_deny() -> None:
    event_store = InMemoryEventStore()
    await _seed_decision(event_store, _DECISION_ID)
    inference_store = InMemoryInferenceStore()
    deps = build_deps(
        ids=[_LOGBOOK_ID, _LOGBOOK_OPEN_EVENT_ID], now=_NOW, event_store=event_store, deny=True
    )
    with pytest.raises(UnauthorizedError) as exc_info:
        await append_inferences.bind(deps, inference_store=inference_store)(
            AppendInferences(decision_id=_DECISION_ID, entries=(_entry(),)),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    assert exc_info.value.reason == "denied for test"
    assert inference_store.all() == []


# ---------- Agent attribution is principal-bound ----------


@pytest.mark.unit
async def test_handler_rejects_entry_whose_agent_id_is_not_the_principal() -> None:
    """Spend rows are summed per agent_id by the budget gate, so a
    producer may only attribute entries to itself. A mismatched
    agent_id rejects the batch before any write: no logbook open, no
    stored rows."""
    event_store = InMemoryEventStore()
    await _seed_decision(event_store, _DECISION_ID)
    inference_store = InMemoryInferenceStore()
    deps = build_deps(ids=[_LOGBOOK_ID, _LOGBOOK_OPEN_EVENT_ID], now=_NOW, event_store=event_store)
    victim_agent_id = str(uuid4())
    with pytest.raises(InferenceAgentMismatchError) as exc_info:
        await append_inferences.bind(deps, inference_store=inference_store)(
            AppendInferences(
                decision_id=_DECISION_ID,
                entries=(_entry(agent_id=victim_agent_id, cost_usd=999.0),),
            ),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    assert exc_info.value.entry_agent_id == victim_agent_id
    assert exc_info.value.principal_id == str(_PRINCIPAL_ID)
    assert inference_store.all() == []
    state = await load_decision(event_store, _DECISION_ID)
    assert state is not None
    assert state.logbooks == {}


@pytest.mark.unit
async def test_handler_rejects_whole_batch_when_one_entry_mismatches() -> None:
    """Atomic rejection: one spoofed entry poisons the batch; the
    producer's own well-attributed entries in it are NOT stored."""
    event_store = InMemoryEventStore()
    await _seed_decision(event_store, _DECISION_ID)
    inference_store = InMemoryInferenceStore()
    deps = build_deps(ids=[_LOGBOOK_ID, _LOGBOOK_OPEN_EVENT_ID], now=_NOW, event_store=event_store)
    with pytest.raises(InferenceAgentMismatchError):
        await append_inferences.bind(deps, inference_store=inference_store)(
            AppendInferences(
                decision_id=_DECISION_ID,
                entries=(
                    _entry(agent_id=str(_PRINCIPAL_ID)),
                    _entry(agent_id=str(uuid4())),
                ),
            ),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    assert inference_store.all() == []


@pytest.mark.unit
async def test_handler_accepts_self_reported_and_agentless_entries() -> None:
    """The binding never blocks the legitimate shapes: agent_id equal
    to the principal (self-report) and agent_id=None (no agent claim,
    operator/tool provenance) both append."""
    event_store = InMemoryEventStore()
    await _seed_decision(event_store, _DECISION_ID)
    inference_store = InMemoryInferenceStore()
    deps = build_deps(ids=[_LOGBOOK_ID, _LOGBOOK_OPEN_EVENT_ID], now=_NOW, event_store=event_store)
    count = await append_inferences.bind(deps, inference_store=inference_store)(
        AppendInferences(
            decision_id=_DECISION_ID,
            entries=(
                _entry(agent_id=str(_PRINCIPAL_ID), cost_usd=0.01),
                _entry(agent_id=None),
            ),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert count == 2
    assert len(inference_store.all()) == 2


# ---------- Decision aggregate state reflects logbook ----------


@pytest.mark.unit
async def test_decision_state_after_append_carries_reasoning_logbook() -> None:
    """The Decision aggregate's logbooks dict gets the new entry
    after the lazy open lands; subsequent `load_decision` reads it."""
    event_store = InMemoryEventStore()
    await _seed_decision(event_store, _DECISION_ID)
    inference_store = InMemoryInferenceStore()
    deps = build_deps(ids=[_LOGBOOK_ID, _LOGBOOK_OPEN_EVENT_ID], now=_NOW, event_store=event_store)
    await append_inferences.bind(deps, inference_store=inference_store)(
        AppendInferences(decision_id=_DECISION_ID, entries=(_entry(),)),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    state = await load_decision(event_store, _DECISION_ID)
    assert state is not None
    assert state.logbooks == {LOGBOOK_KIND_INFERENCE: _LOGBOOK_ID}


# ---------- Wire bundle ----------


@pytest.mark.unit
def test_wire_decision_includes_append_reasoning_entries() -> None:
    deps = build_deps(ids=[uuid4()], now=_NOW)
    handlers = wire_decision(deps)
    assert isinstance(handlers, DecisionHandlers)
    assert callable(handlers.append_inferences)


# ---------- Forward-compat: load + fold via from_stored ----------


@pytest.mark.unit
async def test_decision_logbook_opened_round_trips_through_event_store() -> None:
    """The DecisionLogbookOpened event written via to_payload reads
    back via from_stored (load_decision exercises this fully)."""
    event_store = InMemoryEventStore()
    await _seed_decision(event_store, _DECISION_ID)
    inference_store = InMemoryInferenceStore()
    deps = build_deps(ids=[_LOGBOOK_ID, _LOGBOOK_OPEN_EVENT_ID], now=_NOW, event_store=event_store)
    await append_inferences.bind(deps, inference_store=inference_store)(
        AppendInferences(decision_id=_DECISION_ID, entries=(_entry(),)),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    stored, _ = await event_store.load("Decision", _DECISION_ID)
    events = [from_stored(s) for s in stored]
    state = fold(events)
    assert state is not None
    assert LOGBOOK_KIND_INFERENCE in state.logbooks
