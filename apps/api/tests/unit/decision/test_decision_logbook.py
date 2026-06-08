"""Unit tests for Decision aggregate's logbook lifecycle (8c-a).

Covers:
  - Decision.logbooks state field defaults to empty
  - DecisionLogbookOpened event payload round-trip + dispatch
  - DecisionLogbookClosed event payload round-trip + dispatch
  - Evolver: at-most-one-open-per-kind invariant on open
  - Evolver: strict-not-idempotent guard on close
  - Defensive: open/close before genesis raises corrupted-stream
  - LogbookSchema serializes through jsonb cleanly
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.decision.aggregates.decision import (
    LOGBOOK_KIND_REASONING,
    REASONING_LOGBOOK_SCHEMA,
    Decision,
    DecisionChoice,
    DecisionContext,
    DecisionLogbookAlreadyOpenError,
    DecisionLogbookClosed,
    DecisionLogbookNotOpenError,
    DecisionLogbookOpened,
    DecisionRegistered,
    event_type_name,
    evolve,
    fold,
    from_stored,
    to_payload,
)
from cora.infrastructure.event_envelope import to_new_event
from cora.infrastructure.ports.event_store import StoredEvent
from cora.shared.identity import ActorId
from cora.shared.logbook import LogbookFieldSpec, LogbookSchema

_NOW = datetime(2026, 5, 12, 12, 0, 0, tzinfo=UTC)


def _registered(decision_id: UUID | None = None) -> DecisionRegistered:
    return DecisionRegistered(
        decision_id=decision_id or uuid4(),
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


# ---------- Decision.logbooks default ----------


@pytest.mark.unit
def test_decision_logbooks_field_defaults_to_empty_dict() -> None:
    d = Decision(
        id=uuid4(),
        decided_by=ActorId(uuid4()),
        decided_at=_NOW,
        context=DecisionContext("RecipeApproval"),
        choice=DecisionChoice("Approved"),
    )
    assert d.logbooks == {}


# ---------- LOGBOOK_KIND_REASONING constant ----------


@pytest.mark.unit
def test_logbook_kind_reasoning_value_locked() -> None:
    """Lock the constant value against drift; consumers may
    reference it by string."""
    assert LOGBOOK_KIND_REASONING == "reasoning"


# ---------- REASONING_LOGBOOK_SCHEMA shape ----------


@pytest.mark.unit
def test_reasoning_logbook_schema_includes_required_otel_fields() -> None:
    """Schema documents the required OTel gen_ai.* discriminator
    fields (provider_name + operation_name + request_model)."""
    fields = REASONING_LOGBOOK_SCHEMA.fields
    assert "provider_name" in fields
    assert "operation_name" in fields
    assert "request_model" in fields


@pytest.mark.unit
def test_reasoning_logbook_schema_round_trips_through_dict() -> None:
    raw = REASONING_LOGBOOK_SCHEMA.to_dict()
    rebuilt = LogbookSchema.from_dict(raw)
    assert rebuilt == REASONING_LOGBOOK_SCHEMA


# ---------- DecisionLogbookOpened event ----------


@pytest.mark.unit
def test_decision_logbook_opened_to_payload() -> None:
    decision_id = uuid4()
    logbook_id = uuid4()
    event = DecisionLogbookOpened(
        decision_id=decision_id,
        logbook_id=logbook_id,
        kind=LOGBOOK_KIND_REASONING,
        schema=REASONING_LOGBOOK_SCHEMA,
        occurred_at=_NOW,
    )
    payload = to_payload(event)
    assert payload["decision_id"] == str(decision_id)
    assert payload["logbook_id"] == str(logbook_id)
    assert payload["kind"] == LOGBOOK_KIND_REASONING
    assert payload["occurred_at"] == _NOW.isoformat()
    # Schema serialized as nested dict.
    assert "fields" in payload["schema"]
    assert "provider_name" in payload["schema"]["fields"]


@pytest.mark.unit
def test_decision_logbook_opened_round_trip_through_stored_envelope() -> None:
    decision_id = uuid4()
    logbook_id = uuid4()
    original = DecisionLogbookOpened(
        decision_id=decision_id,
        logbook_id=logbook_id,
        kind=LOGBOOK_KIND_REASONING,
        schema=LogbookSchema(
            fields={"x": LogbookFieldSpec(type="int", units="ms", description="test")},
            description="round-trip",
        ),
        occurred_at=_NOW,
    )
    new_event = to_new_event(
        event_type=event_type_name(original),
        payload=to_payload(original),
        occurred_at=original.occurred_at,
        event_id=uuid4(),
        command_name="OpenDecisionReasoningLogbook",
        correlation_id=uuid4(),
        principal_id=uuid4(),
    )
    stored = StoredEvent(
        position=1,
        event_id=new_event.event_id,
        stream_type="Decision",
        stream_id=decision_id,
        version=2,
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


# ---------- DecisionLogbookClosed event ----------


@pytest.mark.unit
def test_decision_logbook_closed_to_payload() -> None:
    decision_id = uuid4()
    logbook_id = uuid4()
    event = DecisionLogbookClosed(
        decision_id=decision_id,
        logbook_id=logbook_id,
        occurred_at=_NOW,
    )
    payload = to_payload(event)
    assert payload == {
        "decision_id": str(decision_id),
        "logbook_id": str(logbook_id),
        "occurred_at": _NOW.isoformat(),
    }


@pytest.mark.unit
def test_decision_logbook_closed_round_trip_through_stored_envelope() -> None:
    decision_id = uuid4()
    logbook_id = uuid4()
    original = DecisionLogbookClosed(
        decision_id=decision_id, logbook_id=logbook_id, occurred_at=_NOW
    )
    new_event = to_new_event(
        event_type=event_type_name(original),
        payload=to_payload(original),
        occurred_at=original.occurred_at,
        event_id=uuid4(),
        command_name="CloseDecisionReasoningLogbook",
        correlation_id=uuid4(),
        principal_id=uuid4(),
    )
    stored = StoredEvent(
        position=2,
        event_id=new_event.event_id,
        stream_type="Decision",
        stream_id=decision_id,
        version=3,
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


# ---------- Evolver: open ----------


@pytest.mark.unit
def test_evolve_logbook_opened_adds_kind_to_logbooks() -> None:
    decision_id = uuid4()
    logbook_id = uuid4()
    state = evolve(None, _registered(decision_id=decision_id))
    state2 = evolve(
        state,
        DecisionLogbookOpened(
            decision_id=decision_id,
            logbook_id=logbook_id,
            kind=LOGBOOK_KIND_REASONING,
            schema=REASONING_LOGBOOK_SCHEMA,
            occurred_at=_NOW,
        ),
    )
    assert state2.logbooks == {LOGBOOK_KIND_REASONING: logbook_id}


@pytest.mark.unit
def test_evolve_logbook_opened_raises_for_second_logbook_of_same_kind() -> None:
    """At-most-one-open-per-kind: the existing id is carried so
    operators can resolve via close-then-reopen if intentional."""
    decision_id = uuid4()
    first_id = uuid4()
    second_id = uuid4()
    state = fold(
        [
            _registered(decision_id=decision_id),
            DecisionLogbookOpened(
                decision_id=decision_id,
                logbook_id=first_id,
                kind=LOGBOOK_KIND_REASONING,
                schema=REASONING_LOGBOOK_SCHEMA,
                occurred_at=_NOW,
            ),
        ]
    )
    assert state is not None
    with pytest.raises(DecisionLogbookAlreadyOpenError) as exc_info:
        evolve(
            state,
            DecisionLogbookOpened(
                decision_id=decision_id,
                logbook_id=second_id,
                kind=LOGBOOK_KIND_REASONING,
                schema=REASONING_LOGBOOK_SCHEMA,
                occurred_at=_NOW,
            ),
        )
    assert exc_info.value.kind == LOGBOOK_KIND_REASONING
    assert exc_info.value.existing_logbook_id == first_id


@pytest.mark.unit
def test_evolve_logbook_opened_before_genesis_raises_corrupted_stream() -> None:
    """Defensive: a logbook can't attach to a Decision that
    doesn't exist yet."""
    with pytest.raises(ValueError, match="DecisionLogbookOpened cannot be applied to empty state"):
        evolve(
            None,
            DecisionLogbookOpened(
                decision_id=uuid4(),
                logbook_id=uuid4(),
                kind=LOGBOOK_KIND_REASONING,
                schema=REASONING_LOGBOOK_SCHEMA,
                occurred_at=_NOW,
            ),
        )


# ---------- Evolver: close ----------


@pytest.mark.unit
def test_evolve_logbook_closed_removes_kind_from_logbooks() -> None:
    decision_id = uuid4()
    logbook_id = uuid4()
    state = fold(
        [
            _registered(decision_id=decision_id),
            DecisionLogbookOpened(
                decision_id=decision_id,
                logbook_id=logbook_id,
                kind=LOGBOOK_KIND_REASONING,
                schema=REASONING_LOGBOOK_SCHEMA,
                occurred_at=_NOW,
            ),
            DecisionLogbookClosed(decision_id=decision_id, logbook_id=logbook_id, occurred_at=_NOW),
        ]
    )
    assert state is not None
    assert state.logbooks == {}


@pytest.mark.unit
def test_evolve_logbook_closed_can_reopen_same_kind_after_close() -> None:
    """After close, the kind slot is free and can be reopened
    with a new logbook_id (auditable history of opens/closes
    lives in the event stream)."""
    decision_id = uuid4()
    first_id = uuid4()
    second_id = uuid4()
    state = fold(
        [
            _registered(decision_id=decision_id),
            DecisionLogbookOpened(
                decision_id=decision_id,
                logbook_id=first_id,
                kind=LOGBOOK_KIND_REASONING,
                schema=REASONING_LOGBOOK_SCHEMA,
                occurred_at=_NOW,
            ),
            DecisionLogbookClosed(decision_id=decision_id, logbook_id=first_id, occurred_at=_NOW),
            DecisionLogbookOpened(
                decision_id=decision_id,
                logbook_id=second_id,
                kind=LOGBOOK_KIND_REASONING,
                schema=REASONING_LOGBOOK_SCHEMA,
                occurred_at=_NOW,
            ),
        ]
    )
    assert state is not None
    assert state.logbooks == {LOGBOOK_KIND_REASONING: second_id}


@pytest.mark.unit
def test_evolve_logbook_closed_raises_for_unknown_logbook_id() -> None:
    """Strict-not-idempotent: closing an unknown id raises (typo
    or already-closed both fail loud)."""
    decision_id = uuid4()
    state = evolve(None, _registered(decision_id=decision_id))
    with pytest.raises(DecisionLogbookNotOpenError) as exc_info:
        evolve(
            state,
            DecisionLogbookClosed(decision_id=decision_id, logbook_id=uuid4(), occurred_at=_NOW),
        )
    assert exc_info.value.decision_id == decision_id


@pytest.mark.unit
def test_evolve_logbook_closed_before_genesis_raises_corrupted_stream() -> None:
    with pytest.raises(ValueError, match="DecisionLogbookClosed cannot be applied to empty state"):
        evolve(
            None,
            DecisionLogbookClosed(decision_id=uuid4(), logbook_id=uuid4(), occurred_at=_NOW),
        )


# ---------- Error class shape ----------


@pytest.mark.unit
def test_decision_logbook_already_open_error_carries_kind_and_existing_id() -> None:
    decision_id = uuid4()
    existing_id = uuid4()
    err = DecisionLogbookAlreadyOpenError(decision_id, "reasoning", existing_id)
    assert err.decision_id == decision_id
    assert err.kind == "reasoning"
    assert err.existing_logbook_id == existing_id
    assert "reasoning" in str(err)
    assert str(existing_id) in str(err)


@pytest.mark.unit
def test_decision_logbook_not_open_error_carries_decision_and_logbook_ids() -> None:
    decision_id = uuid4()
    logbook_id = uuid4()
    err = DecisionLogbookNotOpenError(decision_id, logbook_id)
    assert err.decision_id == decision_id
    assert err.logbook_id == logbook_id
    assert str(logbook_id) in str(err)
