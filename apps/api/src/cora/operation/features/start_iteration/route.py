"""HTTP route for the `start_iteration` slice.

Action endpoint at `POST /procedures/{procedure_id}/iterations/start`.
The `iterations` noun-resource segment groups the start/end actions;
the verb terminates the path (per the nested sub-resource URL
convention). Body carries the operator-supplied `iteration_index`.
204 No Content on success.
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Path, Request, status
from pydantic import BaseModel, Field

from cora.infrastructure.routing import (
    ErrorResponse,
    get_correlation_id,
    get_principal_id,
    get_surface_id,
)
from cora.operation.features.start_iteration.command import StartProcedureIteration
from cora.operation.features.start_iteration.handler import Handler


class StartProcedureIterationRequest(BaseModel):
    """Body for `POST /procedures/{procedure_id}/iterations/start`."""

    iteration_index: int = Field(
        ...,
        ge=1,
        description=(
            "1-based index of the iteration to begin. Operator-supplied "
            "(capture-don't-recompute); must be the strict successor of the "
            "current iteration_count (no gaps or duplicates). The first "
            "iteration is 1."
        ),
    )


def _get_handler(request: Request) -> Handler:
    handler: Handler = request.app.state.operation.start_iteration
    return handler


router = APIRouter(tags=["operation"])


@router.post(
    "/procedures/{procedure_id}/iterations/start",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        status.HTTP_403_FORBIDDEN: {
            "model": ErrorResponse,
            "description": "Authorize port denied the command.",
        },
        status.HTTP_404_NOT_FOUND: {
            "model": ErrorResponse,
            "description": "No procedure exists with the given id.",
        },
        status.HTTP_409_CONFLICT: {
            "model": ErrorResponse,
            "description": (
                "Procedure is not in `Running`, an iteration is already open, or "
                "iteration_index is not the strict successor of the current "
                "iteration_count, OR a concurrent write to the same procedure "
                "stream conflicted (optimistic concurrency)."
            ),
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": "Path parameter or request body failed schema validation.",
        },
    },
    summary="Begin one convergence-loop iteration on a Running Procedure",
)
async def post_procedures_start_iteration(
    procedure_id: Annotated[UUID, Path(description="Target procedure's id.")],
    body: StartProcedureIterationRequest,
    handler: Annotated[Handler, Depends(_get_handler)],
    cid: Annotated[UUID, Depends(get_correlation_id)],
    principal_id: Annotated[UUID, Depends(get_principal_id)],
    surface_id: Annotated[UUID, Depends(get_surface_id)],
) -> None:
    await handler(
        StartProcedureIteration(
            procedure_id=procedure_id,
            iteration_index=body.iteration_index,
        ),
        principal_id=principal_id,
        correlation_id=cid,
        surface_id=surface_id,
    )
