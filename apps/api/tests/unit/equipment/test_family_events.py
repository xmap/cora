"""Unit tests for the Family aggregate's event (de)serialization helpers."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from cora.equipment.aggregates.family.affordance import Affordance
from cora.equipment.aggregates.family.events import (
    FamilyDefined,
    FamilyDeprecated,
    FamilyPresentsAsAdded,
    FamilyPresentsAsRemoved,
    FamilySettingsSchemaUpdated,
    FamilyVersioned,
    event_type_name,
    from_stored,
    to_payload,
)
from cora.infrastructure.ports.event_store import StoredEvent

_NOW = datetime(2026, 5, 10, 12, 0, 0, tzinfo=UTC)


def _stored(
    event_type: str,
    payload: dict[str, object],
    *,
    stream_id: object | None = None,
) -> StoredEvent:
    """Build a StoredEvent shell — only event_type + payload are read by from_stored."""
    return StoredEvent(
        position=1,
        event_id=uuid4(),
        stream_type="Family",
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
    event = FamilyDefined(family_id=uuid4(), name="Tomography", occurred_at=_NOW)
    assert event_type_name(event) == "FamilyDefined"


@pytest.mark.unit
def test_to_payload_serializes_capability_defined_to_primitives() -> None:
    family_id = uuid4()
    event = FamilyDefined(family_id=family_id, name="Tomography", occurred_at=_NOW)
    assert to_payload(event) == {
        "family_id": str(family_id),
        "name": "Tomography",
        "occurred_at": _NOW.isoformat(),
        "affordances": [],
    }


@pytest.mark.unit
def test_from_stored_rebuilds_capability_defined() -> None:
    family_id = uuid4()
    stored = _stored(
        "FamilyDefined",
        {
            "family_id": str(family_id),
            "name": "Tomography",
            "occurred_at": _NOW.isoformat(),
        },
    )
    rebuilt = from_stored(stored)
    assert rebuilt == FamilyDefined(family_id=family_id, name="Tomography", occurred_at=_NOW)


@pytest.mark.unit
def test_to_payload_then_from_stored_round_trips() -> None:
    """Round-trip safety net: the (de)serialization pair must be each other's inverse."""
    original = FamilyDefined(family_id=uuid4(), name="Tomography", occurred_at=_NOW)
    stored = _stored("FamilyDefined", to_payload(original))
    assert from_stored(stored) == original


@pytest.mark.unit
def test_from_stored_raises_on_unknown_event_type() -> None:
    """Foreign event_types in a stream must fail loud, not be silently dropped."""
    stored = _stored("ActorRegistered", {})
    with pytest.raises(ValueError, match="Unknown FamilyEvent event_type"):
        from_stored(stored)


# ---------- FamilyVersioned ----------


@pytest.mark.unit
def test_event_type_name_returns_capability_versioned_class_name() -> None:
    event = FamilyVersioned(family_id=uuid4(), version_tag="v2", occurred_at=_NOW)
    assert event_type_name(event) == "FamilyVersioned"


@pytest.mark.unit
def test_to_payload_serializes_capability_versioned_with_version_tag() -> None:
    family_id = uuid4()
    event = FamilyVersioned(family_id=family_id, version_tag="2026-Q3", occurred_at=_NOW)
    assert to_payload(event) == {
        "family_id": str(family_id),
        "version_tag": "2026-Q3",
        "occurred_at": _NOW.isoformat(),
        "affordances": [],
    }


@pytest.mark.unit
def test_from_stored_rebuilds_capability_versioned() -> None:
    family_id = uuid4()
    stored = _stored(
        "FamilyVersioned",
        {
            "family_id": str(family_id),
            "version_tag": "v2",
            "occurred_at": _NOW.isoformat(),
        },
    )
    rebuilt = from_stored(stored)
    assert rebuilt == FamilyVersioned(family_id=family_id, version_tag="v2", occurred_at=_NOW)


@pytest.mark.unit
def test_to_payload_then_from_stored_round_trips_for_capability_versioned() -> None:
    original = FamilyVersioned(family_id=uuid4(), version_tag="v3", occurred_at=_NOW)
    stored = _stored("FamilyVersioned", to_payload(original))
    assert from_stored(stored) == original


# ---------- FamilyDeprecated ----------


@pytest.mark.unit
def test_event_type_name_returns_capability_deprecated_class_name() -> None:
    event = FamilyDeprecated(family_id=uuid4(), occurred_at=_NOW)
    assert event_type_name(event) == "FamilyDeprecated"


@pytest.mark.unit
def test_to_payload_serializes_capability_deprecated_to_primitives() -> None:
    """Status NOT in payload — event TYPE encodes the state change.
    Pinned because adding a `status` field would be an additive change
    that must be deliberate."""
    family_id = uuid4()
    event = FamilyDeprecated(family_id=family_id, occurred_at=_NOW)
    payload = to_payload(event)
    assert payload == {
        "family_id": str(family_id),
        "occurred_at": _NOW.isoformat(),
    }
    assert "status" not in payload


@pytest.mark.unit
def test_from_stored_rebuilds_capability_deprecated() -> None:
    family_id = uuid4()
    stored = _stored(
        "FamilyDeprecated",
        {
            "family_id": str(family_id),
            "occurred_at": _NOW.isoformat(),
        },
    )
    rebuilt = from_stored(stored)
    assert rebuilt == FamilyDeprecated(family_id=family_id, occurred_at=_NOW)


@pytest.mark.unit
def test_to_payload_then_from_stored_round_trips_for_capability_deprecated() -> None:
    original = FamilyDeprecated(family_id=uuid4(), occurred_at=_NOW)
    stored = _stored("FamilyDeprecated", to_payload(original))
    assert from_stored(stored) == original


# ---------- FamilySettingsSchemaUpdated ----------


_TEST_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "properties": {"energy": {"type": "number", "unit": {"system": "udunits", "code": "keV"}}},
}


@pytest.mark.unit
def test_event_type_name_returns_capability_settings_schema_updated_class_name() -> None:
    event = FamilySettingsSchemaUpdated(
        family_id=uuid4(),
        settings_schema=_TEST_SCHEMA,
        occurred_at=_NOW,
    )
    assert event_type_name(event) == "FamilySettingsSchemaUpdated"


@pytest.mark.unit
def test_to_payload_serializes_capability_settings_schema_updated_with_schema() -> None:
    family_id = uuid4()
    event = FamilySettingsSchemaUpdated(
        family_id=family_id,
        settings_schema=_TEST_SCHEMA,
        occurred_at=_NOW,
    )
    payload = to_payload(event)
    assert payload == {
        "family_id": str(family_id),
        "settings_schema": _TEST_SCHEMA,
        "occurred_at": _NOW.isoformat(),
    }


@pytest.mark.unit
def test_to_payload_serializes_capability_settings_schema_updated_with_none() -> None:
    """Clear-the-schema event payload carries explicit None."""
    family_id = uuid4()
    event = FamilySettingsSchemaUpdated(
        family_id=family_id,
        settings_schema=None,
        occurred_at=_NOW,
    )
    payload = to_payload(event)
    assert payload == {
        "family_id": str(family_id),
        "settings_schema": None,
        "occurred_at": _NOW.isoformat(),
    }


@pytest.mark.unit
def test_from_stored_rebuilds_capability_settings_schema_updated_with_schema() -> None:
    family_id = uuid4()
    stored = _stored(
        "FamilySettingsSchemaUpdated",
        {
            "family_id": str(family_id),
            "settings_schema": _TEST_SCHEMA,
            "occurred_at": _NOW.isoformat(),
        },
    )
    rebuilt = from_stored(stored)
    assert rebuilt == FamilySettingsSchemaUpdated(
        family_id=family_id,
        settings_schema=_TEST_SCHEMA,
        occurred_at=_NOW,
    )


@pytest.mark.unit
def test_from_stored_rebuilds_settings_schema_updated_with_none_when_payload_missing() -> None:
    """Tolerates payloads missing the settings_schema key (treats as
    None). Matches the additive-evolution stance of from_stored."""
    family_id = uuid4()
    stored = _stored(
        "FamilySettingsSchemaUpdated",
        {
            "family_id": str(family_id),
            "occurred_at": _NOW.isoformat(),
        },
    )
    rebuilt = from_stored(stored)
    assert rebuilt == FamilySettingsSchemaUpdated(
        family_id=family_id,
        settings_schema=None,
        occurred_at=_NOW,
    )


@pytest.mark.unit
def test_to_payload_then_from_stored_round_trips_for_capability_settings_schema_updated() -> None:
    original = FamilySettingsSchemaUpdated(
        family_id=uuid4(),
        settings_schema=_TEST_SCHEMA,
        occurred_at=_NOW,
    )
    stored = _stored("FamilySettingsSchemaUpdated", to_payload(original))
    assert from_stored(stored) == original


# ---------- non-empty affordance round-trip ----------
#
# Gate review P0: the original 5j tests round-tripped EMPTY affordances
# only. These tests pin to_payload + from_stored for non-empty sets,
# the sorted-payload determinism, and legacy upcast with affordances.


@pytest.mark.unit
def test_to_payload_serializes_non_empty_affordances_sorted() -> None:
    """Affordances serialize as a sorted list of enum string values for
    deterministic payload comparison. Sort key is the enum value
    string (PascalCase)."""
    family_id = uuid4()
    event = FamilyDefined(
        family_id=family_id,
        name="RotaryStage",
        occurred_at=_NOW,
        affordances=frozenset({Affordance.ROTATABLE, Affordance.HOMEABLE, Affordance.BENDABLE}),
    )
    payload = to_payload(event)
    assert payload["affordances"] == ["Bendable", "Homeable", "Rotatable"]


@pytest.mark.unit
def test_round_trip_family_defined_with_non_empty_affordances() -> None:
    original = FamilyDefined(
        family_id=uuid4(),
        name="Camera",
        occurred_at=_NOW,
        affordances=frozenset({Affordance.IMAGEABLE, Affordance.TRIGGERABLE}),
    )
    stored = _stored("FamilyDefined", to_payload(original))
    assert from_stored(stored) == original


@pytest.mark.unit
def test_round_trip_family_versioned_with_non_empty_affordances() -> None:
    original = FamilyVersioned(
        family_id=uuid4(),
        version_tag="v3",
        occurred_at=_NOW,
        affordances=frozenset({Affordance.IMAGEABLE, Affordance.STREAMABLE, Affordance.RECORDING}),
    )
    stored = _stored("FamilyVersioned", to_payload(original))
    assert from_stored(stored) == original


@pytest.mark.unit
def test_load_affordances_raises_on_unknown_enum_string() -> None:
    """Defensive guard: a corrupted payload with an unknown affordance
    string fails loud on stream replay rather than silently dropping
    the value."""
    stored = _stored(
        "FamilyDefined",
        {
            "family_id": str(uuid4()),
            "name": "Test",
            "occurred_at": _NOW.isoformat(),
            "affordances": ["NotARealAffordance"],
        },
    )
    with pytest.raises(ValueError, match="is not a valid Affordance"):
        from_stored(stored)


@pytest.mark.unit
@pytest.mark.parametrize(
    "event_type",
    [
        "FamilyDefined",
        "FamilyVersioned",
        "FamilyDeprecated",
        "FamilySettingsSchemaUpdated",
        "FamilyPresentsAsAdded",
        "FamilyPresentsAsRemoved",
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


@pytest.mark.unit
def test_event_type_name_returns_family_presents_as_added_class_name() -> None:
    fid = uuid4()
    rid = uuid4()
    event = FamilyPresentsAsAdded(family_id=fid, role_id=rid, occurred_at=_NOW)
    assert event_type_name(event) == "FamilyPresentsAsAdded"


@pytest.mark.unit
def test_to_payload_family_presents_as_added_serializes_uuids() -> None:
    fid = uuid4()
    rid = uuid4()
    payload = to_payload(FamilyPresentsAsAdded(family_id=fid, role_id=rid, occurred_at=_NOW))
    assert payload == {
        "family_id": str(fid),
        "role_id": str(rid),
        "occurred_at": _NOW.isoformat(),
    }


@pytest.mark.unit
def test_to_payload_family_presents_as_removed_serializes_uuids() -> None:
    fid = uuid4()
    rid = uuid4()
    payload = to_payload(FamilyPresentsAsRemoved(family_id=fid, role_id=rid, occurred_at=_NOW))
    assert payload == {
        "family_id": str(fid),
        "role_id": str(rid),
        "occurred_at": _NOW.isoformat(),
    }


@pytest.mark.unit
def test_round_trip_family_presents_as_added() -> None:
    fid = uuid4()
    rid = uuid4()
    original = FamilyPresentsAsAdded(family_id=fid, role_id=rid, occurred_at=_NOW)
    payload = to_payload(original)
    rebuilt = from_stored(_stored("FamilyPresentsAsAdded", payload))
    assert rebuilt == original


@pytest.mark.unit
def test_round_trip_family_presents_as_removed() -> None:
    fid = uuid4()
    rid = uuid4()
    original = FamilyPresentsAsRemoved(family_id=fid, role_id=rid, occurred_at=_NOW)
    payload = to_payload(original)
    rebuilt = from_stored(_stored("FamilyPresentsAsRemoved", payload))
    assert rebuilt == original


@pytest.mark.unit
def test_from_stored_family_presents_as_added_with_malformed_uuid_raises() -> None:
    """Defensive: bad UUID strings surface as Malformed FamilyPresentsAsAdded."""
    with pytest.raises(ValueError, match="Malformed FamilyPresentsAsAdded"):
        from_stored(
            _stored(
                "FamilyPresentsAsAdded",
                {
                    "family_id": "not-a-uuid",
                    "role_id": str(uuid4()),
                    "occurred_at": _NOW.isoformat(),
                },
            )
        )
