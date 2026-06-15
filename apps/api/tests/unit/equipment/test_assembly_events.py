"""Unit tests for Assembly events: to_payload + from_stored round-trip."""

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import pytest

from cora.equipment.aggregates._drawing import Drawing, DrawingSystem
from cora.equipment.aggregates._value_types import RoleId
from cora.equipment.aggregates.assembly import (
    AssemblyDefined,
    AssemblyDeprecated,
    AssemblyName,
    AssemblyVersioned,
    SlotCardinality,
    SlotName,
    SubAssemblyLink,
    TemplateSlot,
    TemplateWire,
    from_stored,
    to_payload,
)
from cora.infrastructure.ports.event_store import StoredEvent

_NOW = datetime(2026, 6, 2, 12, 0, 0, tzinfo=UTC)


def _stored(event_type: str, payload: dict[str, Any]) -> StoredEvent:
    return StoredEvent(
        position=1,
        event_id=uuid4(),
        stream_type="Assembly",
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


def _slot(slot_name: str = "camera", family_id: UUID | None = None) -> TemplateSlot:
    return TemplateSlot(
        slot_name=SlotName(slot_name),
        required_family_ids=frozenset({family_id or uuid4()}),
        cardinality=SlotCardinality.EXACTLY_1,
    )


def _wire(src_slot: str = "trigger_source", tgt_slot: str = "camera") -> TemplateWire:
    return TemplateWire(
        source_slot_name=src_slot,
        source_port_name="trigger_out",
        target_slot_name=tgt_slot,
        target_port_name="trigger_in",
    )


def _link(
    slot_name: str = "optics",
    child_id: UUID | None = None,
    content_hash: str = "sha256:abcd1234",
) -> SubAssemblyLink:
    return SubAssemblyLink(
        slot_name=SlotName(slot_name),
        sub_assembly_id=child_id or uuid4(),
        content_hash=content_hash,
    )


@pytest.mark.unit
def test_assembly_defined_to_payload_then_from_stored_round_trip() -> None:
    assembly_id = uuid4()
    family_id = uuid4()
    slot1 = _slot("camera", family_id)
    slot2 = _slot("trigger_source", uuid4())
    wire = _wire()
    original = AssemblyDefined(
        assembly_id=assembly_id,
        name=AssemblyName("Detector"),
        presents_as=frozenset({RoleId(uuid4())}),
        required_slots=frozenset({slot1, slot2}),
        required_wires=frozenset({wire}),
        parameter_overrides_schema={"type": "object"},
        drawing=Drawing(system=DrawingSystem.ICMS, number="P4105", revision="A"),
        version="v1.0.0",
        content_hash="a" * 64,
        occurred_at=_NOW,
    )
    payload = to_payload(original)
    stored = _stored("AssemblyDefined", payload)
    rebuilt = from_stored(stored)
    assert rebuilt == original


@pytest.mark.unit
def test_assembly_defined_round_trip_with_no_drawing_no_version_no_schema() -> None:
    original = AssemblyDefined(
        assembly_id=uuid4(),
        name=AssemblyName("Empty"),
        presents_as=frozenset({RoleId(uuid4())}),
        required_slots=frozenset(),
        required_wires=frozenset(),
        parameter_overrides_schema=None,
        drawing=None,
        version=None,
        content_hash="b" * 64,
        occurred_at=_NOW,
    )
    payload = to_payload(original)
    rebuilt = from_stored(_stored("AssemblyDefined", payload))
    assert rebuilt == original


@pytest.mark.unit
def test_assembly_versioned_round_trip_carries_previous_hash() -> None:
    original = AssemblyVersioned(
        assembly_id=uuid4(),
        name=AssemblyName("Detector"),
        presents_as=frozenset({RoleId(uuid4())}),
        required_slots=frozenset({_slot()}),
        required_wires=frozenset(),
        parameter_overrides_schema=None,
        drawing=None,
        version="v1.1.0",
        content_hash="c" * 64,
        previous_content_hash="a" * 64,
        occurred_at=_NOW,
    )
    payload = to_payload(original)
    rebuilt = from_stored(_stored("AssemblyVersioned", payload))
    assert rebuilt == original


@pytest.mark.unit
def test_assembly_versioned_round_trip_allows_no_previous_hash() -> None:
    """First Versioned snapshot may have no previous_content_hash if
    promoted from a Defined that pre-dates the hash field. Optional
    per the additive-state convention."""
    original = AssemblyVersioned(
        assembly_id=uuid4(),
        name=AssemblyName("Detector"),
        presents_as=frozenset({RoleId(uuid4())}),
        required_slots=frozenset(),
        required_wires=frozenset(),
        parameter_overrides_schema=None,
        drawing=None,
        version=None,
        content_hash="d" * 64,
        previous_content_hash=None,
        occurred_at=_NOW,
    )
    rebuilt = from_stored(_stored("AssemblyVersioned", to_payload(original)))
    assert rebuilt == original


@pytest.mark.unit
def test_assembly_deprecated_round_trip() -> None:
    original = AssemblyDeprecated(
        assembly_id=uuid4(),
        reason="superseded by next-generation Microscope revision",
        occurred_at=_NOW,
    )
    rebuilt = from_stored(_stored("AssemblyDeprecated", to_payload(original)))
    assert rebuilt == original


@pytest.mark.unit
def test_assembly_defined_round_trip_with_sub_assemblies() -> None:
    original = AssemblyDefined(
        assembly_id=uuid4(),
        name=AssemblyName("Microscope"),
        presents_as=frozenset({RoleId(uuid4())}),
        required_slots=frozenset(),
        required_wires=frozenset(),
        parameter_overrides_schema=None,
        drawing=None,
        version=None,
        content_hash="e" * 64,
        occurred_at=_NOW,
        required_sub_assemblies=frozenset({_link("optics", uuid4(), "sha256:" + "a" * 8)}),
    )
    rebuilt = from_stored(_stored("AssemblyDefined", to_payload(original)))
    assert rebuilt == original


@pytest.mark.unit
def test_assembly_versioned_round_trip_with_sub_assemblies() -> None:
    original = AssemblyVersioned(
        assembly_id=uuid4(),
        name=AssemblyName("Microscope"),
        presents_as=frozenset({RoleId(uuid4())}),
        required_slots=frozenset(),
        required_wires=frozenset(),
        parameter_overrides_schema=None,
        drawing=None,
        version="v2",
        content_hash="g" * 64,
        previous_content_hash="e" * 64,
        occurred_at=_NOW,
        required_sub_assemblies=frozenset({_link("optics", uuid4(), "sha256:" + "b" * 8)}),
    )
    rebuilt = from_stored(_stored("AssemblyVersioned", to_payload(original)))
    assert rebuilt == original


@pytest.mark.unit
def test_from_stored_defaults_missing_sub_assemblies_to_empty() -> None:
    """Back-compat: a payload written before the required_sub_assemblies
    field folds to an empty frozenset (additive-state .get default)."""
    original = AssemblyDefined(
        assembly_id=uuid4(),
        name=AssemblyName("Detector"),
        presents_as=frozenset({RoleId(uuid4())}),
        required_slots=frozenset(),
        required_wires=frozenset(),
        parameter_overrides_schema=None,
        drawing=None,
        version=None,
        content_hash="f" * 64,
        occurred_at=_NOW,
    )
    payload = to_payload(original)
    del payload["required_sub_assemblies"]
    rebuilt = from_stored(_stored("AssemblyDefined", payload))
    assert isinstance(rebuilt, AssemblyDefined)
    assert rebuilt.required_sub_assemblies == frozenset()


@pytest.mark.unit
def test_from_stored_rejects_unknown_event_type() -> None:
    with pytest.raises(ValueError, match="Unknown AssemblyEvent event_type"):
        from_stored(_stored("MysteryEvent", {"assembly_id": str(uuid4())}))


@pytest.mark.unit
@pytest.mark.parametrize(
    "event_type",
    ["AssemblyDefined", "AssemblyVersioned", "AssemblyDeprecated"],
)
def test_from_stored_wraps_malformed_payload_into_tagged_value_error(
    event_type: str,
) -> None:
    """Per project_from_stored_wrap_convention: every arm wraps
    (KeyError, TypeError, AttributeError) into ValueError tagged
    with the event name. Empty payload triggers KeyError on the
    first required key access."""
    with pytest.raises(ValueError, match=f"Malformed {event_type}"):
        from_stored(_stored(event_type, {}))
