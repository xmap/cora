"""End-to-end integration test: add_asset_family against real Postgres.

Pin: payload round-trips through jsonb with family_id as a UUID
string; the evolver reconstructs into the frozenset on next load.
Two scenarios — adding a single capability, then verifying that
load+fold returns a state with the capability in the set.

Plus the cross-BC subset gate (Asset.model_id binding): when the
Asset is bound to a Model carrying `declared_family_ids`, the
`add_asset_family` handler loads the Model snapshot at decide time
and raises `AssetModelMismatchError` if the post-add Asset family set
is not a superset of the Model's declared families. The PG-backed
test seeds Model + Asset events directly via the event store
(register_asset does not yet accept a model_id) so the gate is
exercised end-to-end against real Postgres.
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import asyncpg
import pytest

from cora.equipment.aggregates.asset import AssetLevel, AssetModelMismatchError, load_asset
from cora.equipment.aggregates.asset.events import AssetRegistered
from cora.equipment.aggregates.asset.events import (
    event_type_name as asset_event_type_name,
)
from cora.equipment.aggregates.asset.events import to_payload as asset_to_payload
from cora.equipment.aggregates.model.events import ModelDefined
from cora.equipment.aggregates.model.events import (
    event_type_name as model_event_type_name,
)
from cora.equipment.aggregates.model.events import to_payload as model_to_payload
from cora.equipment.aggregates.model.state import Manufacturer, ManufacturerName
from cora.equipment.features import add_asset_family, register_asset
from cora.equipment.features.add_asset_family import AddAssetFamily
from cora.equipment.features.register_asset import RegisterAsset
from cora.infrastructure.event_envelope import to_new_event
from cora.infrastructure.kernel import Kernel
from cora.shared.identity import ActorId
from tests.integration._helpers import build_postgres_deps

_NOW = datetime(2026, 5, 10, 12, 0, 0, tzinfo=UTC)
_PARENT_ID = UUID("01900000-0000-7000-8000-00000056fa00")
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")


async def _seed_model(
    deps: Kernel,
    *,
    model_id: UUID,
    declared_family_ids: frozenset[UUID],
) -> None:
    """Append a `ModelDefined` event directly via the event store.

    Bypasses `define_model` (which would require the Families to
    exist in the projection too); this keeps the integration test
    focused on the cross-BC subset gate at the Asset handler.
    """
    event = ModelDefined(
        model_id=model_id,
        name="Aerotech ANT130-L",
        manufacturer=Manufacturer(name=ManufacturerName("Aerotech")),
        part_number="ANT130-L",
        declared_family_ids=declared_family_ids,
        occurred_at=_NOW,
    )
    new_event = to_new_event(
        event_type=model_event_type_name(event),
        payload=model_to_payload(event),
        occurred_at=_NOW,
        event_id=uuid4(),
        command_name="DefineModel",
        correlation_id=_CORRELATION_ID,
        principal_id=_PRINCIPAL_ID,
    )
    await deps.event_store.append(
        stream_type="Model",
        stream_id=model_id,
        expected_version=0,
        events=[new_event],
    )


async def _seed_asset_bound_to_model(
    deps: Kernel,
    *,
    asset_id: UUID,
    model_id: UUID,
) -> None:
    """Append an `AssetRegistered` event with `model_id` set directly.

    Used by the subset-gate tests; the current `register_asset` slice
    does not yet accept `model_id`. Round-trips through PG so the
    handler folds back an Asset state with `model_id` populated.
    """
    registered = AssetRegistered(
        asset_id=asset_id,
        name="APS-2BM",
        level=AssetLevel.UNIT,
        parent_id=_PARENT_ID,
        occurred_at=_NOW,
        model_id=model_id,
        commissioned_by=ActorId(uuid4()),
    )
    new_event = to_new_event(
        event_type=asset_event_type_name(registered),
        payload=asset_to_payload(registered),
        occurred_at=_NOW,
        event_id=uuid4(),
        command_name="RegisterAsset",
        correlation_id=_CORRELATION_ID,
        principal_id=_PRINCIPAL_ID,
    )
    await deps.event_store.append(
        stream_type="Asset",
        stream_id=asset_id,
        expected_version=0,
        events=[new_event],
    )


@pytest.mark.integration
async def test_add_asset_family_persists_event_and_round_trips_through_fold(
    db_pool: asyncpg.Pool,
) -> None:
    asset_id = UUID("01900000-0000-7000-8000-00000056fa01")
    register_event_id = UUID("01900000-0000-7000-8000-00000056fa0e")
    add_event_id = UUID("01900000-0000-7000-8000-00000056fa0f")
    cap1 = UUID("01900000-0000-7000-8000-000000000111")

    deps = build_postgres_deps(db_pool, now=_NOW, ids=[asset_id, register_event_id, add_event_id])

    await register_asset.bind(deps)(
        RegisterAsset(name="APS-2BM", level=AssetLevel.UNIT, parent_id=_PARENT_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await add_asset_family.bind(deps)(
        AddAssetFamily(asset_id=asset_id, family_id=cap1),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    events, version = await deps.event_store.load("Asset", asset_id)
    assert version == 2
    assert [e.event_type for e in events] == [
        "AssetRegistered",
        "AssetFamilyAdded",
    ]
    added = events[1]
    assert added.event_id == add_event_id
    assert added.metadata == {"command": "AddAssetFamily"}
    assert added.payload["family_id"] == str(cap1)

    # Fold-on-read reconstructs the capabilities frozenset.
    state = await load_asset(deps.event_store, asset_id)
    assert state is not None
    assert state.family_ids == frozenset({cap1})


@pytest.mark.integration
async def test_add_asset_family_succeeds_when_bound_model_subset_is_satisfied(
    db_pool: asyncpg.Pool,
) -> None:
    """Asset bound to a Model whose `declared_family_ids` is satisfied
    by the post-add Asset family set: the cross-BC subset gate
    passes, the `AssetFamilyAdded` event lands as usual."""
    asset_id = UUID("01900000-0000-7000-8000-00000057fa01")
    model_id = UUID("01900000-0000-7000-8000-00000057fa02")
    declared_family_id = UUID("01900000-0000-7000-8000-00000057fa03")
    add_event_id = UUID("01900000-0000-7000-8000-00000057fa04")

    deps = build_postgres_deps(db_pool, now=_NOW, ids=[add_event_id])

    await _seed_model(
        deps,
        model_id=model_id,
        declared_family_ids=frozenset({declared_family_id}),
    )
    await _seed_asset_bound_to_model(deps, asset_id=asset_id, model_id=model_id)

    await add_asset_family.bind(deps)(
        AddAssetFamily(asset_id=asset_id, family_id=declared_family_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    events, version = await deps.event_store.load("Asset", asset_id)
    assert version == 2
    assert [e.event_type for e in events] == [
        "AssetRegistered",
        "AssetFamilyAdded",
    ]
    assert events[1].payload["family_id"] == str(declared_family_id)

    state = await load_asset(deps.event_store, asset_id)
    assert state is not None
    assert state.model_id == model_id
    assert state.family_ids == frozenset({declared_family_id})


@pytest.mark.integration
async def test_add_asset_family_raises_asset_model_mismatch_when_subset_is_violated(
    db_pool: asyncpg.Pool,
) -> None:
    """Asset bound to a Model whose `declared_family_ids` is NOT
    satisfied by the post-add Asset family set: the cross-BC subset
    gate raises `AssetModelMismatchError`, no event is appended, the
    Asset stream stays at version 1."""
    asset_id = UUID("01900000-0000-7000-8000-00000058fa01")
    model_id = UUID("01900000-0000-7000-8000-00000058fa02")
    declared_a = UUID("01900000-0000-7000-8000-00000058fa03")
    declared_b = UUID("01900000-0000-7000-8000-00000058fa04")
    unused_add_event_id = UUID("01900000-0000-7000-8000-00000058fa05")

    deps = build_postgres_deps(db_pool, now=_NOW, ids=[unused_add_event_id])

    # Model declares two Families; we add only one; the post-add
    # Asset family set {declared_a} is NOT a superset of the Model's
    # {declared_a, declared_b}, so the gate fails.
    await _seed_model(
        deps,
        model_id=model_id,
        declared_family_ids=frozenset({declared_a, declared_b}),
    )
    await _seed_asset_bound_to_model(deps, asset_id=asset_id, model_id=model_id)

    with pytest.raises(AssetModelMismatchError) as exc_info:
        await add_asset_family.bind(deps)(
            AddAssetFamily(asset_id=asset_id, family_id=declared_a),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )

    assert exc_info.value.asset_id == asset_id
    assert exc_info.value.model_id == model_id
    assert exc_info.value.declared_family_ids == frozenset({declared_a, declared_b})
    assert exc_info.value.asset_family_ids == frozenset({declared_a})

    _, version = await deps.event_store.load("Asset", asset_id)
    assert version == 1
