"""Twin-platform diffractometer deployment at SwissFEL Bernina (Assembly, two Fixtures).

cluster: Commissioning
archetype: setup
bc_primary: Equipment
bc_touches: Equipment

Materializes Bernina's two diffractometer platforms as the SECOND independent
binding of the Assembly(Diffractometer) blueprint (after 8-ID, #340 lineage),
end-to-end against Postgres. The blueprint was earned across 4-ID + 8-ID and
graduated to the catalog; this scenario proves it composes at a non-APS facility
from the assets Bernina's deployment descriptor actually carries
(`deployments/bernina/beamline.yaml`, DIFF-1), rather than re-modelling the
sample circles per platform.

Bernina runs two independent diffractometer platforms (eco gps + eco xrd), so
ONE Assembly blueprint materializes into TWO Fixtures, one per platform:

  - GPS (six-circle, SixCircleBernina recspace): binds
      * GPS_Goniometer     (Family Goniometer)  -> Exactly1 goniometer slot
      * GPS_ReciprocalSpace (Family PseudoAxis) -> Exactly1 reciprocal_space slot
    and NO detector-arm asset, exercising the ZeroOrMore detector_arm slot at
    count 0 (the GPS platform's detector geometry is not a modelled circle here).

  - XRD (You-geometry, XRDYou / diffcalc): binds
      * XRD_Goniometer     (Family Goniometer)  -> Exactly1 goniometer slot
      * XRD_DetectorArm    (Family RotaryStage) -> ZeroOrMore detector_arm slot
      * XRD_ReciprocalSpace (Family PseudoAxis) -> Exactly1 reciprocal_space slot
    exercising the same slot at count 1.

The two Fixtures over one Assembly are the load-bearing assertion: the blueprint
is reusable across platforms that differ only in whether a detector-arm circle is
mounted (CONFIG-1: WHICH sub-assemblies are mounted is read from the non-public
bernina_config JSON and carried unknown), NOT in the composition contract. The
reciprocal-space solver partition (DIFF-2) is left unset, matching 8-ID.

The USDTable hexapod, the Staeubli TX200 robot (ROBOT-1), and the fs pump-probe
laser (LASER-1) are out of scope for this composition structure and are not bound.
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
_CORRELATION_ID = UUID("01900000-0000-7000-8000-000000be00bb")

# Facility hierarchy (scenario tag be = BErnina).
_BERNINA_UNIT_ID = UUID("01900000-0000-7000-8000-000000be0a01")

# Family ids (deterministic uuid5 from the name).
_CAP_GONIOMETER_ID = family_stream_id(FamilyName("Goniometer"))
_CAP_ROTARY_STAGE_ID = family_stream_id(FamilyName("RotaryStage"))
_CAP_PSEUDO_AXIS_ID = family_stream_id(FamilyName("PseudoAxis"))

# The five diffractometer constituent Assets (scenario-supplied ids), mirroring
# the named devices in deployments/bernina/beamline.yaml. GPS carries a goniometer
# + reciprocal-space (no modelled detector arm); XRD carries all three.
_ASSET_GPS_GONIOMETER_ID = UUID("01900000-0000-7000-8000-000000be0a11")
_ASSET_GPS_RECIPROCAL_SPACE_ID = UUID("01900000-0000-7000-8000-000000be0a21")
_ASSET_XRD_GONIOMETER_ID = UUID("01900000-0000-7000-8000-000000be0a31")
_ASSET_XRD_DETECTOR_ARM_ID = UUID("01900000-0000-7000-8000-000000be0a41")
_ASSET_XRD_RECIPROCAL_SPACE_ID = UUID("01900000-0000-7000-8000-000000be0a51")

_DEVICES = (
    DeviceSpec("GPS_Goniometer", _ASSET_GPS_GONIOMETER_ID, "Goniometer", _CAP_GONIOMETER_ID),
    DeviceSpec(
        "GPS_ReciprocalSpace", _ASSET_GPS_RECIPROCAL_SPACE_ID, "PseudoAxis", _CAP_PSEUDO_AXIS_ID
    ),
    DeviceSpec("XRD_Goniometer", _ASSET_XRD_GONIOMETER_ID, "Goniometer", _CAP_GONIOMETER_ID),
    DeviceSpec("XRD_DetectorArm", _ASSET_XRD_DETECTOR_ARM_ID, "RotaryStage", _CAP_ROTARY_STAGE_ID),
    DeviceSpec(
        "XRD_ReciprocalSpace", _ASSET_XRD_RECIPROCAL_SPACE_ID, "PseudoAxis", _CAP_PSEUDO_AXIS_ID
    ),
)

# Per-platform slot bindings (slot_name -> asset_id), the two Fixtures this one
# Assembly materializes. GPS omits detector_arm (ZeroOrMore at count 0).
_GPS_BINDINGS: tuple[tuple[str, UUID], ...] = (
    ("goniometer", _ASSET_GPS_GONIOMETER_ID),
    ("reciprocal_space", _ASSET_GPS_RECIPROCAL_SPACE_ID),
)
_XRD_BINDINGS: tuple[tuple[str, UUID], ...] = (
    ("goniometer", _ASSET_XRD_GONIOMETER_ID),
    ("detector_arm", _ASSET_XRD_DETECTOR_ARM_ID),
    ("reciprocal_space", _ASSET_XRD_RECIPROCAL_SPACE_ID),
)


def _id_queue() -> list[UUID]:
    return [
        *facility_id_prefix(unit_id=_BERNINA_UNIT_ID, devices=_DEVICES),
        *[uuid4() for _ in range(200)],
    ]


@pytest.mark.integration
async def test_diffractometer_blueprint_materializes_two_platforms(db_pool: asyncpg.Pool) -> None:
    """Compose Bernina's GPS and XRD diffractometer platforms as ONE Diffractometer
    Assembly materialized by TWO Fixtures: GPS binds a goniometer + reciprocal-space
    with no detector arm (ZeroOrMore at count 0), XRD binds a goniometer + a
    detector-arm RotaryStage + reciprocal-space (count 1). Assert the single Assembly
    stream, both Fixture streams with their per-platform binding counts, and the
    per-Asset fixture back-references."""
    role_lookup = InMemoryRoleLookup()
    role_lookup.register(SEED_ROLE_POSITIONER_ID, "Positioner")
    deps = build_postgres_deps(db_pool, now=_NOW, ids=_id_queue(), role_lookup=role_lookup)

    # ----- Facility install (Bernina Unit + the five platform Assets) -----
    await install_aps_unit(
        deps,
        profile_store=make_pg_profile_store(db_pool),
        correlation_id=_CORRELATION_ID,
        unit_id=_BERNINA_UNIT_ID,
        devices=_DEVICES,
        unit_name="Bernina",
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
    all_bindings: tuple[tuple[str, tuple[tuple[str, UUID], ...]], ...] = (
        ("gps", _GPS_BINDINGS),
        ("xrd", _XRD_BINDINGS),
    )
    for platform, bindings in all_bindings:
        for i, (slot_name, asset_id) in enumerate(bindings):
            await install_existing_asset_into_fresh_mount(
                db_pool, now=_NOW, asset_id=asset_id, slot_code=f"{platform}_{slot_name}_{i}"
            )

    # ----- Register the two Fixtures (one Assembly, two platforms) -----
    fixture_ids: dict[str, UUID] = {}
    for platform, bindings in all_bindings:
        fixture_ids[platform] = await bind_register_fixture(deps)(
            RegisterFixture(
                assembly_id=assembly_id,
                slot_asset_bindings=frozenset(
                    SlotAssetBinding(slot_name=slot_name, asset_id=asset_id)
                    for slot_name, asset_id in bindings
                ),
            ),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
        for _, asset_id in bindings:
            await bind_attach_asset_to_fixture(deps)(
                AttachAssetToFixture(asset_id=asset_id, fixture_id=fixture_ids[platform]),
                principal_id=_PRINCIPAL_ID,
                correlation_id=_CORRELATION_ID,
            )

    # ===== Assertions =====

    # ONE Assembly stream: AssemblyDefined, three leaf slots, presents Positioner, flat.
    assembly_events, _ = await deps.event_store.load("Assembly", assembly_id)
    assert [e.event_type for e in assembly_events] == ["AssemblyDefined"]
    payload = assembly_events[0].payload
    assert payload["presents_as"] == [str(SEED_ROLE_POSITIONER_ID)]
    assert len(payload["required_slots"]) == 3
    assert payload["required_sub_assemblies"] == []

    # GPS Fixture: two bindings, ZERO under detector_arm (ZeroOrMore at count 0).
    gps_events, _ = await deps.event_store.load("Fixture", fixture_ids["gps"])
    assert [e.event_type for e in gps_events] == ["FixtureRegistered"]
    gps_bindings = gps_events[0].payload["slot_asset_bindings"]
    assert len(gps_bindings) == 2
    assert sum(1 for b in gps_bindings if b["slot_name"] == "detector_arm") == 0
    assert {b["slot_name"] for b in gps_bindings} == {"goniometer", "reciprocal_space"}
    assert gps_events[0].payload["assembly_id"] == str(assembly_id)

    # XRD Fixture: three bindings, ONE under detector_arm (ZeroOrMore at count 1).
    xrd_events, _ = await deps.event_store.load("Fixture", fixture_ids["xrd"])
    assert [e.event_type for e in xrd_events] == ["FixtureRegistered"]
    xrd_bindings = xrd_events[0].payload["slot_asset_bindings"]
    assert len(xrd_bindings) == 3
    assert sum(1 for b in xrd_bindings if b["slot_name"] == "detector_arm") == 1
    assert {b["slot_name"] for b in xrd_bindings} == {
        "goniometer",
        "detector_arm",
        "reciprocal_space",
    }
    assert xrd_events[0].payload["assembly_id"] == str(assembly_id)

    # Both Fixtures reference the SAME Assembly (one blueprint, two platforms).
    assert fixture_ids["gps"] != fixture_ids["xrd"]

    # Each bound Asset across both platforms carries the fixture back-reference.
    for _, bindings in all_bindings:
        for slot_name, asset_id in bindings:
            events, _ = await deps.event_store.load("Asset", asset_id)
            types = [e.event_type for e in events]
            assert "AssetAttachedToFixture" in types, f"{slot_name}: expected fixture attach"
