"""HTTP route for the `abort_procedure` slice.

Action endpoint at `POST /procedures/{procedure_id}/abort`. Body
carries `reason` (1-500 chars). 204 No Content on success.
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
from cora.operation.features.abort_procedure.command import AbortProcedure
from cora.operation.features.abort_procedure.handler import Handler
from cora.shared.text_bounds import REASON_MAX_LENGTH


class AbortProcedureRequest(BaseModel):
    """Body for `POST /procedures/{procedure_id}/abort`."""

    reason: str = Field(
        ...,
        min_length=1,
        max_length=REASON_MAX_LENGTH,
        description=(
            "Free-form reason for the abort (1-500 chars after trimming). "
            "Today the field is unstructured; structured taxonomy is "
            "future-additive (mirrors RunAborted.reason posture)."
        ),
    )


def _get_handler(request: Request) -> Handler:
    handler: Handler = request.app.state.operation.abort_procedure
    return handler


router = APIRouter(tags=["operation"])


@router.post(
    "/procedures/{procedure_id}/abort",
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
                "Procedure is not in `Running` status (abort requires "
                "`Running` today; aborting a `Defined` / `Completed` / "
                "`Aborted` procedure raises), OR a concurrent write to the "
                "same procedure stream conflicted (optimistic concurrency)."
            ),
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": "Path parameter or request body failed schema validation.",
        },
    },
    summary="Mark an existing Procedure as aborted (emergency-exit terminal)",
)
async def post_procedures_abort(
    procedure_id: Annotated[UUID, Path(description="Target procedure's id.")],
    body: AbortProcedureRequest,
    handler: Annotated[Handler, Depends(_get_handler)],
    cid: Annotated[UUID, Depends(get_correlation_id)],
    principal_id: Annotated[UUID, Depends(get_principal_id)],
    surface_id: Annotated[UUID, Depends(get_surface_id)],
) -> None:
    await handler(
        AbortProcedure(procedure_id=procedure_id, reason=body.reason),
        principal_id=principal_id,
        correlation_id=cid,
        surface_id=surface_id,
    )
