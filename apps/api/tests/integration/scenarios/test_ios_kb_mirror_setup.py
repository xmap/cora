"""KB focusing-pair deployment at NSLS-II IOS (Assembly + Fixture).

cluster: Commissioning
archetype: setup
bc_primary: Equipment
bc_touches: Equipment

Materializes IOS's Kirkpatrick-Baez focusing mirror pair as a binding of the
catalog KirkpatrickBaez Assembly, end-to-end against Postgres, from the assets
IOS's deployment descriptor carries (`deployments/ios/beamline.yaml`, OPT-1).

Unlike CDI (which collapses its KB pair into one Asset that the Fixture splits),
IOS's descriptor already models the two mirrors as distinct Mirror Assets, so the
Fixture binds them directly:

  - KBMirror_Vertical   (Family Mirror) -> Exactly1 vertical_mirror slot
  - KBMirror_Horizontal (Family Mirror) -> Exactly1 horizontal_mirror slot

The Assembly presents no Role (presents_as: []): a KB pair focuses the beam and
none of the catalog Roles names that function, so no role_lookup registration is
needed. Focal spot and working distance are pending (OPT-1).
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
from cora.equipment.features.attach_asset_to_fixture import AttachAssetToFixture
from cora.equipment.features.attach_asset_to_fixture import bind as bind_attach_asset_to_fixture
from cora.equipment.features.define_assembly import DefineAssembly
from cora.equipment.features.define_assembly import bind as bind_define_assembly
from cora.equipment.features.register_fixture import RegisterFixture
from cora.equipment.features.register_fixture import bind as bind_register_fixture
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
_CORRELATION_ID = UUID("01900000-0000-7000-8000-000000e500bb")

# Facility hierarchy (scenario tag e5 = ios).
_IOS_UNIT_ID = UUID("01900000-0000-7000-8000-000000e50a01")

# Family id (deterministic uuid5 from the name).
_CAP_MIRROR_ID = family_stream_id(FamilyName("Mirror"))

# The two KB mirror Assets (scenario-supplied ids), mirroring the distinct named
# devices in deployments/ios/beamline.yaml.
_ASSET_VKB_ID = UUID("01900000-0000-7000-8000-000000e50a11")
_ASSET_HKB_ID = UUID("01900000-0000-7000-8000-000000e50a21")

_DEVICES = (
    DeviceSpec("KBMirror_Vertical", _ASSET_VKB_ID, "Mirror", _CAP_MIRROR_ID),
    DeviceSpec("KBMirror_Horizontal", _ASSET_HKB_ID, "Mirror", _CAP_MIRROR_ID),
)

_BINDINGS: tuple[tuple[str, UUID], ...] = (
    ("vertical_mirror", _ASSET_VKB_ID),
    ("horizontal_mirror", _ASSET_HKB_ID),
)


def _id_queue() -> list[UUID]:
    return [
        *facility_id_prefix(unit_id=_IOS_UNIT_ID, devices=_DEVICES),
        *[uuid4() for _ in range(200)],
    ]


@pytest.mark.integration
async def test_kb_pair_materializes_vertical_and_horizontal_mirrors(db_pool: asyncpg.Pool) -> None:
    """Compose IOS's KB focusing pair as the catalog KirkpatrickBaez Assembly
    materialized by one Fixture binding the descriptor's two distinct Mirror Assets
    (vertical + horizontal) to the two Exactly1 mirror slots. Assert the Assembly
    stream (no Role, flat), the Fixture stream with its two-slot binding, and the
    per-Asset fixture back-references."""
    deps = build_postgres_deps(db_pool, now=_NOW, ids=_id_queue())

    await install_aps_unit(
        deps,
        profile_store=make_pg_profile_store(db_pool),
        correlation_id=_CORRELATION_ID,
        unit_id=_IOS_UNIT_ID,
        devices=_DEVICES,
        unit_name="IOS",
    )

    def _slot(name: str) -> TemplateSlot:
        return TemplateSlot(
            slot_name=SlotName(name),
            required_family_ids=frozenset({_CAP_MIRROR_ID}),
            cardinality=SlotCardinality.EXACTLY_1,
        )

    assembly_id = await bind_define_assembly(deps)(
        DefineAssembly(
            name="KirkpatrickBaez",
            presents_as=frozenset(),
            required_slots=frozenset({_slot("vertical_mirror"), _slot("horizontal_mirror")}),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    for i, (slot_name, asset_id) in enumerate(_BINDINGS):
        await install_existing_asset_into_fresh_mount(
            db_pool, now=_NOW, asset_id=asset_id, slot_code=f"kb_{slot_name}_{i}"
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
    assert payload["presents_as"] == []
    assert len(payload["required_slots"]) == 2
    assert payload["required_sub_assemblies"] == []

    fixture_events, _ = await deps.event_store.load("Fixture", fixture_id)
    assert [e.event_type for e in fixture_events] == ["FixtureRegistered"]
    bindings = fixture_events[0].payload["slot_asset_bindings"]
    assert len(bindings) == 2
    assert {b["slot_name"] for b in bindings} == {"vertical_mirror", "horizontal_mirror"}
    assert fixture_events[0].payload["assembly_id"] == str(assembly_id)

    for slot_name, asset_id in _BINDINGS:
        events, _ = await deps.event_store.load("Asset", asset_id)
        types = [e.event_type for e in events]
        assert "AssetAttachedToFixture" in types, f"{slot_name}: expected fixture attach"
