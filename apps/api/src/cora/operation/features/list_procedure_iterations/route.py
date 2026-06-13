"""HTTP route for the `list_procedure_iterations` query slice.

`GET /procedures/{procedure_id}/iterations` returns the per-iteration
convergence records for one Procedure, ordered by index:
`{"items": [{iteration_index, started_at, ended_at, converged, reason}, ...]}`.
Bounded per parent, so no cursor. 200 with an empty list when the
Procedure has no recorded iterations (or does not exist) -- a list read,
not a single-resource fetch.
"""

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Path, Request, status
from pydantic import BaseModel

from cora.infrastructure.routing import (
    ErrorResponse,
    get_correlation_id,
    get_principal_id,
    get_surface_id,
)
from cora.operation.features.list_procedure_iterations.handler import Handler
from cora.operation.features.list_procedure_iterations.query import ListProcedureIterations


class ProcedureIterationDTO(BaseModel):
    """One convergence-loop iteration of a Procedure."""

    iteration_index: int
    started_at: datetime
    ended_at: datetime | None = None
    converged: bool | None = None
    reason: str | None = None


class ProcedureIterationsResponse(BaseModel):
    """All iterations for one Procedure, ordered by index."""

    items: list[ProcedureIterationDTO]


def _get_handler(request: Request) -> Handler:
    handler: Handler = request.app.state.operation.list_procedure_iterations
    return handler


router = APIRouter(tags=["operation"])


@router.get(
    "/procedures/{procedure_id}/iterations",
    status_code=status.HTTP_200_OK,
    response_model=ProcedureIterationsResponse,
    responses={
        status.HTTP_403_FORBIDDEN: {
            "model": ErrorResponse,
            "description": "Authorize port denied the query.",
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": "Path parameter failed schema validation.",
        },
    },
    summary="List the convergence-loop iterations of a Procedure",
)
async def list_procedure_iterations(
    procedure_id: Annotated[UUID, Path(description="Target procedure's id.")],
    handler: Annotated[Handler, Depends(_get_handler)],
    cid: Annotated[UUID, Depends(get_correlation_id)],
    principal_id: Annotated[UUID, Depends(get_principal_id)],
    surface_id: Annotated[UUID, Depends(get_surface_id)],
) -> ProcedureIterationsResponse:
    result = await handler(
        ListProcedureIterations(procedure_id=procedure_id),
        principal_id=principal_id,
        correlation_id=cid,
        surface_id=surface_id,
    )
    return ProcedureIterationsResponse(
        items=[
            ProcedureIterationDTO(
                iteration_index=item.iteration_index,
                started_at=item.started_at,
                ended_at=item.ended_at,
                converged=item.converged,
                reason=item.reason,
            )
            for item in result.items
        ]
    )
