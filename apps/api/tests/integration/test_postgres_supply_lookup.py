"""Integration tests for `PostgresSupplyLookup` against a real Postgres.

Pins the cross-stream query contract under the real Supply projection:
seeds supplies via `register_supply` + `mark_supply_available` +
`deregister_supply` transition handlers, drains the projection
worker, then queries through the adapter and verifies the result
matches the seeded supplies.

Mirrors `tests/integration/test_postgres_clearance_lookup.py`.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from datetime import UTC, datetime
from uuid import UUID, uuid4

import asyncpg
import pytest

from cora.infrastructure.projection import ProjectionRegistry, drain_projections
from cora.supply._projections import register_supply_projections
from cora.supply.adapters import PostgresSupplyLookup
from cora.supply.features import (
    deregister_supply,
    mark_supply_available,
    register_supply,
)
from cora.supply.features.deregister_supply import DeregisterSupply
from cora.supply.features.mark_supply_available import MarkSupplyAvailable
from cora.supply.features.register_supply import RegisterSupply
from tests.integration._helpers import build_postgres_deps

_T0 = datetime(2026, 5, 28, 10, 0, 0, tzinfo=UTC)
_T1 = datetime(2026, 5, 28, 11, 0, 0, tzinfo=UTC)
_T2 = datetime(2026, 5, 28, 12, 0, 0, tzinfo=UTC)
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-00000000c001")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-00000000c002")


async def _drain(db_pool: asyncpg.Pool) -> None:
    registry = ProjectionRegistry()
    register_supply_projections(registry)
    await drain_projections(db_pool, registry, deadline_seconds=2.0)


async def _register_supply(
    db_pool: asyncpg.Pool,
    *,
    supply_id: UUID,
    kind: str,
    name: str,
    now: datetime,
) -> None:
    deps = build_postgres_deps(db_pool, now=now, ids=[supply_id, uuid4()])
    await register_supply.bind(deps)(
        RegisterSupply(kind=kind, name=name, facility_code="cora"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )


async def _mark_available(
    db_pool: asyncpg.Pool,
    *,
    supply_id: UUID,
    now: datetime,
) -> None:
    deps = build_postgres_deps(db_pool, now=now, ids=[uuid4()])
    await mark_supply_available.bind(deps)(
        MarkSupplyAvailable(supply_id=supply_id, reason="walkdown"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )


async def _deregister(
    db_pool: asyncpg.Pool,
    *,
    supply_id: UUID,
    now: datetime,
) -> None:
    deps = build_postgres_deps(db_pool, now=now, ids=[uuid4()])
    await deregister_supply.bind(deps)(
        DeregisterSupply(supply_id=supply_id, reason="typo"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )


@pytest.mark.integration
async def test_find_supplies_by_kind_returns_all_matching_kinds(
    db_pool: asyncpg.Pool,
) -> None:
    """Multiple kinds, multiple supplies per kind; returns grouped by kind."""
    ln2_a, ln2_b, beam = uuid4(), uuid4(), uuid4()
    address_suffix = uuid4()
    await _register_supply(
        db_pool,
        supply_id=ln2_a,
        kind="LiquidNitrogen",
        name=f"LN2-A-{address_suffix}",
        now=_T0,
    )
    await _register_supply(
        db_pool,
        supply_id=ln2_b,
        kind="LiquidNitrogen",
        name=f"LN2-B-{address_suffix}",
        now=_T0,
    )
    await _register_supply(
        db_pool,
        supply_id=beam,
        kind="PhotonBeam",
        name=f"Beam-{address_suffix}",
        now=_T0,
    )
    await _mark_available(db_pool, supply_id=ln2_a, now=_T1)
    await _drain(db_pool)

    lookup = PostgresSupplyLookup(db_pool)
    result = await lookup.find_supplies_by_kind(
        kinds=frozenset({"LiquidNitrogen", "PhotonBeam"}),
    )

    assert set(result.keys()) == {"LiquidNitrogen", "PhotonBeam"}
    ln2_ids = {r.supply_id for r in result["LiquidNitrogen"]}
    assert ln2_ids == {ln2_a, ln2_b}
    assert {r.status for r in result["LiquidNitrogen"] if r.supply_id == ln2_a} == {"Available"}
    assert {r.status for r in result["LiquidNitrogen"] if r.supply_id == ln2_b} == {"Unknown"}
    assert len(result["PhotonBeam"]) == 1
    assert result["PhotonBeam"][0].supply_id == beam


@pytest.mark.integration
async def test_find_supplies_by_kind_excludes_decommissioned(
    db_pool: asyncpg.Pool,
) -> None:
    """Tombstoned supplies don't contribute to gate satisfaction."""
    sup = uuid4()
    name = f"LN2-tomb-{uuid4()}"
    await _register_supply(
        db_pool,
        supply_id=sup,
        kind="LiquidNitrogen",
        name=name,
        now=_T0,
    )
    await _mark_available(db_pool, supply_id=sup, now=_T1)
    await _deregister(db_pool, supply_id=sup, now=_T2)
    await _drain(db_pool)

    lookup = PostgresSupplyLookup(db_pool)
    result = await lookup.find_supplies_by_kind(
        kinds=frozenset({"LiquidNitrogen"}),
    )

    # The decommissioned supply must not appear in any returned bucket.
    assert all(r.supply_id != sup for r in result.get("LiquidNitrogen", []))


@pytest.mark.integration
async def test_find_supplies_by_kind_empty_input_short_circuits(
    db_pool: asyncpg.Pool,
) -> None:
    """Empty kinds set returns empty mapping without hitting PG."""
    lookup = PostgresSupplyLookup(db_pool)
    result = await lookup.find_supplies_by_kind(kinds=frozenset())
    assert result == {}


@pytest.mark.integration
async def test_find_supplies_by_kind_unknown_kind_returns_no_bucket(
    db_pool: asyncpg.Pool,
) -> None:
    """Requested kind with zero registered Supplies is absent from the mapping
    (the decider interprets absence as the missing-kind rejection path)."""
    lookup = PostgresSupplyLookup(db_pool)
    result = await lookup.find_supplies_by_kind(kinds=frozenset({"NeverRegisteredKind"}))
    assert "NeverRegisteredKind" not in result


@pytest.mark.integration
async def test_find_supplies_by_name_returns_matching_row(
    db_pool: asyncpg.Pool,
) -> None:
    """Happy path: the (name, facility_code, kind) match is returned with status."""
    sup = uuid4()
    name = f"primary-store-{uuid4()}"
    await _register_supply(db_pool, supply_id=sup, kind="Storage", name=name, now=_T0)
    await _mark_available(db_pool, supply_id=sup, now=_T1)
    await _drain(db_pool)

    lookup = PostgresSupplyLookup(db_pool)
    result = await lookup.find_supplies_by_name(name=name, facility_code="cora", kind="Storage")

    assert [r.supply_id for r in result] == [sup]
    assert result[0].status == "Available"
    assert result[0].kind == "Storage"
    assert result[0].facility_code == "cora"


@pytest.mark.integration
async def test_find_supplies_by_name_excludes_decommissioned(
    db_pool: asyncpg.Pool,
) -> None:
    """Tombstoned same-name Supply is excluded at the query layer.

    Pins the `status != 'Decommissioned'` clause directly: deregister
    UPDATEs the projection row to status='Decommissioned' (it is not
    physically deleted), and the query must still exclude it.
    """
    sup = uuid4()
    name = f"ephemeral-store-{uuid4()}"
    await _register_supply(db_pool, supply_id=sup, kind="Storage", name=name, now=_T0)
    await _mark_available(db_pool, supply_id=sup, now=_T1)
    await _deregister(db_pool, supply_id=sup, now=_T2)
    await _drain(db_pool)

    lookup = PostgresSupplyLookup(db_pool)
    result = await lookup.find_supplies_by_name(name=name, facility_code="cora", kind="Storage")

    assert result == []


@pytest.mark.integration
async def test_find_supplies_by_name_scopes_by_facility_and_kind(
    db_pool: asyncpg.Pool,
) -> None:
    """A match requires name AND facility_code AND kind; a wrong scope returns []."""
    sup = uuid4()
    name = f"scoped-store-{uuid4()}"
    await _register_supply(db_pool, supply_id=sup, kind="Storage", name=name, now=_T0)
    await _mark_available(db_pool, supply_id=sup, now=_T1)
    await _drain(db_pool)

    lookup = PostgresSupplyLookup(db_pool)
    wrong_facility = await lookup.find_supplies_by_name(
        name=name, facility_code="other-facility", kind="Storage"
    )
    wrong_kind = await lookup.find_supplies_by_name(
        name=name, facility_code="cora", kind="Consumable"
    )
    assert wrong_facility == []
    assert wrong_kind == []
