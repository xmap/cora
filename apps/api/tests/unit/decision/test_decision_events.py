"""Unit tests for the Decision event union: payload round-trip + discriminator."""

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import pytest

from cora.decision.aggregates.decision import (
    DecisionConfidenceSource,
    DecisionRegistered,
    event_type_name,
    from_stored,
    to_payload,
)
from cora.infrastructure.event_envelope import to_new_event
from cora.infrastructure.ports.event_store import StoredEvent
from cora.shared.identity import ActorId

_NOW = datetime(2026, 5, 11, 12, 0, 0, tzinfo=UTC)


def _stored(event_type: str, payload: dict[str, object]) -> StoredEvent:
    return StoredEvent(
        position=1,
        event_id=uuid4(),
        stream_type="Decision",
        stream_id=uuid4(),
        version=1,
        event_type=event_type,
        schema_version=1,
        payload=payload,
        correlation_id=uuid4(),
        causation_id=None,
        occurred_at=_NOW,
        recorded_at=_NOW,
    )


def _registered(**overrides: Any) -> DecisionRegistered:
    base: dict[str, Any] = {
        "decision_id": uuid4(),
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
        "occurred_at": _NOW,
    }
    base.update(overrides)
    return DecisionRegistered(**base)


@pytest.mark.unit
def test_event_type_name_returns_class_name() -> None:
    assert event_type_name(_registered()) == "DecisionRegistered"


@pytest.mark.unit
def test_to_payload_serializes_minimal_event() -> None:
    decision_id = uuid4()
    decided_by = ActorId(uuid4())
    payload = to_payload(_registered(decision_id=decision_id, decided_by=decided_by))
    assert payload == {
        "decision_id": str(decision_id),
        "decided_by": str(decided_by),
        "context": "RecipeApproval",
        "choice": "Approved",
        "parent_id": None,
        "override_kind": None,
        "rule": None,
        "reasoning": None,
        "confidence": None,
        "confidence_source": None,
        "alternatives": [],
        "inputs": None,
        "reasoning_signature": None,
        "occurred_at": _NOW.isoformat(),
    }


@pytest.mark.unit
def test_to_payload_preserves_alternatives_order() -> None:
    """Order matters for AI top-k + Cedar PolicyGrant determining policies."""
    payload = to_payload(_registered(alternatives=("Hold", "Stop", "Abort")))
    assert payload["alternatives"] == ["Hold", "Stop", "Abort"]


@pytest.mark.unit
def test_to_payload_serializes_full_event() -> None:
    decision_id = uuid4()
    decided_by = ActorId(uuid4())
    parent_id = uuid4()
    inputs = {"measured_value": 1.234, "limit": 1.5}
    event = _registered(
        decision_id=decision_id,
        decided_by=decided_by,
        parent_id=parent_id,
        override_kind="exception",
        rule="iso17025:7.1.3:simple_acceptance",
        reasoning="Operator override after measurement re-check.",
        confidence=0.92,
        confidence_source=DecisionConfidenceSource.HUMAN,
        alternatives=("Approve", "Reject", "Re-measure"),
        inputs=inputs,
        reasoning_signature="sha256:abc123",
    )
    payload = to_payload(event)
    assert payload["parent_id"] == str(parent_id)
    assert payload["override_kind"] == "exception"
    assert payload["rule"] == "iso17025:7.1.3:simple_acceptance"
    assert payload["confidence"] == 0.92
    assert payload["confidence_source"] == "human"
    assert payload["alternatives"] == ["Approve", "Reject", "Re-measure"]
    assert payload["inputs"] == inputs
    assert payload["reasoning_signature"] == "sha256:abc123"


@pytest.mark.unit
def test_round_trip_through_stored_envelope() -> None:
    original = _registered(
        decision_id=uuid4(),
        parent_id=uuid4(),
        override_kind="correction",
        rule="iso17025:7.1.3:simple_acceptance",
        reasoning="reasoned",
        confidence=0.7,
        confidence_source=DecisionConfidenceSource.LOGPROB,
        alternatives=("a", "b", "c"),
        inputs={"x": 1, "y": [2, 3]},
        reasoning_signature="sig",
    )
    new_event = to_new_event(
        event_type=event_type_name(original),
        payload=to_payload(original),
        occurred_at=original.occurred_at,
        event_id=uuid4(),
        command_name="RegisterDecision",
        correlation_id=uuid4(),
        principal_id=uuid4(),
    )
    stored = StoredEvent(
        position=1,
        event_id=new_event.event_id,
        stream_type="Decision",
        stream_id=original.decision_id,
        version=1,
        event_type=new_event.event_type,
        schema_version=new_event.schema_version,
        payload=new_event.payload,
        correlation_id=new_event.correlation_id,
        causation_id=new_event.causation_id,
        occurred_at=new_event.occurred_at,
        recorded_at=new_event.occurred_at,
        metadata=new_event.metadata,
    )
    rebuilt = from_stored(stored)
    assert rebuilt == original


@pytest.mark.unit
def test_from_stored_raises_on_unknown_event_type() -> None:
    stored = StoredEvent(
        position=1,
        event_id=uuid4(),
        stream_type="Decision",
        stream_id=uuid4(),
        version=1,
        event_type="DecisionDeleted",
        schema_version=1,
        payload={},
        correlation_id=uuid4(),
        causation_id=None,
        occurred_at=_NOW,
        recorded_at=_NOW,
        metadata={},
    )
    with pytest.raises(ValueError, match="DecisionDeleted"):
        from_stored(stored)


@pytest.mark.unit
def test_round_trip_preserves_uuid_field_types() -> None:
    """UUID fields survive str/UUID conversion through jsonb."""
    decision_id = UUID("01900000-0000-7000-8000-000000099001")
    decided_by = ActorId(UUID("01900000-0000-7000-8000-000000099002"))
    parent_id = UUID("01900000-0000-7000-8000-000000099003")
    original = _registered(decision_id=decision_id, decided_by=decided_by, parent_id=parent_id)
    new_event = to_new_event(
        event_type=event_type_name(original),
        payload=to_payload(original),
        occurred_at=original.occurred_at,
        event_id=uuid4(),
        command_name="RegisterDecision",
        correlation_id=uuid4(),
        principal_id=uuid4(),
    )
    stored = StoredEvent(
        position=1,
        event_id=new_event.event_id,
        stream_type="Decision",
        stream_id=decision_id,
        version=1,
        event_type=new_event.event_type,
        schema_version=new_event.schema_version,
        payload=new_event.payload,
        correlation_id=new_event.correlation_id,
        causation_id=new_event.causation_id,
        occurred_at=new_event.occurred_at,
        recorded_at=new_event.occurred_at,
        metadata=new_event.metadata,
    )
    rebuilt = from_stored(stored)
    assert isinstance(rebuilt, DecisionRegistered)
    assert rebuilt.decision_id == decision_id
    assert rebuilt.decided_by == decided_by
    assert rebuilt.parent_id == parent_id


@pytest.mark.unit
@pytest.mark.parametrize(
    "event_type",
    [
        "DecisionRegistered",
        "DecisionLogbookOpened",
        "DecisionLogbookClosed",
        "DecisionRated",
    ],
)
def test_from_stored_raises_on_malformed_payload(event_type: str) -> None:
    """Per the convention adopted post-corpus-survey (Marten /
    pyeventsourcing / Pydantic / msgspec all wrap), each event-type case
    wraps `KeyError`/`TypeError`/`AttributeError` into a tagged
    `ValueError` so a corrupted event row fails loud with the event-type
    name in the message rather than bubbling a raw KeyError from deep
    in the load path."""
    with pytest.raises(ValueError, match=f"Malformed {event_type} payload"):
        from_stored(_stored(event_type, {}))
