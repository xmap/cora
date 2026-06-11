"""Unit tests for the Acquisition evolver + events round-trip.

The aggregate ships one event arm (AcquisitionRecorded -> RECORDED),
terminal at genesis. Tests lock the genesis fold (including the
dual-time mapping occurred_at -> recorded_at) and the from_stored /
to_payload round-trip including JSON serialization of the settings /
evidence carrier dicts.
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.data.aggregates.acquisition import (
    AcquisitionRecorded,
    AcquisitionStatus,
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


def _event(
    *,
    producing_run_id: UUID | None = None,
    settings: dict[str, object] | None = None,
    evidence: dict[str, object] | None = None,
) -> AcquisitionRecorded:
    return AcquisitionRecorded(
        acquisition_id=uuid4(),
        dataset_id=uuid4(),
        producing_asset_id=uuid4(),
        producing_run_id=producing_run_id,
        captured_at=_CAPTURED_AT,
        settings=settings if settings is not None else {"exposure_ms": 200},
        evidence=evidence if evidence is not None else {"frames": 1801},
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
def test_evolve_copies_carrier_dicts_defensively() -> None:
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
        evidence={"frames": 1801, "ok": True},
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
