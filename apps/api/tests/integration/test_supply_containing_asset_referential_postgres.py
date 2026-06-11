"""Loose cross-BC referential integrity test for Supply.containing_asset_id.

Session 5 Slice 7E per [[project_supply_sector_disposition]] Option A,
Step 7: walks every `proj_supply_summary` row with `containing_asset_id
IS NOT NULL` and asserts each id resolves to a row in
`proj_equipment_asset_summary`. This is a LOOSE projection-side
referential check, NOT a real Postgres FOREIGN KEY constraint.

## Why loose, not a real FK

Per [[project_cross_bc_atomic_writes]] + [[project_seam_model]]:
cross-BC atomic writes are only introduced when broken-window
consequences are unacceptable. Slice 7B chose the lookup-only path
(register_supply queries `AssetLookup` at command time, rejects if
the Asset is unknown). A real FK from `proj_supply_summary.containing_asset_id`
to `proj_equipment_asset_summary.asset_id` would couple the two
projections at the database tier:

  - Projection workers process events asynchronously; a real FK
    would force a publish ordering that the projection workers
    cannot guarantee (Supply event could land first because the
    Supply projection bookmark advanced before the Asset bookmark
    caught up).
  - Forward-only migration of either projection's schema would
    require coordinating with the FK on every change.
  - Test fixtures would have to seed Assets through the full
    aggregate event pipeline before any Supply registration.

The loose check is sufficient for the operational guarantee:
register_supply already rejects unknown containing_asset_id at
command time via the AssetLookup port (`SupplyContainingAssetNotFoundError`
HTTP 404). The remaining failure mode is the eventual-consistency
window (Asset registered + Supply registered immediately), and
register_supply already documents the operator-retry remedy.

## What this test catches

  - A SupplyRegistered event referencing a never-existed Asset id
    (cross-BC bug: handler's AssetLookup short-circuit failed; the
    event landed in the event log + the projection wrote the row).
  - A projection-writer code change that drops or corrupts the
    containing_asset_id binding (silent data loss caught here, not
    at register-time).
  - An Asset deletion / hard-DROP that orphans existing Supply
    bindings (no such operation today; defensive guard).

## What this test does NOT catch

  - Race: register_asset + register_supply fired immediately. The
    Asset projection may not have caught up; the loose check could
    surface a transient violation. We drain projections in the test
    fixture before checking. In production this drift is reported
    by the projection bookmark lag; no operator action needed.
  - Asset.lifecycle filtering: Decommissioned Assets remain valid
    binding targets per the slice 7B decommissioned-binding-allowed
    rule. The loose check does not filter on Asset.lifecycle.

The companion command-time guard is the register_supply handler's
`AssetLookup.lookup` call + the decider's
`SupplyContainingAssetNotFoundError` (404). The projection-side check
here is the audit complement.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from datetime import UTC, datetime
from uuid import UUID, uuid4

import asyncpg
import pytest

from cora.equipment._projections import register_equipment_projections
from cora.equipment.aggregates.asset import AssetTier
from cora.equipment.features.register_asset import RegisterAsset
from cora.equipment.features.register_asset import bind as bind_register_asset
from cora.infrastructure.adapters.in_memory_asset_lookup import (
    InMemoryAssetLookup,
)
from cora.infrastructure.projection import ProjectionRegistry, drain_projections
from cora.supply._projections import register_supply_projections
from cora.supply.features.register_supply import RegisterSupply
from cora.supply.features.register_supply import bind as bind_register_supply
from tests.integration._helpers import build_postgres_deps

_NOW = datetime(2026, 6, 9, 12, 0, 0, tzinfo=UTC)
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")

_REFERENTIAL_CHECK_SQL = """
SELECT s.supply_id, s.containing_asset_id
FROM proj_supply_summary AS s
WHERE s.containing_asset_id IS NOT NULL
  AND NOT EXISTS (
      SELECT 1
      FROM proj_equipment_asset_summary AS a
      WHERE a.asset_id = s.containing_asset_id
  )
"""


async def _drain_supply(db_pool: asyncpg.Pool) -> None:
    registry = ProjectionRegistry()
    register_supply_projections(registry)
    await drain_projections(db_pool, registry, deadline_seconds=2.0)


async def _drain_equipment(db_pool: asyncpg.Pool) -> None:
    registry = ProjectionRegistry()
    register_equipment_projections(registry)
    await drain_projections(db_pool, registry, deadline_seconds=2.0)


@pytest.mark.integration
async def test_supply_containing_asset_id_resolves_to_real_asset_row(
    db_pool: asyncpg.Pool,
) -> None:
    """Happy path: a Supply bound to a registered Asset survives the
    loose referential walk. After registering the Asset (with its
    projection drained) and the Supply (with its projection drained),
    the SQL referential check returns zero violations."""
    # Register a real Asset and drain its projection so
    # proj_equipment_asset_summary has the row before the Supply lands.
    asset_id = uuid4()
    asset_deps = build_postgres_deps(db_pool, now=_NOW, ids=[asset_id, uuid4()])
    await bind_register_asset(asset_deps)(
        RegisterAsset(
            name=f"APS-{asset_id.hex[:8]}",
            tier=AssetTier.UNIT,
            parent_id=None,
            facility_code="cora",
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await _drain_equipment(db_pool)

    # Register a Supply bound to that Asset. AssetLookup is seeded so
    # the handler's containment-validation step resolves.
    asset_lookup = InMemoryAssetLookup()
    asset_lookup.register(
        asset_id=asset_id,
        name=f"APS-{asset_id.hex[:8]}",
        tier="Unit",
    )
    supply_id = uuid4()
    supply_deps = build_postgres_deps(
        db_pool,
        now=_NOW,
        ids=[supply_id, uuid4()],
        asset_lookup=asset_lookup,
    )
    await bind_register_supply(supply_deps)(
        RegisterSupply(
            kind="LiquidNitrogen",
            name=f"2-BM LN2 referential-test-{asset_id.hex[:8]}",
            facility_code="cora",
            containing_asset_id=asset_id,
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await _drain_supply(db_pool)

    # Loose referential walk over the global projection state. The
    # WHERE clause restricts to supplies bound to non-NULL Assets;
    # the NOT EXISTS arm catches any id that does not resolve in
    # the Equipment projection.
    async with db_pool.acquire() as conn:
        orphans = await conn.fetch(_REFERENTIAL_CHECK_SQL)

    assert orphans == [], (
        f"Found {len(orphans)} Supply rows with `containing_asset_id` that "
        f"does not resolve in `proj_equipment_asset_summary`: {list(orphans)}"
    )


@pytest.mark.integration
async def test_supply_containing_asset_id_null_does_not_trigger_check(
    db_pool: asyncpg.Pool,
) -> None:
    """A facility-scope Supply (containing_asset_id IS NULL) is not
    subject to the loose check; the WHERE clause excludes NULL rows.
    Pin the predicate direction."""
    # Register a facility-scope Supply (no containing_asset_id).
    supply_id = uuid4()
    supply_deps = build_postgres_deps(db_pool, now=_NOW, ids=[supply_id, uuid4()])
    await bind_register_supply(supply_deps)(
        RegisterSupply(
            kind="PhotonBeam",
            name=f"APS storage-ring beam {supply_id.hex[:8]}",
            facility_code="cora",
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await _drain_supply(db_pool)

    # The check should not surface this row even though no Asset row
    # exists with id NULL (NULL is not a valid asset_id; the predicate
    # excludes NULL containing_asset_id rows from the scan).
    async with db_pool.acquire() as conn:
        orphans = await conn.fetch(_REFERENTIAL_CHECK_SQL)
        # Confirm OUR facility-scope supply is in the projection
        row = await conn.fetchrow(
            "SELECT containing_asset_id FROM proj_supply_summary WHERE supply_id = $1",
            supply_id,
        )

    assert row is not None
    assert row["containing_asset_id"] is None
    # Loose check returns nothing for OUR supply (and ideally nothing
    # across the entire fixture; other tests in the same pool may have
    # seeded supplies that this assertion would catch).
    our_orphan_ids = [o["supply_id"] for o in orphans if o["supply_id"] == supply_id]
    assert our_orphan_ids == [], (
        f"Facility-scope Supply {supply_id} appeared in the orphan walk; "
        f"the NULL-excluding WHERE clause is broken."
    )
