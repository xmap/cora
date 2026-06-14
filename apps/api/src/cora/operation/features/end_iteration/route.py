"""HTTP route for the `end_iteration` slice.

Action endpoint at `POST /procedures/{procedure_id}/iterations/end`.
The `iterations` noun-resource segment groups the start/end actions;
the verb terminates the path. Body carries `iteration_index` (must
match the open iteration), the optional convergence verdict
(`converged`), and an optional free-form `reason`. 204 No Content on
success.
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
from cora.operation.features.end_iteration.command import EndProcedureIteration
from cora.operation.features.end_iteration.handler import Handler
from cora.shared.text_bounds import REASON_MAX_LENGTH


class EndProcedureIterationRequest(BaseModel):
    """Body for `POST /procedures/{procedure_id}/iterations/end`."""

    iteration_index: int = Field(
        ...,
        ge=1,
        description=(
            "1-based index of the iteration to close. Must equal the currently-open iteration."
        ),
    )
    converged: bool | None = Field(
        default=None,
        description=(
            "Convergence verdict for this iteration: true (met the target), "
            "false (did not), or null (no verdict, for example an inconclusive "
            "or interrupted pass)."
        ),
    )
    reason: str | None = Field(
        default=None,
        min_length=1,
        max_length=REASON_MAX_LENGTH,
        description=(
            "Optional free-form note about how the iteration ended (1-500 chars "
            "after trimming). Captured verbatim for audit."
        ),
    )


def _get_handler(request: Request) -> Handler:
    handler: Handler = request.app.state.operation.end_iteration
    return handler


router = APIRouter(tags=["operation"])


@router.post(
    "/procedures/{procedure_id}/iterations/end",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        status.HTTP_400_BAD_REQUEST: {
            "model": ErrorResponse,
            "description": "Domain invariant violated: whitespace-only reason.",
        },
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
                "Procedure is not in `Running`, no iteration is open, or "
                "iteration_index does not match the open iteration, OR a "
                "concurrent write to the same procedure stream conflicted "
                "(optimistic concurrency)."
            ),
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": "Path parameter or request body failed schema validation.",
        },
    },
    summary="Close the open convergence-loop iteration on a Running Procedure",
)
async def post_procedures_end_iteration(
    procedure_id: Annotated[UUID, Path(description="Target procedure's id.")],
    body: EndProcedureIterationRequest,
    handler: Annotated[Handler, Depends(_get_handler)],
    cid: Annotated[UUID, Depends(get_correlation_id)],
    principal_id: Annotated[UUID, Depends(get_principal_id)],
    surface_id: Annotated[UUID, Depends(get_surface_id)],
) -> None:
    await handler(
        EndProcedureIteration(
            procedure_id=procedure_id,
            iteration_index=body.iteration_index,
            converged=body.converged,
            reason=body.reason,
        ),
        principal_id=principal_id,
        correlation_id=cid,
        surface_id=surface_id,
    )
