"""End-to-end: `list_procedures` handler against real Postgres projection table.

Pins the genesis -> transition fold + projection writes:

  - ProcedureRegistered          -> INSERT (status='Defined', last_status_*=NULL,
                                            interrupted_at=NULL, activity_logbook_id=NULL)
  - ProcedureStarted             -> UPDATE status='Running' + last_status_changed_at
  - ProcedureCompleted           -> UPDATE status='Completed' + last_status_changed_at
  - ProcedureAborted             -> UPDATE status='Aborted' + audit triple
  - ProcedureTruncated           -> UPDATE status='Truncated' + reason + interrupted_at
  - ProcedureActivitiesLogbookOpened  -> UPDATE activity_logbook_id (lazy-open envelope)
  - status / kind / parent_run_id / target_asset_id (UUID[] GIN) filters
  - cursor pagination
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from datetime import UTC, datetime
from uuid import UUID, uuid4

import asyncpg
import pytest

from cora.infrastructure.kernel import Kernel
from cora.infrastructure.projection import ProjectionRegistry, drain_projections
from cora.operation._projections import register_operation_projections
from cora.operation.features.complete_procedure import CompleteProcedure
from cora.operation.features.complete_procedure import bind as bind_complete
from cora.operation.features.list_procedures import ListProcedures
from cora.operation.features.list_procedures import bind as bind_list
from cora.operation.features.register_procedure import RegisterProcedure
from cora.operation.features.register_procedure import bind as bind_register
from cora.operation.features.start_procedure import StartProcedure
from cora.operation.features.start_procedure import bind as bind_start
from cora.operation.features.truncate_procedure import TruncateProcedure
from cora.operation.features.truncate_procedure import bind as bind_truncate
from tests.integration._helpers import build_postgres_deps

_NOW = datetime(2026, 5, 15, 12, 0, 0, tzinfo=UTC)
_LATER = datetime(2026, 5, 15, 13, 0, 0, tzinfo=UTC)
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")


def _build_deps(db_pool: asyncpg.Pool, ids: list[UUID], now: datetime = _NOW) -> Kernel:
    return build_postgres_deps(db_pool, now=now, ids=ids)


async def _drain(db_pool: asyncpg.Pool) -> None:
    registry = ProjectionRegistry()
    register_operation_projections(registry)
    await drain_projections(db_pool, registry, deadline_seconds=2.0)


@pytest.mark.integration
async def test_register_inserts_defined_status_with_null_audit_columns(
    db_pool: asyncpg.Pool,
) -> None:
    """ProcedureRegistered -> projection row in 'Defined' with last_status_* NULL."""
    proc_id = uuid4()
    deps = _build_deps(db_pool, [proc_id, uuid4()])
    await bind_register(deps)(
        RegisterProcedure(name="Vessel-A bakeout", kind="bakeout"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await _drain(db_pool)

    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT name, kind, status, target_asset_ids, parent_run_id, "
            "activity_logbook_id, last_status_changed_at, last_status_reason, "
            "interrupted_at "
            "FROM proj_operation_procedure_summary WHERE procedure_id = $1",
            proc_id,
        )
    assert row is not None
    assert row["name"] == "Vessel-A bakeout"
    assert row["kind"] == "bakeout"
    assert row["status"] == "Defined"
    assert list(row["target_asset_ids"]) == []
    assert row["parent_run_id"] is None
    assert row["activity_logbook_id"] is None
    assert row["last_status_changed_at"] is None
    assert row["last_status_reason"] is None
    assert row["interrupted_at"] is None


@pytest.mark.integration
async def test_full_lifecycle_truncate_path_lands_in_projection(
    db_pool: asyncpg.Pool,
) -> None:
    """Register -> Start -> Truncate roundtrips all status + audit fields."""
    proc_id = uuid4()
    deps = _build_deps(db_pool, [proc_id, uuid4(), uuid4(), uuid4()])
    await bind_register(deps)(
        RegisterProcedure(name="Bakeout", kind="bakeout"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await bind_start(deps)(
        StartProcedure(procedure_id=proc_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    deps2 = _build_deps(db_pool, [uuid4()], now=_LATER)
    await bind_truncate(deps2)(
        TruncateProcedure(
            procedure_id=proc_id,
            reason="weekend power loss",
            interrupted_at=_NOW,
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await _drain(db_pool)

    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT status, last_status_changed_at, last_status_reason, interrupted_at "
            "FROM proj_operation_procedure_summary WHERE procedure_id = $1",
            proc_id,
        )
    assert row is not None
    assert row["status"] == "Truncated"
    assert row["last_status_changed_at"] == _LATER
    assert row["last_status_reason"] == "weekend power loss"
    assert row["interrupted_at"] == _NOW


@pytest.mark.integration
async def test_list_filters_by_status(db_pool: asyncpg.Pool) -> None:
    """Status filter narrows results to one ProcedureStatus value."""
    defined_id = uuid4()
    completed_id = uuid4()
    deps = _build_deps(
        db_pool,
        [defined_id, uuid4(), completed_id, uuid4(), uuid4(), uuid4()],
    )
    # Defined-only procedure
    await bind_register(deps)(
        RegisterProcedure(name="A", kind="bakeout"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    # Completed-path procedure (register + start + complete)
    await bind_register(deps)(
        RegisterProcedure(name="B", kind="bakeout"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await bind_start(deps)(
        StartProcedure(procedure_id=completed_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await bind_complete(deps)(
        CompleteProcedure(procedure_id=completed_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await _drain(db_pool)

    page = await bind_list(deps)(
        ListProcedures(status="Completed"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    procedure_ids = {item.procedure_id for item in page.items}
    assert completed_id in procedure_ids
    assert defined_id not in procedure_ids


@pytest.mark.integration
async def test_list_filters_by_kind(db_pool: asyncpg.Pool) -> None:
    """Kind filter narrows results to one bare-str discriminator."""
    bakeout_id = uuid4()
    alignment_id = uuid4()
    deps = _build_deps(db_pool, [bakeout_id, uuid4(), alignment_id, uuid4()])
    await bind_register(deps)(
        RegisterProcedure(name="Vessel-A bakeout", kind="bakeout"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await bind_register(deps)(
        RegisterProcedure(name="2-BM alignment", kind="alignment"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await _drain(db_pool)

    page = await bind_list(deps)(
        ListProcedures(kind="alignment"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    procedure_ids = {item.procedure_id for item in page.items}
    assert alignment_id in procedure_ids
    assert bakeout_id not in procedure_ids


@pytest.mark.integration
async def test_list_filters_by_parent_run_id(db_pool: asyncpg.Pool) -> None:
    """parent_run_id filter (Phase-of-Run) narrows results."""
    parent_run = uuid4()
    phase_id = uuid4()
    standalone_id = uuid4()
    deps = _build_deps(db_pool, [phase_id, uuid4(), standalone_id, uuid4()])
    await bind_register(deps)(
        RegisterProcedure(name="Mid-run alignment", kind="alignment", parent_run_id=parent_run),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await bind_register(deps)(
        RegisterProcedure(name="Standalone bakeout", kind="bakeout"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await _drain(db_pool)

    page = await bind_list(deps)(
        ListProcedures(parent_run_id=parent_run),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    procedure_ids = {item.procedure_id for item in page.items}
    assert phase_id in procedure_ids
    assert standalone_id not in procedure_ids


@pytest.mark.integration
async def test_list_filters_by_target_asset_id_via_gin_index(
    db_pool: asyncpg.Pool,
) -> None:
    """target_asset_id filter uses `WHERE $1 = ANY(target_asset_ids)`."""
    asset_a = uuid4()
    asset_b = uuid4()
    targets_a_id = uuid4()
    targets_b_id = uuid4()
    deps = _build_deps(db_pool, [targets_a_id, uuid4(), targets_b_id, uuid4()])
    await bind_register(deps)(
        RegisterProcedure(
            name="Aligns asset A",
            kind="alignment",
            target_asset_ids=frozenset({asset_a}),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await bind_register(deps)(
        RegisterProcedure(
            name="Aligns asset B",
            kind="alignment",
            target_asset_ids=frozenset({asset_b}),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await _drain(db_pool)

    page = await bind_list(deps)(
        ListProcedures(target_asset_id=asset_a),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    procedure_ids = {item.procedure_id for item in page.items}
    assert targets_a_id in procedure_ids
    assert targets_b_id not in procedure_ids


@pytest.mark.integration
async def test_list_paginates_with_cursor(db_pool: asyncpg.Pool) -> None:
    """Keyset cursor returns disjoint pages with no within-page duplicates.

    Uses a unique `kind=` per test (sibling test_list_filters_by_kind proves
    filters work) to scope the projection rows down to just the 3 this test
    creates, avoiding cross-test pollution and allowing strict assertions.
    """
    unique_kind = f"pagination-test-{uuid4().hex}"
    ids_a = [uuid4() for _ in range(3)]
    deps = _build_deps(
        db_pool,
        [ids_a[0], uuid4(), ids_a[1], uuid4(), ids_a[2], uuid4()],
    )
    for i in range(3):
        await bind_register(deps)(
            RegisterProcedure(name=f"P{i}", kind=unique_kind),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    await _drain(db_pool)

    deps2 = _build_deps(db_pool, [])
    first_page = await bind_list(deps2)(
        ListProcedures(limit=2, kind=unique_kind),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    # Page 1 must be exactly 2 + signal there's a next page.
    assert len(first_page.items) == 2
    assert first_page.next_cursor is not None
    # Within-page no-duplicates invariant.
    seen_first = {item.procedure_id for item in first_page.items}
    assert len(seen_first) == 2

    second_page = await bind_list(deps2)(
        ListProcedures(limit=2, kind=unique_kind, cursor=first_page.next_cursor),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    # Page 2 must contain the third row.
    assert len(second_page.items) == 1
    seen_second = {item.procedure_id for item in second_page.items}
    # Disjoint pages.
    assert seen_first.isdisjoint(seen_second)
    # Together cover all 3 procedures.
    assert seen_first | seen_second == set(ids_a)
