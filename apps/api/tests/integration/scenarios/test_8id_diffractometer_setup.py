"""Six-circle diffractometer deployment at APS 8-ID (Assembly composes Goniometer).

cluster: Commissioning
archetype: setup
bc_primary: Equipment
bc_touches: Equipment

Materializes the 8-ID-E six-circle Huber diffractometer as a Diffractometer
Assembly and one Fixture, end-to-end against Postgres. This is the first spine
exercise of the reverse-engineered APS deployments (4-ID POLAR and 8-ID): it
proves the Assembly(Diffractometer) blueprint, which COMPOSES the Goniometer
Family graduated for I03 MX (#340) rather than re-modelling the sample circles.

  - one Goniometer Asset (Family Goniometer) for the sample-orientation circles
    (mu / eta / chi / phi) plus x/y/z centring, bound to the Exactly1 `goniometer`
    slot. The Goniometer is the integrated sample orienter; the Diffractometer is
    the larger composed instrument that uses it.
  - two detector-arm circle Assets (Nu, Delta), each Family RotaryStage, bound to
    the ZeroOrMore `detector_arm` slot,
  - one reciprocal-space Asset (ReciprocalSpace, Family PseudoAxis) on the Exactly1
    `reciprocal_space` slot; its hklpy2 solver partition rule is DIFF-2, left unset,
  - a flat Diffractometer Assembly presenting the Positioner Role,
  - one Fixture binding the four Assets across the three slots.

detector_arm is ZeroOrMore so one blueprint spans 8-ID's nu / delta detector arm
and 4-ID's detector-arm-less Eulerian / high-pressure geometries.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from datetime import UTC, datetime
from uuid import UUID, uuid4

import asyncpg
import pytest

from cora.equipment.aggregates.assembly import (
    SlotCardinality,
    SlotName,
    TemplateSlot,
)
from cora.equipment.aggregates.family import FamilyName, family_stream_id
from cora.equipment.aggregates.fixture import SlotAssetBinding
from cora.equipment.aggregates.role import SEED_ROLE_POSITIONER_ID
from cora.equipment.features.attach_asset_to_fixture import AttachAssetToFixture
from cora.equipment.features.attach_asset_to_fixture import bind as bind_attach_asset_to_fixture
from cora.equipment.features.define_assembly import DefineAssembly
from cora.equipment.features.define_assembly import bind as bind_define_assembly
from cora.equipment.features.register_fixture import RegisterFixture
from cora.equipment.features.register_fixture import bind as bind_register_fixture
from cora.infrastructure.adapters.in_memory_role_lookup import InMemoryRoleLookup
from tests.integration._equipment_helpers import install_existing_asset_into_fresh_mount
from tests.integration._helpers import build_postgres_deps, make_pg_profile_store
from tests.integration.scenarios._facility_fixture import (
    DeviceSpec,
    facility_id_prefix,
    install_aps_unit,
    operator_for,
)

_NOW = datetime(2026, 5, 28, 12, 0, 0, tzinfo=UTC)
_PRINCIPAL_ID = operator_for(__file__)
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000008d00bb")

# Facility hierarchy (scenario tag 8d0)
_8ID_UNIT_ID = UUID("01900000-0000-7000-8000-0000008d0a01")

# Family ids (deterministic uuid5 from the name).
_CAP_GONIOMETER_ID = family_stream_id(FamilyName("Goniometer"))
_CAP_ROTARY_STAGE_ID = family_stream_id(FamilyName("RotaryStage"))
_CAP_PSEUDO_AXIS_ID = family_stream_id(FamilyName("PseudoAxis"))

# The four diffractometer constituent Assets (scenario-supplied ids): one
# Goniometer (the mu/eta/chi/phi sample orienter), two detector-arm circles, the
# reciprocal-space pseudo-axis.
_ASSET_GONIOMETER_ID = UUID("01900000-0000-7000-8000-0000008d0a11")
_ASSET_NU_ID = UUID("01900000-0000-7000-8000-0000008d0a21")
_ASSET_DELTA_ID = UUID("01900000-0000-7000-8000-0000008d0a31")
_ASSET_RECIPROCAL_SPACE_ID = UUID("01900000-0000-7000-8000-0000008d0a41")

# The two detector-arm circles share the ZeroOrMore detector_arm slot.
_DETECTOR_CIRCLES: tuple[tuple[str, UUID], ...] = (
    ("Nu", _ASSET_NU_ID),
    ("Delta", _ASSET_DELTA_ID),
)

_DEVICES = (
    DeviceSpec("SampleGoniometer", _ASSET_GONIOMETER_ID, "Goniometer", _CAP_GONIOMETER_ID),
    *(
        DeviceSpec(name, aid, "RotaryStage", _CAP_ROTARY_STAGE_ID)
        for name, aid in _DETECTOR_CIRCLES
    ),
    DeviceSpec("ReciprocalSpace", _ASSET_RECIPROCAL_SPACE_ID, "PseudoAxis", _CAP_PSEUDO_AXIS_ID),
)


def _id_queue() -> list[UUID]:
    return [
        *facility_id_prefix(unit_id=_8ID_UNIT_ID, devices=_DEVICES),
        *[uuid4() for _ in range(200)],
    ]


@pytest.mark.integration
async def test_diffractometer_composes_goniometer_end_to_end(db_pool: asyncpg.Pool) -> None:
    """Compose the 8-ID six-circle diffractometer as a Diffractometer Assembly that
    binds a Goniometer for its sample circles, detector-arm RotaryStages, and a
    reciprocal-space PseudoAxis, then materialize a Fixture. Assert the Assembly and
    Fixture event streams, the ZeroOrMore detector-arm binding count, and the
    fixture back-references."""
    role_lookup = InMemoryRoleLookup()
    role_lookup.register(SEED_ROLE_POSITIONER_ID, "Positioner")
    deps = build_postgres_deps(db_pool, now=_NOW, ids=_id_queue(), role_lookup=role_lookup)

    # ----- Facility install (8-ID Unit + Goniometer + detector circles + pseudo) -----
    await install_aps_unit(
        deps,
        profile_store=make_pg_profile_store(db_pool),
        correlation_id=_CORRELATION_ID,
        unit_id=_8ID_UNIT_ID,
        devices=_DEVICES,
        unit_name="8-ID",
    )

    # ----- Diffractometer Assembly (flat: composes a Goniometer + detector arm) -----
    def _slot(
        name: str, fam_id: UUID, cardinality: SlotCardinality = SlotCardinality.EXACTLY_1
    ) -> TemplateSlot:
        return TemplateSlot(
            slot_name=SlotName(name),
            required_family_ids=frozenset({fam_id}),
            cardinality=cardinality,
        )

    assembly_id = await bind_define_assembly(deps)(
        DefineAssembly(
            name="Diffractometer",
            presents_as=frozenset({SEED_ROLE_POSITIONER_ID}),
            required_slots=frozenset(
                {
                    _slot("goniometer", _CAP_GONIOMETER_ID),
                    _slot("detector_arm", _CAP_ROTARY_STAGE_ID, SlotCardinality.ZERO_OR_MORE),
                    _slot("reciprocal_space", _CAP_PSEUDO_AXIS_ID),
                }
            ),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    # ----- Install each bound Asset in a lightweight Mount (register_fixture
    #       install precondition); the helper runs on its own id pool. -----
    bound: list[tuple[str, UUID]] = [
        ("goniometer", _ASSET_GONIOMETER_ID),
        *(("detector_arm", aid) for _, aid in _DETECTOR_CIRCLES),
        ("reciprocal_space", _ASSET_RECIPROCAL_SPACE_ID),
    ]
    for i, (slot_name, asset_id) in enumerate(bound):
        await install_existing_asset_into_fresh_mount(
            db_pool, now=_NOW, asset_id=asset_id, slot_code=f"diffractometer_{slot_name}_{i}"
        )

    # ----- Register the Fixture (binds the four Assets across three slots) -----
    fixture_id = await bind_register_fixture(deps)(
        RegisterFixture(
            assembly_id=assembly_id,
            slot_asset_bindings=frozenset(
                SlotAssetBinding(slot_name=slot_name, asset_id=asset_id)
                for slot_name, asset_id in bound
            ),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    # ----- Attach each bound Asset (sets its fixture_id back-reference) -----
    for _, asset_id in bound:
        await bind_attach_asset_to_fixture(deps)(
            AttachAssetToFixture(asset_id=asset_id, fixture_id=fixture_id),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )

    # ===== Assertions =====

    # Assembly stream: AssemblyDefined, three leaf slots, presents Positioner, flat.
    assembly_events, _ = await deps.event_store.load("Assembly", assembly_id)
    assert [e.event_type for e in assembly_events] == ["AssemblyDefined"]
    payload = assembly_events[0].payload
    assert payload["presents_as"] == [str(SEED_ROLE_POSITIONER_ID)]
    assert len(payload["required_slots"]) == 3
    assert payload["required_sub_assemblies"] == []

    # Fixture stream: FixtureRegistered binding four Assets, two under detector_arm.
    fixture_events, _ = await deps.event_store.load("Fixture", fixture_id)
    assert [e.event_type for e in fixture_events] == ["FixtureRegistered"]
    bindings = fixture_events[0].payload["slot_asset_bindings"]
    assert len(bindings) == 4
    assert sum(1 for b in bindings if b["slot_name"] == "detector_arm") == 2
    assert {b["slot_name"] for b in bindings} == {
        "goniometer",
        "detector_arm",
        "reciprocal_space",
    }
    assert fixture_events[0].payload["assembly_id"] == str(assembly_id)

    # Each bound Asset carries the fixture back-reference.
    for slot_name, asset_id in bound:
        events, _ = await deps.event_store.load("Asset", asset_id)
        types = [e.event_type for e in events]
        assert "AssetAttachedToFixture" in types, f"{slot_name}: expected fixture attach"
