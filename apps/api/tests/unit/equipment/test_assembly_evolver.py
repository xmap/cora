"""Unit tests for the Assembly evolver: genesis + revision + deprecation."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from cora.equipment.aggregates._drawing import Drawing, DrawingSystem
from cora.equipment.aggregates.assembly import (
    Assembly,
    AssemblyDefined,
    AssemblyDeprecated,
    AssemblyName,
    AssemblyStatus,
    AssemblyVersioned,
    SlotCardinality,
    SlotName,
    SubAssemblyLink,
    TemplateSlot,
    evolve,
    fold,
)

_NOW = datetime(2026, 6, 2, 12, 0, 0, tzinfo=UTC)


def _slot(name: str = "camera") -> TemplateSlot:
    return TemplateSlot(
        slot_name=SlotName(name),
        required_family_ids=frozenset({uuid4()}),
        cardinality=SlotCardinality.EXACTLY_1,
    )


@pytest.mark.unit
def test_evolve_genesis_sets_defined_status() -> None:
    assembly_id = uuid4()
    family_id = uuid4()
    slot = _slot("camera")
    event = AssemblyDefined(
        assembly_id=assembly_id,
        name=AssemblyName("Detector"),
        presents_as_family_id=family_id,
        required_slots=frozenset({slot}),
        required_wires=frozenset(),
        parameter_overrides_schema=None,
        drawing=None,
        version="v0.1.0",
        content_hash="a" * 64,
        occurred_at=_NOW,
    )
    state = evolve(None, event)
    assert state.id == assembly_id
    assert state.presents_as_family_id == family_id
    assert state.status == AssemblyStatus.DEFINED
    assert state.required_slots == frozenset({slot})
    assert state.version == "v0.1.0"
    assert state.content_hash == "a" * 64


@pytest.mark.unit
def test_evolve_carries_sub_assemblies_through_genesis_and_lifecycle() -> None:
    """required_sub_assemblies folds in at genesis and is preserved
    across deprecate (full-dataclass-construction invariant)."""
    assembly_id = uuid4()
    link = SubAssemblyLink(
        slot_name=SlotName("optics"),
        sub_assembly_id=uuid4(),
        content_hash="sha256:" + "a" * 8,
    )
    defined = AssemblyDefined(
        assembly_id=assembly_id,
        name=AssemblyName("Microscope"),
        presents_as_family_id=uuid4(),
        required_slots=frozenset(),
        required_wires=frozenset(),
        parameter_overrides_schema=None,
        drawing=None,
        version=None,
        content_hash="a" * 64,
        occurred_at=_NOW,
        required_sub_assemblies=frozenset({link}),
    )
    deprecated = AssemblyDeprecated(
        assembly_id=assembly_id,
        reason="end of life",
        occurred_at=_NOW,
    )
    state = fold([defined, deprecated])
    assert state is not None
    assert state.required_sub_assemblies == frozenset({link})
    assert state.status == AssemblyStatus.DEPRECATED


@pytest.mark.unit
def test_evolve_versioned_replaces_sub_assemblies() -> None:
    """AssemblyVersioned replaces required_sub_assemblies with the new
    snapshot's set (replace-on-version, mirroring slots/wires)."""
    assembly_id = uuid4()
    fam = uuid4()
    link_v1 = SubAssemblyLink(
        slot_name=SlotName("optics"),
        sub_assembly_id=uuid4(),
        content_hash="sha256:" + "a" * 8,
    )
    link_v2 = SubAssemblyLink(
        slot_name=SlotName("optics"),
        sub_assembly_id=uuid4(),
        content_hash="sha256:" + "b" * 8,
    )
    defined = AssemblyDefined(
        assembly_id=assembly_id,
        name=AssemblyName("Microscope"),
        presents_as_family_id=fam,
        required_slots=frozenset(),
        required_wires=frozenset(),
        parameter_overrides_schema=None,
        drawing=None,
        version="v1",
        content_hash="a" * 64,
        occurred_at=_NOW,
        required_sub_assemblies=frozenset({link_v1}),
    )
    versioned = AssemblyVersioned(
        assembly_id=assembly_id,
        name=AssemblyName("Microscope"),
        presents_as_family_id=fam,
        required_slots=frozenset(),
        required_wires=frozenset(),
        parameter_overrides_schema=None,
        drawing=None,
        version="v2",
        content_hash="b" * 64,
        previous_content_hash="a" * 64,
        occurred_at=_NOW,
        required_sub_assemblies=frozenset({link_v2}),
    )
    state = fold([defined, versioned])
    assert state is not None
    assert state.required_sub_assemblies == frozenset({link_v2})


@pytest.mark.unit
def test_evolve_versioned_replaces_structural_fields_and_status() -> None:
    assembly_id = uuid4()
    family_id = uuid4()
    initial_slot = _slot("camera")
    new_slot = _slot("scintillator")
    defined = AssemblyDefined(
        assembly_id=assembly_id,
        name=AssemblyName("Detector"),
        presents_as_family_id=family_id,
        required_slots=frozenset({initial_slot}),
        required_wires=frozenset(),
        parameter_overrides_schema=None,
        drawing=None,
        version="v0.1.0",
        content_hash="a" * 64,
        occurred_at=_NOW,
    )
    versioned = AssemblyVersioned(
        assembly_id=assembly_id,
        name=AssemblyName("Detector"),
        presents_as_family_id=family_id,
        required_slots=frozenset({initial_slot, new_slot}),
        required_wires=frozenset(),
        parameter_overrides_schema=None,
        drawing=Drawing(system=DrawingSystem.ICMS, number="P4105", revision="B"),
        version="v0.2.0",
        content_hash="b" * 64,
        previous_content_hash="a" * 64,
        occurred_at=_NOW,
    )
    final = fold([defined, versioned])
    assert final is not None
    assert final.status == AssemblyStatus.VERSIONED
    assert final.required_slots == frozenset({initial_slot, new_slot})
    assert final.version == "v0.2.0"
    assert final.content_hash == "b" * 64
    assert final.drawing is not None


@pytest.mark.unit
def test_evolve_versioned_multiple_revisions_replace_each_time() -> None:
    """Multiple AssemblyVersioned events on one stream are permitted;
    each is a fresh snapshot."""
    assembly_id = uuid4()
    family_id = uuid4()
    defined = AssemblyDefined(
        assembly_id=assembly_id,
        name=AssemblyName("Detector"),
        presents_as_family_id=family_id,
        required_slots=frozenset({_slot("camera")}),
        required_wires=frozenset(),
        parameter_overrides_schema=None,
        drawing=None,
        version="v1",
        content_hash="1" * 64,
        occurred_at=_NOW,
    )
    v2 = AssemblyVersioned(
        assembly_id=assembly_id,
        name=AssemblyName("Detector"),
        presents_as_family_id=family_id,
        required_slots=frozenset({_slot("camera")}),
        required_wires=frozenset(),
        parameter_overrides_schema=None,
        drawing=None,
        version="v2",
        content_hash="2" * 64,
        previous_content_hash="1" * 64,
        occurred_at=_NOW,
    )
    v3 = AssemblyVersioned(
        assembly_id=assembly_id,
        name=AssemblyName("Detector"),
        presents_as_family_id=family_id,
        required_slots=frozenset({_slot("camera")}),
        required_wires=frozenset(),
        parameter_overrides_schema=None,
        drawing=None,
        version="v3",
        content_hash="3" * 64,
        previous_content_hash="2" * 64,
        occurred_at=_NOW,
    )
    final = fold([defined, v2, v3])
    assert final is not None
    assert final.version == "v3"
    assert final.content_hash == "3" * 64
    assert final.status == AssemblyStatus.VERSIONED


@pytest.mark.unit
def test_evolve_deprecated_preserves_structural_fields_and_sets_status() -> None:
    assembly_id = uuid4()
    family_id = uuid4()
    slot = _slot()
    defined = AssemblyDefined(
        assembly_id=assembly_id,
        name=AssemblyName("Detector"),
        presents_as_family_id=family_id,
        required_slots=frozenset({slot}),
        required_wires=frozenset(),
        parameter_overrides_schema={"type": "object"},
        drawing=None,
        version="v1",
        content_hash="a" * 64,
        occurred_at=_NOW,
    )
    deprecated = AssemblyDeprecated(
        assembly_id=assembly_id,
        reason="superseded",
        occurred_at=_NOW,
    )
    final = fold([defined, deprecated])
    assert final is not None
    assert final.status == AssemblyStatus.DEPRECATED
    assert final.required_slots == frozenset({slot})
    assert final.parameter_overrides_schema == {"type": "object"}
    assert final.content_hash == "a" * 64


@pytest.mark.unit
def test_evolve_non_genesis_against_empty_state_raises() -> None:
    """AssemblyVersioned and AssemblyDeprecated cannot appear before
    AssemblyDefined in a well-formed stream."""
    versioned = AssemblyVersioned(
        assembly_id=uuid4(),
        name=AssemblyName("X"),
        presents_as_family_id=uuid4(),
        required_slots=frozenset(),
        required_wires=frozenset(),
        parameter_overrides_schema=None,
        drawing=None,
        version=None,
        content_hash="x" * 64,
        previous_content_hash=None,
        occurred_at=_NOW,
    )
    with pytest.raises(ValueError, match="AssemblyVersioned"):
        evolve(None, versioned)


@pytest.mark.unit
def test_fold_empty_event_stream_returns_none() -> None:
    assert fold([]) is None


@pytest.mark.unit
def test_fold_preserves_immutable_id_across_lifecycle() -> None:
    assembly_id = uuid4()
    family_id = uuid4()
    events = [
        AssemblyDefined(
            assembly_id=assembly_id,
            name=AssemblyName("X"),
            presents_as_family_id=family_id,
            required_slots=frozenset(),
            required_wires=frozenset(),
            parameter_overrides_schema=None,
            drawing=None,
            version="v1",
            content_hash="a" * 64,
            occurred_at=_NOW,
        ),
        AssemblyVersioned(
            assembly_id=assembly_id,
            name=AssemblyName("X"),
            presents_as_family_id=family_id,
            required_slots=frozenset(),
            required_wires=frozenset(),
            parameter_overrides_schema=None,
            drawing=None,
            version="v2",
            content_hash="b" * 64,
            previous_content_hash="a" * 64,
            occurred_at=_NOW,
        ),
        AssemblyDeprecated(assembly_id=assembly_id, reason="r", occurred_at=_NOW),
    ]
    final = fold(events)
    assert isinstance(final, Assembly)
    assert final.id == assembly_id
    assert final.presents_as_family_id == family_id
