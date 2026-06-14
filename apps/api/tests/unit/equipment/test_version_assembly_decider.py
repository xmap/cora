"""Unit tests for the `version_assembly` slice's pure decider."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from cora.equipment.aggregates.assembly import (
    Assembly,
    AssemblyCannotVersionError,
    AssemblyName,
    AssemblyNotFoundError,
    AssemblyStatus,
    AssemblyVersioned,
    FamilyNotFoundForAssemblyError,
    InvalidAssemblyNameError,
    InvalidParameterOverridesSchemaError,
    SlotCardinality,
    SlotName,
    SubAssemblyContentHashMismatchError,
    SubAssemblyCycleError,
    SubAssemblyLink,
    SubAssemblyNestingTooDeepError,
    SubAssemblyNotFoundForAssemblyError,
    SubAssemblySlotNameConflictError,
    TemplateSlot,
    TemplateWire,
    WireReferencesUnknownSlotError,
)
from cora.equipment.features import version_assembly
from cora.equipment.features.version_assembly import (
    VersionAssembly,
    VersionAssemblyContext,
)

_NOW = datetime(2026, 6, 2, 13, 0, 0, tzinfo=UTC)


def _slot(name: str = "camera", family_id: object = None) -> TemplateSlot:
    return TemplateSlot(
        slot_name=SlotName(name),
        required_family_ids=frozenset({family_id or uuid4()}),  # type: ignore[arg-type]
        cardinality=SlotCardinality.EXACTLY_1,
    )


def _state(
    assembly_id: object,
    family_id: object,
    *,
    status: AssemblyStatus = AssemblyStatus.DEFINED,
    content_hash: str = "a" * 64,
) -> Assembly:
    return Assembly(
        id=assembly_id,  # type: ignore[arg-type]
        name=AssemblyName("Initial"),
        presents_as_family_id=family_id,  # type: ignore[arg-type]
        status=status,
        content_hash=content_hash,
    )


@pytest.mark.unit
def test_decide_emits_assembly_versioned_from_defined_state() -> None:
    assembly_id = uuid4()
    family_id = uuid4()
    state = _state(assembly_id, family_id, status=AssemblyStatus.DEFINED)
    events = version_assembly.decide(
        state=state,
        command=VersionAssembly(
            assembly_id=assembly_id,
            name="Detector",
            presents_as_family_id=family_id,
            version="v0.2.0",
        ),
        context=VersionAssemblyContext(missing_family_ids=frozenset()),
        now=_NOW,
    )
    assert len(events) == 1
    event = events[0]
    assert isinstance(event, AssemblyVersioned)
    assert event.assembly_id == assembly_id
    assert event.previous_content_hash == "a" * 64
    assert event.version == "v0.2.0"
    assert event.occurred_at == _NOW
    assert len(event.content_hash) == 64


@pytest.mark.unit
def test_decide_emits_assembly_versioned_from_versioned_state() -> None:
    """Multi-source FSM: Versioned -> Versioned is also valid."""
    assembly_id = uuid4()
    family_id = uuid4()
    state = _state(
        assembly_id,
        family_id,
        status=AssemblyStatus.VERSIONED,
        content_hash="b" * 64,
    )
    events = version_assembly.decide(
        state=state,
        command=VersionAssembly(
            assembly_id=assembly_id,
            name="Detector",
            presents_as_family_id=family_id,
            version="v0.3.0",
        ),
        context=VersionAssemblyContext(missing_family_ids=frozenset()),
        now=_NOW,
    )
    assert len(events) == 1
    assert events[0].previous_content_hash == "b" * 64


@pytest.mark.unit
def test_decide_rejects_none_state_with_assembly_not_found() -> None:
    target_id = uuid4()
    with pytest.raises(AssemblyNotFoundError) as exc_info:
        version_assembly.decide(
            state=None,
            command=VersionAssembly(
                assembly_id=target_id,
                name="X",
                presents_as_family_id=uuid4(),
            ),
            context=VersionAssemblyContext(missing_family_ids=frozenset()),
            now=_NOW,
        )
    assert exc_info.value.assembly_id == target_id


@pytest.mark.unit
def test_decide_rejects_deprecated_state_with_cannot_version() -> None:
    assembly_id = uuid4()
    family_id = uuid4()
    state = _state(assembly_id, family_id, status=AssemblyStatus.DEPRECATED)
    with pytest.raises(AssemblyCannotVersionError) as exc_info:
        version_assembly.decide(
            state=state,
            command=VersionAssembly(
                assembly_id=assembly_id,
                name="X",
                presents_as_family_id=family_id,
            ),
            context=VersionAssemblyContext(missing_family_ids=frozenset()),
            now=_NOW,
        )
    assert exc_info.value.assembly_id == assembly_id
    assert "Deprecated" in exc_info.value.reason


@pytest.mark.unit
def test_decide_rejects_missing_family_with_family_not_found() -> None:
    assembly_id = uuid4()
    family_id = uuid4()
    state = _state(assembly_id, family_id)
    missing_family = uuid4()
    with pytest.raises(FamilyNotFoundForAssemblyError) as exc_info:
        version_assembly.decide(
            state=state,
            command=VersionAssembly(
                assembly_id=assembly_id,
                name="X",
                presents_as_family_id=missing_family,
            ),
            context=VersionAssemblyContext(missing_family_ids=frozenset({missing_family})),
            now=_NOW,
        )
    assert exc_info.value.family_id == missing_family


@pytest.mark.unit
def test_decide_rejects_invalid_name_via_vo() -> None:
    assembly_id = uuid4()
    family_id = uuid4()
    state = _state(assembly_id, family_id)
    with pytest.raises(InvalidAssemblyNameError):
        version_assembly.decide(
            state=state,
            command=VersionAssembly(
                assembly_id=assembly_id,
                name="   ",
                presents_as_family_id=family_id,
            ),
            context=VersionAssemblyContext(missing_family_ids=frozenset()),
            now=_NOW,
        )


@pytest.mark.unit
def test_decide_rejects_wire_referencing_unknown_slot() -> None:
    assembly_id = uuid4()
    family_id = uuid4()
    state = _state(assembly_id, family_id)
    wire = TemplateWire(
        source_slot_name="missing",
        source_port_name="out",
        target_slot_name="camera",
        target_port_name="in",
    )
    camera_slot = _slot("camera")
    with pytest.raises(WireReferencesUnknownSlotError) as exc_info:
        version_assembly.decide(
            state=state,
            command=VersionAssembly(
                assembly_id=assembly_id,
                name="X",
                presents_as_family_id=family_id,
                required_slots=frozenset({camera_slot}),
                required_wires=frozenset({wire}),
            ),
            context=VersionAssemblyContext(missing_family_ids=frozenset()),
            now=_NOW,
        )
    assert exc_info.value.slot_name == "missing"


@pytest.mark.unit
def test_decide_rejects_invalid_parameter_overrides_schema() -> None:
    assembly_id = uuid4()
    family_id = uuid4()
    state = _state(assembly_id, family_id)
    with pytest.raises(InvalidParameterOverridesSchemaError):
        version_assembly.decide(
            state=state,
            command=VersionAssembly(
                assembly_id=assembly_id,
                name="X",
                presents_as_family_id=family_id,
                parameter_overrides_schema={"oneOf": [{"type": "object"}]},
            ),
            context=VersionAssemblyContext(missing_family_ids=frozenset()),
            now=_NOW,
        )


@pytest.mark.unit
def test_decide_allows_re_attestation_with_same_content() -> None:
    """Same structural content yields the same content_hash but
    emits a fresh AssemblyVersioned event; the decider does not
    refuse re-attestation."""
    assembly_id = uuid4()
    family_id = uuid4()
    state = _state(assembly_id, family_id, content_hash="prev" + "0" * 60)
    command = VersionAssembly(
        assembly_id=assembly_id,
        name="Stable",
        presents_as_family_id=family_id,
        version="v1.0.0",
    )
    context = VersionAssemblyContext(missing_family_ids=frozenset())
    events_a = version_assembly.decide(state, command, context=context, now=_NOW)
    events_b = version_assembly.decide(state, command, context=context, now=_NOW)
    assert len(events_a) == 1
    assert len(events_b) == 1
    # Same content -> same content_hash. Each call still emits a
    # fresh event (the audit moment is captured per call).
    assert events_a[0].content_hash == events_b[0].content_hash
    assert events_a[0].previous_content_hash == "prev" + "0" * 60


@pytest.mark.unit
def test_decide_replace_on_version_carries_full_new_slot_set() -> None:
    assembly_id = uuid4()
    family_id = uuid4()
    state = _state(assembly_id, family_id)
    new_slots = frozenset({_slot("camera"), _slot("scintillator"), _slot("trigger_source")})
    events = version_assembly.decide(
        state=state,
        command=VersionAssembly(
            assembly_id=assembly_id,
            name="Detector",
            presents_as_family_id=family_id,
            required_slots=new_slots,
        ),
        context=VersionAssemblyContext(missing_family_ids=frozenset()),
        now=_NOW,
    )
    assert events[0].required_slots == new_slots


_SUB_HASH = "sha256:" + "a" * 8


@pytest.mark.unit
def test_decide_emits_versioned_with_required_sub_assemblies() -> None:
    assembly_id = uuid4()
    family_id = uuid4()
    link = SubAssemblyLink(
        slot_name=SlotName("optics"), sub_assembly_id=uuid4(), content_hash=_SUB_HASH
    )
    events = version_assembly.decide(
        state=_state(assembly_id, family_id),
        command=VersionAssembly(
            assembly_id=assembly_id,
            name="Microscope",
            presents_as_family_id=family_id,
            required_sub_assemblies=frozenset({link}),
        ),
        context=VersionAssemblyContext(missing_family_ids=frozenset()),
        now=_NOW,
    )
    assert events[0].required_sub_assemblies == frozenset({link})


@pytest.mark.unit
def test_decide_rejects_missing_sub_assembly() -> None:
    assembly_id = uuid4()
    family_id = uuid4()
    child = uuid4()
    link = SubAssemblyLink(
        slot_name=SlotName("optics"), sub_assembly_id=child, content_hash=_SUB_HASH
    )
    with pytest.raises(SubAssemblyNotFoundForAssemblyError) as exc_info:
        version_assembly.decide(
            state=_state(assembly_id, family_id),
            command=VersionAssembly(
                assembly_id=assembly_id,
                name="Microscope",
                presents_as_family_id=family_id,
                required_sub_assemblies=frozenset({link}),
            ),
            context=VersionAssemblyContext(
                missing_family_ids=frozenset(),
                sub_assembly_missing_ids=frozenset({child}),
            ),
            now=_NOW,
        )
    assert exc_info.value.sub_assembly_id == child


@pytest.mark.unit
def test_decide_rejects_sub_assembly_content_hash_mismatch() -> None:
    assembly_id = uuid4()
    family_id = uuid4()
    child = uuid4()
    current = "sha256:" + "b" * 8
    link = SubAssemblyLink(
        slot_name=SlotName("optics"), sub_assembly_id=child, content_hash=_SUB_HASH
    )
    with pytest.raises(SubAssemblyContentHashMismatchError) as exc_info:
        version_assembly.decide(
            state=_state(assembly_id, family_id),
            command=VersionAssembly(
                assembly_id=assembly_id,
                name="Microscope",
                presents_as_family_id=family_id,
                required_sub_assemblies=frozenset({link}),
            ),
            context=VersionAssemblyContext(
                missing_family_ids=frozenset(),
                sub_assembly_hash_mismatches=frozenset({(child, _SUB_HASH, current)}),
            ),
            now=_NOW,
        )
    assert exc_info.value.current == current


@pytest.mark.unit
def test_decide_rejects_self_referential_sub_assembly() -> None:
    assembly_id = uuid4()
    family_id = uuid4()
    link = SubAssemblyLink(
        slot_name=SlotName("self"), sub_assembly_id=assembly_id, content_hash=_SUB_HASH
    )
    with pytest.raises(SubAssemblyCycleError) as exc_info:
        version_assembly.decide(
            state=_state(assembly_id, family_id),
            command=VersionAssembly(
                assembly_id=assembly_id,
                name="Microscope",
                presents_as_family_id=family_id,
                required_sub_assemblies=frozenset({link}),
            ),
            context=VersionAssemblyContext(missing_family_ids=frozenset()),
            now=_NOW,
        )
    assert exc_info.value.assembly_id == assembly_id


@pytest.mark.unit
def test_decide_rejects_sub_assembly_slot_name_colliding_with_leaf_slot() -> None:
    assembly_id = uuid4()
    family_id = uuid4()
    leaf = _slot("optics", family_id)
    link = SubAssemblyLink(
        slot_name=SlotName("optics"), sub_assembly_id=uuid4(), content_hash=_SUB_HASH
    )
    with pytest.raises(SubAssemblySlotNameConflictError) as exc_info:
        version_assembly.decide(
            state=_state(assembly_id, family_id),
            command=VersionAssembly(
                assembly_id=assembly_id,
                name="Microscope",
                presents_as_family_id=family_id,
                required_slots=frozenset({leaf}),
                required_sub_assemblies=frozenset({link}),
            ),
            context=VersionAssemblyContext(missing_family_ids=frozenset()),
            now=_NOW,
        )
    assert exc_info.value.slot_name == "optics"


@pytest.mark.unit
def test_decide_rejects_duplicate_sub_assembly_link_slot_name() -> None:
    """Two links sharing a slot_name with no colliding leaf slot trip the
    link-vs-link branch (distinct reason from the leaf-collision branch)."""
    assembly_id = uuid4()
    family_id = uuid4()
    link_a = SubAssemblyLink(
        slot_name=SlotName("optics"), sub_assembly_id=uuid4(), content_hash=_SUB_HASH
    )
    link_b = SubAssemblyLink(
        slot_name=SlotName("optics"), sub_assembly_id=uuid4(), content_hash=_SUB_HASH
    )
    with pytest.raises(SubAssemblySlotNameConflictError) as exc_info:
        version_assembly.decide(
            state=_state(assembly_id, family_id),
            command=VersionAssembly(
                assembly_id=assembly_id,
                name="Microscope",
                presents_as_family_id=family_id,
                required_sub_assemblies=frozenset({link_a, link_b}),
            ),
            context=VersionAssemblyContext(missing_family_ids=frozenset()),
            now=_NOW,
        )
    assert exc_info.value.slot_name == "optics"
    assert "duplicate" in exc_info.value.reason


@pytest.mark.unit
def test_decide_rejects_sub_assembly_that_is_itself_a_composite() -> None:
    """A child that declares its own sub-assemblies is too deep at version
    time too, identically to define time."""
    assembly_id = uuid4()
    family_id = uuid4()
    child = uuid4()
    link = SubAssemblyLink(
        slot_name=SlotName("optics"), sub_assembly_id=child, content_hash=_SUB_HASH
    )
    with pytest.raises(SubAssemblyNestingTooDeepError) as exc_info:
        version_assembly.decide(
            state=_state(assembly_id, family_id),
            command=VersionAssembly(
                assembly_id=assembly_id,
                name="Microscope",
                presents_as_family_id=family_id,
                required_sub_assemblies=frozenset({link}),
            ),
            context=VersionAssemblyContext(
                missing_family_ids=frozenset(),
                sub_assembly_too_deep_ids=frozenset({child}),
            ),
            now=_NOW,
        )
    assert exc_info.value.sub_assembly_id == child


@pytest.mark.unit
def test_decide_rejects_leaf_slot_collision_across_composed_blueprints() -> None:
    """A leaf slot_name present in more than one composed blueprint is
    rejected at version time, not only at register_fixture."""
    assembly_id = uuid4()
    family_id = uuid4()
    link = SubAssemblyLink(
        slot_name=SlotName("optics"), sub_assembly_id=uuid4(), content_hash=_SUB_HASH
    )
    with pytest.raises(SubAssemblySlotNameConflictError) as exc_info:
        version_assembly.decide(
            state=_state(assembly_id, family_id),
            command=VersionAssembly(
                assembly_id=assembly_id,
                name="Microscope",
                presents_as_family_id=family_id,
                required_sub_assemblies=frozenset({link}),
            ),
            context=VersionAssemblyContext(
                missing_family_ids=frozenset(),
                sub_assembly_leaf_collisions=frozenset({"camera"}),
            ),
            now=_NOW,
        )
    assert exc_info.value.slot_name == "camera"
    assert "more than one composed blueprint" in exc_info.value.reason
