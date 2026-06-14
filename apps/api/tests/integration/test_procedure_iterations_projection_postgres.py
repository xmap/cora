"""End-to-end: the iteration boundary pair populates the per-iteration
`proj_operation_procedure_iterations` read model, and the
`list_procedure_iterations` handler reads it back, against real Postgres.

Pins:
  - ProcedureIterationStarted -> one row per iteration with started_at.
  - ProcedureIterationEnded   -> fills ended_at + converged verdict + reason.
  - list_procedure_iterations returns the rows ordered by index with the
    verdicts.
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
from cora.operation.features.list_procedure_iterations import ListProcedureIterations
from cora.operation.features.list_procedure_iterations import bind as bind_list_iterations
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


@pytest.mark.integration
async def test_per_iteration_rows_capture_verdict_and_timing(db_pool: asyncpg.Pool) -> None:
    proc_id = uuid4()
    deps = _build_deps(db_pool, [proc_id, *[uuid4() for _ in range(10)]])

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
    # Iteration 1: missed.
    await bind_start_iteration(deps)(
        StartProcedureIteration(procedure_id=proc_id, iteration_index=1),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await bind_end_iteration(deps)(
        EndProcedureIteration(
            procedure_id=proc_id, iteration_index=1, converged=False, reason="off by 2px"
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    # Iteration 2: converged.
    await bind_start_iteration(deps)(
        StartProcedureIteration(procedure_id=proc_id, iteration_index=2),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await bind_end_iteration(deps)(
        EndProcedureIteration(procedure_id=proc_id, iteration_index=2, converged=True, reason=None),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await _drain(db_pool)

    async with db_pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT iteration_index, started_at, ended_at, converged, reason "
            "FROM proj_operation_procedure_iterations "
            "WHERE procedure_id = $1 ORDER BY iteration_index",
            proc_id,
        )
    assert [r["iteration_index"] for r in rows] == [1, 2]
    assert rows[0]["ended_at"] is not None
    assert rows[0]["converged"] is False
    assert rows[0]["reason"] == "off by 2px"
    assert rows[1]["converged"] is True
    assert rows[1]["reason"] is None

    page = await bind_list_iterations(deps)(
        ListProcedureIterations(procedure_id=proc_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert [i.iteration_index for i in page.items] == [1, 2]
    assert page.items[0].converged is False
    assert page.items[1].converged is True


@pytest.mark.integration
async def test_open_iteration_row_has_null_ended_at(db_pool: asyncpg.Pool) -> None:
    proc_id = uuid4()
    deps = _build_deps(db_pool, [proc_id, *[uuid4() for _ in range(6)]])
    await bind_register(deps)(
        RegisterProcedure(name="2-BM roll alignment", kind="roll_alignment"),
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

    page = await bind_list_iterations(deps)(
        ListProcedureIterations(procedure_id=proc_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert len(page.items) == 1
    assert page.items[0].ended_at is None
    assert page.items[0].converged is None
