"""End-to-end integration test: register_fixture handler against Postgres.

A genesis FixtureRegistered event lands on its own Fixture stream
with expected_version=0; the Assembly + Asset streams stay
untouched. The handler concurrently loads the Assembly state and
each referenced Asset state, validates Family-set intersection and
parameter_overrides, then appends.
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import asyncpg
import pytest

from cora.equipment.aggregates.assembly import (
    FixtureAssetNotAttachableError,
    SlotCardinality,
    SlotName,
    TemplateSlot,
)
from cora.equipment.aggregates.asset import AssetLevel, AssetLifecycle
from cora.equipment.aggregates.fixture import SlotAssetBinding
from cora.equipment.features import (
    add_asset_family,
    decommission_asset,
    define_assembly,
    define_family,
    register_asset,
    register_fixture,
)
from cora.equipment.features.add_asset_family import AddAssetFamily
from cora.equipment.features.decommission_asset import DecommissionAsset
from cora.equipment.features.define_assembly import DefineAssembly
from cora.equipment.features.define_family import DefineFamily
from cora.equipment.features.register_asset import RegisterAsset
from cora.equipment.features.register_fixture import RegisterFixture
from tests.integration._helpers import build_postgres_deps

_NOW = datetime(2026, 6, 3, 14, 0, 0, tzinfo=UTC)
_FAMILY_ID = UUID("01900000-0000-7000-8000-00000054ca01")
_FAMILY_EVENT_ID = UUID("01900000-0000-7000-8000-00000054ca0e")
_ASSET_ID = UUID("01900000-0000-7000-8000-00000054ca02")
_ASSET_EVENT_ID = UUID("01900000-0000-7000-8000-00000054ca0f")
_ADD_FAMILY_EVENT_ID = UUID("01900000-0000-7000-8000-00000054ca10")
_ASSEMBLY_ID = UUID("01900000-0000-7000-8000-00000054ca03")
_ASSEMBLY_DEFINED_EVENT_ID = UUID("01900000-0000-7000-8000-00000054ca1e")
_FIXTURE_ID = UUID("01900000-0000-7000-8000-00000054ca04")
_FIXTURE_EVENT_ID = UUID("01900000-0000-7000-8000-00000054ca2e")
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000dd")
_PARENT_ID = UUID("01900000-0000-7000-8000-000000000fff")


@pytest.mark.integration
async def test_register_fixture_appends_genesis_event_to_postgres(
    db_pool: asyncpg.Pool,
) -> None:
    deps = build_postgres_deps(
        db_pool,
        now=_NOW,
        ids=[
            _FAMILY_ID,
            _FAMILY_EVENT_ID,
            _ASSET_ID,
            _ASSET_EVENT_ID,
            _ADD_FAMILY_EVENT_ID,
            _ASSEMBLY_ID,
            _ASSEMBLY_DEFINED_EVENT_ID,
            _FIXTURE_ID,
            _FIXTURE_EVENT_ID,
        ],
    )

    family_id = await define_family.bind(deps)(
        DefineFamily(name="Camera", affordances=frozenset()),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    asset_id = await register_asset.bind(deps)(
        RegisterAsset(name="Camera-1", level=AssetLevel.DEVICE, parent_id=_PARENT_ID),
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

    assert fixture_id == _FIXTURE_ID
    events, version = await deps.event_store.load("Fixture", fixture_id)
    assert version == 1
    assert len(events) == 1
    registered = events[0]
    assert registered.event_type == "FixtureRegistered"
    assert registered.event_id == _FIXTURE_EVENT_ID
    payload = registered.payload
    assert payload["fixture_id"] == str(fixture_id)
    assert payload["assembly_id"] == str(assembly_id)
    assert payload["assembly_content_hash"]
    assert payload["slot_asset_bindings"] == [
        {"slot_name": "camera", "asset_id": str(asset_id)},
    ]
    assert payload["parameter_overrides"] == {}
    assert registered.correlation_id == _CORRELATION_ID
    assert registered.metadata == {"command": "RegisterFixture"}
    assert registered.occurred_at == _NOW

    asset_events, asset_version = await deps.event_store.load("Asset", asset_id)
    assert asset_version == 2  # registered + add_family; UNCHANGED by Fixture
    assembly_events, assembly_version = await deps.event_store.load("Assembly", assembly_id)
    assert assembly_version == 1  # defined only; UNCHANGED
    _ = asset_events
    _ = assembly_events


@pytest.mark.integration
async def test_register_fixture_rejects_decommissioned_asset_with_not_attachable_error(
    db_pool: asyncpg.Pool,
) -> None:
    """Cross-aggregate guard end-to-end: a Decommissioned Asset
    cannot be bound into a Fixture. The lifecycle guard fires in the
    pure decider after the handler folds the Asset's stream via the
    standard load_asset gather (no extra round-trip, no new
    projection). Rejecting at register-time prevents registering a
    Fixture that would inevitably fail later at
    `attach_asset_to_fixture`, since Fixture is single-event-genesis
    and cannot be amended.
    """
    deps = build_postgres_deps(db_pool, now=_NOW, ids=[uuid4() for _ in range(8)])

    # Register a fresh Asset and decommission it directly from
    # Commissioned (no install / activate needed; Slice 1's
    # decommission guards do not fire because the Asset is not
    # bound to a Fixture and not installed in any Mount).
    asset_id = await register_asset.bind(deps)(
        RegisterAsset(name="RetiredCam", level=AssetLevel.DEVICE, parent_id=uuid4()),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await decommission_asset.bind(deps)(
        DecommissionAsset(asset_id=asset_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    family_id = await define_family.bind(deps)(
        DefineFamily(name="RetiredCamera", affordances=frozenset()),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assembly_id = await define_assembly.bind(deps)(
        DefineAssembly(
            name="RetiredRig",
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

    with pytest.raises(FixtureAssetNotAttachableError) as exc_info:
        await register_fixture.bind(deps)(
            RegisterFixture(
                assembly_id=assembly_id,
                slot_asset_bindings=frozenset(
                    {SlotAssetBinding(slot_name="camera", asset_id=asset_id)}
                ),
            ),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    assert exc_info.value.asset_id == asset_id
    assert exc_info.value.current_lifecycle == AssetLifecycle.DECOMMISSIONED.value
