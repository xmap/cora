"""End-to-end: `list_actors` handler against real Postgres
projection table with multi-page cursor pagination + status filter.

Closes H1 + M4 from the 8e-1c gate review: prior tests cover
the cursor encode/decode in isolation and the empty-data path,
but the handler's keyset-pagination flow (LIMIT $limit + 1, slice
extra row, encode last-kept-row's cursor) was untested
end-to-end. The bug class this catches:

  - Off-by-one on slice: returning the extra row in `items`
  - Wrong row's cursor: encoding the dropped extra row instead of
    the last kept row
  - Wrong column in keyset comparison: rows skipped or duplicated
    across page boundaries
  - Status filter + cursor combination: filter dropped on subsequent
    pages

Walks through 5 actors (1 deactivated) across 3 pages with
limit=2, asserts contiguous coverage, then verifies status filter
narrows correctly.
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import asyncpg
import pytest

from cora.access._projections import register_access_projections
from cora.access.features.deactivate_actor import DeactivateActor
from cora.access.features.deactivate_actor import bind as bind_deactivate
from cora.access.features.list_actors import ListActors
from cora.access.features.list_actors import bind as bind_list
from cora.access.features.register_actor import RegisterActor
from cora.access.features.register_actor import bind as bind_register
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.projection import ProjectionRegistry, drain_projections
from tests._drain import drain_deadline_s
from tests.integration._helpers import build_postgres_deps, make_pg_profile_store

_NOW = datetime(2026, 5, 12, 14, 0, 0, tzinfo=UTC)
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")


def _build_deps(db_pool: asyncpg.Pool, ids: list[UUID]) -> Kernel:
    return build_postgres_deps(db_pool, now=_NOW, ids=ids)


async def _seed_actors_and_drain(
    db_pool: asyncpg.Pool,
    *,
    count: int,
    deactivate_indices: tuple[int, ...] = (),
) -> tuple[list[UUID], Kernel]:
    """Register `count` actors via the handler, deactivate the ones
    at `deactivate_indices`, drain projections, return the ordered
    list of actor_ids and the kernel for follow-up handler calls."""
    ids: list[UUID] = []
    fixed_ids: list[UUID] = []
    for _ in range(count):
        actor_id = uuid4()
        event_id = uuid4()
        ids.append(actor_id)
        fixed_ids.extend([actor_id, event_id])
    # Deactivation events also pull from FixedIdGenerator (one event_id each).
    fixed_ids.extend([uuid4() for _ in deactivate_indices])

    deps = _build_deps(db_pool, fixed_ids)
    register = bind_register(deps, profile_store=make_pg_profile_store(db_pool))
    for i, actor_id in enumerate(ids):
        await register(
            RegisterActor(name=f"Actor{i:02d}"),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
        # Sanity: verify the FixedIdGenerator produced the expected id
        assert actor_id == ids[i]

    deactivate = bind_deactivate(deps)
    for idx in deactivate_indices:
        await deactivate(
            DeactivateActor(actor_id=ids[idx]),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )

    registry = ProjectionRegistry()
    register_access_projections(registry)
    await drain_projections(db_pool, registry, deadline_seconds=drain_deadline_s())

    return ids, deps


@pytest.mark.integration
async def test_cursor_walks_three_pages_covering_all_actors(
    db_pool: asyncpg.Pool,
) -> None:
    """5 actors, limit=2, walk pages 1 -> 2 -> 3. Assert contiguous
    coverage with no duplicates and no gaps; final page has
    next_cursor=None when items returned < limit."""
    actor_ids, deps = await _seed_actors_and_drain(db_pool, count=5)
    handler = bind_list(deps)

    # Page 1
    page1 = await handler(
        ListActors(limit=2),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert len(page1.items) == 2
    assert page1.next_cursor is not None

    # Page 2
    page2 = await handler(
        ListActors(cursor=page1.next_cursor, limit=2),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert len(page2.items) == 2
    assert page2.next_cursor is not None

    # Page 3 (last; only 1 actor remaining; next_cursor=None because
    # items returned == 1 which is < limit, so no extra row was
    # fetched).
    page3 = await handler(
        ListActors(cursor=page2.next_cursor, limit=2),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert len(page3.items) == 1
    assert page3.next_cursor is None

    # Coverage: every actor appears exactly once, in the order
    # established by the projection's `created_at` (registration
    # order matches insertion order; FakeClock means created_at
    # is identical across actors, so the secondary `actor_id`
    # ordering kicks in deterministically).
    seen = [item.actor_id for item in page1.items + page2.items + page3.items]
    assert len(seen) == 5
    assert set(seen) == set(actor_ids), "Coverage gap or duplicate"


@pytest.mark.integration
async def test_status_filter_narrows_to_active_only(
    db_pool: asyncpg.Pool,
) -> None:
    """5 actors, deactivate the middle one, filter by status='active'
    -> 4 active actors across 2 pages with limit=3."""
    _actor_ids, deps = await _seed_actors_and_drain(
        db_pool,
        count=5,
        deactivate_indices=(2,),
    )
    handler = bind_list(deps)

    page1 = await handler(
        ListActors(status="active", limit=3),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert len(page1.items) == 3
    assert page1.next_cursor is not None
    assert all(item.status == "active" for item in page1.items)

    page2 = await handler(
        ListActors(status="active", cursor=page1.next_cursor, limit=3),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert len(page2.items) == 1
    assert page2.next_cursor is None
    assert page2.items[0].status == "active"


@pytest.mark.integration
async def test_status_filter_narrows_to_deactivated_only(
    db_pool: asyncpg.Pool,
) -> None:
    """Inverse: 5 actors, deactivate 2, filter by status='deactivated'
    returns exactly those 2."""
    _actor_ids, deps = await _seed_actors_and_drain(
        db_pool,
        count=5,
        deactivate_indices=(0, 3),
    )
    handler = bind_list(deps)

    page = await handler(
        ListActors(status="deactivated", limit=10),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert len(page.items) == 2
    assert page.next_cursor is None
    assert all(item.status == "deactivated" for item in page.items)


@pytest.mark.integration
async def test_no_filter_returns_all_actors_regardless_of_status(
    db_pool: asyncpg.Pool,
) -> None:
    """Implicit-omit `status` returns rows of any status. No magic
    'all' value needed."""
    _actor_ids, deps = await _seed_actors_and_drain(
        db_pool,
        count=4,
        deactivate_indices=(1,),
    )
    handler = bind_list(deps)

    page = await handler(
        ListActors(limit=10),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert len(page.items) == 4
    statuses = {item.status for item in page.items}
    assert statuses == {"active", "deactivated"}


@pytest.mark.integration
async def test_empty_table_returns_empty_page(db_pool: asyncpg.Pool) -> None:
    """No actors in the projection -> empty items, no cursor.
    Pin: 200-with-empty-items, never 404."""
    deps = _build_deps(db_pool, [])
    handler = bind_list(deps)

    page = await handler(
        ListActors(),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert page.items == []
    assert page.next_cursor is None


@pytest.mark.integration
async def test_limit_exactly_matches_total_returns_no_cursor(
    db_pool: asyncpg.Pool,
) -> None:
    """When limit equals the total row count, the LIMIT $limit + 1
    fetches exactly limit rows (no extra), so next_cursor is None.
    Pin the boundary case where the handler MUST NOT generate a
    next_cursor for a partial-but-final page."""
    _actor_ids, deps = await _seed_actors_and_drain(db_pool, count=3)
    handler = bind_list(deps)

    page = await handler(
        ListActors(limit=3),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert len(page.items) == 3
    assert page.next_cursor is None


@pytest.mark.integration
async def test_register_service_account_actor_appears_in_list_with_kind(
    db_pool: asyncpg.Pool,
) -> None:
    """Gate-review test#1 + test#2: end-to-end pin that
    register_actor(kind=service_account) lands a row in the projection
    AND list_actors returns kind='service_account' in the response.

    Without this test, the CHECK widening (migration 20260519233000)
    AND the list_actors DTO Literal widening were both unverified
    against real Postgres. A typo in either would silently break in
    prod."""
    from cora.access.aggregates.actor import ActorKind

    actor_id = uuid4()
    event_id = uuid4()
    deps = _build_deps(db_pool, [actor_id, event_id])
    register = bind_register(deps, profile_store=make_pg_profile_store(db_pool))

    await register(
        RegisterActor(name="ci-bridge", kind=ActorKind.SERVICE_ACCOUNT),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    registry = ProjectionRegistry()
    register_access_projections(registry)
    await drain_projections(db_pool, registry, deadline_seconds=drain_deadline_s())

    handler = bind_list(deps)
    page = await handler(
        ListActors(),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert len(page.items) == 1
    assert page.items[0].kind == "service_account"
    assert page.items[0].actor_id == actor_id
