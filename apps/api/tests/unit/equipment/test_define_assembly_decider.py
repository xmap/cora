"""Unit tests for the `define_assembly` slice's pure decider."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from cora.equipment.aggregates.assembly import (
    Assembly,
    AssemblyAlreadyExistsError,
    AssemblyDefined,
    AssemblyName,
    AssemblyStatus,
    FamilyNotFoundForAssemblyError,
    InvalidAssemblyNameError,
    InvalidParameterOverridesSchemaError,
    SlotCardinality,
    SlotName,
    TemplateSlot,
    TemplateWire,
)
from cora.equipment.features import define_assembly
from cora.equipment.features.define_assembly import (
    DefineAssembly,
    DefineAssemblyContext,
)

_NOW = datetime(2026, 6, 2, 12, 0, 0, tzinfo=UTC)


def _slot(name: str = "camera", family_id: object = None) -> TemplateSlot:
    return TemplateSlot(
        slot_name=SlotName(name),
        required_family_ids=frozenset({family_id or uuid4()}),  # type: ignore[arg-type]
        cardinality=SlotCardinality.EXACTLY_1,
    )


@pytest.mark.unit
def test_decide_emits_assembly_defined_for_minimal_command() -> None:
    new_id = uuid4()
    family_id = uuid4()
    events = define_assembly.decide(
        state=None,
        command=DefineAssembly(
            name="Detector",
            presents_as_family_id=family_id,
            required_slots=frozenset(),
            required_wires=frozenset(),
        ),
        context=DefineAssemblyContext(missing_family_ids=frozenset()),
        now=_NOW,
        new_id=new_id,
    )
    assert len(events) == 1
    event = events[0]
    assert isinstance(event, AssemblyDefined)
    assert event.assembly_id == new_id
    assert event.name == AssemblyName("Detector")
    assert event.presents_as_family_id == family_id
    assert event.required_slots == frozenset()
    assert event.required_wires == frozenset()
    assert event.drawing is None
    assert event.version is None
    assert event.parameter_overrides_schema is None
    assert event.occurred_at == _NOW
    assert len(event.content_hash) == 64
    assert all(c in "0123456789abcdef" for c in event.content_hash)


@pytest.mark.unit
def test_decide_emits_assembly_defined_with_slots_and_wires_and_version() -> None:
    new_id = uuid4()
    family_id = uuid4()
    sf_camera, sf_trigger = uuid4(), uuid4()
    slot_camera = _slot("camera", sf_camera)
    slot_trigger = _slot("trigger_source", sf_trigger)
    wire = TemplateWire(
        source_slot_name="trigger_source",
        source_port_name="trigger_out",
        target_slot_name="camera",
        target_port_name="trigger_in",
    )
    events = define_assembly.decide(
        state=None,
        command=DefineAssembly(
            name="Detector",
            presents_as_family_id=family_id,
            required_slots=frozenset({slot_camera, slot_trigger}),
            required_wires=frozenset({wire}),
            parameter_overrides_schema={
                "$schema": "https://json-schema.org/draft/2020-12/schema",
                "type": "object",
            },
            version="v0.1.0",
        ),
        context=DefineAssemblyContext(missing_family_ids=frozenset()),
        now=_NOW,
        new_id=new_id,
    )
    assert len(events) == 1
    event = events[0]
    assert event.required_slots == frozenset({slot_camera, slot_trigger})
    assert event.required_wires == frozenset({wire})
    assert event.parameter_overrides_schema == {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "type": "object",
    }
    assert event.version == "v0.1.0"


@pytest.mark.unit
def test_decide_rejects_non_none_state_with_assembly_already_exists() -> None:
    existing_id = uuid4()
    family_id = uuid4()
    state = Assembly(
        id=existing_id,
        name=AssemblyName("Existing"),
        presents_as_family_id=family_id,
        status=AssemblyStatus.DEFINED,
    )
    with pytest.raises(AssemblyAlreadyExistsError) as exc_info:
        define_assembly.decide(
            state=state,
            command=DefineAssembly(
                name="X",
                presents_as_family_id=family_id,
            ),
            context=DefineAssemblyContext(missing_family_ids=frozenset()),
            now=_NOW,
            new_id=uuid4(),
        )
    assert exc_info.value.assembly_id == existing_id


@pytest.mark.unit
def test_decide_rejects_missing_presents_as_family_id_with_family_not_found() -> None:
    family_id = uuid4()
    with pytest.raises(FamilyNotFoundForAssemblyError) as exc_info:
        define_assembly.decide(
            state=None,
            command=DefineAssembly(
                name="Detector",
                presents_as_family_id=family_id,
            ),
            context=DefineAssemblyContext(missing_family_ids=frozenset({family_id})),
            now=_NOW,
            new_id=uuid4(),
        )
    assert exc_info.value.family_id == family_id


@pytest.mark.unit
def test_decide_rejects_missing_slot_required_family_with_family_not_found() -> None:
    presents_id = uuid4()
    slot_family = uuid4()
    slot = _slot("camera", slot_family)
    with pytest.raises(FamilyNotFoundForAssemblyError) as exc_info:
        define_assembly.decide(
            state=None,
            command=DefineAssembly(
                name="Detector",
                presents_as_family_id=presents_id,
                required_slots=frozenset({slot}),
            ),
            context=DefineAssemblyContext(missing_family_ids=frozenset({slot_family})),
            now=_NOW,
            new_id=uuid4(),
        )
    assert exc_info.value.family_id == slot_family


@pytest.mark.unit
def test_decide_surfaces_first_missing_family_id_deterministically() -> None:
    """When multiple families are missing, the decider raises with the
    sorted-first id so error responses are stable across runs."""
    a, b, c = uuid4(), uuid4(), uuid4()
    missing = {a, b, c}
    expected_first = sorted(missing, key=str)[0]
    with pytest.raises(FamilyNotFoundForAssemblyError) as exc_info:
        define_assembly.decide(
            state=None,
            command=DefineAssembly(name="X", presents_as_family_id=a),
            context=DefineAssemblyContext(missing_family_ids=frozenset(missing)),
            now=_NOW,
            new_id=uuid4(),
        )
    assert exc_info.value.family_id == expected_first


@pytest.mark.unit
def test_decide_rejects_invalid_name_via_vo() -> None:
    with pytest.raises(InvalidAssemblyNameError):
        define_assembly.decide(
            state=None,
            command=DefineAssembly(name="   ", presents_as_family_id=uuid4()),
            context=DefineAssemblyContext(missing_family_ids=frozenset()),
            now=_NOW,
            new_id=uuid4(),
        )


@pytest.mark.unit
def test_decide_rejects_invalid_parameter_overrides_schema() -> None:
    with pytest.raises(InvalidParameterOverridesSchemaError):
        define_assembly.decide(
            state=None,
            command=DefineAssembly(
                name="Detector",
                presents_as_family_id=uuid4(),
                parameter_overrides_schema={"oneOf": [{"type": "object"}]},
            ),
            context=DefineAssemblyContext(missing_family_ids=frozenset()),
            now=_NOW,
            new_id=uuid4(),
        )


@pytest.mark.unit
def test_decide_content_hash_is_deterministic_across_invocations() -> None:
    """Same command + context yields the same content_hash (pinning
    that the decider does not inject non-deterministic state into
    the hash inputs)."""
    new_id_a = uuid4()
    new_id_b = uuid4()
    family_id = uuid4()
    slot_family = uuid4()

    def _build(new_id: object) -> str:
        events = define_assembly.decide(
            state=None,
            command=DefineAssembly(
                name="Detector",
                presents_as_family_id=family_id,
                required_slots=frozenset({_slot("camera", slot_family)}),
            ),
            context=DefineAssemblyContext(missing_family_ids=frozenset()),
            now=_NOW,
            new_id=new_id,  # type: ignore[arg-type]
        )
        return events[0].content_hash

    assert _build(new_id_a) == _build(new_id_b)


@pytest.mark.unit
def test_decide_emits_assembly_defined_with_drawing() -> None:
    from cora.equipment.aggregates._drawing import Drawing, DrawingSystem

    family_id = uuid4()
    drawing = Drawing(system=DrawingSystem.ICMS, number="P4105", revision="A")
    events = define_assembly.decide(
        state=None,
        command=DefineAssembly(
            name="Detector",
            presents_as_family_id=family_id,
            drawing=drawing,
        ),
        context=DefineAssemblyContext(missing_family_ids=frozenset()),
        now=_NOW,
        new_id=uuid4(),
    )
    assert events[0].drawing == drawing
