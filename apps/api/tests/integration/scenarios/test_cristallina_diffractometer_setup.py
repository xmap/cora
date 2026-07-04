"""Diffractometer deployment at SwissFEL Cristallina (Assembly, one Fixture, DM1).

cluster: Commissioning
archetype: setup
bc_primary: Equipment
bc_touches: Equipment

Materializes Cristallina's DM1 diffractometer as a THIRD independent binding of
the Assembly(Diffractometer) blueprint (after 8-ID and Bernina), end-to-end
against Postgres, from the assets Cristallina's deployment descriptor actually
carries (`deployments/cristallina/beamline.yaml`, DIFF-1).

Cristallina instantiates two diffractometer platforms in slic (DM1 + DM2), but
only DM1 is materializable from the descriptor:

  - DM1 (dilution-fridge, slic Diffractometer): binds
      * DM1_Goniometer      (Family Goniometer)  -> Exactly1 goniometer slot
      * DM1_DetectorArm     (Family RotaryStage) -> ZeroOrMore detector_arm slot
      * DM1_ReciprocalSpace (Family PseudoAxis)  -> Exactly1 reciprocal_space slot
    a full three-slot Fixture (detector_arm at count 1).

  - DM2 (pulsed-magnet) is NOT materialized here. The descriptor carries only a
    DM2_Goniometer; its PV channels are commented out of the active config
    (DISABLED-1) and it has no reciprocal-space Asset. The Assembly's
    reciprocal_space slot is Exactly1 (mandatory), so binding DM2 would require
    inventing an Asset the source does not carry; disciplined partial
    materialization binds only what the descriptor supports.

This is the third facility (APS 8-ID, SwissFEL Bernina, SwissFEL Cristallina) to
bind the one catalog blueprint, past the rule-of-three that graduated it. The
reciprocal-space solver partition (DIFF-2) is left unset, matching 8-ID and
Bernina. The dilution-fridge thermometry, vector magnet (MAG-1), and MX sample
stage (SAMPLE-1) are orthogonal to the diffractometer composition and not bound.
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
_CORRELATION_ID = UUID("01900000-0000-7000-8000-000000ca00bb")

# Facility hierarchy (scenario tag ca = CristAllina).
_CRISTALLINA_UNIT_ID = UUID("01900000-0000-7000-8000-000000ca0a01")

# Family ids (deterministic uuid5 from the name).
_CAP_GONIOMETER_ID = family_stream_id(FamilyName("Goniometer"))
_CAP_ROTARY_STAGE_ID = family_stream_id(FamilyName("RotaryStage"))
_CAP_PSEUDO_AXIS_ID = family_stream_id(FamilyName("PseudoAxis"))

# The three DM1 constituent Assets (scenario-supplied ids), mirroring the named
# devices in deployments/cristallina/beamline.yaml. DM2 is not materialized
# (goniometer-only, DISABLED-1, no reciprocal-space Asset; see module docstring).
_ASSET_DM1_GONIOMETER_ID = UUID("01900000-0000-7000-8000-000000ca0a11")
_ASSET_DM1_DETECTOR_ARM_ID = UUID("01900000-0000-7000-8000-000000ca0a21")
_ASSET_DM1_RECIPROCAL_SPACE_ID = UUID("01900000-0000-7000-8000-000000ca0a31")

_DEVICES = (
    DeviceSpec("DM1_Goniometer", _ASSET_DM1_GONIOMETER_ID, "Goniometer", _CAP_GONIOMETER_ID),
    DeviceSpec("DM1_DetectorArm", _ASSET_DM1_DETECTOR_ARM_ID, "RotaryStage", _CAP_ROTARY_STAGE_ID),
    DeviceSpec(
        "DM1_ReciprocalSpace", _ASSET_DM1_RECIPROCAL_SPACE_ID, "PseudoAxis", _CAP_PSEUDO_AXIS_ID
    ),
)

# DM1 slot bindings (slot_name -> asset_id): a full three-slot Fixture.
_DM1_BINDINGS: tuple[tuple[str, UUID], ...] = (
    ("goniometer", _ASSET_DM1_GONIOMETER_ID),
    ("detector_arm", _ASSET_DM1_DETECTOR_ARM_ID),
    ("reciprocal_space", _ASSET_DM1_RECIPROCAL_SPACE_ID),
)


def _id_queue() -> list[UUID]:
    return [
        *facility_id_prefix(unit_id=_CRISTALLINA_UNIT_ID, devices=_DEVICES),
        *[uuid4() for _ in range(200)],
    ]


@pytest.mark.integration
async def test_diffractometer_blueprint_materializes_dm1(db_pool: asyncpg.Pool) -> None:
    """Compose Cristallina's DM1 diffractometer as the catalog Diffractometer Assembly
    materialized by one Fixture binding a goniometer, a detector-arm RotaryStage, and a
    reciprocal-space PseudoAxis. Assert the Assembly stream, the Fixture stream with its
    three-slot binding (detector_arm at count 1), and the per-Asset fixture
    back-references."""
    role_lookup = InMemoryRoleLookup()
    role_lookup.register(SEED_ROLE_POSITIONER_ID, "Positioner")
    deps = build_postgres_deps(db_pool, now=_NOW, ids=_id_queue(), role_lookup=role_lookup)

    # ----- Facility install (Cristallina Unit + the three DM1 Assets) -----
    await install_aps_unit(
        deps,
        profile_store=make_pg_profile_store(db_pool),
        correlation_id=_CORRELATION_ID,
        unit_id=_CRISTALLINA_UNIT_ID,
        devices=_DEVICES,
        unit_name="Cristallina",
    )

    # ----- Diffractometer Assembly (flat; the catalog blueprint) -----
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
    for i, (slot_name, asset_id) in enumerate(_DM1_BINDINGS):
        await install_existing_asset_into_fresh_mount(
            db_pool, now=_NOW, asset_id=asset_id, slot_code=f"dm1_{slot_name}_{i}"
        )

    # ----- Register the DM1 Fixture (binds three Assets across three slots) -----
    fixture_id = await bind_register_fixture(deps)(
        RegisterFixture(
            assembly_id=assembly_id,
            slot_asset_bindings=frozenset(
                SlotAssetBinding(slot_name=slot_name, asset_id=asset_id)
                for slot_name, asset_id in _DM1_BINDINGS
            ),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    for _, asset_id in _DM1_BINDINGS:
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

    # DM1 Fixture: three bindings, ONE under detector_arm (ZeroOrMore at count 1).
    fixture_events, _ = await deps.event_store.load("Fixture", fixture_id)
    assert [e.event_type for e in fixture_events] == ["FixtureRegistered"]
    bindings = fixture_events[0].payload["slot_asset_bindings"]
    assert len(bindings) == 3
    assert sum(1 for b in bindings if b["slot_name"] == "detector_arm") == 1
    assert {b["slot_name"] for b in bindings} == {
        "goniometer",
        "detector_arm",
        "reciprocal_space",
    }
    assert fixture_events[0].payload["assembly_id"] == str(assembly_id)

    # Each bound Asset carries the fixture back-reference.
    for slot_name, asset_id in _DM1_BINDINGS:
        events, _ = await deps.event_store.load("Asset", asset_id)
        types = [e.event_type for e in events]
        assert "AssetAttachedToFixture" in types, f"{slot_name}: expected fixture attach"
