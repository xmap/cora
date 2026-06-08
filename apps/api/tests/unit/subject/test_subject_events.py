"""Unit tests for the Subject aggregate's event (de)serialization helpers."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from cora.infrastructure.ports.event_store import StoredEvent
from cora.shared.identity import ActorId
from cora.subject.aggregates.subject.events import (
    SubjectDiscarded,
    SubjectDismounted,
    SubjectMeasured,
    SubjectMounted,
    SubjectRegistered,
    SubjectRemoved,
    SubjectReturned,
    SubjectStored,
    event_type_name,
    from_stored,
    to_payload,
)

_NOW = datetime(2026, 5, 10, 12, 0, 0, tzinfo=UTC)
_ACTOR = ActorId(uuid4())


def _stored(
    event_type: str,
    payload: dict[str, object],
    *,
    stream_id: object | None = None,
) -> StoredEvent:
    """Build a StoredEvent shell -- only event_type + payload are read by from_stored."""
    return StoredEvent(
        position=1,
        event_id=uuid4(),
        stream_type="Subject",
        stream_id=stream_id or uuid4(),  # type: ignore[arg-type]
        version=1,
        event_type=event_type,
        schema_version=1,
        payload=payload,
        correlation_id=uuid4(),
        causation_id=None,
        occurred_at=_NOW,
        recorded_at=_NOW,
    )


@pytest.mark.unit
def test_event_type_name_returns_class_name() -> None:
    event = SubjectRegistered(
        subject_id=uuid4(), name="Sample-A1", occurred_at=_NOW, registered_by=_ACTOR
    )
    assert event_type_name(event) == "SubjectRegistered"


@pytest.mark.unit
def test_to_payload_serializes_subject_registered_to_primitives() -> None:
    subject_id = uuid4()
    event = SubjectRegistered(
        subject_id=subject_id, name="Sample-A1", occurred_at=_NOW, registered_by=_ACTOR
    )
    assert to_payload(event) == {
        "subject_id": str(subject_id),
        "name": "Sample-A1",
        "occurred_at": _NOW.isoformat(),
        "registered_by": str(_ACTOR),
    }


@pytest.mark.unit
def test_from_stored_rebuilds_subject_registered() -> None:
    subject_id = uuid4()
    stored = _stored(
        "SubjectRegistered",
        {
            "subject_id": str(subject_id),
            "name": "Sample-A1",
            "occurred_at": _NOW.isoformat(),
            "registered_by": str(_ACTOR),
        },
    )
    rebuilt = from_stored(stored)
    assert rebuilt == SubjectRegistered(
        subject_id=subject_id, name="Sample-A1", occurred_at=_NOW, registered_by=_ACTOR
    )


@pytest.mark.unit
def test_to_payload_then_from_stored_round_trips() -> None:
    """Round-trip safety net: the (de)serialization pair must be each other's inverse."""
    original = SubjectRegistered(
        subject_id=uuid4(), name="Sample-A1", occurred_at=_NOW, registered_by=_ACTOR
    )
    stored = _stored("SubjectRegistered", to_payload(original))
    assert from_stored(stored) == original


@pytest.mark.unit
def test_from_stored_raises_on_unknown_event_type() -> None:
    """Foreign event_types in a stream must fail loud, not be silently dropped."""
    stored = _stored("ActorRegistered", {})
    with pytest.raises(ValueError, match="Unknown SubjectEvent event_type"):
        from_stored(stored)


# ---------- SubjectMounted ----------


@pytest.mark.unit
def test_event_type_name_returns_subject_mounted_class_name() -> None:
    event = SubjectMounted(
        subject_id=uuid4(), asset_id=uuid4(), reason="", occurred_at=_NOW, mounted_by=_ACTOR
    )
    assert event_type_name(event) == "SubjectMounted"


@pytest.mark.unit
def test_to_payload_serializes_subject_mounted_to_primitives() -> None:
    """Status NOT in payload -- event type encodes the state change.
    `asset_id` IS in payload (load-bearing for "where is sample X?"
    downstream queries). `reason` (4f) IS in payload."""
    subject_id = uuid4()
    asset_id = uuid4()
    event = SubjectMounted(
        subject_id=subject_id,
        asset_id=asset_id,
        reason="loaded for run 1234",
        occurred_at=_NOW,
        mounted_by=_ACTOR,
    )
    assert to_payload(event) == {
        "subject_id": str(subject_id),
        "asset_id": str(asset_id),
        "reason": "loaded for run 1234",
        "occurred_at": _NOW.isoformat(),
        "mounted_by": str(_ACTOR),
    }
    assert "status" not in to_payload(event)


@pytest.mark.unit
def test_from_stored_rebuilds_subject_mounted() -> None:
    subject_id = uuid4()
    asset_id = uuid4()
    stored = _stored(
        "SubjectMounted",
        {
            "subject_id": str(subject_id),
            "asset_id": str(asset_id),
            "reason": "loaded for run 1234",
            "occurred_at": _NOW.isoformat(),
            "mounted_by": str(_ACTOR),
        },
    )
    rebuilt = from_stored(stored)
    assert rebuilt == SubjectMounted(
        subject_id=subject_id,
        asset_id=asset_id,
        reason="loaded for run 1234",
        occurred_at=_NOW,
        mounted_by=_ACTOR,
    )


@pytest.mark.unit
def test_from_stored_rebuilds_subject_mounted_with_empty_reason_for_pre_4f_events() -> None:
    """Additive evolution: legacy stored events without the
    reason key fold to reason="" via payload.get fallback."""
    subject_id = uuid4()
    asset_id = uuid4()
    stored = _stored(
        "SubjectMounted",
        {
            "subject_id": str(subject_id),
            "asset_id": str(asset_id),
            # reason key intentionally absent
            "occurred_at": _NOW.isoformat(),
            "mounted_by": str(_ACTOR),
        },
    )
    rebuilt = from_stored(stored)
    assert isinstance(rebuilt, SubjectMounted)
    assert rebuilt.reason == ""


@pytest.mark.unit
def test_to_payload_then_from_stored_round_trips_for_subject_mounted() -> None:
    original = SubjectMounted(
        subject_id=uuid4(), asset_id=uuid4(), reason="", occurred_at=_NOW, mounted_by=_ACTOR
    )
    stored = _stored("SubjectMounted", to_payload(original))
    assert from_stored(stored) == original


# ---------- SubjectMeasured ----------


@pytest.mark.unit
def test_event_type_name_returns_subject_measured_class_name() -> None:
    event = SubjectMeasured(subject_id=uuid4(), occurred_at=_NOW, measured_by=_ACTOR)
    assert event_type_name(event) == "SubjectMeasured"


@pytest.mark.unit
def test_to_payload_serializes_subject_measured_to_primitives() -> None:
    """Status NOT in payload (event type encodes the state change). Same
    convention as SubjectMounted; pinned per-event-class so an additive
    payload field on Measured is a deliberate change."""
    subject_id = uuid4()
    event = SubjectMeasured(subject_id=subject_id, occurred_at=_NOW, measured_by=_ACTOR)
    assert to_payload(event) == {
        "subject_id": str(subject_id),
        "occurred_at": _NOW.isoformat(),
        "measured_by": str(_ACTOR),
    }
    assert "status" not in to_payload(event)


@pytest.mark.unit
def test_from_stored_rebuilds_subject_measured() -> None:
    subject_id = uuid4()
    stored = _stored(
        "SubjectMeasured",
        {
            "subject_id": str(subject_id),
            "occurred_at": _NOW.isoformat(),
            "measured_by": str(_ACTOR),
        },
    )
    rebuilt = from_stored(stored)
    assert rebuilt == SubjectMeasured(subject_id=subject_id, occurred_at=_NOW, measured_by=_ACTOR)


@pytest.mark.unit
def test_to_payload_then_from_stored_round_trips_for_subject_measured() -> None:
    original = SubjectMeasured(subject_id=uuid4(), occurred_at=_NOW, measured_by=_ACTOR)
    stored = _stored("SubjectMeasured", to_payload(original))
    assert from_stored(stored) == original


# ---------- SubjectRemoved ----------


@pytest.mark.unit
def test_event_type_name_returns_subject_removed_class_name() -> None:
    event = SubjectRemoved(subject_id=uuid4(), occurred_at=_NOW, removed_by=_ACTOR)
    assert event_type_name(event) == "SubjectRemoved"


@pytest.mark.unit
def test_to_payload_serializes_subject_removed_to_primitives() -> None:
    """Status NOT in payload -- multi-source-to-single-target transitions
    are still encoded by event TYPE alone. The decider's source-state
    guard is what enforces Mounted | Measured at command time; the
    event itself doesn't need to record where it came from."""
    subject_id = uuid4()
    event = SubjectRemoved(subject_id=subject_id, occurred_at=_NOW, removed_by=_ACTOR)
    assert to_payload(event) == {
        "subject_id": str(subject_id),
        "occurred_at": _NOW.isoformat(),
        "removed_by": str(_ACTOR),
    }
    assert "status" not in to_payload(event)
    assert "from_status" not in to_payload(event)


@pytest.mark.unit
def test_from_stored_rebuilds_subject_removed() -> None:
    subject_id = uuid4()
    stored = _stored(
        "SubjectRemoved",
        {
            "subject_id": str(subject_id),
            "occurred_at": _NOW.isoformat(),
            "removed_by": str(_ACTOR),
        },
    )
    rebuilt = from_stored(stored)
    assert rebuilt == SubjectRemoved(subject_id=subject_id, occurred_at=_NOW, removed_by=_ACTOR)


@pytest.mark.unit
def test_to_payload_then_from_stored_round_trips_for_subject_removed() -> None:
    original = SubjectRemoved(subject_id=uuid4(), occurred_at=_NOW, removed_by=_ACTOR)
    stored = _stored("SubjectRemoved", to_payload(original))
    assert from_stored(stored) == original


# ---------- SubjectReturned ----------


@pytest.mark.unit
def test_event_type_name_returns_subject_returned_class_name() -> None:
    event = SubjectReturned(subject_id=uuid4(), occurred_at=_NOW, returned_by=_ACTOR)
    assert event_type_name(event) == "SubjectReturned"


@pytest.mark.unit
def test_to_payload_serializes_subject_returned_to_primitives() -> None:
    """Status NOT in payload -- terminal disposition events still
    encode the state change by event TYPE alone, same as the
    earlier transitions."""
    subject_id = uuid4()
    event = SubjectReturned(subject_id=subject_id, occurred_at=_NOW, returned_by=_ACTOR)
    assert to_payload(event) == {
        "subject_id": str(subject_id),
        "occurred_at": _NOW.isoformat(),
        "returned_by": str(_ACTOR),
    }
    assert "status" not in to_payload(event)


@pytest.mark.unit
def test_from_stored_rebuilds_subject_returned() -> None:
    subject_id = uuid4()
    stored = _stored(
        "SubjectReturned",
        {
            "subject_id": str(subject_id),
            "occurred_at": _NOW.isoformat(),
            "returned_by": str(_ACTOR),
        },
    )
    rebuilt = from_stored(stored)
    assert rebuilt == SubjectReturned(subject_id=subject_id, occurred_at=_NOW, returned_by=_ACTOR)


@pytest.mark.unit
def test_to_payload_then_from_stored_round_trips_for_subject_returned() -> None:
    original = SubjectReturned(subject_id=uuid4(), occurred_at=_NOW, returned_by=_ACTOR)
    stored = _stored("SubjectReturned", to_payload(original))
    assert from_stored(stored) == original


# ---------- SubjectStored ----------


@pytest.mark.unit
def test_event_type_name_returns_subject_stored_class_name() -> None:
    event = SubjectStored(subject_id=uuid4(), occurred_at=_NOW, stored_by=_ACTOR)
    assert event_type_name(event) == "SubjectStored"


@pytest.mark.unit
def test_to_payload_serializes_subject_stored_to_primitives() -> None:
    subject_id = uuid4()
    event = SubjectStored(subject_id=subject_id, occurred_at=_NOW, stored_by=_ACTOR)
    assert to_payload(event) == {
        "subject_id": str(subject_id),
        "occurred_at": _NOW.isoformat(),
        "stored_by": str(_ACTOR),
    }
    assert "status" not in to_payload(event)


@pytest.mark.unit
def test_from_stored_rebuilds_subject_stored() -> None:
    subject_id = uuid4()
    stored = _stored(
        "SubjectStored",
        {
            "subject_id": str(subject_id),
            "occurred_at": _NOW.isoformat(),
            "stored_by": str(_ACTOR),
        },
    )
    rebuilt = from_stored(stored)
    assert rebuilt == SubjectStored(subject_id=subject_id, occurred_at=_NOW, stored_by=_ACTOR)


@pytest.mark.unit
def test_to_payload_then_from_stored_round_trips_for_subject_stored() -> None:
    original = SubjectStored(subject_id=uuid4(), occurred_at=_NOW, stored_by=_ACTOR)
    stored = _stored("SubjectStored", to_payload(original))
    assert from_stored(stored) == original


# ---------- SubjectDiscarded ----------


@pytest.mark.unit
def test_event_type_name_returns_subject_discarded_class_name() -> None:
    event = SubjectDiscarded(
        subject_id=uuid4(), reason="contaminated", occurred_at=_NOW, discarded_by=_ACTOR
    )
    assert event_type_name(event) == "SubjectDiscarded"


@pytest.mark.unit
def test_to_payload_serializes_subject_discarded_to_primitives() -> None:
    subject_id = uuid4()
    event = SubjectDiscarded(
        subject_id=subject_id,
        reason="contaminated",
        occurred_at=_NOW,
        discarded_by=_ACTOR,
    )
    assert to_payload(event) == {
        "subject_id": str(subject_id),
        "reason": "contaminated",
        "occurred_at": _NOW.isoformat(),
        "discarded_by": str(_ACTOR),
    }
    assert "status" not in to_payload(event)


@pytest.mark.unit
def test_from_stored_rebuilds_subject_discarded() -> None:
    subject_id = uuid4()
    stored = _stored(
        "SubjectDiscarded",
        {
            "subject_id": str(subject_id),
            "reason": "contaminated",
            "occurred_at": _NOW.isoformat(),
            "discarded_by": str(_ACTOR),
        },
    )
    rebuilt = from_stored(stored)
    assert rebuilt == SubjectDiscarded(
        subject_id=subject_id,
        reason="contaminated",
        occurred_at=_NOW,
        discarded_by=_ACTOR,
    )


@pytest.mark.unit
def test_to_payload_then_from_stored_round_trips_for_subject_discarded() -> None:
    original = SubjectDiscarded(
        subject_id=uuid4(),
        reason="contaminated",
        occurred_at=_NOW,
        discarded_by=_ACTOR,
    )
    stored = _stored("SubjectDiscarded", to_payload(original))
    assert from_stored(stored) == original


# ---------- SubjectDismounted ----------


@pytest.mark.unit
def test_event_type_name_returns_subject_dismounted_class_name() -> None:
    event = SubjectDismounted(
        subject_id=uuid4(),
        from_asset_id=uuid4(),
        reason="x",
        occurred_at=_NOW,
        dismounted_by=_ACTOR,
    )
    assert event_type_name(event) == "SubjectDismounted"


@pytest.mark.unit
def test_to_payload_serializes_subject_dismounted() -> None:
    subject_id = uuid4()
    asset_id = uuid4()
    event = SubjectDismounted(
        subject_id=subject_id,
        from_asset_id=asset_id,
        reason="run complete",
        occurred_at=_NOW,
        dismounted_by=_ACTOR,
    )
    assert to_payload(event) == {
        "subject_id": str(subject_id),
        "from_asset_id": str(asset_id),
        "reason": "run complete",
        "occurred_at": _NOW.isoformat(),
        "dismounted_by": str(_ACTOR),
    }


@pytest.mark.unit
def test_from_stored_rebuilds_subject_dismounted() -> None:
    subject_id = uuid4()
    asset_id = uuid4()
    stored = _stored(
        "SubjectDismounted",
        {
            "subject_id": str(subject_id),
            "from_asset_id": str(asset_id),
            "reason": "moving to next stage",
            "occurred_at": _NOW.isoformat(),
            "dismounted_by": str(_ACTOR),
        },
    )
    rebuilt = from_stored(stored)
    assert rebuilt == SubjectDismounted(
        subject_id=subject_id,
        from_asset_id=asset_id,
        reason="moving to next stage",
        occurred_at=_NOW,
        dismounted_by=_ACTOR,
    )


@pytest.mark.unit
def test_round_trip_for_subject_dismounted() -> None:
    original = SubjectDismounted(
        subject_id=uuid4(),
        from_asset_id=uuid4(),
        reason="x",
        occurred_at=_NOW,
        dismounted_by=_ACTOR,
    )
    stored = _stored("SubjectDismounted", to_payload(original))
    assert from_stored(stored) == original


# `to_new_event` envelope construction lives at
# `cora.infrastructure.event_envelope` and is covered by
# `tests/unit/test_event_envelope.py`.


@pytest.mark.unit
@pytest.mark.parametrize(
    "event_type",
    [
        "SubjectRegistered",
        "SubjectMounted",
        "SubjectMeasured",
        "SubjectRemoved",
        "SubjectReturned",
        "SubjectStored",
        "SubjectDiscarded",
        "SubjectDismounted",
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
