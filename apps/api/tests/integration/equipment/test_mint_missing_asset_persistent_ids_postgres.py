"""Bulk-mint sweep against real Postgres: enumerate-missing -> mint -> re-run no-op.

The only tier where the sweep actually runs: enumeration reads
`proj_equipment_asset_summary` (needs a real pool + drained projections), and
each per-asset mint goes through the wired `assign_asset_persistent_id` handler
against the inert `StubDoiMinter`. Pins the end-to-end contract: every Asset
missing a persistent id gets one, and a second sweep finds nothing.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import UUID, uuid4

import asyncpg
import pytest

from cora.equipment.aggregates.asset import AssetTier
from cora.equipment.features import (
    assign_asset_persistent_id,
    mint_missing_asset_persistent_ids,
    register_asset,
)
from cora.equipment.features.assign_asset_persistent_id import AssignAssetPersistentId
from cora.equipment.features.mint_missing_asset_persistent_ids import (
    MintMissingAssetPersistentIds,
)
from cora.equipment.features.register_asset import RegisterAsset
from cora.infrastructure.adapters.stub_doi_minter import StubDoiMinter
from cora.infrastructure.kernel import Kernel
from cora.shared.identifier import PersistentIdentifier, PersistentIdentifierScheme
from tests.integration._equipment_helpers import drain_equipment_projections
from tests.integration._helpers import build_postgres_deps

pytestmark = pytest.mark.timeout(60, method="thread")

_NOW = datetime(2026, 6, 12, 12, 0, 0, tzinfo=UTC)
_PARENT_ID = UUID("01900000-0000-7000-8000-0000ee020000")
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")


def _build_deps(db_pool: asyncpg.Pool, *, ids: list[UUID]) -> Kernel:
    deps = build_postgres_deps(db_pool, ids=ids, now=_NOW)
    # Parity with wire_equipment when no DataCite credentials are present.
    object.__setattr__(deps, "equipment", SimpleNamespace(doi_minter=StubDoiMinter()))
    return deps


async def _register_asset(db_pool: asyncpg.Pool, *, name: str) -> UUID:
    asset_id = uuid4()
    deps = _build_deps(db_pool, ids=[asset_id, uuid4()])
    returned = await register_asset.bind(deps)(
        RegisterAsset(name=name, tier=AssetTier.DEVICE, parent_id=_PARENT_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert returned == asset_id
    return asset_id


def _bulk_handler(deps: Kernel) -> mint_missing_asset_persistent_ids.Handler:
    """Bridge the bulk orchestrator to the assign slice, mirroring wire_equipment."""
    assign = assign_asset_persistent_id.bind(deps)

    async def mint_one(
        asset_id: UUID,
        *,
        scheme: PersistentIdentifierScheme,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None,
        surface_id: UUID,
    ) -> PersistentIdentifier:
        return await assign(
            AssignAssetPersistentId(asset_id=asset_id, scheme=scheme, suffix=None),
            principal_id=principal_id,
            correlation_id=correlation_id,
            causation_id=causation_id,
            surface_id=surface_id,
        )

    return mint_missing_asset_persistent_ids.bind(deps, mint_one=mint_one)


async def _persistent_ids(db_pool: asyncpg.Pool, asset_ids: list[UUID]) -> dict[UUID, object]:
    rows = await db_pool.fetch(
        "SELECT asset_id, persistent_id FROM proj_equipment_asset_summary "
        "WHERE asset_id = ANY($1::uuid[])",
        asset_ids,
    )
    return {row["asset_id"]: row["persistent_id"] for row in rows}


@pytest.mark.integration
async def test_bulk_mint_assigns_persistent_id_to_every_missing_asset(
    db_pool: asyncpg.Pool,
) -> None:
    a = await _register_asset(db_pool, name="Bulk-Asset-A")
    b = await _register_asset(db_pool, name="Bulk-Asset-B")
    c = await _register_asset(db_pool, name="Bulk-Asset-C")
    await drain_equipment_projections(db_pool)

    # One event id per minted Asset (each assign emits one AssetPersistentIdAssigned).
    deps = _build_deps(db_pool, ids=[uuid4(), uuid4(), uuid4()])
    result = await _bulk_handler(deps)(
        MintMissingAssetPersistentIds(),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    assert result.scanned == 3
    assert {m.asset_id for m in result.minted} == {a, b, c}
    assert result.skipped == ()
    assert result.failed == ()

    await drain_equipment_projections(db_pool)
    pids = await _persistent_ids(db_pool, [a, b, c])
    assert all(pids[asset_id] is not None for asset_id in (a, b, c))


@pytest.mark.integration
async def test_bulk_mint_is_a_noop_on_rerun(db_pool: asyncpg.Pool) -> None:
    asset_id = await _register_asset(db_pool, name="Bulk-Asset-Solo")
    await drain_equipment_projections(db_pool)

    first = await _bulk_handler(_build_deps(db_pool, ids=[uuid4()]))(
        MintMissingAssetPersistentIds(),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert first.scanned == 1
    assert {m.asset_id for m in first.minted} == {asset_id}

    await drain_equipment_projections(db_pool)

    # No ids queued: a second sweep must enumerate nothing, so the assign
    # delegate is never called (a stray mint would exhaust the empty id queue).
    second = await _bulk_handler(_build_deps(db_pool, ids=[]))(
        MintMissingAssetPersistentIds(),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert second.scanned == 0
    assert second.minted == ()
    assert second.skipped == ()
    assert second.failed == ()
