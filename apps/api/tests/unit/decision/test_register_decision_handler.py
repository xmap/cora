"""Unit tests for the `register_decision` application handler."""

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import pytest

from cora.access.aggregates.actor import ActorKind
from cora.access.aggregates.actor.events import (
    ActorRegistered,
)
from cora.access.aggregates.actor.events import (
    event_type_name as actor_event_type_name,
)
from cora.access.aggregates.actor.events import (
    to_payload as actor_to_payload,
)
from cora.decision import DecisionHandlers, UnauthorizedError, wire_decision
from cora.decision.aggregates.decision import (
    DeciderActorNotFoundError,
    DecisionParentNotFoundError,
)
from cora.decision.aggregates.decision.events import (
    DecisionRegistered,
    event_type_name,
    to_payload,
)
from cora.decision.features import register_decision
from cora.decision.features.register_decision import RegisterDecision
from cora.infrastructure.adapters.in_memory_event_store import InMemoryEventStore
from cora.infrastructure.event_envelope import to_new_event
from cora.shared.identity import ActorId
from tests.unit._helpers import build_deps

_NOW = datetime(2026, 5, 11, 12, 0, 0, tzinfo=UTC)
_DECISION_ID = UUID("01900000-0000-7000-8000-000000008a01")
_REG_EVENT_ID = UUID("01900000-0000-7000-8000-000000008a02")
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")


def _good_command(**overrides: Any) -> RegisterDecision:
    base: dict[str, Any] = {
        "decided_by": ActorId(uuid4()),
        "context": "RecipeApproval",
        "choice": "Approved",
        "parent_id": None,
        "override_kind": None,
        "rule": None,
        "reasoning": None,
        "confidence": None,
        "confidence_source": None,
        "alternatives": (),
        "inputs": None,
        "reasoning_signature": None,
    }
    base.update(overrides)
    return RegisterDecision(**base)


async def _seed_actor(store: InMemoryEventStore, actor_id: UUID) -> None:
    event = ActorRegistered(actor_id=actor_id, occurred_at=_NOW, kind=ActorKind.HUMAN)
    new_event = to_new_event(
        event_type=actor_event_type_name(event),
        payload=actor_to_payload(event),
        occurred_at=_NOW,
        event_id=uuid4(),
        command_name="RegisterActor",
        correlation_id=_CORRELATION_ID,
        principal_id=uuid4(),
    )
    await store.append(
        stream_type="Actor", stream_id=actor_id, expected_version=0, events=[new_event]
    )


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


# ---------- Happy path ----------


@pytest.mark.unit
async def test_handler_returns_new_decision_id_on_success() -> None:
    store = InMemoryEventStore()
    actor_id = uuid4()
    await _seed_actor(store, actor_id)
    deps = build_deps(ids=[_DECISION_ID, _REG_EVENT_ID], now=_NOW, event_store=store)
    decision_id = await register_decision.bind(deps)(
        _good_command(decided_by=ActorId(actor_id)),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert decision_id == _DECISION_ID


@pytest.mark.unit
async def test_handler_appends_decision_registered_event() -> None:
    store = InMemoryEventStore()
    actor_id = uuid4()
    await _seed_actor(store, actor_id)
    deps = build_deps(ids=[_DECISION_ID, _REG_EVENT_ID], now=_NOW, event_store=store)
    await register_decision.bind(deps)(
        _good_command(decided_by=ActorId(actor_id), choice="Conditionally approved"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    events, version = await store.load("Decision", _DECISION_ID)
    assert version == 1
    assert [e.event_type for e in events] == ["DecisionRegistered"]
    registered = events[0]
    assert registered.event_id == _REG_EVENT_ID
    assert registered.metadata == {"command": "RegisterDecision"}
    assert registered.payload["choice"] == "Conditionally approved"
    assert registered.payload["decided_by"] == str(actor_id)


@pytest.mark.unit
async def test_handler_propagates_causation_id() -> None:
    causation = UUID("01900000-0000-7000-8000-0000000000bb")
    store = InMemoryEventStore()
    actor_id = uuid4()
    await _seed_actor(store, actor_id)
    deps = build_deps(ids=[_DECISION_ID, _REG_EVENT_ID], now=_NOW, event_store=store)
    await register_decision.bind(deps)(
        _good_command(decided_by=ActorId(actor_id)),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
        causation_id=causation,
    )
    events, _ = await store.load("Decision", _DECISION_ID)
    assert events[0].causation_id == causation


# ---------- Authz ----------


@pytest.mark.unit
async def test_handler_raises_unauthorized_on_deny() -> None:
    store = InMemoryEventStore()
    actor_id = uuid4()
    await _seed_actor(store, actor_id)
    deny_deps = build_deps(
        ids=[_DECISION_ID, _REG_EVENT_ID], now=_NOW, event_store=store, deny=True
    )
    with pytest.raises(UnauthorizedError) as exc_info:
        await register_decision.bind(deny_deps)(
            _good_command(decided_by=ActorId(actor_id)),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    assert exc_info.value.reason == "denied for test"
    events, _ = await store.load("Decision", _DECISION_ID)
    assert events == []


# ---------- Cross-aggregate validation ----------


@pytest.mark.unit
async def test_handler_raises_actor_not_found_when_actor_missing() -> None:
    deps = build_deps(ids=[_DECISION_ID, _REG_EVENT_ID], now=_NOW)
    missing_actor = uuid4()
    with pytest.raises(DeciderActorNotFoundError) as exc_info:
        await register_decision.bind(deps)(
            _good_command(decided_by=ActorId(missing_actor)),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    assert exc_info.value.decided_by == missing_actor


@pytest.mark.unit
async def test_handler_raises_parent_not_found_when_parent_missing() -> None:
    store = InMemoryEventStore()
    actor_id = uuid4()
    await _seed_actor(store, actor_id)
    deps = build_deps(ids=[_DECISION_ID, _REG_EVENT_ID], now=_NOW, event_store=store)
    missing_parent = uuid4()
    with pytest.raises(DecisionParentNotFoundError) as exc_info:
        await register_decision.bind(deps)(
            _good_command(
                decided_by=ActorId(actor_id),
                parent_id=missing_parent,
                override_kind="correction",
            ),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    assert exc_info.value.parent_id == missing_parent


@pytest.mark.unit
async def test_handler_loads_existing_parent_and_appends_with_link() -> None:
    store = InMemoryEventStore()
    actor_id = uuid4()
    parent_id = uuid4()
    await _seed_actor(store, actor_id)
    await _seed_decision(store, parent_id)
    deps = build_deps(ids=[_DECISION_ID, _REG_EVENT_ID], now=_NOW, event_store=store)
    await register_decision.bind(deps)(
        _good_command(
            decided_by=ActorId(actor_id),
            parent_id=parent_id,
            override_kind="correction",
            choice="Re-approved with conditions",
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    events, _ = await store.load("Decision", _DECISION_ID)
    assert events[0].payload["parent_id"] == str(parent_id)
    assert events[0].payload["override_kind"] == "correction"


# ---------- Wire bundle ----------


@pytest.mark.unit
def test_wire_decision_includes_register_and_get() -> None:
    deps = build_deps(ids=[_DECISION_ID, _REG_EVENT_ID], now=_NOW)
    handlers = wire_decision(deps)
    assert isinstance(handlers, DecisionHandlers)
    assert callable(handlers.register_decision)
    assert callable(handlers.get_decision)
