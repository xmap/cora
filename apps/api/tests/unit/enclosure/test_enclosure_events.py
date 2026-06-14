"""Enclosure event payload + round-trip + malformed-payload unit tests."""

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import pytest

from cora.enclosure.aggregates._value_types import EnclosureId
from cora.enclosure.aggregates.enclosure import (
    EnclosureDecommissioned,
    EnclosurePermitObserved,
    EnclosureRegistered,
    event_type_name,
    from_stored,
    to_payload,
)
from cora.enclosure.aggregates.enclosure.events import (
    _check_trigger_pairing,  # pyright: ignore[reportPrivateUsage]
)
from cora.infrastructure.ports.event_store import StoredEvent
from cora.shared.facility_code import FacilityCode
from cora.shared.identity import ActorId, MonitorSourceId

_ENCLOSURE_ID = EnclosureId(UUID("01900000-0000-7000-8000-00000000e0c1"))
_FACILITY_CODE = FacilityCode("aps")
_ACTOR_ID = ActorId(UUID("01900000-0000-7000-8000-00000000ac01"))
_MONITOR_SOURCE_ID = MonitorSourceId(UUID("01900000-0000-7000-8000-00000000d0c5"))
_OCCURRED_AT = datetime(2026, 6, 8, 12, 0, 0, tzinfo=UTC)


def _stored(event_type: str, payload: dict[str, Any]) -> StoredEvent:
    return StoredEvent(
        position=1,
        event_id=UUID("01900000-0000-7000-8000-00000000eed1"),
        stream_type="Enclosure",
        stream_id=_ENCLOSURE_ID,
        version=1,
        event_type=event_type,
        schema_version=1,
        payload=payload,
        correlation_id=UUID("01900000-0000-7000-8000-00000000c0e1"),
        causation_id=None,
        occurred_at=_OCCURRED_AT,
        recorded_at=_OCCURRED_AT,
        principal_id=_ACTOR_ID,
    )


# ---------- event_type_name ----------


@pytest.mark.unit
def test_event_type_name_is_class_name() -> None:
    """event_type_name returns the dataclass __name__ for every variant."""
    registered = EnclosureRegistered(
        enclosure_id=_ENCLOSURE_ID,
        name="Hutch A",
        facility_code=_FACILITY_CODE,
        registered_by=_ACTOR_ID,
        occurred_at=_OCCURRED_AT,
    )
    observed = EnclosurePermitObserved(
        enclosure_id=_ENCLOSURE_ID,
        from_status="Unknown",
        to_status="Permitted",
        reason="PSS interlock chain healthy",
        trigger="Monitor",
        triggered_by=_MONITOR_SOURCE_ID,
        occurred_at=_OCCURRED_AT,
        monitor_ref="epics:HUTCH:A:PSS",
    )
    decommissioned = EnclosureDecommissioned(
        enclosure_id=_ENCLOSURE_ID,
        reason="enclosure consolidated into adjacent hutch",
        triggered_by=_ACTOR_ID,
        occurred_at=_OCCURRED_AT,
    )
    assert event_type_name(registered) == "EnclosureRegistered"
    assert event_type_name(observed) == "EnclosurePermitObserved"
    assert event_type_name(decommissioned) == "EnclosureDecommissioned"


# ---------- EnclosureRegistered round-trip ----------


@pytest.mark.unit
def test_enclosure_registered_round_trips() -> None:
    """EnclosureRegistered survives to_payload -> from_stored unchanged."""
    event = EnclosureRegistered(
        enclosure_id=_ENCLOSURE_ID,
        name="Hutch A",
        facility_code=_FACILITY_CODE,
        registered_by=_ACTOR_ID,
        occurred_at=_OCCURRED_AT,
    )
    payload = to_payload(event)
    rebuilt = from_stored(_stored("EnclosureRegistered", payload))
    assert rebuilt == event


# ---------- EnclosurePermitObserved round-trip ----------


@pytest.mark.unit
def test_enclosure_permit_observed_round_trips() -> None:
    """EnclosurePermitObserved survives to_payload -> from_stored unchanged."""
    event = EnclosurePermitObserved(
        enclosure_id=_ENCLOSURE_ID,
        from_status="Unknown",
        to_status="Permitted",
        reason="PSS interlock chain healthy",
        trigger="Monitor",
        triggered_by=_MONITOR_SOURCE_ID,
        occurred_at=_OCCURRED_AT,
        monitor_ref="epics:HUTCH:A:PSS",
    )
    payload = to_payload(event)
    rebuilt = from_stored(_stored("EnclosurePermitObserved", payload))
    assert rebuilt == event


# ---------- EnclosureDecommissioned round-trip ----------


@pytest.mark.unit
def test_enclosure_decommissioned_round_trips() -> None:
    """EnclosureDecommissioned survives to_payload -> from_stored unchanged."""
    event = EnclosureDecommissioned(
        enclosure_id=_ENCLOSURE_ID,
        reason="enclosure consolidated into adjacent hutch",
        triggered_by=_ACTOR_ID,
        occurred_at=_OCCURRED_AT,
    )
    payload = to_payload(event)
    rebuilt = from_stored(_stored("EnclosureDecommissioned", payload))
    assert rebuilt == event


# ---------- monitor_ref wire-shape ----------


@pytest.mark.unit
def test_permit_observed_monitor_ref_present_on_wire_when_set() -> None:
    """to_payload includes monitor_ref in the dict when the field is populated."""
    event = EnclosurePermitObserved(
        enclosure_id=_ENCLOSURE_ID,
        from_status="Unknown",
        to_status="Permitted",
        reason="PSS interlock chain healthy",
        trigger="Monitor",
        triggered_by=_MONITOR_SOURCE_ID,
        occurred_at=_OCCURRED_AT,
        monitor_ref="epics:HUTCH:A:PSS",
    )
    payload = to_payload(event)
    assert payload["monitor_ref"] == "epics:HUTCH:A:PSS"


@pytest.mark.unit
def test_permit_observed_monitor_ref_omitted_on_wire_when_none() -> None:
    """to_payload omits the monitor_ref key entirely when the field is None.

    The dataclass `__post_init__` enforces monitor_ref-required-when-Monitor at
    construction, so we bypass it with `object.__new__` + `object.__setattr__`
    to exercise the serialization branch in isolation. This guards the wire
    convention shared with Supply's transition events: omit-when-None rather
    than emit-as-null.
    """
    event = object.__new__(EnclosurePermitObserved)
    object.__setattr__(event, "enclosure_id", _ENCLOSURE_ID)
    object.__setattr__(event, "from_status", "Unknown")
    object.__setattr__(event, "to_status", "Permitted")
    object.__setattr__(event, "reason", "PSS interlock chain healthy")
    object.__setattr__(event, "trigger", "Monitor")
    object.__setattr__(event, "triggered_by", _MONITOR_SOURCE_ID)
    object.__setattr__(event, "occurred_at", _OCCURRED_AT)
    object.__setattr__(event, "monitor_ref", None)
    payload = to_payload(event)
    assert "monitor_ref" not in payload


# ---------- _check_trigger_pairing invariant ----------


@pytest.mark.unit
def test_check_trigger_pairing_rejects_operator_trigger() -> None:
    """trigger='Operator' is rejected per the D6.L2 anti-lock."""
    with pytest.raises(ValueError, match="trigger must be 'Monitor'"):
        _check_trigger_pairing(
            trigger="Operator",
            triggered_by=_MONITOR_SOURCE_ID,
            monitor_ref="epics:HUTCH:A:PSS",
        )


@pytest.mark.unit
def test_check_trigger_pairing_rejects_monitor_with_none_monitor_ref() -> None:
    """trigger='Monitor' without a populated monitor_ref is rejected."""
    with pytest.raises(ValueError, match="monitor_ref is required when trigger"):
        _check_trigger_pairing(
            trigger="Monitor",
            triggered_by=_MONITOR_SOURCE_ID,
            monitor_ref=None,
        )


# ---------- from_stored error paths ----------


@pytest.mark.unit
def test_from_stored_unknown_event_type_raises_value_error() -> None:
    """from_stored raises ValueError on a discriminator it cannot dispatch."""
    with pytest.raises(ValueError, match="Unknown EnclosureEvent event_type"):
        from_stored(_stored("EnclosureResurrected", {}))


@pytest.mark.unit
def test_from_stored_enclosure_registered_missing_key_raises_malformed() -> None:
    """A payload missing a required key surfaces as 'Malformed Enclosure...'."""
    bad_payload: dict[str, Any] = {
        "enclosure_id": str(_ENCLOSURE_ID),
        # missing name, facility_code, registered_by, occurred_at
    }
    with pytest.raises(ValueError, match="Malformed EnclosureRegistered payload"):
        from_stored(_stored("EnclosureRegistered", bad_payload))


@pytest.mark.unit
def test_from_stored_enclosure_registered_wrong_type_field_raises_malformed() -> None:
    """A payload with a non-UUID-shaped id surfaces as 'Malformed Enclosure...'."""
    bad_payload: dict[str, Any] = {
        "enclosure_id": "not-a-uuid",
        "name": "Hutch A",
        "facility_code": str(_FACILITY_CODE),
        "registered_by": str(_ACTOR_ID),
        "occurred_at": _OCCURRED_AT.isoformat(),
    }
    with pytest.raises(ValueError, match="Malformed EnclosureRegistered payload"):
        from_stored(_stored("EnclosureRegistered", bad_payload))
