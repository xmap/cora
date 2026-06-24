"""Six-circle diffractometer deployment at APS 8-ID (Assembly + Fixture).

cluster: Commissioning
archetype: setup
bc_primary: Equipment
bc_touches: Equipment

Materializes the 8-ID-E six-circle Huber diffractometer as a Diffractometer
Assembly and one Fixture, end-to-end against Postgres. This is the first spine
exercise of the reverse-engineered APS deployments (4-ID POLAR and 8-ID): it
proves the Assembly(Diffractometer) blueprint the catalog-graduation pass
designed.

  - six rotation-circle Assets (mu, eta, chi, phi, nu, delta), each Family
    RotaryStage, that bind one OneOrMore `sample_circles` slot,
  - one sample-translation Asset (SampleTable, Family LinearStage) on the
    Exactly1 `sample_table` slot,
  - one reciprocal-space Asset (ReciprocalSpace, Family PseudoAxis) on the
    Exactly1 `reciprocal_space` slot; its hklpy2 solver partition rule is
    DIFF-2, left unset here,
  - a flat Diffractometer Assembly (no sub-assembly, unlike Microscope)
    presenting the Positioner Role via presents_as,
  - one Fixture binding the eight Assets across the three slots.

The OneOrMore `sample_circles` slot is what lets one blueprint span 8-ID's
six circles and 4-ID's four-circle Eulerian / high-pressure geometries: the
circle count is a per-deployment geometry, not a Family split.
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
_CAP_ROTARY_STAGE_ID = family_stream_id(FamilyName("RotaryStage"))
_CAP_LINEAR_STAGE_ID = family_stream_id(FamilyName("LinearStage"))
_CAP_PSEUDO_AXIS_ID = family_stream_id(FamilyName("PseudoAxis"))

# The eight diffractometer constituent Assets (scenario-supplied ids).
_ASSET_MU_ID = UUID("01900000-0000-7000-8000-0000008d0a11")
_ASSET_ETA_ID = UUID("01900000-0000-7000-8000-0000008d0a21")
_ASSET_CHI_ID = UUID("01900000-0000-7000-8000-0000008d0a31")
_ASSET_PHI_ID = UUID("01900000-0000-7000-8000-0000008d0a41")
_ASSET_NU_ID = UUID("01900000-0000-7000-8000-0000008d0a51")
_ASSET_DELTA_ID = UUID("01900000-0000-7000-8000-0000008d0a61")
_ASSET_SAMPLE_TABLE_ID = UUID("01900000-0000-7000-8000-0000008d0a71")
_ASSET_RECIPROCAL_SPACE_ID = UUID("01900000-0000-7000-8000-0000008d0a81")

# The six circles share one OneOrMore slot; the table and pseudo-axis are Exactly1.
_CIRCLES: tuple[tuple[str, UUID], ...] = (
    ("Mu", _ASSET_MU_ID),
    ("Eta", _ASSET_ETA_ID),
    ("Chi", _ASSET_CHI_ID),
    ("Phi", _ASSET_PHI_ID),
    ("Nu", _ASSET_NU_ID),
    ("Delta", _ASSET_DELTA_ID),
)

_DEVICES = (
    *(DeviceSpec(name, aid, "RotaryStage", _CAP_ROTARY_STAGE_ID) for name, aid in _CIRCLES),
    DeviceSpec("SampleTable", _ASSET_SAMPLE_TABLE_ID, "LinearStage", _CAP_LINEAR_STAGE_ID),
    DeviceSpec("ReciprocalSpace", _ASSET_RECIPROCAL_SPACE_ID, "PseudoAxis", _CAP_PSEUDO_AXIS_ID),
)


def _id_queue() -> list[UUID]:
    return [
        *facility_id_prefix(unit_id=_8ID_UNIT_ID, devices=_DEVICES),
        *[uuid4() for _ in range(200)],
    ]


@pytest.mark.integration
async def test_diffractometer_deployment_plays_out_end_to_end(db_pool: asyncpg.Pool) -> None:
    """Compose the 8-ID six-circle diffractometer as a Diffractometer Assembly +
    Fixture end-to-end: facility install of the eight constituent Assets, the flat
    Assembly (sample_circles OneOrMore + sample_table + reciprocal_space, presenting
    Positioner), per-constituent Mount install, the Fixture binding the eight Assets,
    and the eight attaches. Assert the Assembly and Fixture event streams, the
    OneOrMore circle binding count, and the fixture back-references."""
    role_lookup = InMemoryRoleLookup()
    role_lookup.register(SEED_ROLE_POSITIONER_ID, "Positioner")
    deps = build_postgres_deps(db_pool, now=_NOW, ids=_id_queue(), role_lookup=role_lookup)

    # ----- Facility install (8-ID Unit + the eight diffractometer Assets) -----
    await install_aps_unit(
        deps,
        profile_store=make_pg_profile_store(db_pool),
        correlation_id=_CORRELATION_ID,
        unit_id=_8ID_UNIT_ID,
        devices=_DEVICES,
        unit_name="8-ID",
    )

    # ----- Diffractometer Assembly (flat: three leaf slots, presents Positioner) -----
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
                    _slot("sample_circles", _CAP_ROTARY_STAGE_ID, SlotCardinality.ONE_OR_MORE),
                    _slot("sample_table", _CAP_LINEAR_STAGE_ID),
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
        *(("sample_circles", aid) for _, aid in _CIRCLES),
        ("sample_table", _ASSET_SAMPLE_TABLE_ID),
        ("reciprocal_space", _ASSET_RECIPROCAL_SPACE_ID),
    ]
    for i, (slot_name, asset_id) in enumerate(bound):
        await install_existing_asset_into_fresh_mount(
            db_pool, now=_NOW, asset_id=asset_id, slot_code=f"diffractometer_{slot_name}_{i}"
        )

    # ----- Register the Fixture (binds the eight Assets across three slots) -----
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

    # Fixture stream: FixtureRegistered binding eight Assets, six under sample_circles.
    fixture_events, _ = await deps.event_store.load("Fixture", fixture_id)
    assert [e.event_type for e in fixture_events] == ["FixtureRegistered"]
    bindings = fixture_events[0].payload["slot_asset_bindings"]
    assert len(bindings) == 8
    assert sum(1 for b in bindings if b["slot_name"] == "sample_circles") == 6
    assert {b["slot_name"] for b in bindings} == {
        "sample_circles",
        "sample_table",
        "reciprocal_space",
    }
    assert fixture_events[0].payload["assembly_id"] == str(assembly_id)

    # Each bound Asset carries the fixture back-reference.
    for slot_name, asset_id in bound:
        events, _ = await deps.event_store.load("Asset", asset_id)
        types = [e.event_type for e in events]
        assert "AssetAttachedToFixture" in types, f"{slot_name}: expected fixture attach"
