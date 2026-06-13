"""End-to-end integration test: register_asset handler against real Postgres.

Two scenarios cover both genesis paths of the hierarchy rule:
Enterprise root (parent_id=None) and Site-with-parent. Pinned
because the payload's nullable parent_id round-trip through
Postgres jsonb is one of the structural guarantees Asset relies on.

A third scenario seeds a Model via `define_model` then registers an
Asset bound to it via `command.model_id`, verifying the
AssetRegistered payload carries `model_id` and the folded Asset
state round-trips it. The Model load-and-confirm-exists step happens
inside the register_asset handler against the real Postgres event
store.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from datetime import UTC, datetime
from uuid import UUID

import asyncpg
import pytest

from cora.equipment._projections import register_equipment_projections
from cora.equipment.aggregates.asset import (
    AssetLifecycle,
    AssetName,
    AssetTier,
    load_asset,
)
from cora.equipment.aggregates.family import FamilyName, family_stream_id
from cora.equipment.aggregates.model import (
    Manufacturer,
    ManufacturerName,
    ModelNotFoundError,
    PartNumber,
    model_stream_id,
)
from cora.equipment.features import define_family, define_model, register_asset
from cora.equipment.features.define_family import DefineFamily
from cora.equipment.features.define_model import DefineModel
from cora.equipment.features.register_asset import RegisterAsset
from cora.infrastructure.projection import ProjectionRegistry, drain_projections
from cora.shared.identifier import (
    AlternateIdentifier,
    AlternateIdentifierKind,
)
from tests.integration._helpers import build_postgres_deps

_NOW = datetime(2026, 5, 10, 12, 0, 0, tzinfo=UTC)
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")


@pytest.mark.integration
async def test_register_asset_persists_enterprise_root_to_postgres(
    db_pool: asyncpg.Pool,
) -> None:
    """Enterprise-level Asset with parent_id=None: payload's null
    serializes through jsonb and the evolver round-trip preserves
    None on read."""
    asset_id = UUID("01900000-0000-7000-8000-00000054ea01")
    event_id = UUID("01900000-0000-7000-8000-00000054ea0e")

    deps = build_postgres_deps(db_pool, now=_NOW, ids=[asset_id, event_id])

    returned_asset_id = await register_asset.bind(deps)(
        RegisterAsset(name="ANL", tier=AssetTier.UNIT, parent_id=None, facility_code="cora"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert returned_asset_id == asset_id

    events, version = await deps.event_store.load("Asset", asset_id)
    assert version == 1
    stored = events[0]
    assert stored.event_type == "AssetRegistered"
    assert stored.payload == {
        "asset_id": str(asset_id),
        "name": "ANL",
        "tier": "Unit",
        "parent_id": None,
        "occurred_at": _NOW.isoformat(),
        "commissioned_by": str(_PRINCIPAL_ID),
        "facility_code": "cora",
    }
    assert stored.event_id == event_id

    # Round-trip: load_asset folds back to the expected state.
    state = await load_asset(deps.event_store, asset_id)
    assert state is not None
    assert state.id == asset_id
    assert state.name == AssetName("ANL")
    assert state.tier is AssetTier.UNIT
    assert state.parent_id is None
    assert state.lifecycle is AssetLifecycle.COMMISSIONED


@pytest.mark.integration
async def test_register_asset_persists_site_with_parent_to_postgres(
    db_pool: asyncpg.Pool,
) -> None:
    """Non-Enterprise Asset with a parent_id: payload's UUID round-
    trips through jsonb as a string and rebuilds via UUID() on read."""
    asset_id = UUID("01900000-0000-7000-8000-00000054eb01")
    event_id = UUID("01900000-0000-7000-8000-00000054eb0e")
    parent_id = UUID("01900000-0000-7000-8000-00000054eb00")

    deps = build_postgres_deps(db_pool, now=_NOW, ids=[asset_id, event_id])

    await register_asset.bind(deps)(
        RegisterAsset(name="APS", tier=AssetTier.UNIT, parent_id=parent_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    state = await load_asset(deps.event_store, asset_id)
    assert state is not None
    assert state.parent_id == parent_id
    assert state.tier is AssetTier.UNIT
    assert state.lifecycle is AssetLifecycle.COMMISSIONED


async def _drain_equipment_projections(db_pool: asyncpg.Pool) -> None:
    """Pump Equipment-owned projections so cross-BC reads see fresh writes.

    `define_model.handler` queries `proj_equipment_family_summary` via
    `list_family_ids`; the upstream `define_family` event must be
    drained into the projection before the Model definition runs.
    """
    registry = ProjectionRegistry()
    register_equipment_projections(registry)
    await drain_projections(db_pool, registry, deadline_seconds=2.0)


@pytest.mark.integration
async def test_register_asset_persists_model_binding_to_postgres(
    db_pool: asyncpg.Pool,
) -> None:
    """Seed a Family + Model, then register an Asset bound to that
    Model via `command.model_id`. The handler's Model existence check
    runs against the real Postgres event store; AssetRegistered payload
    carries `model_id` as a string; folded Asset state round-trips it."""
    family_id = family_stream_id(FamilyName("ContinuousRotationTomography"))
    family_event_id = UUID("01900000-0000-7000-8000-000000054e0e")
    model_fallback_id = UUID("01900000-0000-7000-8000-00000054ec01")
    model_event_id = UUID("01900000-0000-7000-8000-00000054ec0e")
    model_id = model_stream_id(
        Manufacturer(name=ManufacturerName("Dectris")),
        PartNumber("EX9M-001"),
        new_id=UUID(int=0),
    )
    asset_id = UUID("01900000-0000-7000-8000-00000054ed01")
    asset_event_id = UUID("01900000-0000-7000-8000-00000054ed0e")
    parent_id = UUID("01900000-0000-7000-8000-00000054ed00")

    deps = build_postgres_deps(
        db_pool,
        now=_NOW,
        ids=[
            family_event_id,
            model_fallback_id,
            model_event_id,
            asset_id,
            asset_event_id,
        ],
    )
    await define_family.bind(deps)(
        DefineFamily(name="ContinuousRotationTomography", affordances=frozenset()),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await _drain_equipment_projections(db_pool)
    await define_model.bind(deps)(
        DefineModel(
            name="EigerX-9M",
            manufacturer=Manufacturer(name=ManufacturerName("Dectris")),
            part_number="EX9M-001",
            declared_family_ids=frozenset({family_id}),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    returned_asset_id = await register_asset.bind(deps)(
        RegisterAsset(
            name="APS-2BM-Det",
            tier=AssetTier.DEVICE,
            parent_id=parent_id,
            model_id=model_id,
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert returned_asset_id == asset_id

    events, version = await deps.event_store.load("Asset", asset_id)
    assert version == 1
    stored = events[0]
    assert stored.event_type == "AssetRegistered"
    assert stored.payload["model_id"] == str(model_id)
    assert stored.payload["asset_id"] == str(asset_id)
    assert stored.payload["tier"] == "Device"
    assert stored.payload["parent_id"] == str(parent_id)

    state = await load_asset(deps.event_store, asset_id)
    assert state is not None
    assert state.id == asset_id
    assert state.name == AssetName("APS-2BM-Det")
    assert state.model_id == model_id
    assert state.lifecycle is AssetLifecycle.COMMISSIONED


@pytest.mark.integration
async def test_register_asset_persists_alternate_identifiers_to_postgres(
    db_pool: asyncpg.Pool,
) -> None:
    """Seed a Family + Model, then register an Asset bound to that Model
    with two `alternate_identifiers` entries. The AssetRegistered payload
    must carry the list (sorted by (kind, value) per the canonical wire
    shape); the projection row must materialize the same list into the
    `alternate_identifiers` JSONB column; folded Asset state must round-
    trip the frozenset."""
    family_id = family_stream_id(FamilyName("ContinuousRotationTomography"))
    family_event_id = UUID("01900000-0000-7000-8000-000000054fae")
    model_fallback_id = UUID("01900000-0000-7000-8000-00000054fb01")
    model_event_id = UUID("01900000-0000-7000-8000-00000054fb0e")
    model_id = model_stream_id(
        Manufacturer(name=ManufacturerName("Aerotech")),
        PartNumber("ANT130L-G10"),
        new_id=UUID(int=0),
    )
    asset_id = UUID("01900000-0000-7000-8000-00000054fc01")
    asset_event_id = UUID("01900000-0000-7000-8000-00000054fc0e")
    parent_id = UUID("01900000-0000-7000-8000-00000054fc00")

    serial = AlternateIdentifier(kind=AlternateIdentifierKind.SERIAL_NUMBER, value="ANT130L-12345")
    inventory = AlternateIdentifier(
        kind=AlternateIdentifierKind.INVENTORY_NUMBER, value="APS-2BM-RS-001"
    )
    identifiers = frozenset({serial, inventory})

    deps = build_postgres_deps(
        db_pool,
        now=_NOW,
        ids=[
            family_event_id,
            model_fallback_id,
            model_event_id,
            asset_id,
            asset_event_id,
        ],
    )
    await define_family.bind(deps)(
        DefineFamily(name="ContinuousRotationTomography", affordances=frozenset()),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await _drain_equipment_projections(db_pool)
    await define_model.bind(deps)(
        DefineModel(
            name="ANT130L",
            manufacturer=Manufacturer(name=ManufacturerName("Aerotech")),
            part_number="ANT130L-G10",
            declared_family_ids=frozenset({family_id}),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    returned_asset_id = await register_asset.bind(deps)(
        RegisterAsset(
            name="APS-2BM-RotaryStage",
            tier=AssetTier.DEVICE,
            parent_id=parent_id,
            model_id=model_id,
            alternate_identifiers=identifiers,
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert returned_asset_id == asset_id

    events, version = await deps.event_store.load("Asset", asset_id)
    assert version == 1
    stored = events[0]
    assert stored.event_type == "AssetRegistered"
    payload_alt_ids = stored.payload["alternate_identifiers"]
    assert payload_alt_ids == [
        {"kind": "InventoryNumber", "value": "APS-2BM-RS-001"},
        {"kind": "SerialNumber", "value": "ANT130L-12345"},
    ]

    # Round-trip: load_asset folds back to the expected state.
    state = await load_asset(deps.event_store, asset_id)
    assert state is not None
    assert state.alternate_identifiers == identifiers

    # Projection: drain the AssetRegistered event into
    # proj_equipment_asset_summary and verify the JSONB column carries
    # the same canonical sorted list.
    await _drain_equipment_projections(db_pool)
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT alternate_identifiers FROM proj_equipment_asset_summary WHERE asset_id = $1",
            asset_id,
        )
    assert row is not None
    # The pool init callback registers a jsonb codec that decodes the
    # column straight to a Python list; no json.loads needed here.
    assert row["alternate_identifiers"] == [
        {"kind": "InventoryNumber", "value": "APS-2BM-RS-001"},
        {"kind": "SerialNumber", "value": "ANT130L-12345"},
    ]


@pytest.mark.integration
async def test_register_asset_raises_model_not_found_on_unknown_model_id(
    db_pool: asyncpg.Pool,
) -> None:
    """When `command.model_id` references a Model stream that does not
    exist, the handler raises ModelNotFoundError BEFORE appending any
    Asset event."""
    asset_id = UUID("01900000-0000-7000-8000-00000054ef01")
    asset_event_id = UUID("01900000-0000-7000-8000-00000054ef0e")
    unknown_model_id = UUID("01900000-0000-7000-8000-00000bad7e57")
    parent_id = UUID("01900000-0000-7000-8000-00000054ef00")

    deps = build_postgres_deps(db_pool, now=_NOW, ids=[asset_id, asset_event_id])

    with pytest.raises(ModelNotFoundError) as exc_info:
        await register_asset.bind(deps)(
            RegisterAsset(
                name="APS-2BM",
                tier=AssetTier.UNIT,
                parent_id=parent_id,
                model_id=unknown_model_id,
            ),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    assert exc_info.value.model_id == unknown_model_id

    _, version = await deps.event_store.load("Asset", asset_id)
    assert version == 0
