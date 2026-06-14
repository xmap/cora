"""Unit tests for the Assembly aggregate's state, VOs, enums, and errors."""

from uuid import uuid4

import pytest

from cora.equipment.aggregates.assembly import (
    ASSEMBLY_NAME_MAX_LENGTH,
    SLOT_NAME_MAX_LENGTH,
    Assembly,
    AssemblyAlreadyExistsError,
    AssemblyCannotDeprecateError,
    AssemblyCannotInstantiateError,
    AssemblyCannotVersionError,
    AssemblyName,
    AssemblyNotFoundError,
    AssemblyStatus,
    FamilyNotFoundForAssemblyError,
    FixtureAssetFamilyMismatchError,
    FixtureMappingIncompleteError,
    FixtureParameterOverridesInvalidError,
    InvalidAssemblyNameError,
    InvalidParameterOverridesSchemaError,
    InvalidSlotCardinalityError,
    InvalidSlotNameError,
    SlotCardinality,
    SlotName,
    SubAssemblyLink,
    SubAssemblySlotNameConflictError,
    TemplateSlot,
    TemplateWire,
    WireReferencesUnknownSlotError,
)


@pytest.mark.unit
def test_assembly_status_has_three_template_lifecycle_values() -> None:
    assert {s.value for s in AssemblyStatus} == {"Defined", "Versioned", "Deprecated"}


@pytest.mark.unit
def test_slot_cardinality_has_four_closed_values() -> None:
    assert {c.value for c in SlotCardinality} == {
        "Exactly1",
        "ZeroOrOne",
        "OneOrMore",
        "ZeroOrMore",
    }


@pytest.mark.unit
def test_assembly_name_trims_and_validates_bounded_text() -> None:
    name = AssemblyName("  Microscope  ")
    assert name.value == "Microscope"


@pytest.mark.unit
@pytest.mark.parametrize("value", ["", "   "])
def test_assembly_name_rejects_empty_or_whitespace(value: str) -> None:
    with pytest.raises(InvalidAssemblyNameError):
        AssemblyName(value)


@pytest.mark.unit
def test_assembly_name_rejects_too_long() -> None:
    with pytest.raises(InvalidAssemblyNameError):
        AssemblyName("x" * (ASSEMBLY_NAME_MAX_LENGTH + 1))


@pytest.mark.unit
def test_slot_name_trims_and_validates_bounded_text() -> None:
    name = SlotName(" objective_0 ")
    assert name.value == "objective_0"


@pytest.mark.unit
@pytest.mark.parametrize("value", ["", "   "])
def test_slot_name_rejects_empty_or_whitespace(value: str) -> None:
    with pytest.raises(InvalidSlotNameError):
        SlotName(value)


@pytest.mark.unit
def test_slot_name_rejects_too_long() -> None:
    with pytest.raises(InvalidSlotNameError):
        SlotName("x" * (SLOT_NAME_MAX_LENGTH + 1))


@pytest.mark.unit
def test_assembly_empty_closure_passes() -> None:
    """An Assembly with no slots and no wires is structurally valid."""
    assembly = Assembly(
        id=uuid4(),
        name=AssemblyName("EmptyTemplate"),
        presents_as_family_id=uuid4(),
    )
    assert assembly.required_slots == frozenset()
    assert assembly.required_wires == frozenset()
    assert assembly.status == AssemblyStatus.DEFINED
    assert assembly.version is None
    assert assembly.content_hash is None


@pytest.mark.unit
def test_assembly_closure_accepts_wire_referencing_declared_slot() -> None:
    slot = TemplateSlot(
        slot_name=SlotName("camera"),
        required_family_ids=frozenset({uuid4()}),
        cardinality=SlotCardinality.EXACTLY_1,
    )
    slot2 = TemplateSlot(
        slot_name=SlotName("trigger_source"),
        required_family_ids=frozenset({uuid4()}),
        cardinality=SlotCardinality.EXACTLY_1,
    )
    wire = TemplateWire(
        source_slot_name="trigger_source",
        source_port_name="trigger_out",
        target_slot_name="camera",
        target_port_name="trigger_in",
    )
    assembly = Assembly(
        id=uuid4(),
        name=AssemblyName("Detector"),
        presents_as_family_id=uuid4(),
        required_slots=frozenset({slot, slot2}),
        required_wires=frozenset({wire}),
    )
    assert wire in assembly.required_wires


@pytest.mark.unit
def test_assembly_closure_rejects_wire_referencing_unknown_source_slot() -> None:
    slot = TemplateSlot(
        slot_name=SlotName("camera"),
        required_family_ids=frozenset({uuid4()}),
        cardinality=SlotCardinality.EXACTLY_1,
    )
    wire = TemplateWire(
        source_slot_name="missing_panda",
        source_port_name="trigger_out",
        target_slot_name="camera",
        target_port_name="trigger_in",
    )
    with pytest.raises(WireReferencesUnknownSlotError) as exc_info:
        Assembly(
            id=uuid4(),
            name=AssemblyName("Broken"),
            presents_as_family_id=uuid4(),
            required_slots=frozenset({slot}),
            required_wires=frozenset({wire}),
        )
    assert exc_info.value.slot_name == "missing_panda"


@pytest.mark.unit
def test_assembly_closure_rejects_wire_referencing_unknown_target_slot() -> None:
    slot = TemplateSlot(
        slot_name=SlotName("trigger_source"),
        required_family_ids=frozenset({uuid4()}),
        cardinality=SlotCardinality.EXACTLY_1,
    )
    wire = TemplateWire(
        source_slot_name="trigger_source",
        source_port_name="trigger_out",
        target_slot_name="missing_camera",
        target_port_name="trigger_in",
    )
    with pytest.raises(WireReferencesUnknownSlotError) as exc_info:
        Assembly(
            id=uuid4(),
            name=AssemblyName("Broken"),
            presents_as_family_id=uuid4(),
            required_slots=frozenset({slot}),
            required_wires=frozenset({wire}),
        )
    assert exc_info.value.slot_name == "missing_camera"


@pytest.mark.unit
def test_assembly_already_exists_error_carries_assembly_id() -> None:
    assembly_id = uuid4()
    err = AssemblyAlreadyExistsError(assembly_id)
    assert err.assembly_id == assembly_id
    assert str(assembly_id) in str(err)


@pytest.mark.unit
def test_assembly_not_found_error_carries_assembly_id() -> None:
    assembly_id = uuid4()
    err = AssemblyNotFoundError(assembly_id)
    assert err.assembly_id == assembly_id


@pytest.mark.unit
def test_assembly_cannot_version_carries_id_and_reason() -> None:
    assembly_id = uuid4()
    err = AssemblyCannotVersionError(assembly_id, "already Deprecated")
    assert err.assembly_id == assembly_id
    assert err.reason == "already Deprecated"


@pytest.mark.unit
def test_assembly_cannot_deprecate_carries_id_and_reason() -> None:
    assembly_id = uuid4()
    err = AssemblyCannotDeprecateError(assembly_id, "already Deprecated")
    assert err.assembly_id == assembly_id


@pytest.mark.unit
def test_assembly_cannot_instantiate_carries_id_and_reason() -> None:
    assembly_id = uuid4()
    err = AssemblyCannotInstantiateError(assembly_id, "Assembly is Deprecated")
    assert err.assembly_id == assembly_id


@pytest.mark.unit
def test_family_not_found_for_assembly_carries_family_id() -> None:
    family_id = uuid4()
    err = FamilyNotFoundForAssemblyError(family_id)
    assert err.family_id == family_id


@pytest.mark.unit
def test_invalid_slot_cardinality_carries_value() -> None:
    err = InvalidSlotCardinalityError("BogusCardinality")
    assert err.value == "BogusCardinality"
    assert "BogusCardinality" in str(err)


@pytest.mark.unit
def test_invalid_parameter_overrides_schema_carries_reason() -> None:
    err = InvalidParameterOverridesSchemaError("oneOf is forbidden in the subset")
    assert err.reason == "oneOf is forbidden in the subset"
    assert "oneOf is forbidden" in str(err)


@pytest.mark.unit
def test_fixture_mapping_incomplete_carries_slot_and_reason() -> None:
    err = FixtureMappingIncompleteError("camera", "Exactly1 slot received zero Assets")
    assert err.slot_name == "camera"
    assert err.reason == "Exactly1 slot received zero Assets"
    assert "camera" in str(err)


@pytest.mark.unit
def test_fixture_asset_family_mismatch_carries_slot_and_asset() -> None:
    asset_id = uuid4()
    err = FixtureAssetFamilyMismatchError("rotary", asset_id)
    assert err.slot_name == "rotary"
    assert err.asset_id == asset_id
    assert "rotary" in str(err)
    assert str(asset_id) in str(err)


@pytest.mark.unit
def test_fixture_parameter_overrides_invalid_carries_reason() -> None:
    err = FixtureParameterOverridesInvalidError("exposure_ms must be <= 60000")
    assert err.reason == "exposure_ms must be <= 60000"
    assert "exposure_ms" in str(err)


_SUB_HASH = "sha256:" + "c" * 8


@pytest.mark.unit
def test_assembly_accepts_sub_assembly_link_with_distinct_slot_name() -> None:
    """A sub-assembly link coexists with leaf slots when its slot_name
    does not collide with any leaf slot."""
    leaf = TemplateSlot(
        slot_name=SlotName("camera"),
        required_family_ids=frozenset({uuid4()}),
        cardinality=SlotCardinality.EXACTLY_1,
    )
    link = SubAssemblyLink(
        slot_name=SlotName("optics"),
        sub_assembly_id=uuid4(),
        content_hash=_SUB_HASH,
    )
    assembly = Assembly(
        id=uuid4(),
        name=AssemblyName("Microscope"),
        presents_as_family_id=uuid4(),
        required_slots=frozenset({leaf}),
        required_sub_assemblies=frozenset({link}),
    )
    assert assembly.required_sub_assemblies == frozenset({link})


@pytest.mark.unit
def test_assembly_rejects_sub_assembly_link_colliding_with_leaf_slot() -> None:
    """A link's slot_name must not collide with a leaf slot_name: both
    share one named-position namespace for the register_fixture union."""
    leaf = TemplateSlot(
        slot_name=SlotName("optics"),
        required_family_ids=frozenset({uuid4()}),
        cardinality=SlotCardinality.EXACTLY_1,
    )
    link = SubAssemblyLink(
        slot_name=SlotName("optics"),
        sub_assembly_id=uuid4(),
        content_hash=_SUB_HASH,
    )
    with pytest.raises(SubAssemblySlotNameConflictError) as exc_info:
        Assembly(
            id=uuid4(),
            name=AssemblyName("Microscope"),
            presents_as_family_id=uuid4(),
            required_slots=frozenset({leaf}),
            required_sub_assemblies=frozenset({link}),
        )
    assert exc_info.value.slot_name == "optics"


@pytest.mark.unit
def test_assembly_rejects_duplicate_sub_assembly_link_slot_names() -> None:
    """Two links may not share a slot_name; each names a distinct
    position in the parent."""
    link_a = SubAssemblyLink(
        slot_name=SlotName("optics"),
        sub_assembly_id=uuid4(),
        content_hash="sha256:" + "a" * 8,
    )
    link_b = SubAssemblyLink(
        slot_name=SlotName("optics"),
        sub_assembly_id=uuid4(),
        content_hash="sha256:" + "b" * 8,
    )
    with pytest.raises(SubAssemblySlotNameConflictError) as exc_info:
        Assembly(
            id=uuid4(),
            name=AssemblyName("Microscope"),
            presents_as_family_id=uuid4(),
            required_sub_assemblies=frozenset({link_a, link_b}),
        )
    assert exc_info.value.slot_name == "optics"
