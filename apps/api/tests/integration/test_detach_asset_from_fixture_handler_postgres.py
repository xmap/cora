"""End-to-end integration test: detach_asset_from_fixture handler against Postgres.

Verifies single-stream-write to the Asset stream + the Fixture stream
stays untouched + the Asset's fixture_id back-reference clears to
None in the fold of the Asset's events post-detach.
"""

from datetime import UTC, datetime
from uuid import UUID

import asyncpg
import pytest

from cora.equipment.aggregates.assembly import SlotCardinality, SlotName, TemplateSlot
from cora.equipment.aggregates.asset import load_asset
from cora.equipment.aggregates.fixture import SlotAssetBinding
from cora.equipment.features import (
    add_asset_family,
    attach_asset_to_fixture,
    define_assembly,
    define_family,
    detach_asset_from_fixture,
    register_fixture,
)
from cora.equipment.features.add_asset_family import AddAssetFamily
from cora.equipment.features.attach_asset_to_fixture import AttachAssetToFixture
from cora.equipment.features.define_assembly import DefineAssembly
from cora.equipment.features.define_family import DefineFamily
from cora.equipment.features.detach_asset_from_fixture import DetachAssetFromFixture
from cora.equipment.features.register_fixture import RegisterFixture
from tests.integration._equipment_helpers import seed_installed_asset
from tests.integration._helpers import build_postgres_deps

_NOW = datetime(2026, 6, 4, 14, 0, 0, tzinfo=UTC)
_FAMILY_EVENT_ID = UUID("01900000-0000-7000-8000-00000054cc0e")
_ADD_FAMILY_EVENT_ID = UUID("01900000-0000-7000-8000-00000054cc10")
_ASSEMBLY_ID = UUID("01900000-0000-7000-8000-00000054cc03")
_ASSEMBLY_DEFINED_EVENT_ID = UUID("01900000-0000-7000-8000-00000054cc1e")
_FIXTURE_ID = UUID("01900000-0000-7000-8000-00000054cc04")
_FIXTURE_EVENT_ID = UUID("01900000-0000-7000-8000-00000054cc2e")
_ATTACH_EVENT_ID = UUID("01900000-0000-7000-8000-00000054cc3e")
_DETACH_EVENT_ID = UUID("01900000-0000-7000-8000-00000054cc4e")
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000dd")


@pytest.mark.integration
async def test_detach_asset_from_fixture_clears_back_reference_in_postgres(
    db_pool: asyncpg.Pool,
) -> None:
    # Pre-seed: Frame + Mount + Asset, installed (passes register_fixture's install-required guard).
    _, _, asset_id = await seed_installed_asset(
        db_pool, now=_NOW, slot_code="02-BM-detach", asset_name="Cam-1"
    )

    deps = build_postgres_deps(
        db_pool,
        now=_NOW,
        ids=[
            _FAMILY_EVENT_ID,
            _ADD_FAMILY_EVENT_ID,
            _ASSEMBLY_ID,
            _ASSEMBLY_DEFINED_EVENT_ID,
            _FIXTURE_ID,
            _FIXTURE_EVENT_ID,
            _ATTACH_EVENT_ID,
            _DETACH_EVENT_ID,
        ],
    )

    family_id = await define_family.bind(deps)(
        DefineFamily(name="Camera", affordances=frozenset()),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await add_asset_family.bind(deps)(
        AddAssetFamily(asset_id=asset_id, family_id=family_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assembly_id = await define_assembly.bind(deps)(
        DefineAssembly(
            name="MCTOptics",
            presents_as_family_id=family_id,
            required_slots=frozenset(
                {
                    TemplateSlot(
                        slot_name=SlotName("camera"),
                        required_family_ids=frozenset({family_id}),
                        cardinality=SlotCardinality.EXACTLY_1,
                    )
                }
            ),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    fixture_id = await register_fixture.bind(deps)(
        RegisterFixture(
            assembly_id=assembly_id,
            slot_asset_bindings=frozenset(
                {SlotAssetBinding(slot_name="camera", asset_id=asset_id)}
            ),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await attach_asset_to_fixture.bind(deps)(
        AttachAssetToFixture(asset_id=asset_id, fixture_id=fixture_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    await detach_asset_from_fixture.bind(deps)(
        DetachAssetFromFixture(asset_id=asset_id, fixture_id=fixture_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    # Asset stream: Registered + AddFamily + AttachedToFixture + DetachedFromFixture.
    asset_events, asset_version = await deps.event_store.load("Asset", asset_id)
    # Asset stream: Registered + Activated + AddFamily + AttachedToFixture +
    # DetachedFromFixture (Activated comes from seed_installed_asset).
    assert asset_version == 5
    detach_event = asset_events[4]
    assert detach_event.event_type == "AssetDetachedFromFixture"
    assert detach_event.event_id == _DETACH_EVENT_ID
    assert detach_event.payload == {
        "asset_id": str(asset_id),
        "fixture_id": str(fixture_id),
        "occurred_at": _NOW.isoformat(),
    }
    assert detach_event.correlation_id == _CORRELATION_ID
    assert detach_event.metadata == {"command": "DetachAssetFromFixture"}

    # Folded Asset state: fixture_id is back to None.
    asset = await load_asset(deps.event_store, asset_id)
    assert asset is not None
    assert asset.fixture_id is None

    # Fixture stream stays at version 1 (untouched by detach).
    _, fixture_version = await deps.event_store.load("Fixture", fixture_id)
    assert fixture_version == 1
