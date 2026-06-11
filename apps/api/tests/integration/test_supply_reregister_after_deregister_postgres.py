"""Re-registration after deregister: pins the partial UNIQUE INDEX behavior.

This is the load-bearing integration test for
[[project_deregister_supply_design]]. The design promise is that
once a Supply is `Decommissioned`, an operator can re-register
the same address with a fresh supply_id. The mechanism is the
partial UNIQUE INDEX on `proj_supply_summary`:

    CREATE UNIQUE INDEX proj_supply_summary_address_uq
        ON proj_supply_summary (
            facility_code,
            COALESCE(containing_asset_id::text, ''),
            kind,
            name
        )
        WHERE status != 'Decommissioned';

Slice 7C swapped the address tuple from the original
`(scope, kind, name)` to the current
`(facility_code, COALESCE(containing_asset_id::text, ''), kind, name)`
per [[project_supply_sector_disposition]] Option A so two
facilities + per-containing-Asset bindings can coexist without
colliding.

Without the partial predicate the second register at the same
address would be rejected at projection-insert time (silent
WARN-log fallback, fresh supply_id orphaned from the projection).
With it, both rows coexist in the projection: one Decommissioned
(old supply_id, audit) + one Unknown (new supply_id, active).

A second invariant pinned here: two ACTIVE supplies (both non-
Decommissioned) at the same address still trip the unique index;
the WARN-log fallback fires. The partial predicate has the right
direction. A third invariant: two ACTIVE supplies at the same
`(kind, name)` but DIFFERENT `facility_code` (or different
`containing_asset_id` within one facility) BOTH land cleanly;
the post-Slice-7C index correctly distinguishes by both keys.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from datetime import UTC, datetime
from uuid import UUID, uuid4

import asyncpg
import pytest

from cora.infrastructure.kernel import Kernel
from cora.infrastructure.projection import ProjectionRegistry, drain_projections
from cora.supply._projections import register_supply_projections
from cora.supply.features.deregister_supply import DeregisterSupply
from cora.supply.features.deregister_supply import bind as bind_deregister
from cora.supply.features.list_supplies import ListSupplies
from cora.supply.features.list_supplies import bind as bind_list
from cora.supply.features.register_supply import RegisterSupply
from cora.supply.features.register_supply import bind as bind_register
from tests.integration._helpers import build_postgres_deps

_T0 = datetime(2026, 5, 27, 10, 0, 0, tzinfo=UTC)
_T1 = datetime(2026, 5, 27, 11, 0, 0, tzinfo=UTC)
_T2 = datetime(2026, 5, 27, 12, 0, 0, tzinfo=UTC)
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")


def _build_deps(db_pool: asyncpg.Pool, ids: list[UUID], now: datetime) -> Kernel:
    return build_postgres_deps(db_pool, now=now, ids=ids)


async def _drain(db_pool: asyncpg.Pool) -> None:
    registry = ProjectionRegistry()
    register_supply_projections(registry)
    await drain_projections(db_pool, registry, deadline_seconds=2.0)


@pytest.mark.integration
async def test_reregister_at_same_address_after_deregister_creates_fresh_supply_id(
    db_pool: asyncpg.Pool,
) -> None:
    """Register -> deregister -> register at same (scope, kind, name) -> new id."""
    kind = "LiquidNitrogen"
    name = f"2-BM LN2 reregister-test-{uuid4()}"

    first_supply_id = uuid4()
    first_genesis_event_id = uuid4()
    deps_register_first = _build_deps(
        db_pool, ids=[first_supply_id, first_genesis_event_id], now=_T0
    )
    sid_first = await bind_register(deps_register_first)(
        RegisterSupply(kind=kind, name=name, facility_code="cora"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert sid_first == first_supply_id

    deregister_event_id = uuid4()
    deps_deregister = _build_deps(db_pool, ids=[deregister_event_id], now=_T1)
    await bind_deregister(deps_deregister)(
        DeregisterSupply(supply_id=first_supply_id, reason="typo; re-registering"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await _drain(db_pool)

    second_supply_id = uuid4()
    second_genesis_event_id = uuid4()
    deps_register_second = _build_deps(
        db_pool, ids=[second_supply_id, second_genesis_event_id], now=_T2
    )
    sid_second = await bind_register(deps_register_second)(
        RegisterSupply(kind=kind, name=name, facility_code="cora"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await _drain(db_pool)

    assert sid_second == second_supply_id
    assert sid_second != first_supply_id

    deps_list = _build_deps(db_pool, ids=[uuid4()], now=_T2)
    page = await bind_list(deps_list)(
        ListSupplies(kind="LiquidNitrogen"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    matching = [item for item in page.items if item.name == name]
    assert len(matching) == 2, f"expected two rows at the same address, got {matching}"
    by_id = {item.supply_id: item for item in matching}
    assert by_id[first_supply_id].status == "Decommissioned"
    assert by_id[second_supply_id].status == "Unknown"


@pytest.mark.integration
async def test_second_active_registration_at_same_address_is_swallowed(
    db_pool: asyncpg.Pool,
) -> None:
    """Two non-Decommissioned supplies at the same address still trip the
    partial UNIQUE INDEX; the projection's WARN-log fallback fires and the
    second event lives in the event store as audit (no projection row).
    Pins the predicate's direction: `WHERE status != 'Decommissioned'`
    excludes Decommissioned rows from uniqueness, not active ones."""
    kind = "CompressedAir"
    name = f"2-BM CA active-dup-test-{uuid4()}"

    first_supply_id = uuid4()
    deps_first = _build_deps(db_pool, ids=[first_supply_id, uuid4()], now=_T0)
    await bind_register(deps_first)(
        RegisterSupply(kind=kind, name=name, facility_code="cora"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await _drain(db_pool)

    second_supply_id = uuid4()
    deps_second = _build_deps(db_pool, ids=[second_supply_id, uuid4()], now=_T1)
    await bind_register(deps_second)(
        RegisterSupply(kind=kind, name=name, facility_code="cora"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await _drain(db_pool)

    deps_list = _build_deps(db_pool, ids=[uuid4()], now=_T2)
    page = await bind_list(deps_list)(
        ListSupplies(kind="CompressedAir"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    matching = [item for item in page.items if item.name == name]
    assert len(matching) == 1, "duplicate active address should not double-insert"
    assert matching[0].supply_id == first_supply_id


@pytest.mark.integration
async def test_same_kind_name_across_facilities_coexist(
    db_pool: asyncpg.Pool,
) -> None:
    """Slice 7C: two Supplies with the same `(scope, kind, name)` but
    DIFFERENT `facility_code` BOTH land in the projection. The new
    UNIQUE INDEX composes facility_code first, so the two rows occupy
    distinct slots."""
    from cora.infrastructure.adapters.in_memory_facility_lookup import (
        InMemoryFacilityLookup,
    )
    from cora.shared.facility_code import FacilityCode

    kind = "LiquidNitrogen"
    name = f"2-BM LN2 cross-facility-{uuid4()}"

    aps_supply_id = uuid4()
    aps_lookup = InMemoryFacilityLookup()
    aps_lookup.register(
        facility_id=UUID("01900000-0000-7000-8000-00000000c0a0"),
        code=FacilityCode("aps"),
        kind="Site",
        status="Active",
    )
    aps_deps = build_postgres_deps(
        db_pool,
        now=_T0,
        ids=[aps_supply_id, uuid4()],
        facility_lookup=aps_lookup,
    )
    await bind_register(aps_deps)(
        RegisterSupply(kind=kind, name=name, facility_code="aps"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    maxiv_supply_id = uuid4()
    maxiv_lookup = InMemoryFacilityLookup()
    maxiv_lookup.register(
        facility_id=UUID("01900000-0000-7000-8000-00000000c0a1"),
        code=FacilityCode("maxiv"),
        kind="Site",
        status="Active",
    )
    maxiv_deps = build_postgres_deps(
        db_pool,
        now=_T1,
        ids=[maxiv_supply_id, uuid4()],
        facility_lookup=maxiv_lookup,
    )
    await bind_register(maxiv_deps)(
        RegisterSupply(kind=kind, name=name, facility_code="maxiv"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await _drain(db_pool)

    deps_list = build_postgres_deps(db_pool, ids=[uuid4()], now=_T2)
    page = await bind_list(deps_list)(
        ListSupplies(kind=kind),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    matching = sorted([item.supply_id for item in page.items if item.name == name])
    assert sorted([aps_supply_id, maxiv_supply_id]) == matching, (
        f"expected both cross-facility rows to coexist, got {matching}"
    )


@pytest.mark.integration
async def test_same_kind_name_across_containing_assets_coexist(
    db_pool: asyncpg.Pool,
) -> None:
    """Slice 7C: two Supplies with the same `(scope, kind, name)` and
    SAME `facility_code` but DIFFERENT `containing_asset_id` BOTH land
    in the projection. The new UNIQUE INDEX composes
    COALESCE(containing_asset_id::text, '') so distinct UUIDs occupy
    distinct slots within one facility."""
    from cora.infrastructure.adapters.in_memory_asset_lookup import (
        InMemoryAssetLookup,
    )

    kind = "LiquidNitrogen"
    name = f"LN2 cross-asset-{uuid4()}"

    asset_a_id = uuid4()
    asset_b_id = uuid4()
    asset_lookup = InMemoryAssetLookup()
    asset_lookup.register(asset_id=asset_a_id, name="2-BM-A", tier="Unit")
    asset_lookup.register(asset_id=asset_b_id, name="2-BM-B", tier="Unit")

    first_supply_id = uuid4()
    first_deps = build_postgres_deps(
        db_pool,
        now=_T0,
        ids=[first_supply_id, uuid4()],
        asset_lookup=asset_lookup,
    )
    await bind_register(first_deps)(
        RegisterSupply(
            kind=kind,
            name=name,
            facility_code="cora",
            containing_asset_id=asset_a_id,
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    second_supply_id = uuid4()
    second_deps = build_postgres_deps(
        db_pool,
        now=_T1,
        ids=[second_supply_id, uuid4()],
        asset_lookup=asset_lookup,
    )
    await bind_register(second_deps)(
        RegisterSupply(
            kind=kind,
            name=name,
            facility_code="cora",
            containing_asset_id=asset_b_id,
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await _drain(db_pool)

    deps_list = build_postgres_deps(db_pool, ids=[uuid4()], now=_T2)
    page = await bind_list(deps_list)(
        ListSupplies(kind=kind),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    matching = sorted([item.supply_id for item in page.items if item.name == name])
    assert sorted([first_supply_id, second_supply_id]) == matching, (
        f"expected both cross-asset rows to coexist, got {matching}"
    )
