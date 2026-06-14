"""Application handler for the `list_procedure_iterations` query slice.

Reads `proj_operation_procedure_iterations` directly (a bounded
per-parent list, so no cursor pagination -- unlike `list_procedures`,
which uses the keyset `make_list_query_handler` factory). Mirrors that
factory's authorize + pool-short-circuit shape, then runs a single
ordered SELECT.

BOLA: command-name gating only (`ListProcedureIterations`). Per-row
scoping deferred until ReBAC, same posture as `list_procedures`.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol
from uuid import UUID

from cora.infrastructure.kernel import Kernel
from cora.infrastructure.logging import get_logger
from cora.infrastructure.ports import Deny
from cora.infrastructure.routing import NIL_SENTINEL_ID
from cora.operation.errors import UnauthorizedError
from cora.operation.features.list_procedure_iterations.query import ListProcedureIterations

_log = get_logger("list_procedure_iterations")

_SELECT_SQL = """
SELECT procedure_id, iteration_index, started_at, ended_at, converged, reason
FROM proj_operation_procedure_iterations
WHERE procedure_id = $1
ORDER BY iteration_index ASC
"""


@dataclass(frozen=True)
class ProcedureIterationItem:
    """One iteration row from the per-iteration projection."""

    procedure_id: UUID
    iteration_index: int
    started_at: datetime
    ended_at: datetime | None
    converged: bool | None
    reason: str | None


@dataclass(frozen=True)
class ProcedureIterationsList:
    """All iterations for one Procedure, ordered by index."""

    items: list[ProcedureIterationItem]


class Handler(Protocol):
    """Callable interface every list_procedure_iterations handler implements."""

    async def __call__(
        self,
        query: ListProcedureIterations,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> ProcedureIterationsList: ...


def _row_to_item(row: Any) -> ProcedureIterationItem:
    return ProcedureIterationItem(
        procedure_id=row["procedure_id"],
        iteration_index=int(row["iteration_index"]),
        started_at=row["started_at"],
        ended_at=row["ended_at"],
        converged=row["converged"],
        reason=str(row["reason"]) if row["reason"] is not None else None,
    )


def bind(deps: Kernel) -> Handler:
    """Build a list_procedure_iterations handler closed over the shared deps."""

    async def handler(
        query: ListProcedureIterations,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> ProcedureIterationsList:
        _log.info(
            "list_procedure_iterations.start",
            procedure_id=str(query.procedure_id),
            principal_id=str(principal_id),
            correlation_id=str(correlation_id),
        )
        decision = await deps.authz.authorize(
            principal_id=principal_id,
            command_name="ListProcedureIterations",
            conduit_id=NIL_SENTINEL_ID,
            surface_id=surface_id,
        )
        if isinstance(decision, Deny):
            _log.info(
                "list_procedure_iterations.denied",
                procedure_id=str(query.procedure_id),
                principal_id=str(principal_id),
                correlation_id=str(correlation_id),
                reason=decision.reason,
            )
            raise UnauthorizedError(decision.reason)

        if deps.pool is None:
            return ProcedureIterationsList(items=[])

        async with deps.pool.acquire() as conn:
            rows = await conn.fetch(_SELECT_SQL, query.procedure_id)
        return ProcedureIterationsList(items=[_row_to_item(r) for r in rows])

    return handler


__all__ = [
    "Handler",
    "ProcedureIterationItem",
    "ProcedureIterationsList",
    "bind",
]
