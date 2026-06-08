"""CalibrationEvent serialization round-trips + serialize_source / deserialize_source.

Pins the exclusive-arc invariant (Q5 lock) and the to_payload/from_stored
round-trip discipline (Q6 lock: jsonb canonicalisation handled by
Postgres; in-Python equality preserves dict identity).
"""

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import pytest

from cora.calibration.aggregates.calibration import (
    AssertedSource,
    CalibrationDefined,
    CalibrationRevisionAppended,
    CalibrationStatus,
    ComputedSource,
    InvalidCalibrationSourceError,
    MeasuredSource,
    deserialize_source,
    event_type_name,
    from_stored,
    serialize_source,
    to_payload,
)
from cora.infrastructure.ports.event_store import StoredEvent
from cora.shared.identity import ActorId

_NOW = datetime(2026, 5, 18, 12, 0, 0, tzinfo=UTC)
_CALIBRATION_ID = UUID("01900000-0000-7000-8000-000000ca0001")
_SUBSYSTEM_ID = UUID("01900000-0000-7000-8000-000000ca0002")
_ACTOR_ID = ActorId(UUID("01900000-0000-7000-8000-000000ca0003"))
_PROCEDURE_ID = UUID("01900000-0000-7000-8000-000000ca0004")
_DATASET_ID = UUID("01900000-0000-7000-8000-000000ca0005")
_REVISION_ID = UUID("01900000-0000-7000-8000-000000ca0006")
_DECISION_ID = UUID("01900000-0000-7000-8000-000000ca0007")


def _stored(event_type: str, payload: dict[str, Any]) -> StoredEvent:
    return StoredEvent(
        position=1,
        event_id=uuid4(),
        stream_type="Calibration",
        stream_id=_CALIBRATION_ID,
        version=1,
        event_type=event_type,
        schema_version=1,
        payload=payload,
        correlation_id=uuid4(),
        causation_id=None,
        occurred_at=_NOW,
        recorded_at=_NOW,
    )


# ---------- serialize_source / deserialize_source ----------


@pytest.mark.unit
def test_serialize_source_for_measured() -> None:
    payload = serialize_source(MeasuredSource(procedure_id=_PROCEDURE_ID))
    assert payload == {
        "source_procedure_id": str(_PROCEDURE_ID),
        "source_dataset_id": None,
        "asserted_by": None,
    }


@pytest.mark.unit
def test_serialize_source_for_computed() -> None:
    payload = serialize_source(ComputedSource(dataset_id=_DATASET_ID))
    assert payload == {
        "source_procedure_id": None,
        "source_dataset_id": str(_DATASET_ID),
        "asserted_by": None,
    }


@pytest.mark.unit
def test_serialize_source_for_asserted() -> None:
    payload = serialize_source(AssertedSource(asserted_by=_ACTOR_ID))
    assert payload == {
        "source_procedure_id": None,
        "source_dataset_id": None,
        "asserted_by": str(_ACTOR_ID),
    }


@pytest.mark.unit
def test_deserialize_source_round_trips_each_arm() -> None:
    for source in [
        MeasuredSource(procedure_id=_PROCEDURE_ID),
        ComputedSource(dataset_id=_DATASET_ID),
        AssertedSource(asserted_by=_ACTOR_ID),
    ]:
        assert deserialize_source(serialize_source(source)) == source


@pytest.mark.unit
def test_deserialize_source_rejects_all_null() -> None:
    """Exclusive-arc CHECK: zero non-null sources is invalid."""
    with pytest.raises(InvalidCalibrationSourceError):
        deserialize_source(
            {
                "source_procedure_id": None,
                "source_dataset_id": None,
                "asserted_by": None,
            }
        )


@pytest.mark.unit
def test_deserialize_source_rejects_multiple_non_null() -> None:
    """Exclusive-arc CHECK: two non-null sources is invalid."""
    with pytest.raises(InvalidCalibrationSourceError):
        deserialize_source(
            {
                "source_procedure_id": str(_PROCEDURE_ID),
                "source_dataset_id": str(_DATASET_ID),
                "asserted_by": None,
            }
        )


# ---------- CalibrationDefined ----------


@pytest.mark.unit
def test_event_type_name_for_calibration_defined() -> None:
    event = CalibrationDefined(
        calibration_id=_CALIBRATION_ID,
        target_id=_SUBSYSTEM_ID,
        quantity="rotation_center",
        operating_point={"energy": 25, "optics_config": "5x"},
        description=None,
        defined_by=_ACTOR_ID,
        occurred_at=_NOW,
    )
    assert event_type_name(event) == "CalibrationDefined"


@pytest.mark.unit
def test_to_payload_serializes_calibration_defined_to_primitives() -> None:
    event = CalibrationDefined(
        calibration_id=_CALIBRATION_ID,
        target_id=_SUBSYSTEM_ID,
        quantity="rotation_center",
        operating_point={"energy": 25, "optics_config": "5x"},
        description="vessel-A bakeout pre-scan",
        defined_by=_ACTOR_ID,
        occurred_at=_NOW,
    )
    # `defined_at` is folded from envelope `occurred_at` at the evolver;
    # the wire payload carries `defined_by` + `occurred_at` only.
    assert to_payload(event) == {
        "calibration_id": str(_CALIBRATION_ID),
        "target_id": str(_SUBSYSTEM_ID),
        "quantity": "rotation_center",
        "operating_point": {"energy": 25, "optics_config": "5x"},
        "description": "vessel-A bakeout pre-scan",
        "defined_by": str(_ACTOR_ID),
        "occurred_at": _NOW.isoformat(),
    }


@pytest.mark.unit
def test_calibration_defined_round_trips_through_event_log() -> None:
    original = CalibrationDefined(
        calibration_id=_CALIBRATION_ID,
        target_id=_SUBSYSTEM_ID,
        quantity="rotation_center",
        operating_point={"energy": 25, "optics_config": "5x"},
        description=None,
        defined_by=_ACTOR_ID,
        occurred_at=_NOW,
    )
    stored = _stored("CalibrationDefined", to_payload(original))
    assert from_stored(stored) == original


# ---------- CalibrationRevisionAppended ----------


@pytest.mark.unit
def test_to_payload_serializes_revision_appended_with_measured_source() -> None:
    event = CalibrationRevisionAppended(
        revision_id=_REVISION_ID,
        calibration_id=_CALIBRATION_ID,
        value={"center": 1024.5},
        status=CalibrationStatus.PROVISIONAL,
        source_procedure_id=_PROCEDURE_ID,
        source_dataset_id=None,
        asserted_by=None,
        established_at=_NOW,
        established_by=_ACTOR_ID,
        decided_by_decision_id=None,
        supersedes_revision_id=None,
        occurred_at=_NOW,
    )
    payload = to_payload(event)
    assert payload["source_procedure_id"] == str(_PROCEDURE_ID)
    assert payload["source_dataset_id"] is None
    assert payload["asserted_by"] is None
    assert payload["status"] == "Provisional"  # status serializes as enum.value


@pytest.mark.unit
def test_revision_appended_round_trips_with_decision_link() -> None:
    original = CalibrationRevisionAppended(
        revision_id=_REVISION_ID,
        calibration_id=_CALIBRATION_ID,
        value={"center": 1024.5, "uncertainty": 0.3},
        status=CalibrationStatus.VERIFIED,
        source_procedure_id=None,
        source_dataset_id=_DATASET_ID,
        asserted_by=None,
        established_at=_NOW,
        established_by=_ACTOR_ID,
        decided_by_decision_id=_DECISION_ID,
        supersedes_revision_id=uuid4(),
        occurred_at=_NOW,
    )
    stored = _stored("CalibrationRevisionAppended", to_payload(original))
    assert from_stored(stored) == original


@pytest.mark.unit
def test_event_type_name_for_calibration_revision_appended() -> None:
    """Mirror the genesis-event pin for the revision-appended discriminator."""
    event = CalibrationRevisionAppended(
        revision_id=_REVISION_ID,
        calibration_id=_CALIBRATION_ID,
        value={"center": 1024.5},
        status=CalibrationStatus.PROVISIONAL,
        source_procedure_id=_PROCEDURE_ID,
        source_dataset_id=None,
        asserted_by=None,
        established_at=_NOW,
        established_by=_ACTOR_ID,
        decided_by_decision_id=None,
        supersedes_revision_id=None,
        occurred_at=_NOW,
    )
    assert event_type_name(event) == "CalibrationRevisionAppended"


@pytest.mark.unit
def test_from_stored_raises_on_unknown_event_type() -> None:
    with pytest.raises(ValueError, match="Unknown Calibration event type"):
        from_stored(_stored("RandomGarbage", {"k": "v"}))


@pytest.mark.unit
@pytest.mark.parametrize(
    "event_type",
    [
        "CalibrationDefined",
        "CalibrationRevisionAppended",
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
