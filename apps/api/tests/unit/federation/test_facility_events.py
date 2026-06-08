"""Facility event payload + round-trip + malformed-payload unit tests."""

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import pytest

from cora.federation.aggregates._value_types import FacilityId
from cora.federation.aggregates.facility import (
    FacilityDecommissioned,
    FacilityKind,
    FacilityRegistered,
    event_type_name,
    from_stored,
    to_payload,
)
from cora.infrastructure.ports.event_store import StoredEvent
from cora.shared.facility_code import FacilityCode
from cora.shared.identifier import AlternateIdentifier, AlternateIdentifierKind
from cora.shared.identity import ActorId

_FACILITY_ID = FacilityId(UUID("01900000-0000-7000-8000-00000000fac1"))
_PARENT_FACILITY_ID = FacilityId(UUID("01900000-0000-7000-8000-00000000fac2"))
_ACTOR_ID = ActorId(UUID("01900000-0000-7000-8000-00000000ac01"))
_NOW = datetime(2026, 6, 8, 12, 0, 0, tzinfo=UTC)
_CODE = FacilityCode("aps")


def _stored(event_type: str, payload: dict[str, Any]) -> StoredEvent:
    return StoredEvent(
        position=1,
        event_id=UUID("01900000-0000-7000-8000-00000000eed1"),
        stream_type="Facility",
        stream_id=_FACILITY_ID,
        version=1,
        event_type=event_type,
        schema_version=1,
        payload=payload,
        correlation_id=UUID("01900000-0000-7000-8000-00000000c0e1"),
        causation_id=None,
        occurred_at=_NOW,
        recorded_at=_NOW,
        principal_id=_ACTOR_ID,
    )


# ---------- event_type_name ----------


@pytest.mark.unit
def test_event_type_name_is_class_name() -> None:
    registered = FacilityRegistered(
        facility_id=_FACILITY_ID,
        code=_CODE,
        display_name="Advanced Photon Source",
        kind=FacilityKind.SITE,
        parent_id=None,
        registered_by=_ACTOR_ID,
        occurred_at=_NOW,
    )
    assert event_type_name(registered) == "FacilityRegistered"

    decommissioned = FacilityDecommissioned(
        facility_id=_FACILITY_ID,
        decommissioned_by=_ACTOR_ID,
        occurred_at=_NOW,
    )
    assert event_type_name(decommissioned) == "FacilityDecommissioned"


# ---------- FacilityRegistered round-trip ----------


@pytest.mark.unit
def test_facility_registered_site_round_trips() -> None:
    event = FacilityRegistered(
        facility_id=_FACILITY_ID,
        code=_CODE,
        display_name="Advanced Photon Source",
        kind=FacilityKind.SITE,
        parent_id=None,
        registered_by=_ACTOR_ID,
        occurred_at=_NOW,
    )
    payload = to_payload(event)
    rebuilt = from_stored(_stored("FacilityRegistered", payload))
    assert rebuilt == event


@pytest.mark.unit
def test_facility_registered_area_round_trips() -> None:
    event = FacilityRegistered(
        facility_id=_FACILITY_ID,
        code=FacilityCode("2-bm"),
        display_name="2-BM Beamline",
        kind=FacilityKind.AREA,
        parent_id=_PARENT_FACILITY_ID,
        registered_by=_ACTOR_ID,
        occurred_at=_NOW,
    )
    payload = to_payload(event)
    rebuilt = from_stored(_stored("FacilityRegistered", payload))
    assert rebuilt == event


@pytest.mark.unit
def test_facility_registered_with_alternate_identifiers_round_trips() -> None:
    alts = frozenset(
        {
            AlternateIdentifier(kind=AlternateIdentifierKind.SERIAL_NUMBER, value="APS-2BM"),
            AlternateIdentifier(kind=AlternateIdentifierKind.OTHER, value="aps-id-42"),
        }
    )
    event = FacilityRegistered(
        facility_id=_FACILITY_ID,
        code=_CODE,
        display_name="Advanced Photon Source",
        kind=FacilityKind.SITE,
        parent_id=None,
        registered_by=_ACTOR_ID,
        occurred_at=_NOW,
        alternate_identifiers=alts,
    )
    payload = to_payload(event)
    rebuilt = from_stored(_stored("FacilityRegistered", payload))
    assert rebuilt == event


@pytest.mark.unit
def test_facility_registered_payload_sorts_alternate_identifiers_deterministically() -> None:
    """Round-trip is order-insensitive but the serialised list MUST be sorted
    so byte-equal payloads compare equal across runs."""
    alts = frozenset(
        {
            AlternateIdentifier(kind=AlternateIdentifierKind.OTHER, value="zzz"),
            AlternateIdentifier(kind=AlternateIdentifierKind.SERIAL_NUMBER, value="aaa"),
        }
    )
    payload = to_payload(
        FacilityRegistered(
            facility_id=_FACILITY_ID,
            code=_CODE,
            display_name="Advanced Photon Source",
            kind=FacilityKind.SITE,
            parent_id=None,
            registered_by=_ACTOR_ID,
            occurred_at=_NOW,
            alternate_identifiers=alts,
        )
    )
    alt_list = payload["alternate_identifiers"]
    assert alt_list == [
        {"kind": "Other", "value": "zzz"},
        {"kind": "SerialNumber", "value": "aaa"},
    ]


# ---------- FacilityDecommissioned round-trip ----------


@pytest.mark.unit
def test_facility_decommissioned_round_trips() -> None:
    event = FacilityDecommissioned(
        facility_id=_FACILITY_ID,
        decommissioned_by=_ACTOR_ID,
        occurred_at=_NOW,
        reason="end-of-life",
    )
    payload = to_payload(event)
    rebuilt = from_stored(_stored("FacilityDecommissioned", payload))
    assert rebuilt == event


@pytest.mark.unit
def test_facility_decommissioned_without_reason_round_trips() -> None:
    event = FacilityDecommissioned(
        facility_id=_FACILITY_ID,
        decommissioned_by=_ACTOR_ID,
        occurred_at=_NOW,
    )
    payload = to_payload(event)
    rebuilt = from_stored(_stored("FacilityDecommissioned", payload))
    assert rebuilt == event
    assert isinstance(rebuilt, FacilityDecommissioned)
    assert rebuilt.reason is None


# ---------- malformed payload wraps ----------


@pytest.mark.unit
def test_from_stored_facility_registered_missing_key_raises_malformed() -> None:
    bad_payload: dict[str, Any] = {
        "facility_id": str(_FACILITY_ID),
        # missing required keys
    }
    with pytest.raises(ValueError, match="Malformed FacilityRegistered payload"):
        from_stored(_stored("FacilityRegistered", bad_payload))


@pytest.mark.unit
def test_from_stored_facility_registered_invalid_code_raises_malformed() -> None:
    bad_payload: dict[str, Any] = {
        "facility_id": str(_FACILITY_ID),
        "code": "Has Uppercase",  # violates FacilityCode pattern
        "display_name": "Advanced Photon Source",
        "kind": "Site",
        "parent_id": None,
        "alternate_identifiers": [],
        "registered_by": str(_ACTOR_ID),
        "occurred_at": _NOW.isoformat(),
    }
    with pytest.raises(ValueError, match="Malformed FacilityRegistered payload"):
        from_stored(_stored("FacilityRegistered", bad_payload))


@pytest.mark.unit
def test_from_stored_facility_registered_invalid_kind_raises_malformed() -> None:
    bad_payload: dict[str, Any] = {
        "facility_id": str(_FACILITY_ID),
        "code": "aps",
        "display_name": "Advanced Photon Source",
        "kind": "Sector",  # not in FacilityKind closed enum
        "parent_id": None,
        "alternate_identifiers": [],
        "registered_by": str(_ACTOR_ID),
        "occurred_at": _NOW.isoformat(),
    }
    with pytest.raises(ValueError, match="Malformed FacilityRegistered payload"):
        from_stored(_stored("FacilityRegistered", bad_payload))


@pytest.mark.unit
def test_from_stored_facility_decommissioned_missing_key_raises_malformed() -> None:
    bad_payload: dict[str, Any] = {
        "facility_id": str(_FACILITY_ID),
        # missing decommissioned_by + occurred_at
    }
    with pytest.raises(ValueError, match="Malformed FacilityDecommissioned payload"):
        from_stored(_stored("FacilityDecommissioned", bad_payload))


@pytest.mark.unit
def test_from_stored_unknown_event_type_raises_value_error() -> None:
    with pytest.raises(ValueError, match="Unknown Facility event type"):
        from_stored(_stored("FacilityResurrected", {}))
