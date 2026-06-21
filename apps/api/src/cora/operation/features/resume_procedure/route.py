"""HTTP route for the `resume_procedure` slice.

Action endpoint at `POST /procedures/{procedure_id}/resume`. Body carries
`re_establishment_boundary` (>= 0). 204 No Content on success.
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
from cora.operation.features.resume_procedure.command import ResumeProcedure
from cora.operation.features.resume_procedure.handler import Handler


class ResumeProcedureRequest(BaseModel):
    """Body for `POST /procedures/{procedure_id}/resume`."""

    re_establishment_boundary: int = Field(
        ...,
        ge=0,
        description=(
            "Index in the pinned resolved step list from which the resume "
            "re-drives setpoints and re-runs checks. >= 0 (0 = re-establish "
            "from the first step). NOT a continuity proof."
        ),
    )


def _get_handler(request: Request) -> Handler:
    handler: Handler = request.app.state.operation.resume_procedure
    return handler


router = APIRouter(tags=["operation"])


@router.post(
    "/procedures/{procedure_id}/resume",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        status.HTTP_400_BAD_REQUEST: {
            "model": ErrorResponse,
            "description": "Domain invariant violated: negative re_establishment_boundary.",
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
                "Procedure is not in `Held` status (resume requires `Held`; "
                "resuming a `Running` / `Defined` / terminal procedure raises), "
                "OR a concurrent write to the same procedure stream conflicted "
                "(optimistic concurrency)."
            ),
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": "Path parameter or request body failed schema validation.",
        },
    },
    summary="Resume a held Procedure conduct (Held -> Running)",
)
async def post_procedures_resume(
    procedure_id: Annotated[UUID, Path(description="Target procedure's id.")],
    body: ResumeProcedureRequest,
    handler: Annotated[Handler, Depends(_get_handler)],
    cid: Annotated[UUID, Depends(get_correlation_id)],
    principal_id: Annotated[UUID, Depends(get_principal_id)],
    surface_id: Annotated[UUID, Depends(get_surface_id)],
) -> None:
    await handler(
        ResumeProcedure(
            procedure_id=procedure_id,
            re_establishment_boundary=body.re_establishment_boundary,
        ),
        principal_id=principal_id,
        correlation_id=cid,
        surface_id=surface_id,
    )
