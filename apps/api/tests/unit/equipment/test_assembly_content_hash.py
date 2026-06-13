"""Unit tests for the Assembly content_hash helper.

Pins three key properties:
  1. Determinism: same canonical content produces the same hash.
  2. Order-insensitivity: slot order and wire order do not affect
     the hash (because the canonical-subset materializer sorts).
  3. Round-trip equivalence: compute_assembly_content_hash(...) on
     raw fields equals compute_assembly_content_hash_from_state(...)
     on the corresponding Assembly state.
"""

from uuid import UUID, uuid4

import pytest

from cora.equipment.aggregates.assembly import (
    Assembly,
    AssemblyName,
    SlotCardinality,
    SlotName,
    TemplateSlot,
    TemplateWire,
)
from cora.equipment.aggregates.assembly._content_hash import (
    compute_assembly_content_hash,
    compute_assembly_content_hash_from_state,
)
from cora.equipment.aggregates.family import FamilyName, family_stream_id


def _slot(name: str, family_id: UUID) -> TemplateSlot:
    return TemplateSlot(
        slot_name=SlotName(name),
        required_family_ids=frozenset({family_id}),
        cardinality=SlotCardinality.EXACTLY_1,
    )


def _wire(src_slot: str, tgt_slot: str) -> TemplateWire:
    return TemplateWire(
        source_slot_name=src_slot,
        source_port_name="trigger_out",
        target_slot_name=tgt_slot,
        target_port_name="trigger_in",
    )


@pytest.mark.unit
def test_content_hash_is_sha256_hex_64_chars() -> None:
    h = compute_assembly_content_hash(
        name="Empty",
        presents_as_family_id=uuid4(),
        required_slots=frozenset(),
        required_wires=frozenset(),
        parameter_overrides_schema=None,
    )
    assert len(h) == 64
    assert all(c in "0123456789abcdef" for c in h)


@pytest.mark.unit
def test_content_hash_is_deterministic_for_same_input() -> None:
    name = "Detector"
    family_id = uuid4()
    slot_family = uuid4()
    slots = frozenset({_slot("camera", slot_family)})
    wires = frozenset({_wire("trigger_source", "camera")})
    h1 = compute_assembly_content_hash(
        name=name,
        presents_as_family_id=family_id,
        required_slots=slots,
        required_wires=wires,
        parameter_overrides_schema={"type": "object"},
    )
    h2 = compute_assembly_content_hash(
        name=name,
        presents_as_family_id=family_id,
        required_slots=slots,
        required_wires=wires,
        parameter_overrides_schema={"type": "object"},
    )
    assert h1 == h2


@pytest.mark.unit
def test_content_hash_differs_when_name_differs() -> None:
    family_id = uuid4()
    h1 = compute_assembly_content_hash(
        name="Detector",
        presents_as_family_id=family_id,
        required_slots=frozenset(),
        required_wires=frozenset(),
        parameter_overrides_schema=None,
    )
    h2 = compute_assembly_content_hash(
        name="DetectorV2",
        presents_as_family_id=family_id,
        required_slots=frozenset(),
        required_wires=frozenset(),
        parameter_overrides_schema=None,
    )
    assert h1 != h2


@pytest.mark.unit
def test_content_hash_differs_when_presents_as_family_id_differs() -> None:
    h1 = compute_assembly_content_hash(
        name="X",
        presents_as_family_id=uuid4(),
        required_slots=frozenset(),
        required_wires=frozenset(),
        parameter_overrides_schema=None,
    )
    h2 = compute_assembly_content_hash(
        name="X",
        presents_as_family_id=uuid4(),
        required_slots=frozenset(),
        required_wires=frozenset(),
        parameter_overrides_schema=None,
    )
    assert h1 != h2


@pytest.mark.unit
def test_content_hash_differs_when_slot_added() -> None:
    family_id = uuid4()
    slot_family = uuid4()
    h_empty = compute_assembly_content_hash(
        name="Detector",
        presents_as_family_id=family_id,
        required_slots=frozenset(),
        required_wires=frozenset(),
        parameter_overrides_schema=None,
    )
    h_with_slot = compute_assembly_content_hash(
        name="Detector",
        presents_as_family_id=family_id,
        required_slots=frozenset({_slot("camera", slot_family)}),
        required_wires=frozenset(),
        parameter_overrides_schema=None,
    )
    assert h_empty != h_with_slot


@pytest.mark.unit
def test_content_hash_is_insensitive_to_slot_iteration_order() -> None:
    """Building the slot set from a list in two different orders must
    produce the same hash (the canonical-subset materializer sorts)."""
    family_id = uuid4()
    sf_a, sf_b, sf_c = uuid4(), uuid4(), uuid4()
    slots_one = frozenset(
        {
            _slot("camera", sf_a),
            _slot("scintillator", sf_b),
            _slot("trigger_source", sf_c),
        }
    )
    slots_two = frozenset(
        {
            _slot("trigger_source", sf_c),
            _slot("camera", sf_a),
            _slot("scintillator", sf_b),
        }
    )
    h1 = compute_assembly_content_hash(
        name="Detector",
        presents_as_family_id=family_id,
        required_slots=slots_one,
        required_wires=frozenset(),
        parameter_overrides_schema=None,
    )
    h2 = compute_assembly_content_hash(
        name="Detector",
        presents_as_family_id=family_id,
        required_slots=slots_two,
        required_wires=frozenset(),
        parameter_overrides_schema=None,
    )
    assert h1 == h2


@pytest.mark.unit
def test_content_hash_differs_when_wire_added() -> None:
    family_id = uuid4()
    sf_a, sf_b = uuid4(), uuid4()
    slots = frozenset({_slot("camera", sf_a), _slot("trigger_source", sf_b)})
    h_no_wires = compute_assembly_content_hash(
        name="Detector",
        presents_as_family_id=family_id,
        required_slots=slots,
        required_wires=frozenset(),
        parameter_overrides_schema=None,
    )
    h_with_wire = compute_assembly_content_hash(
        name="Detector",
        presents_as_family_id=family_id,
        required_slots=slots,
        required_wires=frozenset({_wire("trigger_source", "camera")}),
        parameter_overrides_schema=None,
    )
    assert h_no_wires != h_with_wire


@pytest.mark.unit
def test_content_hash_differs_when_parameter_overrides_schema_differs() -> None:
    family_id = uuid4()
    h_none = compute_assembly_content_hash(
        name="X",
        presents_as_family_id=family_id,
        required_slots=frozenset(),
        required_wires=frozenset(),
        parameter_overrides_schema=None,
    )
    h_simple = compute_assembly_content_hash(
        name="X",
        presents_as_family_id=family_id,
        required_slots=frozenset(),
        required_wires=frozenset(),
        parameter_overrides_schema={"type": "object"},
    )
    h_richer = compute_assembly_content_hash(
        name="X",
        presents_as_family_id=family_id,
        required_slots=frozenset(),
        required_wires=frozenset(),
        parameter_overrides_schema={"type": "object", "additionalProperties": False},
    )
    assert h_none != h_simple
    assert h_simple != h_richer
    assert h_none != h_richer


@pytest.mark.unit
def test_content_hash_differs_when_slot_cardinality_differs() -> None:
    family_id = uuid4()
    slot_family = uuid4()
    slot_exactly_1 = TemplateSlot(
        slot_name=SlotName("camera"),
        required_family_ids=frozenset({slot_family}),
        cardinality=SlotCardinality.EXACTLY_1,
    )
    slot_zero_or_one = TemplateSlot(
        slot_name=SlotName("camera"),
        required_family_ids=frozenset({slot_family}),
        cardinality=SlotCardinality.ZERO_OR_ONE,
    )
    h_a = compute_assembly_content_hash(
        name="Detector",
        presents_as_family_id=family_id,
        required_slots=frozenset({slot_exactly_1}),
        required_wires=frozenset(),
        parameter_overrides_schema=None,
    )
    h_b = compute_assembly_content_hash(
        name="Detector",
        presents_as_family_id=family_id,
        required_slots=frozenset({slot_zero_or_one}),
        required_wires=frozenset(),
        parameter_overrides_schema=None,
    )
    assert h_a != h_b


@pytest.mark.unit
def test_content_hash_differs_when_default_settings_differs() -> None:
    family_id = uuid4()
    slot_family = uuid4()
    slot_low = TemplateSlot(
        slot_name=SlotName("camera"),
        required_family_ids=frozenset({slot_family}),
        cardinality=SlotCardinality.EXACTLY_1,
        default_settings={"exposure_ms": 100},
    )
    slot_high = TemplateSlot(
        slot_name=SlotName("camera"),
        required_family_ids=frozenset({slot_family}),
        cardinality=SlotCardinality.EXACTLY_1,
        default_settings={"exposure_ms": 200},
    )
    h_a = compute_assembly_content_hash(
        name="Detector",
        presents_as_family_id=family_id,
        required_slots=frozenset({slot_low}),
        required_wires=frozenset(),
        parameter_overrides_schema=None,
    )
    h_b = compute_assembly_content_hash(
        name="Detector",
        presents_as_family_id=family_id,
        required_slots=frozenset({slot_high}),
        required_wires=frozenset(),
        parameter_overrides_schema=None,
    )
    assert h_a != h_b


@pytest.mark.unit
def test_content_hash_is_insensitive_to_wire_iteration_order() -> None:
    """Three wires authored in two different orderings must produce
    the same hash; canonical-subset materializer sorts the wire set."""
    family_id = uuid4()
    sf_a, sf_b, sf_c, sf_d = uuid4(), uuid4(), uuid4(), uuid4()
    slots = frozenset(
        {
            _slot("trigger_source", sf_a),
            _slot("camera", sf_b),
            _slot("scintillator", sf_c),
            _slot("filter", sf_d),
        }
    )
    wires_one = frozenset(
        {
            _wire("trigger_source", "camera"),
            _wire("camera", "scintillator"),
            _wire("filter", "camera"),
        }
    )
    wires_two = frozenset(
        {
            _wire("filter", "camera"),
            _wire("trigger_source", "camera"),
            _wire("camera", "scintillator"),
        }
    )
    h1 = compute_assembly_content_hash(
        name="Detector",
        presents_as_family_id=family_id,
        required_slots=slots,
        required_wires=wires_one,
        parameter_overrides_schema=None,
    )
    h2 = compute_assembly_content_hash(
        name="Detector",
        presents_as_family_id=family_id,
        required_slots=slots,
        required_wires=wires_two,
        parameter_overrides_schema=None,
    )
    assert h1 == h2


@pytest.mark.unit
def test_content_hash_round_trip_via_state_with_default_placement() -> None:
    """Round-trip equivalence must hold when slots carry non-None
    default_placement. Pins that the Placement subset survives both
    paths (state.content_subset and compute_assembly_content_hash)
    identically; without this test, drift between
    `canonical_placement_subset` and any drift-introduced copy would
    be invisible."""
    from cora.equipment.aggregates._placement import (
        Placement,
        ReferenceSurface,
        UnitSystem,
    )

    family_id = uuid4()
    slot_family = uuid4()
    frame_id = uuid4()
    placement = Placement(
        x=12.5,
        y=-3.0,
        z=27626.0,
        rx=0.0,
        ry=0.001,
        rz=0.0,
        parent_frame_id=frame_id,
        reference_surface=ReferenceSurface.OPTIC_CENTER,
        tol_x=0.25,
        tol_y=0.25,
        tol_z=5.0,
        tol_rx=0.0001,
        tol_ry=0.0001,
        tol_rz=0.0001,
        units=UnitSystem.SI_MM_RAD,
    )
    slot_with_placement = TemplateSlot(
        slot_name=SlotName("camera"),
        required_family_ids=frozenset({slot_family}),
        cardinality=SlotCardinality.EXACTLY_1,
        default_placement=placement,
    )
    slots = frozenset({slot_with_placement})
    h_from_args = compute_assembly_content_hash(
        name="Detector",
        presents_as_family_id=family_id,
        required_slots=slots,
        required_wires=frozenset(),
        parameter_overrides_schema=None,
    )
    state = Assembly(
        id=uuid4(),
        name=AssemblyName("Detector"),
        presents_as_family_id=family_id,
        required_slots=slots,
        required_wires=frozenset(),
    )
    h_from_state = compute_assembly_content_hash_from_state(state)
    assert h_from_args == h_from_state


@pytest.mark.unit
def test_content_hash_round_trip_via_state() -> None:
    """compute_assembly_content_hash(args) MUST equal
    compute_assembly_content_hash_from_state(Assembly(args)).

    This pins that the two computation paths (raw-args and via
    state.content_subset()) materialize the same canonical body.
    """
    family_id = uuid4()
    slot_family = uuid4()
    slots = frozenset({_slot("camera", slot_family)})
    wires = frozenset({_wire("trigger_source", "camera")})

    extra_slot = _slot("trigger_source", uuid4())
    full_slots = slots | {extra_slot}

    h_from_args = compute_assembly_content_hash(
        name="Detector",
        presents_as_family_id=family_id,
        required_slots=full_slots,
        required_wires=wires,
        parameter_overrides_schema={"type": "object"},
    )
    state = Assembly(
        id=uuid4(),
        name=AssemblyName("Detector"),
        presents_as_family_id=family_id,
        required_slots=full_slots,
        required_wires=wires,
        parameter_overrides_schema={"type": "object"},
    )
    h_from_state = compute_assembly_content_hash_from_state(state)
    assert h_from_args == h_from_state


@pytest.mark.unit
def test_content_hash_ignores_drawing_per_design_lock() -> None:
    """Drawing is excluded from the canonical subset; two Assemblies
    differing only by drawing collide on content_hash (intended)."""
    from cora.equipment.aggregates._drawing import Drawing, DrawingSystem

    family_id = uuid4()
    state_no_drawing = Assembly(
        id=uuid4(),
        name=AssemblyName("X"),
        presents_as_family_id=family_id,
        required_slots=frozenset(),
        required_wires=frozenset(),
    )
    state_with_drawing = Assembly(
        id=uuid4(),
        name=AssemblyName("X"),
        presents_as_family_id=family_id,
        required_slots=frozenset(),
        required_wires=frozenset(),
        drawing=Drawing(system=DrawingSystem.ICMS, number="P4105", revision="A"),
    )
    assert compute_assembly_content_hash_from_state(
        state_no_drawing
    ) == compute_assembly_content_hash_from_state(state_with_drawing)


@pytest.mark.unit
def test_two_assemblies_same_intent_across_facilities_share_hash() -> None:
    """The headline cross-facility guarantee: two facilities that author
    the same Assembly intent from the same Family NAMES converge on one
    content_hash. This holds only because Family ids are deterministic
    (uuid5 over the name); with random per-facility Family ids the slot
    and presenter ids would differ and the hashes would diverge."""

    def _hash_authored_from_names() -> str:
        return compute_assembly_content_hash(
            name="MCTOptics",
            presents_as_family_id=family_stream_id(FamilyName("Imager")),
            required_slots=frozenset(
                {
                    _slot("camera", family_stream_id(FamilyName("Camera"))),
                    _slot("scintillator", family_stream_id(FamilyName("Scintillator"))),
                }
            ),
            required_wires=frozenset(),
            parameter_overrides_schema=None,
        )

    facility_a = _hash_authored_from_names()
    facility_b = _hash_authored_from_names()
    assert facility_a == facility_b


@pytest.mark.unit
def test_different_family_names_yield_distinct_hashes() -> None:
    presenter = family_stream_id(FamilyName("Imager"))
    h_camera = compute_assembly_content_hash(
        name="MCTOptics",
        presents_as_family_id=presenter,
        required_slots=frozenset({_slot("sensor", family_stream_id(FamilyName("Camera")))}),
        required_wires=frozenset(),
        parameter_overrides_schema=None,
    )
    h_objective = compute_assembly_content_hash(
        name="MCTOptics",
        presents_as_family_id=presenter,
        required_slots=frozenset({_slot("sensor", family_stream_id(FamilyName("Objective")))}),
        required_wires=frozenset(),
        parameter_overrides_schema=None,
    )
    assert h_camera != h_objective


@pytest.mark.unit
def test_content_hash_ignores_version_per_design_lock() -> None:
    """Version is operator-curated lifecycle metadata, excluded from
    content_subset; two snapshots with same structure but different
    version labels collide on content_hash (intended re-attestation)."""
    family_id = uuid4()
    state_v1 = Assembly(
        id=uuid4(),
        name=AssemblyName("X"),
        presents_as_family_id=family_id,
        required_slots=frozenset(),
        required_wires=frozenset(),
        version="v1",
    )
    state_v2 = Assembly(
        id=uuid4(),
        name=AssemblyName("X"),
        presents_as_family_id=family_id,
        required_slots=frozenset(),
        required_wires=frozenset(),
        version="v2",
    )
    assert compute_assembly_content_hash_from_state(
        state_v1
    ) == compute_assembly_content_hash_from_state(state_v2)
