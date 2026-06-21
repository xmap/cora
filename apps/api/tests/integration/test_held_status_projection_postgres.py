"""End-to-end: the Held/Resumed FSM drives `status` in the
`proj_operation_procedure_summary` read model against real Postgres.

This is the only place the widened status CHECK (migration
20260621060000, admitting 'Held') is actually exercised: the projection
unit tests use a mocked connection, so the column constraint is enforced
only here.

Pins:
  - ProcedureHeld folds to status='Held' + last_status_reason (the hold
    reason), proving the CHECK admits 'Held'.
  - ProcedureResumed folds back to status='Running' and clears
    last_status_reason (Running is not reason-bearing).
  - The list_procedures read path surfaces + filters on status='Held'.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from datetime import UTC, datetime
from uuid import UUID, uuid4

import asyncpg
import pytest

from cora.infrastructure.kernel import Kernel
from cora.infrastructure.projection import ProjectionRegistry, drain_projections
from cora.operation._projections import register_operation_projections
from cora.operation.features.hold_procedure import HoldProcedure
from cora.operation.features.hold_procedure import bind as bind_hold
from cora.operation.features.list_procedures import ListProcedures
from cora.operation.features.list_procedures import bind as bind_list
from cora.operation.features.register_procedure import RegisterProcedure
from cora.operation.features.register_procedure import bind as bind_register
from cora.operation.features.resume_procedure import ResumeProcedure
from cora.operation.features.resume_procedure import bind as bind_resume
from cora.operation.features.start_procedure import StartProcedure
from cora.operation.features.start_procedure import bind as bind_start
from tests.integration._helpers import build_postgres_deps

_NOW = datetime(2026, 6, 21, 12, 0, 0, tzinfo=UTC)
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")


def _build_deps(db_pool: asyncpg.Pool, ids: list[UUID]) -> Kernel:
    return build_postgres_deps(db_pool, now=_NOW, ids=ids)


async def _drain(db_pool: asyncpg.Pool) -> None:
    registry = ProjectionRegistry()
    register_operation_projections(registry)
    await drain_projections(db_pool, registry, deadline_seconds=2.0)


async def _status_row(db_pool: asyncpg.Pool, proc_id: UUID) -> asyncpg.Record:
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT status, last_status_reason FROM proj_operation_procedure_summary "
            "WHERE procedure_id = $1",
            proc_id,
        )
    assert row is not None
    return row


@pytest.mark.integration
async def test_hold_then_resume_drives_status_in_read_model(db_pool: asyncpg.Pool) -> None:
    proc_id = uuid4()
    deps = _build_deps(db_pool, [proc_id, *[uuid4() for _ in range(8)]])

    await bind_register(deps)(
        RegisterProcedure(name="2-BM center alignment", kind="center_alignment"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await bind_start(deps)(
        StartProcedure(procedure_id=proc_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    # Hold: the projection writes status='Held' (the CHECK must admit it) +
    # the hold reason.
    await bind_hold(deps)(
        HoldProcedure(procedure_id=proc_id, reason="beam dropped"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await _drain(db_pool)
    held = await _status_row(db_pool, proc_id)
    assert held["status"] == "Held"
    assert held["last_status_reason"] == "beam dropped"

    # The list read path surfaces + filters on the new status.
    page = await bind_list(deps)(
        ListProcedures(status="Held"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    item = next(i for i in page.items if i.procedure_id == proc_id)
    assert item.status == "Held"
    assert item.last_status_reason == "beam dropped"

    # Resume: back to Running, hold reason cleared.
    await bind_resume(deps)(
        ResumeProcedure(procedure_id=proc_id, re_establishment_boundary=0),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await _drain(db_pool)
    resumed = await _status_row(db_pool, proc_id)
    assert resumed["status"] == "Running"
    assert resumed["last_status_reason"] is None
