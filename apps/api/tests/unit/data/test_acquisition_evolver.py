"""Unit tests for the Acquisition evolver + events round-trip.

The aggregate ships one event arm (AcquisitionRecorded -> RECORDED),
terminal at genesis. Tests lock the genesis fold (including the
dual-time mapping occurred_at -> recorded_at) and the from_stored /
to_payload round-trip, including JSON serialization of the settings
carrier dict and the AcquisitionEvidence VO.
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.data.aggregates.acquisition import (
    AcquisitionEvidence,
    AcquisitionRecorded,
    AcquisitionStatus,
    CapturedAtSource,
    evolve,
    fold,
    from_stored,
    to_payload,
)
from cora.infrastructure.ports.event_store import StoredEvent
from cora.shared.identity import ActorId

_CAPTURED_AT = datetime(2026, 6, 10, 9, 0, 0, tzinfo=UTC)
_OCCURRED_AT = datetime(2026, 6, 11, 12, 0, 0, tzinfo=UTC)
_RECORDED_BY = ActorId(UUID("01900000-0000-7000-8000-0000000000c1"))
_DEFAULT_EVIDENCE = AcquisitionEvidence(projection_count=1801)


def _event(
    *,
    producing_run_id: UUID | None = None,
    settings: dict[str, object] | None = None,
    evidence: AcquisitionEvidence | None = None,
) -> AcquisitionRecorded:
    return AcquisitionRecorded(
        acquisition_id=uuid4(),
        dataset_id=uuid4(),
        producing_asset_id=uuid4(),
        producing_run_id=producing_run_id,
        captured_at=_CAPTURED_AT,
        settings=settings if settings is not None else {"exposure_ms": 200},
        evidence=evidence if evidence is not None else _DEFAULT_EVIDENCE,
        occurred_at=_OCCURRED_AT,
        recorded_by=_RECORDED_BY,
    )


@pytest.mark.unit
def test_evolve_recorded_creates_acquisition_with_recorded_status() -> None:
    event = _event()
    state = evolve(state=None, event=event)
    assert state.id == event.acquisition_id
    assert state.dataset_id == event.dataset_id
    assert state.producing_asset_id == event.producing_asset_id
    assert state.producing_run_id is None
    assert state.status is AcquisitionStatus.RECORDED


@pytest.mark.unit
def test_evolve_maps_occurred_at_to_recorded_at_and_keeps_captured_at() -> None:
    """Dual-time fold: occurred_at -> recorded_at; captured_at is verbatim."""
    event = _event()
    state = evolve(state=None, event=event)
    assert state.recorded_at == _OCCURRED_AT
    assert state.captured_at == _CAPTURED_AT
    assert state.recorded_at != state.captured_at


@pytest.mark.unit
def test_evolve_preserves_producing_run_id_when_set() -> None:
    run_id = uuid4()
    state = evolve(state=None, event=_event(producing_run_id=run_id))
    assert state.producing_run_id == run_id


@pytest.mark.unit
def test_evolve_copies_settings_dict_defensively() -> None:
    settings: dict[str, object] = {"a": 1}
    state = evolve(state=None, event=_event(settings=settings))
    settings["b"] = 2
    assert state.settings == {"a": 1}


@pytest.mark.unit
def test_fold_single_event_equals_evolve() -> None:
    event = _event()
    assert fold([event]) == evolve(state=None, event=event)


@pytest.mark.unit
def test_fold_empty_returns_none() -> None:
    assert fold([]) is None


@pytest.mark.unit
def test_to_payload_from_stored_round_trip() -> None:
    event = _event(
        producing_run_id=uuid4(),
        settings={"exposure_ms": 200, "roi": {"w": 1024}},
        evidence=AcquisitionEvidence(
            reader_kind="DataExchange",
            checksum_computer_kind="PosixChecksum",
            captured_at_source=CapturedAtSource.END_DATE,
            captured_at_raw="2026-06-10T09:00:00",
            projection_count=1501,
            flat_count=40,
            dark_count=20,
            invalid_count=0,
            commanded_projection_count=1501,
            commanded_flat_count=40,
            commanded_dark_count=20,
            dropped_frame_count=0,
            projection_angle_count=1501,
            projection_angle_first=0.0,
            projection_angle_last=180.0,
        ),
    )
    payload = to_payload(event)
    stored = StoredEvent(
        position=1,
        event_id=uuid4(),
        stream_type="Acquisition",
        stream_id=event.acquisition_id,
        version=1,
        event_type="AcquisitionRecorded",
        schema_version=1,
        payload=payload,
        correlation_id=uuid4(),
        causation_id=None,
        occurred_at=_OCCURRED_AT,
        recorded_at=_OCCURRED_AT,
    )
    rebuilt = from_stored(stored)
    assert rebuilt == event


@pytest.mark.unit
def test_to_payload_serializes_none_run_id_as_null() -> None:
    payload = to_payload(_event(producing_run_id=None))
    assert payload["producing_run_id"] is None


@pytest.mark.unit
def test_to_payload_omits_none_evidence_fields_rather_than_nulling() -> None:
    payload = to_payload(_event(evidence=AcquisitionEvidence(projection_count=5)))
    assert payload["evidence"] == {"projection_count": 5}


@pytest.mark.unit
def test_to_payload_no_evidence_supplied_serializes_as_empty_object() -> None:
    payload = to_payload(_event(evidence=AcquisitionEvidence()))
    assert payload["evidence"] == {}


@pytest.mark.unit
def test_to_payload_key_ordering_is_pinned() -> None:
    payload = to_payload(_event())
    assert list(payload.keys()) == [
        "acquisition_id",
        "dataset_id",
        "producing_asset_id",
        "producing_run_id",
        "captured_at",
        "settings",
        "evidence",
        "occurred_at",
        "recorded_by",
    ]


@pytest.mark.unit
def test_from_stored_unknown_event_type_raises() -> None:
    stored = StoredEvent(
        position=1,
        event_id=uuid4(),
        stream_type="Acquisition",
        stream_id=uuid4(),
        version=1,
        event_type="AcquisitionSuperseded",
        schema_version=1,
        payload={},
        correlation_id=uuid4(),
        causation_id=None,
        occurred_at=_OCCURRED_AT,
        recorded_at=_OCCURRED_AT,
    )
    with pytest.raises(ValueError, match="Unknown AcquisitionEvent event_type"):
        from_stored(stored)


@pytest.mark.unit
def test_from_stored_malformed_payload_raises_wrapped() -> None:
    stored = StoredEvent(
        position=1,
        event_id=uuid4(),
        stream_type="Acquisition",
        stream_id=uuid4(),
        version=1,
        event_type="AcquisitionRecorded",
        schema_version=1,
        payload={"acquisition_id": "not-a-uuid"},
        correlation_id=uuid4(),
        causation_id=None,
        occurred_at=_OCCURRED_AT,
        recorded_at=_OCCURRED_AT,
    )
    with pytest.raises(ValueError, match="Malformed AcquisitionRecorded payload"):
        from_stored(stored)


@pytest.mark.unit
def test_from_stored_evidence_with_unknown_key_raises_wrapped() -> None:
    """A stored payload whose nested evidence no longer validates (an
    old-shape carrier from before this VO existed, or a hand-written
    store mutation) is Malformed, not silently reconstructed or a raw
    InvalidAcquisitionEvidenceError leaking past the aggregate boundary."""
    payload = to_payload(_event())
    payload["evidence"] = {"frames": 1801}
    stored = StoredEvent(
        position=1,
        event_id=uuid4(),
        stream_type="Acquisition",
        stream_id=uuid4(),
        version=1,
        event_type="AcquisitionRecorded",
        schema_version=1,
        payload=payload,
        correlation_id=uuid4(),
        causation_id=None,
        occurred_at=_OCCURRED_AT,
        recorded_at=_OCCURRED_AT,
    )
    with pytest.raises(ValueError, match="Malformed AcquisitionRecorded payload"):
        from_stored(stored)


@pytest.mark.unit
def test_from_stored_evidence_with_unknown_captured_at_source_raises_wrapped() -> None:
    """A future layout naming a fourth captured_at_source (see
    CapturedAtSource's docstring) fails loud on replay, not silently."""
    payload = to_payload(_event())
    payload["evidence"] = {"captured_at_source": "acquisition_time"}
    stored = StoredEvent(
        position=1,
        event_id=uuid4(),
        stream_type="Acquisition",
        stream_id=uuid4(),
        version=1,
        event_type="AcquisitionRecorded",
        schema_version=1,
        payload=payload,
        correlation_id=uuid4(),
        causation_id=None,
        occurred_at=_OCCURRED_AT,
        recorded_at=_OCCURRED_AT,
    )
    with pytest.raises(ValueError, match="Malformed AcquisitionRecorded payload"):
        from_stored(stored)
