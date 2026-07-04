"""Kappa four-circle diffractometer deployment at Diamond i19 (Assembly + Fixture).

cluster: Commissioning
archetype: setup
bc_primary: Equipment
bc_touches: Equipment

Materializes Diamond i19's Newport kappa four-circle diffractometer (phi / omega /
kappa sample circles + the 2THETA detector arm + det_z) as a binding of the catalog
Diffractometer Assembly, end-to-end against Postgres, from the assets i19's
deployment descriptor carries (`deployments/i19/beamline.yaml`, DIFF-1).

This is a fifth independent binding of the one blueprint (after 4-ID + 8-ID +
Bernina + Cristallina), a hard X-ray kappa-geometry small-molecule instrument:
proof the composition contract spans the kappa family too.

  - Diffractometer   (Family Goniometer)  -> Exactly1 goniometer slot
                     (phi / omega / kappa circles; kappa is a setting)
  - ReciprocalSpace  (Family PseudoAxis)  -> Exactly1 reciprocal_space slot

The 2THETA detector arm is folded into the goniometer's circle set in the
descriptor rather than modelled as a separate RotaryStage Asset, so the ZeroOrMore
detector_arm slot binds at count 0 (as at Bernina GPS). The serial / microfocus
fixed-target arm (a second sample-orientation stage, SERIAL-1) is a distinct
platform and is not bound here. The reciprocal-space solver partition (DIFF-2) is
left unset, matching the earlier fixtures.
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
from cora.equipment.features.define_family import DefineFamily
from cora.equipment.features.define_family import bind as bind_define_family
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
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000001900bb")

# Facility hierarchy (scenario tag 19 = i19).
_I19_UNIT_ID = UUID("01900000-0000-7000-8000-000000190a01")

# Family ids (deterministic uuid5 from the name). RotaryStage is the detector_arm
# slot's family in the catalog blueprint; i19 binds no arm Asset (count 0) but the
# slot's required family stays RotaryStage so the blueprint matches the catalog.
_CAP_GONIOMETER_ID = family_stream_id(FamilyName("Goniometer"))
_CAP_ROTARY_STAGE_ID = family_stream_id(FamilyName("RotaryStage"))
_CAP_PSEUDO_AXIS_ID = family_stream_id(FamilyName("PseudoAxis"))

# The two constituent Assets (scenario-supplied ids), mirroring the named devices
# in deployments/i19/beamline.yaml.
_ASSET_GONIOMETER_ID = UUID("01900000-0000-7000-8000-000000190a11")
_ASSET_RECIPROCAL_SPACE_ID = UUID("01900000-0000-7000-8000-000000190a21")

_DEVICES = (
    DeviceSpec("Diffractometer", _ASSET_GONIOMETER_ID, "Goniometer", _CAP_GONIOMETER_ID),
    DeviceSpec("ReciprocalSpace", _ASSET_RECIPROCAL_SPACE_ID, "PseudoAxis", _CAP_PSEUDO_AXIS_ID),
)

_BINDINGS: tuple[tuple[str, UUID], ...] = (
    ("goniometer", _ASSET_GONIOMETER_ID),
    ("reciprocal_space", _ASSET_RECIPROCAL_SPACE_ID),
)


def _id_queue() -> list[UUID]:
    return [
        *facility_id_prefix(unit_id=_I19_UNIT_ID, devices=_DEVICES),
        *[uuid4() for _ in range(200)],
    ]


@pytest.mark.integration
async def test_diffractometer_blueprint_materializes_at_i19(db_pool: asyncpg.Pool) -> None:
    """Compose i19's Newport kappa four-circle diffractometer as the catalog Diffractometer
    Assembly materialized by one Fixture binding a goniometer and a reciprocal-space
    PseudoAxis (detector_arm at count 0). Assert the Assembly stream, the Fixture
    stream and its binding, and the per-Asset fixture back-references."""
    role_lookup = InMemoryRoleLookup()
    role_lookup.register(SEED_ROLE_POSITIONER_ID, "Positioner")
    deps = build_postgres_deps(db_pool, now=_NOW, ids=_id_queue(), role_lookup=role_lookup)

    await install_aps_unit(
        deps,
        profile_store=make_pg_profile_store(db_pool),
        correlation_id=_CORRELATION_ID,
        unit_id=_I19_UNIT_ID,
        devices=_DEVICES,
        unit_name="i19",
    )

    # The detector_arm slot references the RotaryStage Family, which i19 binds no
    # instance of (count 0). Define the Family so the blueprint can reference it
    # (a Family is a federation-shared device class; defining it does not assert
    # i19 owns a RotaryStage device).
    await bind_define_family(deps)(
        DefineFamily(name="RotaryStage", affordances=frozenset()),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

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

    for i, (slot_name, asset_id) in enumerate(_BINDINGS):
        await install_existing_asset_into_fresh_mount(
            db_pool, now=_NOW, asset_id=asset_id, slot_code=f"i19_{slot_name}_{i}"
        )

    fixture_id = await bind_register_fixture(deps)(
        RegisterFixture(
            assembly_id=assembly_id,
            slot_asset_bindings=frozenset(
                SlotAssetBinding(slot_name=slot_name, asset_id=asset_id)
                for slot_name, asset_id in _BINDINGS
            ),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    for _, asset_id in _BINDINGS:
        await bind_attach_asset_to_fixture(deps)(
            AttachAssetToFixture(asset_id=asset_id, fixture_id=fixture_id),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )

    # ===== Assertions =====

    assembly_events, _ = await deps.event_store.load("Assembly", assembly_id)
    assert [e.event_type for e in assembly_events] == ["AssemblyDefined"]
    payload = assembly_events[0].payload
    assert payload["presents_as"] == [str(SEED_ROLE_POSITIONER_ID)]
    assert len(payload["required_slots"]) == 3
    assert payload["required_sub_assemblies"] == []

    fixture_events, _ = await deps.event_store.load("Fixture", fixture_id)
    assert [e.event_type for e in fixture_events] == ["FixtureRegistered"]
    bindings = fixture_events[0].payload["slot_asset_bindings"]
    assert len(bindings) == 2
    assert sum(1 for b in bindings if b["slot_name"] == "detector_arm") == 0
    assert {b["slot_name"] for b in bindings} == {"goniometer", "reciprocal_space"}
    assert fixture_events[0].payload["assembly_id"] == str(assembly_id)

    for slot_name, asset_id in _BINDINGS:
        events, _ = await deps.event_store.load("Asset", asset_id)
        types = [e.event_type for e in events]
        assert "AssetAttachedToFixture" in types, f"{slot_name}: expected fixture attach"
