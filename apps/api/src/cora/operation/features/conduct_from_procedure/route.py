"""HTTP route for the `conduct_from_procedure` slice.

`POST /procedures/{procedure_id}/conduct-from` resumes a Held Procedure and
replays its pinned step-list tail from `re_establishment_boundary`.

## Response code: 200, replay outcomes in body

Like `conduct_procedure`, replay outcomes (a step that failed, an
acquisition that needs an operator decision) are NORMAL operational
results that land in the body, not HTTP errors. Only protocol / auth /
guard faults map to HTTP codes: 403 (authz deny), 404 (no procedure),
409 (Procedure not Held, or parent Run Held -- from the resume guard),
422 (negative boundary / malformed id), 500 (Held Procedure missing its
pinned resolved steps -- corruption).
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
from cora.operation._conduct_wire import ConductorFailureResponse, failure_to_wire
from cora.operation.features.conduct_from_procedure.command import (
    ConductFromProcedure,
    ConductFromProcedureResult,
)
from cora.operation.features.conduct_from_procedure.handler import Handler


class ConductFromProcedureRequest(BaseModel):
    """Body for `POST /procedures/{procedure_id}/conduct-from`."""

    re_establishment_boundary: int = Field(
        ...,
        ge=0,
        description=(
            "Index in the pinned resolved step list from which the resume "
            "re-drives setpoints and re-runs checks. >= 0 (0 = re-establish "
            "from the first step). NOT a continuity proof."
        ),
    )

    model_config = {"extra": "forbid"}


class ConductFromProcedureResponse(BaseModel):
    """Response body for the conduct_from_procedure slice.

    `succeeded` is the replay's pass/fail bit. `acquisition_halt` is True
    iff the replay stopped at an acquisition needing an operator decision
    (the Procedure is left Running). `failure` is non-null iff `succeeded`
    is False (a halt or a genuine step failure).
    """

    procedure_id: UUID
    completed_count: int
    succeeded: bool
    re_establishment_boundary: int
    acquisition_halt: bool
    failure: ConductorFailureResponse | None = None
    actuation_kind: str | None = None


def result_to_wire(result: ConductFromProcedureResult) -> ConductFromProcedureResponse:
    """Build a `ConductFromProcedureResponse` from the slice result.

    Public because `tool.py` calls it too.
    """
    return ConductFromProcedureResponse(
        procedure_id=result.procedure_id,
        completed_count=result.completed_count,
        succeeded=result.succeeded,
        re_establishment_boundary=result.re_establishment_boundary,
        acquisition_halt=result.acquisition_halt,
        failure=failure_to_wire(result.failure) if result.failure is not None else None,
        actuation_kind=result.actuation_kind,
    )


def _get_handler(request: Request) -> Handler:
    handler: Handler = request.app.state.operation.conduct_from_procedure
    return handler


router = APIRouter(tags=["operation"])


@router.post(
    "/procedures/{procedure_id}/conduct-from",
    status_code=status.HTTP_200_OK,
    response_model=ConductFromProcedureResponse,
    responses={
        status.HTTP_400_BAD_REQUEST: {
            "model": ErrorResponse,
            "description": "re_establishment_boundary is past the pinned resolved step count.",
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
                "Procedure is not in `Held` status, OR its parent Run is "
                "itself `Held` (off-diagonal guard)."
            ),
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": "Path parameter or request body failed schema validation.",
        },
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "model": ErrorResponse,
            "description": "Held Procedure is missing its pinned resolved steps (corruption).",
        },
    },
    summary="Resume a held Procedure and replay its pinned step-list tail (Held -> Running)",
)
async def post_procedures_conduct_from(
    procedure_id: Annotated[UUID, Path(description="Target procedure's id.")],
    body: ConductFromProcedureRequest,
    handler: Annotated[Handler, Depends(_get_handler)],
    cid: Annotated[UUID, Depends(get_correlation_id)],
    principal_id: Annotated[UUID, Depends(get_principal_id)],
    surface_id: Annotated[UUID, Depends(get_surface_id)],
) -> ConductFromProcedureResponse:
    """Resume + replay a Held Procedure. Replay outcomes land in the body."""
    command = ConductFromProcedure(
        procedure_id=procedure_id,
        re_establishment_boundary=body.re_establishment_boundary,
    )
    result = await handler(
        command,
        principal_id=principal_id,
        correlation_id=cid,
        surface_id=surface_id,
    )
    return result_to_wire(result)
