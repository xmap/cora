"""KB focusing-pair deployment at NSLS-II CDI/CHX (Assembly + Fixture).

cluster: Commissioning
archetype: setup
bc_primary: Equipment
bc_touches: Equipment

Materializes CDI's Kirkpatrick-Baez nanofocusing mirror pair as the FIRST binding
of the catalog KirkpatrickBaez Assembly (which shipped with zero Fixtures),
end-to-end against Postgres, from the assets CDI's deployment descriptor carries
(`deployments/cdi/beamline.yaml`, KB-1).

CDI's descriptor collapses the pair into ONE `KBMirror` Mirror Asset, but its note
names both physical mirrors with their real PVs: a vertical VKB at `Mir:KBv` and a
horizontal HKB at `Mir:KBh`. The KirkpatrickBaez Assembly declares two Exactly1
Mirror slots (vertical_mirror + horizontal_mirror), and the catalog note sanctions
exactly this move: "deployments that today carry the pair as one collapsed Mirror
Asset split it into the two mirrors that physically exist when they materialize the
Fixture." So this scenario binds:

  - VKB (Mir:KBv, Family Mirror) -> Exactly1 vertical_mirror slot
  - HKB (Mir:KBh, Family Mirror) -> Exactly1 horizontal_mirror slot

The Assembly presents no Role (presents_as: []): a KB pair focuses the beam and
none of the catalog Roles names that function, so no role_lookup registration is
needed (unlike the Positioner-presenting Diffractometer fixtures). The exit window
(Wnd:Exit), defining slits, and fluorescent screens on the KB module are orthogonal
to the focusing composition and are not bound; focal size and coating are pending
(KB-1).
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
_CORRELATION_ID = UUID("01900000-0000-7000-8000-000000cd00bb")

# Facility hierarchy (scenario tag cd = CDi).
_CDI_UNIT_ID = UUID("01900000-0000-7000-8000-000000cd0a01")

# Family id (deterministic uuid5 from the name).
_CAP_MIRROR_ID = family_stream_id(FamilyName("Mirror"))

# The two KB mirror Assets (scenario-supplied ids), split from the collapsed
# `KBMirror` device in deployments/cdi/beamline.yaml per its note (Mir:KBv +
# Mir:KBh) and the catalog KirkpatrickBaez split-on-materialize sanction.
_ASSET_VKB_ID = UUID("01900000-0000-7000-8000-000000cd0a11")
_ASSET_HKB_ID = UUID("01900000-0000-7000-8000-000000cd0a21")

_DEVICES = (
    DeviceSpec("VKB", _ASSET_VKB_ID, "Mirror", _CAP_MIRROR_ID),
    DeviceSpec("HKB", _ASSET_HKB_ID, "Mirror", _CAP_MIRROR_ID),
)

# Slot bindings (slot_name -> asset_id): the two Exactly1 mirror slots.
_BINDINGS: tuple[tuple[str, UUID], ...] = (
    ("vertical_mirror", _ASSET_VKB_ID),
    ("horizontal_mirror", _ASSET_HKB_ID),
)


def _id_queue() -> list[UUID]:
    return [
        *facility_id_prefix(unit_id=_CDI_UNIT_ID, devices=_DEVICES),
        *[uuid4() for _ in range(200)],
    ]


@pytest.mark.integration
async def test_kb_pair_materializes_vertical_and_horizontal_mirrors(db_pool: asyncpg.Pool) -> None:
    """Compose CDI's KB nanofocusing pair as the catalog KirkpatrickBaez Assembly
    materialized by one Fixture binding a vertical (VKB) and a horizontal (HKB) Mirror
    Asset to the two Exactly1 mirror slots. Assert the Assembly stream (no Role, flat),
    the Fixture stream with its two-slot binding, and the per-Asset fixture
    back-references."""
    deps = build_postgres_deps(db_pool, now=_NOW, ids=_id_queue())

    # ----- Facility install (CDI Unit + the two KB mirror Assets) -----
    await install_aps_unit(
        deps,
        profile_store=make_pg_profile_store(db_pool),
        correlation_id=_CORRELATION_ID,
        unit_id=_CDI_UNIT_ID,
        devices=_DEVICES,
        unit_name="CDI",
    )

    # ----- KirkpatrickBaez Assembly (flat, presents no Role) -----
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

    # ----- Install each bound Asset in a lightweight Mount (register_fixture
    #       install precondition); the helper runs on its own id pool. -----
    for i, (slot_name, asset_id) in enumerate(_BINDINGS):
        await install_existing_asset_into_fresh_mount(
            db_pool, now=_NOW, asset_id=asset_id, slot_code=f"kb_{slot_name}_{i}"
        )

    # ----- Register the Fixture (binds the two mirrors across the two slots) -----
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

    # Assembly stream: AssemblyDefined, two leaf slots, presents no Role, flat.
    assembly_events, _ = await deps.event_store.load("Assembly", assembly_id)
    assert [e.event_type for e in assembly_events] == ["AssemblyDefined"]
    payload = assembly_events[0].payload
    assert payload["presents_as"] == []
    assert len(payload["required_slots"]) == 2
    assert payload["required_sub_assemblies"] == []

    # Fixture stream: FixtureRegistered binding the two mirrors to the two slots.
    fixture_events, _ = await deps.event_store.load("Fixture", fixture_id)
    assert [e.event_type for e in fixture_events] == ["FixtureRegistered"]
    bindings = fixture_events[0].payload["slot_asset_bindings"]
    assert len(bindings) == 2
    assert {b["slot_name"] for b in bindings} == {"vertical_mirror", "horizontal_mirror"}
    assert fixture_events[0].payload["assembly_id"] == str(assembly_id)

    # Each bound Asset carries the fixture back-reference.
    for slot_name, asset_id in _BINDINGS:
        events, _ = await deps.event_store.load("Asset", asset_id)
        types = [e.event_type for e in events]
        assert "AssetAttachedToFixture" in types, f"{slot_name}: expected fixture attach"
