"""End-to-end: `list_conduits` handler against real Postgres
projection table.

Pins the INSERT round-trip through the full projection path
(ConduitDefined -> proj_trust_conduit_summary INSERT) including the
two endpoint-zone UUID columns surfacing as filter targets.

  - Sanity: ConduitDefined inserts a row with both endpoint zones.
  - source_zone_id filter narrows results to one of two conduits.
  - target_zone_id filter narrows results to one of two conduits.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from datetime import UTC, datetime
from uuid import UUID, uuid4

import asyncpg
import pytest

from cora.infrastructure.kernel import Kernel
from cora.infrastructure.projection import ProjectionRegistry, drain_projections
from cora.trust._projections import register_trust_projections
from cora.trust.features.define_conduit import DefineConduit
from cora.trust.features.define_conduit import bind as bind_define_conduit
from cora.trust.features.list_conduits import ListConduits
from cora.trust.features.list_conduits import bind as bind_list
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


def _conduit_ids(conduit_id: UUID) -> list[UUID]:
    """4 ids consumed by define_conduit:
    conduit_id + verdict_logbook_id + 2 event_ids."""
    return [conduit_id, uuid4(), uuid4(), uuid4()]


@pytest.mark.integration
async def test_conduit_defined_inserts_both_endpoint_zones(
    db_pool: asyncpg.Pool,
) -> None:
    conduit_id = uuid4()
    source_zone = uuid4()
    target_zone = uuid4()
    deps = _build_deps(db_pool, _conduit_ids(conduit_id))
    await bind_define_conduit(deps)(
        DefineConduit(
            name="DetectorToStorage",
            source_zone_id=source_zone,
            target_zone_id=target_zone,
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await _drain(db_pool)

    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT conduit_id, name, source_zone_id, target_zone_id, created_at "
            "FROM proj_trust_conduit_summary WHERE conduit_id = $1",
            conduit_id,
        )
    assert row is not None
    assert row["name"] == "DetectorToStorage"
    assert row["source_zone_id"] == source_zone
    assert row["target_zone_id"] == target_zone
    assert row["created_at"] == _NOW


@pytest.mark.integration
async def test_source_zone_filter_narrows_results(db_pool: asyncpg.Pool) -> None:
    source_a = uuid4()
    source_b = uuid4()
    target = uuid4()

    conduit_a = uuid4()
    deps_a = _build_deps(db_pool, _conduit_ids(conduit_a))
    await bind_define_conduit(deps_a)(
        DefineConduit(name="from-a", source_zone_id=source_a, target_zone_id=target),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    conduit_b = uuid4()
    deps_b = _build_deps(db_pool, _conduit_ids(conduit_b))
    await bind_define_conduit(deps_b)(
        DefineConduit(name="from-b", source_zone_id=source_b, target_zone_id=target),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    await _drain(db_pool)
    handler = bind_list(deps_a)
    page = await handler(
        ListConduits(source_zone_id=source_a, limit=10),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert len(page.items) == 1
    assert page.items[0].conduit_id == conduit_a
    assert page.items[0].source_zone_id == source_a


@pytest.mark.integration
async def test_target_zone_filter_narrows_results(db_pool: asyncpg.Pool) -> None:
    source = uuid4()
    target_a = uuid4()
    target_b = uuid4()

    conduit_a = uuid4()
    deps_a = _build_deps(db_pool, _conduit_ids(conduit_a))
    await bind_define_conduit(deps_a)(
        DefineConduit(name="to-a", source_zone_id=source, target_zone_id=target_a),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    conduit_b = uuid4()
    deps_b = _build_deps(db_pool, _conduit_ids(conduit_b))
    await bind_define_conduit(deps_b)(
        DefineConduit(name="to-b", source_zone_id=source, target_zone_id=target_b),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    await _drain(db_pool)
    handler = bind_list(deps_a)
    page = await handler(
        ListConduits(target_zone_id=target_b, limit=10),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert len(page.items) == 1
    assert page.items[0].conduit_id == conduit_b
    assert page.items[0].target_zone_id == target_b


@pytest.mark.integration
async def test_empty_table_returns_empty_page(db_pool: asyncpg.Pool) -> None:
    deps = _build_deps(db_pool, [])
    handler = bind_list(deps)
    page = await handler(
        ListConduits(),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert page.items == []
    assert page.next_cursor is None
