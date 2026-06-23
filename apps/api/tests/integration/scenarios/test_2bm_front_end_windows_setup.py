"""Front-end Be-window materialization at APS 2-BM (passive beam-path tier).

cluster: Commissioning
archetype: setup
bc_primary: Equipment
bc_touches: Equipment

Materializes the 2-BM front-end window as the first slice of the passive
beam-path tier, end-to-end against Postgres:

  - the passive `Window` Family (affordances empty, the GenericProbe shape),
  - a `FrontEndWindow` Component Asset under the 2-BM Unit,
  - its three OFHC-housed Be-window Device children (parent_id = the
    FrontEndWindow), each carrying its own engineering drawing.

The windows are modelled IDENTITY ONLY: no settings, no Role, no
Attenuable. The beam-effect (transmission-vs-energy) quantity is deferred;
registering the Assets now is the prerequisite that unblocks it later
(a Calibration keyed to the Window Asset, pinned via Run.pinned_calibration_ids).

## Window facts (BEAM-2, source APS_2191941, staff-verified)

Three Be windows, total 0.63 mm Be: W4-20 (0.25 mm, z 28718), W4-60
(0.13 mm, z 30804), and an unlabelled downstream window (0.25 mm, z 32417).
The drawing numbers are confirmed; revisions are not stated, so the Drawing
revision resolves to latest (None).

## Naming

The two labelled windows carry their vendor designation (W4-20 / W4-60);
the unlabelled downstream-most one is Window_DS. Physical spec (thickness,
aperture, z) lives on the descriptor, not in the Asset names.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from datetime import UTC, datetime
from uuid import UUID, uuid4

import asyncpg
import pytest

from cora.equipment.aggregates._drawing import Drawing, DrawingSystem
from cora.equipment.aggregates.asset import AssetTier
from cora.equipment.aggregates.family import FamilyName, family_stream_id
from cora.equipment.features.add_asset_family import AddAssetFamily
from cora.equipment.features.add_asset_family import bind as bind_add_asset_family
from cora.equipment.features.define_family import DefineFamily
from cora.equipment.features.define_family import bind as bind_define_family
from cora.equipment.features.register_asset import RegisterAsset
from cora.equipment.features.register_asset import bind as bind_register_asset
from tests.integration._helpers import build_postgres_deps, make_pg_profile_store
from tests.integration.scenarios._facility_fixture import (
    facility_id_prefix,
    install_aps_unit,
    operator_for,
)

_NOW = datetime(2026, 5, 28, 12, 0, 0, tzinfo=UTC)
_PRINCIPAL_ID = operator_for(__file__)
_CORRELATION_ID = UUID("01900000-0000-7000-8000-00000004bebb")

# Facility hierarchy (scenario tag 4be)
_2BM_UNIT_ID = UUID("01900000-0000-7000-8000-0000004bea01")

# The single earned passive-window Family (deterministic uuid5 from the name).
_CAP_WINDOW_ID = family_stream_id(FamilyName("Window"))

# The three Be windows: (Asset name, own drawing). z / thickness / aperture stay
# on the descriptor; the registered Asset is identity plus its drawing.
_WINDOWS = (
    ("Window_W4_20", Drawing(system=DrawingSystem.ICMS, number="4105090804-200000")),
    ("Window_W4_60", Drawing(system=DrawingSystem.ICMS, number="4105090804-600000")),
    ("Window_DS", Drawing(system=DrawingSystem.ICMS, number="4102020106-400000")),
)


def _id_queue() -> list[UUID]:
    """FixedIdGenerator queue: the facility prefix (no extra Devices in the
    install) plus a generous anonymous tail. The FrontEndWindow and its three
    children draw their ids from the tail and are captured from the handler
    return values, not hand-ordered."""
    return [
        *facility_id_prefix(unit_id=_2BM_UNIT_ID, devices=()),
        *[uuid4() for _ in range(50)],
    ]


@pytest.mark.integration
async def test_front_end_windows_register_as_window_family_children(
    db_pool: asyncpg.Pool,
) -> None:
    """Install 2-BM, then register the Window Family, the FrontEndWindow
    Component, and its three Be-window Device children. Assert the Family
    stream, the containment chain (children -> FrontEndWindow -> 2-BM Unit),
    the Window family on all four Assets, each child's drawing, and that every
    Asset is identity-only (no settings)."""
    deps = build_postgres_deps(db_pool, now=_NOW, ids=_id_queue())

    # ----- Facility install (APS -> 2-BM; no pre-existing Devices needed) -----
    await install_aps_unit(
        deps,
        profile_store=make_pg_profile_store(db_pool),
        correlation_id=_CORRELATION_ID,
        unit_id=_2BM_UNIT_ID,
        devices=(),
    )

    # ----- The earned passive Window Family (no affordances) -----
    await bind_define_family(deps)(
        DefineFamily(name="Window", affordances=frozenset()),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    # ----- FrontEndWindow Component under the 2-BM Unit -----
    frontend_window_id = await bind_register_asset(deps)(
        RegisterAsset(name="FrontEndWindow", tier=AssetTier.COMPONENT, parent_id=_2BM_UNIT_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await bind_add_asset_family(deps)(
        AddAssetFamily(asset_id=frontend_window_id, family_id=_CAP_WINDOW_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    # ----- Three Be-window Device children (parent_id = FrontEndWindow), each
    #       identity-only with its own drawing -----
    child_ids: list[UUID] = []
    for name, drawing in _WINDOWS:
        child_id = await bind_register_asset(deps)(
            RegisterAsset(
                name=name,
                tier=AssetTier.DEVICE,
                parent_id=frontend_window_id,
                drawing=drawing,
            ),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
        child_ids.append(child_id)
        await bind_add_asset_family(deps)(
            AddAssetFamily(asset_id=child_id, family_id=_CAP_WINDOW_ID),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )

    # ===== Assertions =====

    # The Window Family was defined.
    fam_events, _ = await deps.event_store.load("Family", _CAP_WINDOW_ID)
    assert [e.event_type for e in fam_events] == ["FamilyDefined"]

    # FrontEndWindow: a Component under the Unit, carrying the Window family,
    # identity-only (no settings).
    few_events, _ = await deps.event_store.load("Asset", frontend_window_id)
    few_types = [e.event_type for e in few_events]
    few_genesis = few_events[0]
    assert few_genesis.event_type == "AssetRegistered"
    assert few_genesis.payload["tier"] == "Component"
    assert few_genesis.payload["parent_id"] == str(_2BM_UNIT_ID)
    assert few_genesis.payload.get("drawing") is None
    assert "AssetSettingsUpdated" not in few_types
    few_family_added = [e for e in few_events if e.event_type == "AssetFamilyAdded"]
    assert [e.payload["family_id"] for e in few_family_added] == [str(_CAP_WINDOW_ID)]

    # Three Be-window children: Devices under the FrontEndWindow, each carrying
    # the Window family and its own drawing, identity-only.
    assert len(child_ids) == 3
    for (name, drawing), child_id in zip(_WINDOWS, child_ids, strict=True):
        child_events, _ = await deps.event_store.load("Asset", child_id)
        child_types = [e.event_type for e in child_events]
        genesis = child_events[0]
        assert genesis.event_type == "AssetRegistered"
        assert genesis.payload["name"] == name
        assert genesis.payload["tier"] == "Device"
        assert genesis.payload["parent_id"] == str(frontend_window_id)
        assert genesis.payload["drawing"]["system"] == "ICMS"
        assert genesis.payload["drawing"]["number"] == drawing.number
        assert "AssetSettingsUpdated" not in child_types
        child_family_added = [e for e in child_events if e.event_type == "AssetFamilyAdded"]
        assert [e.payload["family_id"] for e in child_family_added] == [str(_CAP_WINDOW_ID)]
