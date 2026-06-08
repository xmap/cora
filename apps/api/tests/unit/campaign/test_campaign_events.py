"""CampaignEvent serialization round-trips + Identifier (external-ref) helpers."""

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import pytest

from cora.campaign.aggregates.campaign import (
    CampaignAbandoned,
    CampaignClosed,
    CampaignHeld,
    CampaignRegistered,
    CampaignResumed,
    CampaignStarted,
    deserialize_external_ref,
    event_type_name,
    from_stored,
    serialize_external_ref,
    to_payload,
)
from cora.infrastructure.ports.event_store import StoredEvent
from cora.shared.identifier import Identifier

_NOW = datetime(2026, 5, 16, 12, 0, 0, tzinfo=UTC)
_CAMPAIGN_ID = UUID("01900000-0000-7000-8000-00000000a001")
_LEAD_ACTOR_ID = UUID("01900000-0000-7000-8000-00000000a002")
_SUBJECT_ID = UUID("01900000-0000-7000-8000-00000000a003")


def _stored(event_type: str, payload: dict[str, Any]) -> StoredEvent:
    return StoredEvent(
        position=1,
        event_id=uuid4(),
        stream_type="Campaign",
        stream_id=_CAMPAIGN_ID,
        version=1,
        event_type=event_type,
        schema_version=1,
        payload=payload,
        correlation_id=uuid4(),
        causation_id=None,
        occurred_at=_NOW,
        recorded_at=_NOW,
    )


# ---------- serialize_external_ref / deserialize_external_ref ----------


@pytest.mark.unit
def test_serialize_external_ref() -> None:
    ref = Identifier(scheme="proposal", value="2025-100")
    assert serialize_external_ref(ref) == {"scheme": "proposal", "value": "2025-100"}


@pytest.mark.unit
def test_deserialize_external_ref() -> None:
    ref = deserialize_external_ref({"scheme": "proposal", "value": "2025-100"})
    assert ref == Identifier(scheme="proposal", value="2025-100")


@pytest.mark.unit
def test_external_ref_round_trip() -> None:
    original = Identifier(scheme="btr", value="ABC-12345")
    rebuilt = deserialize_external_ref(serialize_external_ref(original))
    assert rebuilt == original


@pytest.mark.unit
def test_deserialize_external_ref_rejects_missing_scheme() -> None:
    with pytest.raises(ValueError, match="Malformed Identifier payload"):
        deserialize_external_ref({"value": "abc"})


@pytest.mark.unit
def test_deserialize_external_ref_rejects_missing_value() -> None:
    with pytest.raises(ValueError, match="Malformed Identifier payload"):
        deserialize_external_ref({"scheme": "proposal"})


# ---------- CampaignRegistered round trip ----------


@pytest.mark.unit
def test_campaign_registered_round_trip_minimal() -> None:
    """No subject, no description, no tags, no external refs."""
    event = CampaignRegistered(
        campaign_id=_CAMPAIGN_ID,
        name="basic",
        intent="Series",
        lead_actor_id=_LEAD_ACTOR_ID,
        subject_id=None,
        description=None,
        tags=frozenset(),
        external_refs=frozenset(),
        external_id=None,
        occurred_at=_NOW,
    )
    payload = to_payload(event)
    rebuilt = from_stored(_stored(event_type_name(event), payload))
    assert rebuilt == event


@pytest.mark.unit
def test_campaign_registered_round_trip_full() -> None:
    """All optional fields populated; tags sorted; external_refs included."""
    refs = frozenset(
        {
            Identifier(scheme="proposal", value="2025-100"),
            Identifier(scheme="visit", value="V-77"),
        }
    )
    event = CampaignRegistered(
        campaign_id=_CAMPAIGN_ID,
        name="In-situ heating",
        intent="Series",
        lead_actor_id=_LEAD_ACTOR_ID,
        subject_id=_SUBJECT_ID,
        description="long-form description",
        tags=frozenset({"battery", "heating"}),
        external_refs=refs,
        external_id="DOI:10.1234/abc",
        occurred_at=_NOW,
    )
    payload = to_payload(event)
    assert payload["tags"] == ["battery", "heating"]
    assert payload["external_refs"] == [
        {"scheme": "proposal", "value": "2025-100"},
        {"scheme": "visit", "value": "V-77"},
    ]
    assert payload["subject_id"] == str(_SUBJECT_ID)
    assert payload["external_id"] == "DOI:10.1234/abc"
    rebuilt = from_stored(_stored(event_type_name(event), payload))
    assert rebuilt == event


@pytest.mark.unit
def test_campaign_registered_serializes_subject_none_as_none() -> None:
    event = CampaignRegistered(
        campaign_id=_CAMPAIGN_ID,
        name="x",
        intent="Series",
        lead_actor_id=_LEAD_ACTOR_ID,
        subject_id=None,
        description=None,
        tags=frozenset(),
        external_refs=frozenset(),
        external_id=None,
        occurred_at=_NOW,
    )
    payload = to_payload(event)
    assert payload["subject_id"] is None
    assert payload["description"] is None
    assert payload["external_id"] is None


@pytest.mark.unit
def test_campaign_registered_from_stored_uses_get_for_nullable_keys() -> None:
    """Forward-compat: defensive .get() on optional payload keys."""
    payload: dict[str, Any] = {
        "campaign_id": str(_CAMPAIGN_ID),
        "name": "min",
        "intent": "Series",
        "lead_actor_id": str(_LEAD_ACTOR_ID),
        # subject_id, description, external_id, external_refs all omitted
        "tags": [],
        "occurred_at": _NOW.isoformat(),
    }
    rebuilt = from_stored(_stored("CampaignRegistered", payload))
    assert isinstance(rebuilt, CampaignRegistered)
    assert rebuilt.subject_id is None
    assert rebuilt.description is None
    assert rebuilt.external_id is None
    assert rebuilt.external_refs == frozenset()


@pytest.mark.unit
def test_campaign_registered_from_stored_rejects_malformed_payload() -> None:
    with pytest.raises(ValueError, match="Malformed CampaignRegistered payload"):
        from_stored(_stored("CampaignRegistered", {}))


# ---------- CampaignStarted round trip ----------


@pytest.mark.unit
def test_campaign_started_round_trip() -> None:
    event = CampaignStarted(campaign_id=_CAMPAIGN_ID, occurred_at=_NOW)
    payload = to_payload(event)
    rebuilt = from_stored(_stored(event_type_name(event), payload))
    assert rebuilt == event


@pytest.mark.unit
def test_campaign_started_from_stored_rejects_malformed_payload() -> None:
    with pytest.raises(ValueError, match="Malformed CampaignStarted payload"):
        from_stored(_stored("CampaignStarted", {}))


# ---------- CampaignHeld round trip ----------


@pytest.mark.unit
def test_campaign_held_round_trip() -> None:
    event = CampaignHeld(
        campaign_id=_CAMPAIGN_ID,
        reason="beam interruption",
        occurred_at=_NOW,
    )
    payload = to_payload(event)
    assert payload["reason"] == "beam interruption"
    rebuilt = from_stored(_stored(event_type_name(event), payload))
    assert rebuilt == event


@pytest.mark.unit
def test_campaign_held_from_stored_rejects_malformed_payload() -> None:
    with pytest.raises(ValueError, match="Malformed CampaignHeld payload"):
        from_stored(_stored("CampaignHeld", {}))


# ---------- CampaignResumed round trip ----------


@pytest.mark.unit
def test_campaign_resumed_round_trip() -> None:
    event = CampaignResumed(campaign_id=_CAMPAIGN_ID, occurred_at=_NOW)
    payload = to_payload(event)
    rebuilt = from_stored(_stored(event_type_name(event), payload))
    assert rebuilt == event


@pytest.mark.unit
def test_campaign_resumed_from_stored_rejects_malformed_payload() -> None:
    with pytest.raises(ValueError, match="Malformed CampaignResumed payload"):
        from_stored(_stored("CampaignResumed", {}))


# ---------- CampaignClosed round trip ----------


@pytest.mark.unit
def test_campaign_closed_round_trip() -> None:
    event = CampaignClosed(campaign_id=_CAMPAIGN_ID, occurred_at=_NOW)
    payload = to_payload(event)
    rebuilt = from_stored(_stored(event_type_name(event), payload))
    assert rebuilt == event


@pytest.mark.unit
def test_campaign_closed_from_stored_rejects_malformed_payload() -> None:
    with pytest.raises(ValueError, match="Malformed CampaignClosed payload"):
        from_stored(_stored("CampaignClosed", {}))


# ---------- CampaignAbandoned round trip ----------


@pytest.mark.unit
def test_campaign_abandoned_round_trip() -> None:
    event = CampaignAbandoned(
        campaign_id=_CAMPAIGN_ID,
        reason="instrument failure; no recovery in window",
        occurred_at=_NOW,
    )
    payload = to_payload(event)
    assert payload["reason"] == "instrument failure; no recovery in window"
    rebuilt = from_stored(_stored(event_type_name(event), payload))
    assert rebuilt == event


@pytest.mark.unit
def test_campaign_abandoned_from_stored_rejects_malformed_payload() -> None:
    with pytest.raises(ValueError, match="Malformed CampaignAbandoned payload"):
        from_stored(_stored("CampaignAbandoned", {}))


# ---------- Unknown event_type ----------


@pytest.mark.unit
def test_from_stored_rejects_unknown_event_type() -> None:
    with pytest.raises(ValueError, match="Unknown CampaignEvent event_type"):
        from_stored(_stored("WhateverEvent", {}))


# ---------- event_type_name ----------


@pytest.mark.unit
def test_event_type_name_matches_class_name() -> None:
    event = CampaignStarted(campaign_id=_CAMPAIGN_ID, occurred_at=_NOW)
    assert event_type_name(event) == "CampaignStarted"


# ---------- CampaignRunAdded / CampaignRunRemoved ----------


@pytest.mark.unit
def test_campaign_run_added_round_trips() -> None:
    from uuid import uuid4

    from cora.campaign.aggregates.campaign import CampaignRunAdded

    original = CampaignRunAdded(
        campaign_id=_CAMPAIGN_ID,
        run_id=uuid4(),
        occurred_at=_NOW,
    )
    stored = _stored("CampaignRunAdded", to_payload(original))
    assert from_stored(stored) == original


@pytest.mark.unit
def test_campaign_run_removed_round_trips_with_reason() -> None:
    from uuid import uuid4

    from cora.campaign.aggregates.campaign import CampaignRunRemoved

    original = CampaignRunRemoved(
        campaign_id=_CAMPAIGN_ID,
        run_id=uuid4(),
        reason="moved to follow-on campaign",
        occurred_at=_NOW,
    )
    stored = _stored("CampaignRunRemoved", to_payload(original))
    assert from_stored(stored) == original


@pytest.mark.unit
def test_from_stored_rejects_malformed_campaign_run_added_payload() -> None:
    with pytest.raises(ValueError, match="Malformed CampaignRunAdded payload"):
        from_stored(_stored("CampaignRunAdded", {}))


@pytest.mark.unit
def test_from_stored_rejects_malformed_campaign_run_removed_payload() -> None:
    with pytest.raises(ValueError, match="Malformed CampaignRunRemoved payload"):
        from_stored(_stored("CampaignRunRemoved", {}))
