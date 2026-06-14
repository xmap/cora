"""End-to-end: the iteration boundary pair drives `iteration_count` in the
`proj_operation_procedure_summary` read model against real Postgres.

Pins:
  - ProcedureRegistered seeds iteration_count = 0.
  - ProcedureIterationStarted sets iteration_count to the operator-supplied
    index (replay-safe set-to-index).
  - The count survives a ProcedureIterationEnded (which is not projected) and
    advances on the next ProcedureIterationStarted.
  - The list_procedures read path surfaces iteration_count.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from datetime import UTC, datetime
from uuid import UUID, uuid4

import asyncpg
import pytest

from cora.infrastructure.kernel import Kernel
from cora.infrastructure.projection import ProjectionRegistry, drain_projections
from cora.operation._projections import register_operation_projections
from cora.operation.features.end_iteration import EndProcedureIteration
from cora.operation.features.end_iteration import bind as bind_end_iteration
from cora.operation.features.list_procedures import ListProcedures
from cora.operation.features.list_procedures import bind as bind_list
from cora.operation.features.register_procedure import RegisterProcedure
from cora.operation.features.register_procedure import bind as bind_register
from cora.operation.features.start_iteration import StartProcedureIteration
from cora.operation.features.start_iteration import bind as bind_start_iteration
from cora.operation.features.start_procedure import StartProcedure
from cora.operation.features.start_procedure import bind as bind_start
from tests.integration._helpers import build_postgres_deps

_NOW = datetime(2026, 6, 13, 12, 0, 0, tzinfo=UTC)
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")


def _build_deps(db_pool: asyncpg.Pool, ids: list[UUID]) -> Kernel:
    return build_postgres_deps(db_pool, now=_NOW, ids=ids)


async def _drain(db_pool: asyncpg.Pool) -> None:
    registry = ProjectionRegistry()
    register_operation_projections(registry)
    await drain_projections(db_pool, registry, deadline_seconds=2.0)


async def _iteration_count(db_pool: asyncpg.Pool, proc_id: UUID) -> int:
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT iteration_count FROM proj_operation_procedure_summary WHERE procedure_id = $1",
            proc_id,
        )
    assert row is not None
    return int(row["iteration_count"])


@pytest.mark.integration
async def test_register_seeds_iteration_count_zero(db_pool: asyncpg.Pool) -> None:
    proc_id = uuid4()
    deps = _build_deps(db_pool, [proc_id, uuid4()])
    await bind_register(deps)(
        RegisterProcedure(name="2-BM center alignment", kind="center_alignment"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await _drain(db_pool)
    assert await _iteration_count(db_pool, proc_id) == 0


@pytest.mark.integration
async def test_iteration_loop_advances_iteration_count(db_pool: asyncpg.Pool) -> None:
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
    await bind_start_iteration(deps)(
        StartProcedureIteration(procedure_id=proc_id, iteration_index=1),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await _drain(db_pool)
    assert await _iteration_count(db_pool, proc_id) == 1

    # Close iteration 1 (not projected) then open iteration 2.
    await bind_end_iteration(deps)(
        EndProcedureIteration(
            procedure_id=proc_id, iteration_index=1, converged=False, reason="off by 2px"
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await bind_start_iteration(deps)(
        StartProcedureIteration(procedure_id=proc_id, iteration_index=2),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await _drain(db_pool)
    assert await _iteration_count(db_pool, proc_id) == 2

    # The list read path surfaces the denorm.
    page = await bind_list(deps)(
        ListProcedures(kind="center_alignment"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    item = next(i for i in page.items if i.procedure_id == proc_id)
    assert item.iteration_count == 2
