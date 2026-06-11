"""End-to-end: `list_supplies` handler against real Postgres projection table.

Pins the genesis -> transition fold + projection writes:

  - SupplyRegistered -> INSERT (status='Unknown', last_status_*=NULL)
  - SupplyMarkedAvailable -> UPDATE status='Available' + last_status_changed_at
                                     + last_status_reason + last_trigger
  - facility_code filter
  - containing_asset_id filter
  - kind filter
  - status filter
  - cursor pagination
  - 5-status SupplyStatusFilter Literal locked day one (Unknown / Available
    reachable via genesis; Degraded / Unavailable / Recovering reachable via transitions)
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from datetime import UTC, datetime
from uuid import UUID, uuid4

import asyncpg
import pytest

from cora.infrastructure.kernel import Kernel
from cora.infrastructure.projection import ProjectionRegistry, drain_projections
from cora.supply._projections import register_supply_projections
from cora.supply.features.list_supplies import ListSupplies
from cora.supply.features.list_supplies import bind as bind_list
from cora.supply.features.mark_supply_available import MarkSupplyAvailable
from cora.supply.features.mark_supply_available import bind as bind_mark
from cora.supply.features.register_supply import RegisterSupply
from cora.supply.features.register_supply import bind as bind_register
from tests.integration._helpers import build_postgres_deps

_NOW = datetime(2026, 5, 14, 12, 0, 0, tzinfo=UTC)
_LATER = datetime(2026, 5, 14, 13, 0, 0, tzinfo=UTC)
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")


def _build_deps(db_pool: asyncpg.Pool, ids: list[UUID], now: datetime = _NOW) -> Kernel:
    return build_postgres_deps(db_pool, now=now, ids=ids)


async def _drain(db_pool: asyncpg.Pool) -> None:
    registry = ProjectionRegistry()
    register_supply_projections(registry)
    await drain_projections(db_pool, registry, deadline_seconds=2.0)


@pytest.mark.integration
async def test_register_inserts_unknown_status_with_null_audit_columns(
    db_pool: asyncpg.Pool,
) -> None:
    """SupplyRegistered -> projection row in 'Unknown' with last_status_* NULL."""
    sup_id = uuid4()
    deps = _build_deps(db_pool, [sup_id, uuid4()])
    await bind_register(deps)(
        RegisterSupply(
            kind="LiquidNitrogen",
            name="2-BM LN2",
            facility_code="cora",
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await _drain(db_pool)

    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT kind, name, status, last_status_changed_at, "
            "last_status_reason, last_trigger "
            "FROM proj_supply_summary WHERE supply_id = $1",
            sup_id,
        )
    assert row is not None
    assert row["kind"] == "LiquidNitrogen"
    assert row["name"] == "2-BM LN2"
    assert row["status"] == "Unknown"
    assert row["last_status_changed_at"] is None
    assert row["last_status_reason"] is None
    assert row["last_trigger"] is None


@pytest.mark.integration
async def test_mark_available_updates_status_and_audit_triple(
    db_pool: asyncpg.Pool,
) -> None:
    """Register -> mark_available: status flips Available + audit triple lands."""
    sup_id = uuid4()
    deps = _build_deps(db_pool, [sup_id, uuid4()])
    await bind_register(deps)(
        RegisterSupply(
            kind="LiquidNitrogen",
            name="2-BM LN2",
            facility_code="cora",
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    later_deps = _build_deps(db_pool, [uuid4()], now=_LATER)
    await bind_mark(later_deps)(
        MarkSupplyAvailable(supply_id=sup_id, reason="operator walkdown"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await _drain(db_pool)

    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT status, last_status_changed_at, last_status_reason, last_trigger "
            "FROM proj_supply_summary WHERE supply_id = $1",
            sup_id,
        )
    assert row is not None
    assert row["status"] == "Available"
    assert row["last_status_changed_at"] == _LATER
    assert row["last_status_reason"] == "operator walkdown"
    assert row["last_trigger"] == "Operator"


@pytest.mark.integration
async def test_list_returns_registered_supplies(db_pool: asyncpg.Pool) -> None:
    deps = _build_deps(db_pool, [uuid4(), uuid4()])
    await bind_register(deps)(
        RegisterSupply(
            kind="LiquidNitrogen",
            name="2-BM LN2",
            facility_code="cora",
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await _drain(db_pool)

    page = await bind_list(deps)(
        ListSupplies(),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert len(page.items) == 1
    assert page.items[0].name == "2-BM LN2"
    assert page.items[0].status == "Unknown"
    assert page.next_cursor is None


@pytest.mark.integration
async def test_list_filters_by_containing_asset_kind_status(db_pool: asyncpg.Pool) -> None:
    """Slice 7D: filter axes (containing_asset_id, kind, status) compose
    via the NULL-or pattern. The prior `scope` filter axis was retired
    per [[project_supply_sector_disposition]] Option A; the equivalent
    operator query ('all beamline supplies') now selects by the binding
    Asset id."""
    from cora.infrastructure.adapters.in_memory_asset_lookup import (
        InMemoryAssetLookup,
    )

    bm_asset_id = uuid4()
    asset_lookup = InMemoryAssetLookup()
    asset_lookup.register(asset_id=bm_asset_id, name="2-BM", tier="Unit")

    # Register 3 supplies: 2 bound to 2-BM Asset, 1 facility-scope.
    bm_ln2_id = uuid4()
    fac_beam_id = uuid4()
    bm_air_id = uuid4()

    for sup_id, kind, name, containing_id in (
        (bm_ln2_id, "LiquidNitrogen", "2-BM LN2", bm_asset_id),
        (fac_beam_id, "PhotonBeam", "APS storage-ring beam", None),
        (bm_air_id, "CompressedAir", "2-BM CompAir", bm_asset_id),
    ):
        deps = build_postgres_deps(
            db_pool,
            now=_NOW,
            ids=[sup_id, uuid4()],
            asset_lookup=asset_lookup,
        )
        await bind_register(deps)(
            RegisterSupply(
                kind=kind,
                name=name,
                facility_code="cora",
                containing_asset_id=containing_id,
            ),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    # Mark only the LN2 one Available
    mark_deps = _build_deps(db_pool, [uuid4()], now=_LATER)
    await bind_mark(mark_deps)(
        MarkSupplyAvailable(supply_id=bm_ln2_id, reason="operator walkdown"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await _drain(db_pool)

    list_deps = _build_deps(db_pool, [])

    # Filter by containing_asset_id=bm_asset_id -> 2 results (the 2-BM-bound supplies)
    page = await bind_list(list_deps)(
        ListSupplies(containing_asset_id=bm_asset_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert len(page.items) == 2
    assert {item.kind for item in page.items} == {"LiquidNitrogen", "CompressedAir"}

    # Filter by kind=PhotonBeam -> 1 result
    page = await bind_list(list_deps)(
        ListSupplies(kind="PhotonBeam"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert len(page.items) == 1
    assert page.items[0].name == "APS storage-ring beam"

    # Filter by status=Available -> 1 result (only the marked one)
    page = await bind_list(list_deps)(
        ListSupplies(status="Available"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert len(page.items) == 1
    assert page.items[0].supply_id == bm_ln2_id

    # Combined: containing_asset_id=bm_asset_id AND status=Unknown -> 1 result (CompAir)
    page = await bind_list(list_deps)(
        ListSupplies(containing_asset_id=bm_asset_id, status="Unknown"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert len(page.items) == 1
    assert page.items[0].supply_id == bm_air_id

    # Filter by facility_code=cora -> all 3 results (every supply is on 'cora')
    page = await bind_list(list_deps)(
        ListSupplies(facility_code="cora"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert len(page.items) == 3


@pytest.mark.integration
async def test_list_cursor_pagination(db_pool: asyncpg.Pool) -> None:
    """Pages-of-2 across 3 supplies produces a cursor on page 1, no cursor on page 2."""
    for i in range(3):
        deps = _build_deps(db_pool, [uuid4(), uuid4()])
        await bind_register(deps)(
            RegisterSupply(
                kind=f"K{i}",
                name=f"Supply-{i}",
                facility_code="cora",
            ),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    await _drain(db_pool)

    list_deps = _build_deps(db_pool, [])
    page1 = await bind_list(list_deps)(
        ListSupplies(limit=2),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert len(page1.items) == 2
    assert page1.next_cursor is not None

    page2 = await bind_list(list_deps)(
        ListSupplies(limit=2, cursor=page1.next_cursor),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert len(page2.items) == 1
    assert page2.next_cursor is None


@pytest.mark.integration
async def test_list_returns_audit_triple_after_mark_available(
    db_pool: asyncpg.Pool,
) -> None:
    """H1 from gate review: pin the round-trip of `last_status_changed_at` /
    `last_status_reason` / `last_trigger` from projection -> handler item ->
    list response. Without this, a regression breaking the field-mapping
    SQL or the SupplySummaryItem construction would ship green."""
    sup_id = uuid4()
    register_deps = _build_deps(db_pool, [sup_id, uuid4()])
    await bind_register(register_deps)(
        RegisterSupply(
            kind="LiquidNitrogen",
            name="2-BM LN2",
            facility_code="cora",
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    mark_deps = _build_deps(db_pool, [uuid4()], now=_LATER)
    await bind_mark(mark_deps)(
        MarkSupplyAvailable(supply_id=sup_id, reason="operator walkdown confirms LN2 flowing"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await _drain(db_pool)

    list_deps = _build_deps(db_pool, [])
    page = await bind_list(list_deps)(
        ListSupplies(),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert len(page.items) == 1
    item = page.items[0]
    assert item.status == "Available"
    assert item.last_status_changed_at == _LATER
    assert item.last_status_reason == "operator walkdown confirms LN2 flowing"
    assert item.last_trigger == "Operator"


@pytest.mark.integration
async def test_list_cursor_with_filter_paginates_within_filtered_set(
    db_pool: asyncpg.Pool,
) -> None:
    """M3 from gate review: cursor + filter in combination exercises the
    `_LIST_WITH_CURSOR_SQL` branch (the more complex SQL path) under
    real filter pressure. Register 3 supplies bound to one Asset + 1
    facility-scope supply, page-of-2 filtered by
    containing_asset_id, expect page1 to have a cursor, page2 to have
    the remaining bound supply only. Slice 7D migrated the filter axis
    from `scope` to `containing_asset_id` per
    [[project_supply_sector_disposition]] Option A."""
    from cora.infrastructure.adapters.in_memory_asset_lookup import (
        InMemoryAssetLookup,
    )

    bm_asset_id = uuid4()
    asset_lookup = InMemoryAssetLookup()
    asset_lookup.register(asset_id=bm_asset_id, name="2-BM", tier="Unit")

    for i in range(3):
        deps = build_postgres_deps(
            db_pool,
            now=_NOW,
            ids=[uuid4(), uuid4()],
            asset_lookup=asset_lookup,
        )
        await bind_register(deps)(
            RegisterSupply(
                kind=f"K{i}",
                name=f"BM-{i}",
                facility_code="cora",
                containing_asset_id=bm_asset_id,
            ),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    facility_deps = _build_deps(db_pool, [uuid4(), uuid4()])
    await bind_register(facility_deps)(
        RegisterSupply(
            kind="PhotonBeam",
            name="APS-Beam",
            facility_code="cora",
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await _drain(db_pool)

    list_deps = _build_deps(db_pool, [])
    page1 = await bind_list(list_deps)(
        ListSupplies(containing_asset_id=bm_asset_id, limit=2),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert len(page1.items) == 2
    assert all(item.containing_asset_id == bm_asset_id for item in page1.items)
    assert page1.next_cursor is not None

    page2 = await bind_list(list_deps)(
        ListSupplies(containing_asset_id=bm_asset_id, limit=2, cursor=page1.next_cursor),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert len(page2.items) == 1
    assert page2.items[0].containing_asset_id == bm_asset_id
    assert page2.next_cursor is None


@pytest.mark.integration
async def test_list_unique_address_swallows_second_active_insert_and_keeps_worker_running(
    db_pool: asyncpg.Pool,
) -> None:
    """Duplicate-key UniqueViolation in the projection is caught and logged.

    Two ACTIVE supplies with the same (scope, kind, name) trip the
    projection's partial UNIQUE INDEX on the second INSERT. The projection
    catches the UniqueViolation, logs a structured warning, and advances
    the bookmark so the worker keeps running. Operational behavior verified:

      - Both Supply event streams exist in the event store (the duplicate
        registration is audit-recorded, not silently dropped at the
        write layer).
      - The projection has exactly one row (the first insert wins; the
        second's INSERT is a no-op via the catch).
      - The drain itself does NOT raise (worker would otherwise stall
        and block all Supply projection progress including transitions
        on unrelated supplies).

    The aggregate cannot enforce cross-stream uniqueness without DCB
    (see [[project_deferred]]); graceful projection-level handling is
    the right operational behavior pre-DCB. Watch item 10 of
    [[project_supply_design]] has SHIPPED as the `deregister_supply`
    slice; once a duplicate is identified, operators deregister one
    via `POST /supplies/{id}/deregister` and the partial UNIQUE INDEX
    (`WHERE status != 'Decommissioned'`) then permits re-registering
    the address with a fresh `supply_id`. The companion test
    `test_supply_reregister_after_deregister_postgres.py` pins that
    re-registration cycle; this test pins the still-active-duplicate
    case (the other direction of the partial predicate).
    """
    sup_id_1 = uuid4()
    sup_id_2 = uuid4()
    for sup_id in (sup_id_1, sup_id_2):
        deps = _build_deps(db_pool, [sup_id, uuid4()])
        await bind_register(deps)(
            RegisterSupply(
                kind="LiquidNitrogen",
                name="2-BM LN2",
                facility_code="cora",
            ),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    # Drain succeeds (UniqueViolation caught + logged + swallowed).
    await _drain(db_pool)

    # Exactly one projection row (first insert wins).
    list_deps = _build_deps(db_pool, [])
    page = await bind_list(list_deps)(
        ListSupplies(),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert len(page.items) == 1
    assert page.items[0].supply_id in {sup_id_1, sup_id_2}

    # Both Supply event streams exist in the event store (audit preserved).
    async with db_pool.acquire() as conn:
        row_count = await conn.fetchval("SELECT count(*) FROM events WHERE stream_type = 'Supply'")
    assert row_count == 2
