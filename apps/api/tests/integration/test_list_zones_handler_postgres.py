"""End-to-end: `list_zones` handler against real Postgres projection
table.

Trust's Zone aggregate is the simplest of the 8 projection-backed
aggregates: one event (ZoneDefined), no cross-aggregate refs, no
lifecycle status today. This test pins the INSERT round-trip + the
keyset cursor advance through real PG.

  - Sanity: ZoneDefined inserts a row with the right name + created_at.
  - Two zones, second-page cursor returns the second zone.
  - Empty table returns empty page + null next_cursor.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from datetime import UTC, datetime
from uuid import UUID, uuid4

import asyncpg
import pytest

from cora.infrastructure.kernel import Kernel
from cora.infrastructure.projection import ProjectionRegistry, drain_projections
from cora.trust._projections import register_trust_projections
from cora.trust.features.define_zone import DefineZone
from cora.trust.features.define_zone import bind as bind_define_zone
from cora.trust.features.list_zones import ListZones
from cora.trust.features.list_zones import bind as bind_list
from tests._drain import drain_deadline_s
from tests.integration._helpers import build_postgres_deps

_NOW = datetime(2026, 5, 13, 12, 0, 0, tzinfo=UTC)
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")


def _build_deps(db_pool: asyncpg.Pool, ids: list[UUID]) -> Kernel:
    return build_postgres_deps(db_pool, now=_NOW, ids=ids)


async def _drain(db_pool: asyncpg.Pool) -> None:
    """Drain Trust projections."""
    registry = ProjectionRegistry()
    register_trust_projections(registry)
    await drain_projections(db_pool, registry, deadline_seconds=drain_deadline_s())


@pytest.mark.integration
async def test_zone_defined_inserts_with_name_and_created_at(
    db_pool: asyncpg.Pool,
) -> None:
    zone_id = uuid4()
    deps = _build_deps(db_pool, [zone_id, uuid4()])
    await bind_define_zone(deps)(
        DefineZone(name="Detector"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await _drain(db_pool)

    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT zone_id, name, created_at FROM proj_trust_zone_summary WHERE zone_id = $1",
            zone_id,
        )
    assert row is not None
    assert row["zone_id"] == zone_id
    assert row["name"] == "Detector"
    assert row["created_at"] == _NOW


@pytest.mark.integration
async def test_handler_returns_zones_in_keyset_order(
    db_pool: asyncpg.Pool,
) -> None:
    """Two zones land; list returns both in (created_at, zone_id) order."""
    zone_a = uuid4()
    deps_a = _build_deps(db_pool, [zone_a, uuid4()])
    await bind_define_zone(deps_a)(
        DefineZone(name="ZoneAlpha"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    zone_b = uuid4()
    deps_b = _build_deps(db_pool, [zone_b, uuid4()])
    await bind_define_zone(deps_b)(
        DefineZone(name="ZoneBeta"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    await _drain(db_pool)

    handler = bind_list(deps_a)
    page = await handler(
        ListZones(limit=10),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    returned_ids = {item.zone_id for item in page.items}
    assert zone_a in returned_ids
    assert zone_b in returned_ids


@pytest.mark.integration
async def test_empty_table_returns_empty_page(db_pool: asyncpg.Pool) -> None:
    deps = _build_deps(db_pool, [])
    handler = bind_list(deps)
    page = await handler(
        ListZones(),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert page.items == []
    assert page.next_cursor is None
