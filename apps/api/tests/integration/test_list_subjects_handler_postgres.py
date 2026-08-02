"""End-to-end: `list_subjects` handler against real Postgres
projection table with multi-page cursor pagination + status filter
across the Subject lifecycle.

The Subject BC's 7-event lifecycle gives this test more variety
than `list_actors_handler_postgres` (which only had active /
deactivated). Walks several subjects through different terminal
states and exercises the status filter on each.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from datetime import UTC, datetime
from uuid import UUID, uuid4

import asyncpg
import pytest

from cora.infrastructure.kernel import Kernel
from cora.infrastructure.projection import ProjectionRegistry, drain_projections
from cora.subject._projections import register_subject_projections
from cora.subject.features.discard_subject import DiscardSubject
from cora.subject.features.discard_subject import bind as bind_discard
from cora.subject.features.list_subjects import ListSubjects
from cora.subject.features.list_subjects import bind as bind_list
from cora.subject.features.measure_subject import MeasureSubject
from cora.subject.features.measure_subject import bind as bind_measure
from cora.subject.features.mount_subject import MountSubject
from cora.subject.features.mount_subject import bind as bind_mount
from cora.subject.features.register_subject import RegisterSubject
from cora.subject.features.register_subject import bind as bind_register
from cora.subject.features.remove_subject import RemoveSubject
from cora.subject.features.remove_subject import bind as bind_remove
from cora.subject.features.return_subject import ReturnSubject
from cora.subject.features.return_subject import bind as bind_return
from tests._drain import drain_deadline_s
from tests.integration._helpers import build_postgres_deps
from tests.unit.subject._helpers import seed_active_asset

_NOW = datetime(2026, 5, 12, 14, 0, 0, tzinfo=UTC)
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")


def _build_deps(db_pool: asyncpg.Pool, ids: list[UUID]) -> Kernel:
    return build_postgres_deps(db_pool, now=_NOW, ids=ids)


async def _seed_subjects(db_pool: asyncpg.Pool, count: int) -> tuple[list[UUID], Kernel]:
    """Register `count` subjects (all in Received status). Returns
    ordered list of subject_ids and the kernel for follow-up commands."""
    fixed_ids: list[UUID] = []
    subject_ids: list[UUID] = []
    for _ in range(count):
        sid = uuid4()
        eid = uuid4()
        subject_ids.append(sid)
        fixed_ids.extend([sid, eid])

    deps = _build_deps(db_pool, fixed_ids)
    register = bind_register(deps)
    for i, sid in enumerate(subject_ids):
        returned = await register(
            RegisterSubject(name=f"Sample-{i:02d}"),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
        assert returned == sid

    return subject_ids, deps


async def _drain(db_pool: asyncpg.Pool) -> None:
    registry = ProjectionRegistry()
    register_subject_projections(registry)
    await drain_projections(db_pool, registry, deadline_seconds=drain_deadline_s())


@pytest.mark.integration
async def test_register_emits_received_status_in_proj_table(
    db_pool: asyncpg.Pool,
) -> None:
    """Sanity: a freshly-registered subject lands as status='Received'."""
    subject_ids, _deps = await _seed_subjects(db_pool, 1)
    await _drain(db_pool)

    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT name, status FROM proj_subject_summary WHERE subject_id = $1",
            subject_ids[0],
        )
    assert row is not None
    assert row["name"] == "Sample-00"
    assert row["status"] == "Received"


@pytest.mark.integration
async def test_full_lifecycle_transitions_status_through_all_phases(
    db_pool: asyncpg.Pool,
) -> None:
    """Walk one subject through Received -> Mounted -> Measured ->
    Removed -> Returned (terminal). Verify the projection reflects
    each transition. Pin: each event_type maps to its expected
    status string in the read model."""
    sid = uuid4()
    register_eid = uuid4()
    mount_eid = uuid4()
    measure_eid = uuid4()
    remove_eid = uuid4()
    return_eid = uuid4()
    deps = _build_deps(
        db_pool,
        [sid, register_eid, mount_eid, measure_eid, remove_eid, return_eid],
    )

    await bind_register(deps)(
        RegisterSubject(name="LifecycleSample"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await _drain(db_pool)
    await _assert_status(db_pool, sid, "Received")

    asset_id = await seed_active_asset(deps.event_store, now=_NOW, correlation_id=_CORRELATION_ID)
    await bind_mount(deps)(
        MountSubject(subject_id=sid, asset_id=asset_id, reason=""),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await _drain(db_pool)
    await _assert_status(db_pool, sid, "Mounted")

    await bind_measure(deps)(
        MeasureSubject(subject_id=sid),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await _drain(db_pool)
    await _assert_status(db_pool, sid, "Measured")

    await bind_remove(deps)(
        RemoveSubject(subject_id=sid),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await _drain(db_pool)
    await _assert_status(db_pool, sid, "Removed")

    await bind_return(deps)(
        ReturnSubject(subject_id=sid),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await _drain(db_pool)
    await _assert_status(db_pool, sid, "Returned")


async def _assert_status(db_pool: asyncpg.Pool, subject_id: UUID, expected: str) -> None:
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT status FROM proj_subject_summary WHERE subject_id = $1",
            subject_id,
        )
    assert row is not None
    assert row["status"] == expected, f"Expected {expected}, got {row['status']}"


@pytest.mark.integration
async def test_cursor_walks_three_pages_covering_all_subjects(
    db_pool: asyncpg.Pool,
) -> None:
    subject_ids, deps = await _seed_subjects(db_pool, 5)
    await _drain(db_pool)
    handler = bind_list(deps)

    page1 = await handler(
        ListSubjects(limit=2),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    page2 = await handler(
        ListSubjects(cursor=page1.next_cursor, limit=2),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    page3 = await handler(
        ListSubjects(cursor=page2.next_cursor, limit=2),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    assert len(page1.items) == 2 and page1.next_cursor is not None
    assert len(page2.items) == 2 and page2.next_cursor is not None
    assert len(page3.items) == 1 and page3.next_cursor is None

    seen = {item.subject_id for p in (page1, page2, page3) for item in p.items}
    assert seen == set(subject_ids), "Coverage gap or duplicate"


@pytest.mark.integration
async def test_status_filter_narrows_to_mounted_only(
    db_pool: asyncpg.Pool,
) -> None:
    """5 subjects: register all, mount 2 of them, filter status=Mounted."""
    base_ids: list[UUID] = []
    fixed_ids: list[UUID] = []
    for _ in range(5):
        sid = uuid4()
        base_ids.append(sid)
        fixed_ids.extend([sid, uuid4()])
    # Two mount events follow; each consumes one event_id
    fixed_ids.extend([uuid4(), uuid4()])
    deps = _build_deps(db_pool, fixed_ids)

    register = bind_register(deps)
    for i in range(len(base_ids)):
        await register(
            RegisterSubject(name=f"Sample-{i:02d}"),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )

    asset_id = await seed_active_asset(deps.event_store, now=_NOW, correlation_id=_CORRELATION_ID)
    mount = bind_mount(deps)
    for sid in (base_ids[1], base_ids[3]):
        await mount(
            MountSubject(subject_id=sid, asset_id=asset_id, reason=""),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )

    await _drain(db_pool)
    handler = bind_list(deps)
    page = await handler(
        ListSubjects(status="Mounted", limit=10),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert len(page.items) == 2
    assert all(item.status == "Mounted" for item in page.items)
    assert {item.subject_id for item in page.items} == {base_ids[1], base_ids[3]}


@pytest.mark.integration
async def test_status_filter_narrows_to_discarded_terminal(
    db_pool: asyncpg.Pool,
) -> None:
    """One subject through register -> mount -> remove -> discard."""
    sid = uuid4()
    deps = _build_deps(
        db_pool,
        [sid, uuid4(), uuid4(), uuid4(), uuid4()],
    )
    await bind_register(deps)(
        RegisterSubject(name="Doomed"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    asset_id = await seed_active_asset(deps.event_store, now=_NOW, correlation_id=_CORRELATION_ID)
    await bind_mount(deps)(
        MountSubject(subject_id=sid, asset_id=asset_id, reason=""),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await bind_remove(deps)(
        RemoveSubject(subject_id=sid),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await bind_discard(deps)(
        DiscardSubject(subject_id=sid, reason="contaminated; biohazard incinerator"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await _drain(db_pool)

    handler = bind_list(deps)
    page = await handler(
        ListSubjects(status="Discarded"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert len(page.items) == 1
    assert page.items[0].subject_id == sid
    assert page.items[0].status == "Discarded"


@pytest.mark.integration
async def test_empty_table_returns_empty_page(db_pool: asyncpg.Pool) -> None:
    deps = _build_deps(db_pool, [])
    handler = bind_list(deps)
    page = await handler(
        ListSubjects(),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert page.items == []
    assert page.next_cursor is None
