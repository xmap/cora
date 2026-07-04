"""Soft X-ray diffractometer deployment at ESRF ID32 (Assembly + Fixture).

cluster: Commissioning
archetype: setup
bc_primary: Equipment
bc_touches: Equipment

Materializes ESRF ID32's four-circle sample diffractometer (BLISS DiffE4CH, E4CH
geometry) as a binding of the catalog Diffractometer Assembly, end-to-end against
Postgres, from the assets ID32's deployment descriptor carries
(`deployments/id32/beamline.yaml`, DIFF-1).

This extends the blueprint beyond the hard X-ray six-circle it was earned on
(4-ID + 8-ID) and the SwissFEL platforms (Bernina + Cristallina) to an ESRF soft
X-ray RIXS instrument: proof the one composition contract spans a different
diffractometer family.

  - Diffractometer   (Family Goniometer)  -> Exactly1 goniometer slot (E4CH circles)
  - ReciprocalSpace  (Family PseudoAxis)  -> Exactly1 reciprocal_space slot (hkl)

The detector arm is not modelled as a separate RotaryStage Asset in the descriptor
(the RIXS spectrometer arm is a distinct device), so the ZeroOrMore detector_arm
slot binds at count 0 (as at Bernina GPS). The reciprocal-space solver partition
(DIFF-2) is left unset, matching the earlier fixtures.
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
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000003200bb")

# Facility hierarchy (scenario tag 32 = ID32).
_ID32_UNIT_ID = UUID("01900000-0000-7000-8000-000000320a01")

# Family ids (deterministic uuid5 from the name). RotaryStage is the detector_arm
# slot's family in the catalog blueprint; id32 binds no arm Asset (count 0) but the
# slot's required family stays RotaryStage so the blueprint matches the catalog.
_CAP_GONIOMETER_ID = family_stream_id(FamilyName("Goniometer"))
_CAP_ROTARY_STAGE_ID = family_stream_id(FamilyName("RotaryStage"))
_CAP_PSEUDO_AXIS_ID = family_stream_id(FamilyName("PseudoAxis"))

# The two constituent Assets (scenario-supplied ids), mirroring the named devices
# in deployments/id32/beamline.yaml.
_ASSET_GONIOMETER_ID = UUID("01900000-0000-7000-8000-000000320a11")
_ASSET_RECIPROCAL_SPACE_ID = UUID("01900000-0000-7000-8000-000000320a21")

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
        *facility_id_prefix(unit_id=_ID32_UNIT_ID, devices=_DEVICES),
        *[uuid4() for _ in range(200)],
    ]


@pytest.mark.integration
async def test_diffractometer_blueprint_materializes_at_id32(db_pool: asyncpg.Pool) -> None:
    """Compose ID32's E4CH four-circle diffractometer as the catalog Diffractometer
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
        unit_id=_ID32_UNIT_ID,
        devices=_DEVICES,
        unit_name="id32",
    )

    # The detector_arm slot references the RotaryStage Family, which id32 binds no
    # instance of (count 0). Define the Family so the blueprint can reference it
    # (a Family is a federation-shared device class; defining it does not assert
    # id32 owns a RotaryStage device).
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
            db_pool, now=_NOW, asset_id=asset_id, slot_code=f"id32_{slot_name}_{i}"
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
