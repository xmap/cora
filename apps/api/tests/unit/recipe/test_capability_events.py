"""Unit tests for the Capability aggregate's event (de)serialization helpers."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from cora.equipment.aggregates.family import Affordance
from cora.infrastructure.ports.event_store import StoredEvent
from cora.recipe.aggregates.capability import (
    CapabilityDefined,
    CapabilityDeprecated,
    CapabilitySuggestedRolesUpdated,
    CapabilityVersioned,
    ExecutorShape,
    event_type_name,
    from_stored,
    to_payload,
)

_NOW = datetime(2026, 5, 18, 12, 0, 0, tzinfo=UTC)


def _stored(event_type: str, payload: dict[str, object]) -> StoredEvent:
    return StoredEvent(
        position=1,
        event_id=uuid4(),
        stream_type="Capability",
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
def test_event_type_names() -> None:
    cid = uuid4()
    defn = CapabilityDefined(
        capability_id=cid,
        code="cora.capability.x",
        name="X",
        required_affordances=frozenset(),
        executor_shapes=frozenset({ExecutorShape.METHOD}),
        occurred_at=_NOW,
    )
    assert event_type_name(defn) == "CapabilityDefined"
    assert (
        event_type_name(
            CapabilityVersioned(
                capability_id=cid,
                version_tag="v2",
                required_affordances=frozenset(),
                executor_shapes=frozenset({ExecutorShape.METHOD}),
                occurred_at=_NOW,
            )
        )
        == "CapabilityVersioned"
    )
    assert (
        event_type_name(CapabilityDeprecated(capability_id=cid, occurred_at=_NOW))
        == "CapabilityDeprecated"
    )


@pytest.mark.unit
def test_to_payload_capability_defined_sorts_affordances_and_shapes() -> None:
    cid = uuid4()
    event = CapabilityDefined(
        capability_id=cid,
        code="cora.capability.flyscan",
        name="FlyScan",
        description="continuous rotation",
        required_affordances=frozenset(
            {Affordance.ROTATABLE, Affordance.HOMEABLE, Affordance.TRIGGERABLE}
        ),
        executor_shapes=frozenset({ExecutorShape.PROCEDURE, ExecutorShape.METHOD}),
        parameters_schema={"$schema": "https://json-schema.org/draft/2020-12/schema"},
        occurred_at=_NOW,
    )
    payload = to_payload(event)
    assert payload["capability_id"] == str(cid)
    assert payload["code"] == "cora.capability.flyscan"
    assert payload["name"] == "FlyScan"
    assert payload["description"] == "continuous rotation"
    assert payload["required_affordances"] == ["Homeable", "Rotatable", "Triggerable"]
    assert payload["executor_shapes"] == ["Method", "Procedure"]
    assert payload["parameters_schema"] == {
        "$schema": "https://json-schema.org/draft/2020-12/schema"
    }


@pytest.mark.unit
def test_round_trip_capability_defined() -> None:
    original = CapabilityDefined(
        capability_id=uuid4(),
        code="cora.capability.tomo",
        name="Tomo",
        description=None,
        required_affordances=frozenset({Affordance.ROTATABLE}),
        executor_shapes=frozenset({ExecutorShape.METHOD}),
        parameters_schema=None,
        occurred_at=_NOW,
    )
    stored = _stored("CapabilityDefined", to_payload(original))
    assert from_stored(stored) == original


@pytest.mark.unit
def test_round_trip_capability_versioned() -> None:
    original = CapabilityVersioned(
        capability_id=uuid4(),
        version_tag="v2",
        description="updated",
        required_affordances=frozenset({Affordance.IMAGEABLE}),
        executor_shapes=frozenset({ExecutorShape.METHOD}),
        parameters_schema={"$schema": "https://json-schema.org/draft/2020-12/schema"},
        occurred_at=_NOW,
    )
    stored = _stored("CapabilityVersioned", to_payload(original))
    assert from_stored(stored) == original


@pytest.mark.unit
def test_round_trip_capability_deprecated_without_replacement() -> None:
    original = CapabilityDeprecated(
        capability_id=uuid4(),
        replaced_by_capability_id=None,
        occurred_at=_NOW,
    )
    stored = _stored("CapabilityDeprecated", to_payload(original))
    assert from_stored(stored) == original


@pytest.mark.unit
def test_round_trip_capability_deprecated_with_replacement() -> None:
    replaced_by = uuid4()
    original = CapabilityDeprecated(
        capability_id=uuid4(),
        replaced_by_capability_id=replaced_by,
        occurred_at=_NOW,
    )
    stored = _stored("CapabilityDeprecated", to_payload(original))
    assert from_stored(stored) == original


@pytest.mark.unit
def test_from_stored_raises_on_unknown_event_type() -> None:
    stored = _stored("ActorRegistered", {})
    with pytest.raises(ValueError, match="Unknown CapabilityEvent event_type"):
        from_stored(stored)


@pytest.mark.unit
def test_from_stored_capability_defined_with_empty_optional_fields() -> None:
    """Pre-event-evolution payloads (no description/parameters_schema keys)
    fold cleanly via additive-state defaults."""
    cid = uuid4()
    stored = _stored(
        "CapabilityDefined",
        {
            "capability_id": str(cid),
            "code": "cora.capability.x",
            "name": "X",
            "required_affordances": [],
            "executor_shapes": ["Method"],
            "occurred_at": _NOW.isoformat(),
        },
    )
    rebuilt = from_stored(stored)
    assert isinstance(rebuilt, CapabilityDefined)
    assert rebuilt.description is None
    assert rebuilt.parameters_schema is None


@pytest.mark.unit
def test_from_stored_rejects_unknown_affordance_string() -> None:
    """Defensive replay guard: a corrupted payload with bogus affordance fails loud."""
    stored = _stored(
        "CapabilityDefined",
        {
            "capability_id": str(uuid4()),
            "code": "cora.capability.x",
            "name": "X",
            "required_affordances": ["Bogus"],
            "executor_shapes": ["Method"],
            "occurred_at": _NOW.isoformat(),
        },
    )
    with pytest.raises(ValueError, match="is not a valid Affordance"):
        from_stored(stored)


@pytest.mark.unit
def test_from_stored_rejects_unknown_executor_shape_string() -> None:
    stored = _stored(
        "CapabilityDefined",
        {
            "capability_id": str(uuid4()),
            "code": "cora.capability.x",
            "name": "X",
            "required_affordances": [],
            "executor_shapes": ["Workflow"],
            "occurred_at": _NOW.isoformat(),
        },
    )
    with pytest.raises(ValueError, match="is not a valid ExecutorShape"):
        from_stored(stored)


@pytest.mark.unit
@pytest.mark.parametrize(
    "event_type",
    [
        "CapabilityDefined",
        "CapabilityVersioned",
        "CapabilityDeprecated",
        "CapabilitySuggestedRolesUpdated",
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
def test_event_type_name_returns_capability_suggested_roles_updated_class_name() -> None:
    """Layer 3 sub-slice 3E: new event class name discriminator."""
    cid = uuid4()
    event = CapabilitySuggestedRolesUpdated(
        capability_id=cid, suggested_role_ids=frozenset(), occurred_at=_NOW
    )
    assert event_type_name(event) == "CapabilitySuggestedRolesUpdated"


@pytest.mark.unit
def test_to_payload_capability_suggested_roles_updated_sorts_role_ids() -> None:
    """Deterministic byte-stable payload: role_ids sorted as strings."""
    cid = uuid4()
    rid_a = uuid4()
    rid_b = uuid4()
    payload = to_payload(
        CapabilitySuggestedRolesUpdated(
            capability_id=cid,
            suggested_role_ids=frozenset({rid_a, rid_b}),
            occurred_at=_NOW,
        )
    )
    assert payload["capability_id"] == str(cid)
    assert payload["suggested_role_ids"] == sorted([str(rid_a), str(rid_b)])
    assert payload["occurred_at"] == _NOW.isoformat()


@pytest.mark.unit
def test_round_trip_capability_suggested_roles_updated() -> None:
    cid = uuid4()
    rid = uuid4()
    original = CapabilitySuggestedRolesUpdated(
        capability_id=cid, suggested_role_ids=frozenset({rid}), occurred_at=_NOW
    )
    payload = to_payload(original)
    rebuilt = from_stored(_stored("CapabilitySuggestedRolesUpdated", payload))
    assert rebuilt == original


@pytest.mark.unit
def test_to_payload_capability_suggested_roles_updated_with_empty_set() -> None:
    cid = uuid4()
    payload = to_payload(
        CapabilitySuggestedRolesUpdated(
            capability_id=cid, suggested_role_ids=frozenset(), occurred_at=_NOW
        )
    )
    assert payload["suggested_role_ids"] == []


@pytest.mark.unit
def test_from_stored_capability_suggested_roles_updated_malformed_uuid_raises() -> None:
    """Defensive: malformed UUID strings surface as Malformed
    CapabilitySuggestedRolesUpdated."""
    with pytest.raises(ValueError, match="Malformed CapabilitySuggestedRolesUpdated"):
        from_stored(
            _stored(
                "CapabilitySuggestedRolesUpdated",
                {
                    "capability_id": str(uuid4()),
                    "suggested_role_ids": ["not-a-uuid"],
                    "occurred_at": _NOW.isoformat(),
                },
            )
        )
