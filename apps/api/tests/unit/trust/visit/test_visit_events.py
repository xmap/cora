"""Codec round-trip tests for all 9 Visit events.

Every event must serialize via `to_payload` and deserialize via
`from_stored` back to the same value. Malformed payloads raise
`ValueError("Malformed ...")` per `[[project_from_stored_wrap_convention]]`.
"""

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

import pytest

from cora.infrastructure.ports.event_store import StoredEvent
from cora.shared.identifier import Identifier
from cora.trust.aggregates.visit import (
    VisitAborted,
    VisitArrived,
    VisitCancelled,
    VisitCompleted,
    VisitEvent,
    VisitHeld,
    VisitRegistered,
    VisitResumed,
    VisitStarted,
    VisitType,
    VisitVoided,
    event_type_name,
    from_stored,
    to_payload,
)

_NOW = datetime(2026, 5, 27, 12, 0, 0, tzinfo=UTC)
_VID = UUID("01900000-0000-7000-8000-00000000b001")
_PID = UUID("01900000-0000-7000-8000-00000000b002")
_SID = UUID("01900000-0000-7000-8000-00000000b003")


def _stored(event_type: str, payload: dict[str, Any]) -> StoredEvent:
    """Build a StoredEvent shell carrying the payload for from_stored testing."""
    return StoredEvent(
        position=1,
        event_id=uuid4(),
        stream_type="Visit",
        stream_id=_VID,
        version=1,
        event_type=event_type,
        schema_version=1,
        payload=payload,
        correlation_id=uuid4(),
        causation_id=None,
        occurred_at=_NOW,
        recorded_at=_NOW,
    )


def _round_trips(event: VisitEvent) -> VisitEvent:
    """Encode + decode the event; return what comes back."""
    payload = to_payload(event)
    stored = _stored(event_type_name(event), payload)
    return from_stored(stored)


@pytest.mark.unit
def test_visit_registered_round_trips_with_external_refs_and_part_of() -> None:
    e = VisitRegistered(
        visit_id=_VID,
        policy_id=_PID,
        surface_id=_SID,
        type=VisitType.COMMISSIONING.value,
        planned_start_at=_NOW,
        planned_end_at=_NOW + timedelta(hours=4),
        occurred_at=_NOW,
        parent_id=uuid4(),
        external_refs=frozenset(
            {
                Identifier(scheme="proposal", value="12345"),
                Identifier(scheme="visit", value="cm98765-1"),
            }
        ),
    )
    assert _round_trips(e) == e


@pytest.mark.unit
def test_visit_registered_round_trips_without_optional_fields() -> None:
    e = VisitRegistered(
        visit_id=_VID,
        policy_id=_PID,
        surface_id=_SID,
        type=VisitType.USER.value,
        planned_start_at=_NOW,
        planned_end_at=_NOW + timedelta(hours=4),
        occurred_at=_NOW,
    )
    decoded = _round_trips(e)
    assert decoded == e
    assert decoded.parent_id is None  # type: ignore[union-attr]
    assert decoded.external_refs == frozenset()  # type: ignore[union-attr]


@pytest.mark.parametrize(
    "event_cls",
    [VisitArrived, VisitStarted, VisitResumed, VisitCompleted],
)
@pytest.mark.unit
def test_simple_lifecycle_event_round_trips(
    event_cls: type[VisitArrived] | type[VisitStarted] | type[VisitResumed] | type[VisitCompleted],
) -> None:
    e = event_cls(visit_id=_VID, occurred_at=_NOW)
    assert _round_trips(e) == e


@pytest.mark.parametrize(
    "event_cls",
    [VisitHeld, VisitCancelled, VisitAborted, VisitVoided],
)
@pytest.mark.unit
def test_with_reason_event_round_trips(
    event_cls: type[VisitHeld] | type[VisitCancelled] | type[VisitAborted] | type[VisitVoided],
) -> None:
    e = event_cls(visit_id=_VID, reason="beam dump", occurred_at=_NOW)
    assert _round_trips(e) == e


@pytest.mark.unit
def test_to_payload_external_refs_are_sorted_for_determinism() -> None:
    """Determinism lock: same logical refs serialize to same byte order
    so hash-based idempotency + content-addressing stay stable."""
    e1 = VisitRegistered(
        visit_id=_VID,
        policy_id=_PID,
        surface_id=_SID,
        type=VisitType.USER.value,
        planned_start_at=_NOW,
        planned_end_at=_NOW + timedelta(hours=1),
        occurred_at=_NOW,
        external_refs=frozenset(
            {
                Identifier(scheme="proposal", value="12345"),
                Identifier(scheme="cycle", value="2026-1"),
            }
        ),
    )
    e2 = VisitRegistered(
        visit_id=_VID,
        policy_id=_PID,
        surface_id=_SID,
        type=VisitType.USER.value,
        planned_start_at=_NOW,
        planned_end_at=_NOW + timedelta(hours=1),
        occurred_at=_NOW,
        external_refs=frozenset(
            {
                Identifier(scheme="cycle", value="2026-1"),
                Identifier(scheme="proposal", value="12345"),
            }
        ),
    )
    assert to_payload(e1) == to_payload(e2)


@pytest.mark.unit
def test_from_stored_rejects_unknown_event_type() -> None:
    with pytest.raises(ValueError, match="Unknown VisitEvent event_type"):
        from_stored(_stored("NotARealEvent", {"visit_id": str(_VID)}))


@pytest.mark.unit
def test_from_stored_wraps_malformed_payload_as_value_error() -> None:
    """Per [[project_from_stored_wrap_convention]] -- KeyError on missing
    fields surfaces as a tagged 'Malformed <Event>' ValueError."""
    with pytest.raises(ValueError, match="Malformed VisitArrived"):
        from_stored(_stored("VisitArrived", {"visit_id": str(_VID)}))  # missing occurred_at
