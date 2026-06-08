"""Unit tests for the Dataset event union: payload round-trip + discriminator."""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.data.aggregates.dataset import (
    DATASET_CHECKSUM_SHA256_HEX_LENGTH,
    DatasetDemoted,
    DatasetPromoted,
    DatasetRegistered,
    event_type_name,
    from_stored,
    to_payload,
)
from cora.infrastructure.event_envelope import to_new_event
from cora.infrastructure.ports.event_store import StoredEvent
from cora.shared.identity import ActorId

_GOOD_SHA256 = "a" * DATASET_CHECKSUM_SHA256_HEX_LENGTH
_NOW = datetime(2026, 5, 11, 12, 0, 0, tzinfo=UTC)
_REGISTERED_BY = ActorId(UUID("01900000-0000-7000-8000-0000000000a1"))
_DISCARDED_BY = ActorId(UUID("01900000-0000-7000-8000-0000000000a2"))
_PROMOTED_BY = ActorId(UUID("01900000-0000-7000-8000-0000000000a3"))
_DEMOTED_BY = ActorId(UUID("01900000-0000-7000-8000-0000000000a4"))


def _stored(event_type: str, payload: dict[str, object]) -> StoredEvent:
    return StoredEvent(
        position=1,
        event_id=uuid4(),
        stream_type="Dataset",
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


@pytest.mark.unit
def test_event_type_name_returns_class_name() -> None:
    event = DatasetRegistered(
        dataset_id=uuid4(),
        name="D",
        uri="s3://b/k",
        checksum_algorithm="sha256",
        checksum_value=_GOOD_SHA256,
        byte_size=0,
        media_type="application/x-hdf5",
        conforms_to=frozenset(),
        producing_run_id=None,
        subject_id=None,
        derived_from=frozenset(),
        occurred_at=_NOW,
        registered_by=_REGISTERED_BY,
    )
    assert event_type_name(event) == "DatasetRegistered"


@pytest.mark.unit
def test_to_payload_serializes_all_fields_with_nulls_and_empties() -> None:
    dataset_id = uuid4()
    event = DatasetRegistered(
        dataset_id=dataset_id,
        name="D",
        uri="s3://b/k",
        checksum_algorithm="sha256",
        checksum_value=_GOOD_SHA256,
        byte_size=0,
        media_type="application/x-hdf5",
        conforms_to=frozenset(),
        producing_run_id=None,
        subject_id=None,
        derived_from=frozenset(),
        occurred_at=_NOW,
        registered_by=_REGISTERED_BY,
    )
    payload = to_payload(event)
    assert payload == {
        "dataset_id": str(dataset_id),
        "name": "D",
        "uri": "s3://b/k",
        "checksum": {"algorithm": "sha256", "value": _GOOD_SHA256},
        "byte_size": 0,
        "encoding": {"media_type": "application/x-hdf5", "conforms_to": []},
        "producing_run_id": None,
        "subject_id": None,
        "derived_from": [],
        "occurred_at": _NOW.isoformat(),
        "registered_by": str(_REGISTERED_BY),
        "producing_run_end_state": None,
        "intent": "Trial",
        "used_calibration_ids": [],
    }


@pytest.mark.unit
def test_to_payload_sorts_set_semantic_fields_deterministically() -> None:
    """Two registrations of the same logical Dataset produce byte-
    identical jsonb. Set-semantic fields (`derived_from`, `encoding.
    conforms_to`) sort canonically in the wire payload."""
    derived_a = uuid4()
    derived_b = uuid4()
    derived_c = uuid4()
    event = DatasetRegistered(
        dataset_id=uuid4(),
        name="D",
        uri="s3://b/k",
        checksum_algorithm="sha256",
        checksum_value=_GOOD_SHA256,
        byte_size=1,
        media_type="application/x-hdf5",
        conforms_to=frozenset({"https://b.example/", "https://a.example/"}),
        producing_run_id=None,
        subject_id=None,
        derived_from=frozenset({derived_a, derived_b, derived_c}),
        occurred_at=_NOW,
        registered_by=_REGISTERED_BY,
    )
    payload = to_payload(event)
    assert payload["encoding"]["conforms_to"] == ["https://a.example/", "https://b.example/"]
    assert payload["derived_from"] == sorted([str(derived_a), str(derived_b), str(derived_c)])


@pytest.mark.unit
def test_to_payload_serializes_optional_refs_when_set() -> None:
    run_id = uuid4()
    subject_id = uuid4()
    event = DatasetRegistered(
        dataset_id=uuid4(),
        name="D",
        uri="s3://b/k",
        checksum_algorithm="sha256",
        checksum_value=_GOOD_SHA256,
        byte_size=0,
        media_type="application/x-hdf5",
        conforms_to=frozenset(),
        producing_run_id=run_id,
        subject_id=subject_id,
        derived_from=frozenset(),
        occurred_at=_NOW,
        registered_by=_REGISTERED_BY,
    )
    payload = to_payload(event)
    assert payload["producing_run_id"] == str(run_id)
    assert payload["subject_id"] == str(subject_id)


@pytest.mark.unit
def test_round_trip_through_stored_envelope() -> None:
    """to_payload + from_stored is a no-op on the in-memory event."""
    dataset_id = uuid4()
    run_id = uuid4()
    subject_id = uuid4()
    derived_id = uuid4()
    original = DatasetRegistered(
        dataset_id=dataset_id,
        name="32-ID Recon",
        uri="s3://aps-32id/runs/abc/recon.h5",
        checksum_algorithm="sha256",
        checksum_value=_GOOD_SHA256,
        byte_size=1_073_741_824,
        media_type="application/x-hdf5",
        conforms_to=frozenset({"https://manual.nexusformat.org/"}),
        producing_run_id=run_id,
        subject_id=subject_id,
        derived_from=frozenset({derived_id}),
        occurred_at=_NOW,
        registered_by=_REGISTERED_BY,
    )
    new_event = to_new_event(
        event_type=event_type_name(original),
        payload=to_payload(original),
        occurred_at=original.occurred_at,
        event_id=uuid4(),
        command_name="RegisterDataset",
        correlation_id=uuid4(),
        principal_id=uuid4(),
    )
    # Round trip via the StoredEvent shape.
    from cora.infrastructure.ports.event_store import StoredEvent

    stored = StoredEvent(
        position=1,
        event_id=new_event.event_id,
        stream_type="Dataset",
        stream_id=dataset_id,
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
    """Stream contamination fails loud rather than silently."""
    from cora.infrastructure.ports.event_store import StoredEvent

    stored = StoredEvent(
        position=1,
        event_id=uuid4(),
        stream_type="Dataset",
        stream_id=uuid4(),
        version=1,
        event_type="DatasetTeleported",
        schema_version=1,
        payload={},
        correlation_id=uuid4(),
        causation_id=None,
        occurred_at=_NOW,
        recorded_at=_NOW,
        metadata={},
    )
    with pytest.raises(ValueError, match="DatasetTeleported"):
        from_stored(stored)


# ---------- additive evolution: DatasetRegistered new fields ----------


@pytest.mark.unit
def test_to_payload_includes_phase_7e_fields_when_set() -> None:
    """When Run is captured at registration, payload carries the
    end_state and intent."""
    event = DatasetRegistered(
        dataset_id=uuid4(),
        name="D",
        uri="s3://b/k",
        checksum_algorithm="sha256",
        checksum_value=_GOOD_SHA256,
        byte_size=0,
        media_type="application/x-hdf5",
        conforms_to=frozenset(),
        producing_run_id=uuid4(),
        subject_id=None,
        derived_from=frozenset(),
        occurred_at=_NOW,
        producing_run_end_state="Completed",
        intent="Trial",
        registered_by=_REGISTERED_BY,
    )
    payload = to_payload(event)
    assert payload["producing_run_end_state"] == "Completed"
    assert payload["intent"] == "Trial"


@pytest.mark.unit
def test_from_stored_pre_7e_dataset_registered_folds_with_defaults() -> None:
    """Backward compat: legacy DatasetRegistered events (without
    producing_run_end_state or intent in the payload) fold cleanly
    via payload.get defaults: end_state=None, intent='Trial'."""
    dataset_id = uuid4()
    pre_7e_payload: dict[str, object] = {
        "dataset_id": str(dataset_id),
        "name": "D",
        "uri": "s3://b/k",
        "checksum": {"algorithm": "sha256", "value": _GOOD_SHA256},
        "byte_size": 0,
        "encoding": {"media_type": "application/x-hdf5", "conforms_to": []},
        "producing_run_id": None,
        "subject_id": None,
        "derived_from": [],
        "occurred_at": _NOW.isoformat(),
        "registered_by": str(_REGISTERED_BY),
        # NOTE: producing_run_end_state + intent deliberately ABSENT
    }
    stored = StoredEvent(
        position=1,
        event_id=uuid4(),
        stream_type="Dataset",
        stream_id=dataset_id,
        version=1,
        event_type="DatasetRegistered",
        schema_version=1,
        payload=pre_7e_payload,
        correlation_id=uuid4(),
        causation_id=None,
        occurred_at=_NOW,
        recorded_at=_NOW,
        metadata={},
    )
    event = from_stored(stored)
    assert isinstance(event, DatasetRegistered)
    assert event.producing_run_end_state is None
    assert event.intent == "Trial"


# ---------- DatasetPromoted ----------


@pytest.mark.unit
def test_dataset_promoted_event_type_name() -> None:
    event = DatasetPromoted(
        dataset_id=uuid4(), reason="passed review", occurred_at=_NOW, promoted_by=_PROMOTED_BY
    )
    assert event_type_name(event) == "DatasetPromoted"


@pytest.mark.unit
def test_dataset_promoted_to_payload_serializes_primitive_fields() -> None:
    dataset_id = uuid4()
    event = DatasetPromoted(
        dataset_id=dataset_id, reason="passed review", occurred_at=_NOW, promoted_by=_PROMOTED_BY
    )
    payload = to_payload(event)
    assert payload == {
        "dataset_id": str(dataset_id),
        "reason": "passed review",
        "occurred_at": _NOW.isoformat(),
        "promoted_by": str(_PROMOTED_BY),
    }


@pytest.mark.unit
def test_dataset_promoted_round_trip_through_stored() -> None:
    """Full round-trip: original -> to_payload -> from_stored == original."""
    original = DatasetPromoted(
        dataset_id=uuid4(),
        reason="initial promotion",
        occurred_at=_NOW,
        promoted_by=_PROMOTED_BY,
    )
    new_event = to_new_event(
        event_type=event_type_name(original),
        payload=to_payload(original),
        occurred_at=original.occurred_at,
        event_id=uuid4(),
        command_name="PromoteDataset",
        correlation_id=uuid4(),
        principal_id=uuid4(),
    )
    stored = StoredEvent(
        position=1,
        event_id=new_event.event_id,
        stream_type="Dataset",
        stream_id=original.dataset_id,
        version=1,
        event_type="DatasetPromoted",
        schema_version=1,
        payload=new_event.payload,
        correlation_id=new_event.correlation_id,
        causation_id=new_event.causation_id,
        occurred_at=new_event.occurred_at,
        recorded_at=_NOW,
        metadata=new_event.metadata,
    )
    rebuilt = from_stored(stored)
    assert rebuilt == original


# ---------- Post-Q4 compensation primitive: DatasetDemoted ----------


@pytest.mark.unit
def test_dataset_demoted_event_type_name() -> None:
    event = DatasetDemoted(
        dataset_id=uuid4(), reason="calibration error", occurred_at=_NOW, demoted_by=_DEMOTED_BY
    )
    assert event_type_name(event) == "DatasetDemoted"


@pytest.mark.unit
def test_dataset_demoted_to_payload_serializes_primitive_fields() -> None:
    dataset_id = uuid4()
    event = DatasetDemoted(
        dataset_id=dataset_id, reason="calibration error", occurred_at=_NOW, demoted_by=_DEMOTED_BY
    )
    payload = to_payload(event)
    assert payload == {
        "dataset_id": str(dataset_id),
        "reason": "calibration error",
        "occurred_at": _NOW.isoformat(),
        "demoted_by": str(_DEMOTED_BY),
    }


@pytest.mark.unit
def test_dataset_demoted_round_trip_through_stored() -> None:
    """Full round-trip: original -> to_payload -> from_stored == original."""
    original = DatasetDemoted(
        dataset_id=uuid4(),
        reason="discovered calibration error",
        occurred_at=_NOW,
        demoted_by=_DEMOTED_BY,
    )
    new_event = to_new_event(
        event_type=event_type_name(original),
        payload=to_payload(original),
        occurred_at=original.occurred_at,
        event_id=uuid4(),
        command_name="DemoteDataset",
        correlation_id=uuid4(),
        principal_id=uuid4(),
    )
    stored = StoredEvent(
        position=1,
        event_id=new_event.event_id,
        stream_type="Dataset",
        stream_id=original.dataset_id,
        version=1,
        event_type="DatasetDemoted",
        schema_version=1,
        payload=new_event.payload,
        correlation_id=new_event.correlation_id,
        causation_id=new_event.causation_id,
        occurred_at=new_event.occurred_at,
        recorded_at=_NOW,
        metadata=new_event.metadata,
    )
    rebuilt = from_stored(stored)
    assert rebuilt == original


@pytest.mark.unit
@pytest.mark.parametrize(
    "event_type",
    [
        "DatasetRegistered",
        "DatasetDiscarded",
        "DatasetPromoted",
        "DatasetDemoted",
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


# ---------- DatasetRegistered.used_calibration_ids AsShot citation ----------


@pytest.mark.unit
def test_to_payload_serializes_used_calibration_ids_as_sorted_string_list() -> None:
    """The aggregate carries `tuple[UUID, ...]` for deterministic
    bytes; to_payload emits a sorted list of UUID strings. Matches
    derived_from + Run.pinned_calibration_ids precedent. Mixed order
    on the in-memory tuple must produce the same payload bytes as
    any other ordering."""
    cal_a = UUID("01900000-0000-7000-8000-00000000ca01")
    cal_b = UUID("01900000-0000-7000-8000-00000000ca02")
    cal_c = UUID("01900000-0000-7000-8000-00000000ca03")
    # Construct event with deliberately scrambled order:
    event = DatasetRegistered(
        dataset_id=uuid4(),
        name="D",
        uri="s3://b/k",
        checksum_algorithm="sha256",
        checksum_value=_GOOD_SHA256,
        byte_size=0,
        media_type="application/x-hdf5",
        conforms_to=frozenset(),
        producing_run_id=None,
        subject_id=None,
        derived_from=frozenset(),
        occurred_at=_NOW,
        used_calibration_ids=(cal_c, cal_a, cal_b),
        registered_by=_REGISTERED_BY,
    )
    payload = to_payload(event)
    assert payload["used_calibration_ids"] == sorted([str(cal_a), str(cal_b), str(cal_c)])


@pytest.mark.unit
def test_to_payload_serializes_empty_used_calibration_ids_as_empty_list() -> None:
    """Default empty tuple serializes to empty list (NOT missing key)
    so writers emit a uniform payload shape."""
    event = DatasetRegistered(
        dataset_id=uuid4(),
        name="D",
        uri="s3://b/k",
        checksum_algorithm="sha256",
        checksum_value=_GOOD_SHA256,
        byte_size=0,
        media_type="application/x-hdf5",
        conforms_to=frozenset(),
        producing_run_id=None,
        subject_id=None,
        derived_from=frozenset(),
        occurred_at=_NOW,
        registered_by=_REGISTERED_BY,
    )
    payload = to_payload(event)
    assert payload["used_calibration_ids"] == []


@pytest.mark.unit
def test_from_stored_pre_12c_dataset_registered_folds_with_empty_used_calibration_ids() -> None:
    """Backward compat: legacy DatasetRegistered events (without
    used_calibration_ids in the payload) fold cleanly via
    `payload.get("used_calibration_ids", [])` returning an empty list
    that becomes an empty tuple on the event dataclass."""
    dataset_id = uuid4()
    pre_12c_payload: dict[str, object] = {
        "dataset_id": str(dataset_id),
        "name": "D",
        "uri": "s3://b/k",
        "checksum": {"algorithm": "sha256", "value": _GOOD_SHA256},
        "byte_size": 0,
        "encoding": {"media_type": "application/x-hdf5", "conforms_to": []},
        "producing_run_id": None,
        "subject_id": None,
        "derived_from": [],
        "occurred_at": _NOW.isoformat(),
        "registered_by": str(_REGISTERED_BY),
        "producing_run_end_state": None,
        "intent": "Trial",
        # NOTE: used_calibration_ids deliberately ABSENT
    }
    stored = _stored("DatasetRegistered", pre_12c_payload)
    event = from_stored(stored)
    assert isinstance(event, DatasetRegistered)
    assert event.used_calibration_ids == ()


@pytest.mark.unit
def test_used_calibration_ids_round_trip_through_stored_envelope() -> None:
    """Full to_payload -> from_stored cycle preserves the citation
    set verbatim (UUID identity is preserved; the on-the-wire form
    is sorted but the rebuilt tuple holds UUID objects)."""
    cal_a = UUID("01900000-0000-7000-8000-00000000ca01")
    cal_b = UUID("01900000-0000-7000-8000-00000000ca02")
    event = DatasetRegistered(
        dataset_id=uuid4(),
        name="D",
        uri="s3://b/k",
        checksum_algorithm="sha256",
        checksum_value=_GOOD_SHA256,
        byte_size=0,
        media_type="application/x-hdf5",
        conforms_to=frozenset(),
        producing_run_id=None,
        subject_id=None,
        derived_from=frozenset(),
        occurred_at=_NOW,
        used_calibration_ids=(cal_b, cal_a),  # scrambled
        registered_by=_REGISTERED_BY,
    )
    payload = to_payload(event)
    stored = _stored("DatasetRegistered", payload)
    rebuilt = from_stored(stored)
    assert isinstance(rebuilt, DatasetRegistered)
    # Tuple is sorted on the wire; rebuild keeps that order.
    assert rebuilt.used_calibration_ids == (cal_a, cal_b)


@pytest.mark.unit
def test_used_calibration_ids_payload_bytes_are_order_independent() -> None:
    """Two events with the same logical citation set in different
    construction orders produce byte-identical jsonb payloads.
    Pins the determinism-of-on-the-wire-bytes invariant that the
    decider's sort guarantees."""
    cal_a = UUID("01900000-0000-7000-8000-00000000ca01")
    cal_b = UUID("01900000-0000-7000-8000-00000000ca02")
    cal_c = UUID("01900000-0000-7000-8000-00000000ca03")
    dataset_id = uuid4()

    def _build(used_calibration_ids: tuple[UUID, ...]) -> DatasetRegistered:
        return DatasetRegistered(
            dataset_id=dataset_id,
            name="D",
            uri="s3://b/k",
            checksum_algorithm="sha256",
            checksum_value=_GOOD_SHA256,
            byte_size=0,
            media_type="application/x-hdf5",
            conforms_to=frozenset(),
            producing_run_id=None,
            subject_id=None,
            derived_from=frozenset(),
            occurred_at=_NOW,
            used_calibration_ids=used_calibration_ids,
            registered_by=_REGISTERED_BY,
        )

    e1 = _build((cal_a, cal_b, cal_c))
    e2 = _build((cal_c, cal_b, cal_a))
    assert to_payload(e1)["used_calibration_ids"] == to_payload(e2)["used_calibration_ids"]
