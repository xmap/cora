"""Unit tests for the `get_decision` query handler."""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.decision import UnauthorizedError
from cora.decision.aggregates.decision.events import (
    DecisionRegistered,
    event_type_name,
    to_payload,
)
from cora.decision.features import get_decision
from cora.decision.features.get_decision import GetDecision
from cora.infrastructure.adapters.in_memory_event_store import InMemoryEventStore
from cora.infrastructure.event_envelope import to_new_event
from cora.shared.identity import ActorId
from tests.unit._helpers import build_deps

_NOW = datetime(2026, 5, 11, 12, 0, 0, tzinfo=UTC)
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")


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


@pytest.mark.unit
async def test_handler_returns_decision_when_present() -> None:
    store = InMemoryEventStore()
    decision_id = uuid4()
    await _seed_decision(store, decision_id)
    deps = build_deps(ids=[uuid4()], now=_NOW, event_store=store)
    result = await get_decision.bind(deps)(
        GetDecision(decision_id=decision_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert result is not None
    assert result.id == decision_id
    assert result.choice.value == "Approved"


@pytest.mark.unit
async def test_handler_returns_none_when_decision_missing() -> None:
    deps = build_deps(ids=[uuid4()], now=_NOW)
    result = await get_decision.bind(deps)(
        GetDecision(decision_id=uuid4()),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert result is None


@pytest.mark.unit
async def test_handler_raises_unauthorized_on_deny() -> None:
    deps = build_deps(ids=[uuid4()], now=_NOW, deny=True)
    with pytest.raises(UnauthorizedError):
        await get_decision.bind(deps)(
            GetDecision(decision_id=uuid4()),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
