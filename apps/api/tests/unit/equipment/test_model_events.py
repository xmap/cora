"""Round-trip tests for Model event payloads (to_payload / from_stored)."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from cora.equipment.aggregates.model import (
    Manufacturer,
    ManufacturerIdentifier,
    ManufacturerIdentifierType,
    ManufacturerName,
    ModelDefined,
    ModelDeprecated,
    ModelFamilyAdded,
    ModelFamilyRemoved,
    ModelVersioned,
    event_type_name,
    from_stored,
    to_payload,
)
from cora.infrastructure.ports.event_store import StoredEvent

_NOW = datetime(2026, 6, 1, 12, 0, tzinfo=UTC)


def _stored(event_type: str, payload: dict[str, object]) -> StoredEvent:
    """Wrap a payload as a StoredEvent for from_stored round-tripping.

    Only `event_type` and `payload` are read by `from_stored`; the rest
    is fixture noise.
    """
    return StoredEvent(
        position=1,
        event_id=uuid4(),
        stream_type="Model",
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
def test_model_defined_round_trips_with_minimal_manufacturer() -> None:
    family_a = uuid4()
    family_b = uuid4()
    event = ModelDefined(
        model_id=uuid4(),
        name="Aerotech ANT130-L",
        manufacturer=Manufacturer(name=ManufacturerName("Aerotech")),
        part_number="ANT130-L",
        declared_families=frozenset({family_a, family_b}),
        occurred_at=datetime(2026, 6, 1, 12, 0, tzinfo=UTC),
    )
    payload = to_payload(event)
    assert payload["manufacturer"] == {"name": "Aerotech"}
    assert "identifier" not in payload["manufacturer"]
    assert "version_tag" not in payload
    restored = from_stored(_stored("ModelDefined", payload))
    assert restored == event


@pytest.mark.unit
def test_model_defined_to_payload_serializes_to_canonical_dict_literal() -> None:
    """Pin the WIRE shape: explicit dict literal catches key renames on
    the to_payload side that a round-trip would mask."""
    model_id = uuid4()
    family_a = uuid4()
    family_b = uuid4()
    event = ModelDefined(
        model_id=model_id,
        name="Aerotech ANT130-L",
        manufacturer=Manufacturer(
            name=ManufacturerName("Aerotech"),
            identifier=ManufacturerIdentifier("https://ror.org/05gvnxz63"),
            identifier_type=ManufacturerIdentifierType.ROR,
        ),
        part_number="ANT130-L",
        declared_families=frozenset({family_a, family_b}),
        occurred_at=datetime(2026, 6, 1, 12, 0, tzinfo=UTC),
        version_tag="rev-A",
    )
    assert to_payload(event) == {
        "model_id": str(model_id),
        "name": "Aerotech ANT130-L",
        "manufacturer": {
            "name": "Aerotech",
            "identifier": "https://ror.org/05gvnxz63",
            "identifier_type": "ROR",
        },
        "part_number": "ANT130-L",
        "declared_families": sorted([str(family_a), str(family_b)]),
        "occurred_at": "2026-06-01T12:00:00+00:00",
        "version_tag": "rev-A",
    }


@pytest.mark.unit
def test_model_defined_from_stored_rebuilds_from_canonical_dict_literal() -> None:
    """Pin the READ shape: explicit dict literal catches key renames on
    the from_stored side that a round-trip would mask."""
    model_id = uuid4()
    family_a = uuid4()
    family_b = uuid4()
    payload: dict[str, object] = {
        "model_id": str(model_id),
        "name": "Aerotech ANT130-L",
        "manufacturer": {
            "name": "Aerotech",
            "identifier": "https://ror.org/05gvnxz63",
            "identifier_type": "ROR",
        },
        "part_number": "ANT130-L",
        "declared_families": sorted([str(family_a), str(family_b)]),
        "occurred_at": "2026-06-01T12:00:00+00:00",
        "version_tag": "rev-A",
    }
    rebuilt = from_stored(_stored("ModelDefined", payload))
    assert rebuilt == ModelDefined(
        model_id=model_id,
        name="Aerotech ANT130-L",
        manufacturer=Manufacturer(
            name=ManufacturerName("Aerotech"),
            identifier=ManufacturerIdentifier("https://ror.org/05gvnxz63"),
            identifier_type=ManufacturerIdentifierType.ROR,
        ),
        part_number="ANT130-L",
        declared_families=frozenset({family_a, family_b}),
        occurred_at=datetime(2026, 6, 1, 12, 0, tzinfo=UTC),
        version_tag="rev-A",
    )


@pytest.mark.unit
def test_model_defined_round_trips_with_full_manufacturer_and_version_tag() -> None:
    event = ModelDefined(
        model_id=uuid4(),
        name="Aerotech ANT130-L",
        manufacturer=Manufacturer(
            name=ManufacturerName("Aerotech"),
            identifier=ManufacturerIdentifier("https://ror.org/05gvnxz63"),
            identifier_type=ManufacturerIdentifierType.ROR,
        ),
        part_number="ANT130-L",
        declared_families=frozenset({uuid4()}),
        occurred_at=datetime(2026, 6, 1, 12, 0, tzinfo=UTC),
        version_tag="rev-A",
    )
    payload = to_payload(event)
    assert payload["manufacturer"]["identifier"] == "https://ror.org/05gvnxz63"
    assert payload["manufacturer"]["identifier_type"] == "ROR"
    assert payload["version_tag"] == "rev-A"
    restored = from_stored(_stored("ModelDefined", payload))
    assert restored == event


@pytest.mark.unit
def test_model_defined_payload_sorts_declared_families_deterministically() -> None:
    family_a = uuid4()
    family_b = uuid4()
    event = ModelDefined(
        model_id=uuid4(),
        name="N",
        manufacturer=Manufacturer(name=ManufacturerName("M")),
        part_number="P",
        declared_families=frozenset({family_a, family_b}),
        occurred_at=datetime(2026, 6, 1, 0, 0, tzinfo=UTC),
    )
    payload = to_payload(event)
    assert payload["declared_families"] == sorted([str(family_a), str(family_b)])


@pytest.mark.unit
def test_model_versioned_round_trips() -> None:
    event = ModelVersioned(
        model_id=uuid4(),
        name="Aerotech ANT130-L",
        manufacturer=Manufacturer(name=ManufacturerName("Aerotech")),
        part_number="ANT130-L",
        declared_families=frozenset({uuid4()}),
        version_tag="rev-B",
        occurred_at=datetime(2026, 6, 1, 13, 0, tzinfo=UTC),
    )
    payload = to_payload(event)
    restored = from_stored(_stored("ModelVersioned", payload))
    assert restored == event


@pytest.mark.unit
def test_model_versioned_to_payload_serializes_to_canonical_dict_literal() -> None:
    """Pin the WIRE shape for ModelVersioned: every key + every value."""
    model_id = uuid4()
    family_a = uuid4()
    family_b = uuid4()
    event = ModelVersioned(
        model_id=model_id,
        name="Aerotech ANT130-L",
        manufacturer=Manufacturer(name=ManufacturerName("Aerotech")),
        part_number="ANT130-L",
        declared_families=frozenset({family_a, family_b}),
        version_tag="rev-B",
        occurred_at=datetime(2026, 6, 1, 13, 0, tzinfo=UTC),
    )
    assert to_payload(event) == {
        "model_id": str(model_id),
        "name": "Aerotech ANT130-L",
        "manufacturer": {"name": "Aerotech"},
        "part_number": "ANT130-L",
        "declared_families": sorted([str(family_a), str(family_b)]),
        "version_tag": "rev-B",
        "occurred_at": "2026-06-01T13:00:00+00:00",
    }


@pytest.mark.unit
def test_model_versioned_from_stored_rebuilds_from_canonical_dict_literal() -> None:
    """Pin the READ shape for ModelVersioned."""
    model_id = uuid4()
    family_a = uuid4()
    family_b = uuid4()
    payload: dict[str, object] = {
        "model_id": str(model_id),
        "name": "Aerotech ANT130-L",
        "manufacturer": {"name": "Aerotech"},
        "part_number": "ANT130-L",
        "declared_families": sorted([str(family_a), str(family_b)]),
        "version_tag": "rev-B",
        "occurred_at": "2026-06-01T13:00:00+00:00",
    }
    rebuilt = from_stored(_stored("ModelVersioned", payload))
    assert rebuilt == ModelVersioned(
        model_id=model_id,
        name="Aerotech ANT130-L",
        manufacturer=Manufacturer(name=ManufacturerName("Aerotech")),
        part_number="ANT130-L",
        declared_families=frozenset({family_a, family_b}),
        version_tag="rev-B",
        occurred_at=datetime(2026, 6, 1, 13, 0, tzinfo=UTC),
    )


@pytest.mark.unit
def test_model_deprecated_round_trips() -> None:
    event = ModelDeprecated(
        model_id=uuid4(),
        reason="Vendor end-of-life announcement 2026-05-28",
        occurred_at=datetime(2026, 6, 1, 14, 0, tzinfo=UTC),
    )
    payload = to_payload(event)
    restored = from_stored(_stored("ModelDeprecated", payload))
    assert restored == event


@pytest.mark.unit
def test_model_deprecated_to_payload_serializes_to_canonical_dict_literal() -> None:
    """Pin the WIRE shape for ModelDeprecated."""
    model_id = uuid4()
    event = ModelDeprecated(
        model_id=model_id,
        reason="Vendor end-of-life announcement 2026-05-28",
        occurred_at=datetime(2026, 6, 1, 14, 0, tzinfo=UTC),
    )
    assert to_payload(event) == {
        "model_id": str(model_id),
        "reason": "Vendor end-of-life announcement 2026-05-28",
        "occurred_at": "2026-06-01T14:00:00+00:00",
    }


@pytest.mark.unit
def test_model_deprecated_from_stored_rebuilds_from_canonical_dict_literal() -> None:
    """Pin the READ shape for ModelDeprecated."""
    model_id = uuid4()
    payload: dict[str, object] = {
        "model_id": str(model_id),
        "reason": "Vendor end-of-life announcement 2026-05-28",
        "occurred_at": "2026-06-01T14:00:00+00:00",
    }
    rebuilt = from_stored(_stored("ModelDeprecated", payload))
    assert rebuilt == ModelDeprecated(
        model_id=model_id,
        reason="Vendor end-of-life announcement 2026-05-28",
        occurred_at=datetime(2026, 6, 1, 14, 0, tzinfo=UTC),
    )


@pytest.mark.unit
def test_model_family_added_round_trips() -> None:
    event = ModelFamilyAdded(
        model_id=uuid4(),
        family_id=uuid4(),
        occurred_at=datetime(2026, 6, 1, 15, 0, tzinfo=UTC),
    )
    payload = to_payload(event)
    restored = from_stored(_stored("ModelFamilyAdded", payload))
    assert restored == event


@pytest.mark.unit
def test_model_family_added_to_payload_serializes_to_canonical_dict_literal() -> None:
    """Pin the WIRE shape for ModelFamilyAdded."""
    model_id = uuid4()
    family_id = uuid4()
    event = ModelFamilyAdded(
        model_id=model_id,
        family_id=family_id,
        occurred_at=datetime(2026, 6, 1, 15, 0, tzinfo=UTC),
    )
    assert to_payload(event) == {
        "model_id": str(model_id),
        "family_id": str(family_id),
        "occurred_at": "2026-06-01T15:00:00+00:00",
    }


@pytest.mark.unit
def test_model_family_added_from_stored_rebuilds_from_canonical_dict_literal() -> None:
    """Pin the READ shape for ModelFamilyAdded."""
    model_id = uuid4()
    family_id = uuid4()
    payload: dict[str, object] = {
        "model_id": str(model_id),
        "family_id": str(family_id),
        "occurred_at": "2026-06-01T15:00:00+00:00",
    }
    rebuilt = from_stored(_stored("ModelFamilyAdded", payload))
    assert rebuilt == ModelFamilyAdded(
        model_id=model_id,
        family_id=family_id,
        occurred_at=datetime(2026, 6, 1, 15, 0, tzinfo=UTC),
    )


@pytest.mark.unit
def test_model_family_removed_round_trips() -> None:
    event = ModelFamilyRemoved(
        model_id=uuid4(),
        family_id=uuid4(),
        occurred_at=datetime(2026, 6, 1, 16, 0, tzinfo=UTC),
    )
    payload = to_payload(event)
    restored = from_stored(_stored("ModelFamilyRemoved", payload))
    assert restored == event


@pytest.mark.unit
def test_model_family_removed_to_payload_serializes_to_canonical_dict_literal() -> None:
    """Pin the WIRE shape for ModelFamilyRemoved."""
    model_id = uuid4()
    family_id = uuid4()
    event = ModelFamilyRemoved(
        model_id=model_id,
        family_id=family_id,
        occurred_at=datetime(2026, 6, 1, 16, 0, tzinfo=UTC),
    )
    assert to_payload(event) == {
        "model_id": str(model_id),
        "family_id": str(family_id),
        "occurred_at": "2026-06-01T16:00:00+00:00",
    }


@pytest.mark.unit
def test_model_family_removed_from_stored_rebuilds_from_canonical_dict_literal() -> None:
    """Pin the READ shape for ModelFamilyRemoved."""
    model_id = uuid4()
    family_id = uuid4()
    payload: dict[str, object] = {
        "model_id": str(model_id),
        "family_id": str(family_id),
        "occurred_at": "2026-06-01T16:00:00+00:00",
    }
    rebuilt = from_stored(_stored("ModelFamilyRemoved", payload))
    assert rebuilt == ModelFamilyRemoved(
        model_id=model_id,
        family_id=family_id,
        occurred_at=datetime(2026, 6, 1, 16, 0, tzinfo=UTC),
    )


@pytest.mark.unit
def test_from_stored_rejects_unknown_event_type() -> None:
    with pytest.raises(ValueError, match="Unknown ModelEvent event_type"):
        from_stored(_stored("ModelMystery", {}))


@pytest.mark.unit
def test_event_type_name_returns_class_name() -> None:
    event = ModelDeprecated(model_id=uuid4(), reason="r", occurred_at=datetime.now(tz=UTC))
    assert event_type_name(event) == "ModelDeprecated"
