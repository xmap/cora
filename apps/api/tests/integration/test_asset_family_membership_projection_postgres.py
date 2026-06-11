"""End-to-end: AssetFamilyMembershipProjection populates the
`proj_equipment_asset_family_membership` join table from real
AssetFamilyAdded / AssetFamilyRemoved events against Postgres.

Pins:
  - AssetFamilyAdded -> INSERT (asset_id, family_id, added_at)
  - AssetFamilyRemoved -> DELETE matching row
  - Reverse index (family_id, asset_id) supports "Assets carrying
    Family X" lookup -- the diagnostic's seed query for the next phase
  - Idempotency: replay-from-zero produces the same final state
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from datetime import UTC, datetime
from uuid import UUID, uuid4

import asyncpg
import pytest

from cora.equipment._projections import register_equipment_projections
from cora.equipment.aggregates.asset import AssetTier
from cora.equipment.features import (
    add_asset_family,
    define_family,
    register_asset,
    remove_asset_family,
)
from cora.equipment.features.add_asset_family import AddAssetFamily
from cora.equipment.features.define_family import DefineFamily
from cora.equipment.features.register_asset import RegisterAsset
from cora.equipment.features.remove_asset_family import RemoveAssetFamily
from cora.infrastructure.projection import ProjectionRegistry, drain_projections
from tests.integration._helpers import build_postgres_deps

_NOW = datetime(2026, 5, 27, 14, 0, 0, tzinfo=UTC)
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")


async def _drain(db_pool: asyncpg.Pool) -> None:
    registry = ProjectionRegistry()
    register_equipment_projections(registry)
    await drain_projections(db_pool, registry, deadline_seconds=2.0)


@pytest.mark.integration
async def test_asset_family_added_inserts_row_with_added_at(
    db_pool: asyncpg.Pool,
) -> None:
    """End-to-end: register Asset + define Family + add -> join row exists."""
    ids = [uuid4() for _ in range(8)]
    deps = build_postgres_deps(db_pool, now=_NOW, ids=ids)

    family_id = await define_family.bind(deps)(
        DefineFamily(name="RotaryStage", affordances=frozenset()),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    asset_id = await register_asset.bind(deps)(
        RegisterAsset(name="ABRS-1", tier=AssetTier.UNIT, parent_id=None, facility_code="cora"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await add_asset_family.bind(deps)(
        AddAssetFamily(asset_id=asset_id, family_id=family_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await _drain(db_pool)

    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT asset_id, family_id, added_at "
            "FROM proj_equipment_asset_family_membership "
            "WHERE asset_id = $1 AND family_id = $2",
            asset_id,
            family_id,
        )
    assert row is not None
    assert row["asset_id"] == asset_id
    assert row["family_id"] == family_id
    assert row["added_at"] == _NOW


@pytest.mark.integration
async def test_asset_family_removed_deletes_join_row(
    db_pool: asyncpg.Pool,
) -> None:
    ids = [uuid4() for _ in range(10)]
    deps = build_postgres_deps(db_pool, now=_NOW, ids=ids)

    family_id = await define_family.bind(deps)(
        DefineFamily(name="LinearStage", affordances=frozenset()),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    asset_id = await register_asset.bind(deps)(
        RegisterAsset(name="Newport-X", tier=AssetTier.UNIT, parent_id=None, facility_code="cora"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await add_asset_family.bind(deps)(
        AddAssetFamily(asset_id=asset_id, family_id=family_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await remove_asset_family.bind(deps)(
        RemoveAssetFamily(asset_id=asset_id, family_id=family_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await _drain(db_pool)

    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT 1 FROM proj_equipment_asset_family_membership "
            "WHERE asset_id = $1 AND family_id = $2",
            asset_id,
            family_id,
        )
    assert row is None


@pytest.mark.integration
async def test_reverse_index_supports_assets_carrying_family_lookup(
    db_pool: asyncpg.Pool,
) -> None:
    """Two Assets, each bound to the same Family; reverse lookup by
    family_id returns both. This is the Y.c diagnostic's seed query
    pattern ('which Assets afford requirement X')."""
    ids = [uuid4() for _ in range(15)]
    deps = build_postgres_deps(db_pool, now=_NOW, ids=ids)

    family_id = await define_family.bind(deps)(
        DefineFamily(name="Hexapod", affordances=frozenset()),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    asset_a = await register_asset.bind(deps)(
        RegisterAsset(name="Hex-A", tier=AssetTier.UNIT, parent_id=None, facility_code="cora"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    asset_b = await register_asset.bind(deps)(
        RegisterAsset(name="Hex-B", tier=AssetTier.UNIT, parent_id=None, facility_code="cora"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    for asset_id in (asset_a, asset_b):
        await add_asset_family.bind(deps)(
            AddAssetFamily(asset_id=asset_id, family_id=family_id),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    await _drain(db_pool)

    async with db_pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT asset_id FROM proj_equipment_asset_family_membership "
            "WHERE family_id = $1 ORDER BY asset_id::text",
            family_id,
        )
    asset_ids = sorted([asset_a, asset_b], key=str)
    assert [r["asset_id"] for r in rows] == asset_ids


@pytest.mark.integration
async def test_replay_from_zero_produces_consistent_join_state(
    db_pool: asyncpg.Pool,
) -> None:
    """Drain twice with no new events between drains: row count
    stable (idempotency from ON CONFLICT DO NOTHING + bookmark
    advancement)."""
    ids = [uuid4() for _ in range(8)]
    deps = build_postgres_deps(db_pool, now=_NOW, ids=ids)

    family_id = await define_family.bind(deps)(
        DefineFamily(name="Shutter", affordances=frozenset()),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    asset_id = await register_asset.bind(deps)(
        RegisterAsset(
            name="FastShutter-1", tier=AssetTier.UNIT, parent_id=None, facility_code="cora"
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await add_asset_family.bind(deps)(
        AddAssetFamily(asset_id=asset_id, family_id=family_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    await _drain(db_pool)
    await _drain(db_pool)

    async with db_pool.acquire() as conn:
        count = await conn.fetchval(
            "SELECT COUNT(*) FROM proj_equipment_asset_family_membership "
            "WHERE asset_id = $1 AND family_id = $2",
            asset_id,
            family_id,
        )
    assert count == 1
