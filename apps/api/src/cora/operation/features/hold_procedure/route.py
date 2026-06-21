"""HTTP route for the `hold_procedure` slice.

Action endpoint at `POST /procedures/{procedure_id}/hold`. Body carries
`reason` (1-500 chars). 204 No Content on success. Mirrors abort_procedure.
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
from cora.operation.features.hold_procedure.command import HoldProcedure
from cora.operation.features.hold_procedure.handler import Handler
from cora.shared.text_bounds import REASON_MAX_LENGTH


class HoldProcedureRequest(BaseModel):
    """Body for `POST /procedures/{procedure_id}/hold`."""

    reason: str = Field(
        ...,
        min_length=1,
        max_length=REASON_MAX_LENGTH,
        description=(
            "Free-form reason for the hold (1-500 chars after trimming). "
            "Required: pausing a halted conduct is a deliberate operator act "
            "(unlike a routine RunHeld, which carries no reason)."
        ),
    )


def _get_handler(request: Request) -> Handler:
    handler: Handler = request.app.state.operation.hold_procedure
    return handler


router = APIRouter(tags=["operation"])


@router.post(
    "/procedures/{procedure_id}/hold",
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
                "Procedure is not in `Running` status (hold requires "
                "`Running`; holding a `Defined` / `Held` / terminal procedure "
                "raises), OR a concurrent write to the same procedure stream "
                "conflicted (optimistic concurrency)."
            ),
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": "Path parameter or request body failed schema validation.",
        },
    },
    summary="Pause an actively-running Procedure conduct (Running -> Held)",
)
async def post_procedures_hold(
    procedure_id: Annotated[UUID, Path(description="Target procedure's id.")],
    body: HoldProcedureRequest,
    handler: Annotated[Handler, Depends(_get_handler)],
    cid: Annotated[UUID, Depends(get_correlation_id)],
    principal_id: Annotated[UUID, Depends(get_principal_id)],
    surface_id: Annotated[UUID, Depends(get_surface_id)],
) -> None:
    await handler(
        HoldProcedure(procedure_id=procedure_id, reason=body.reason),
        principal_id=principal_id,
        correlation_id=cid,
        surface_id=surface_id,
    )
