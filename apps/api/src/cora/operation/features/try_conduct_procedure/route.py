"""HTTP route for the `try_conduct_procedure` slice.

`POST /procedures/{procedure_id}/try-conduct` accepts the same step-list body
as conduct, but on a RECOVERABLE step failure (a setpoint / check) the
Procedure is PAUSED to `Held` (resumable via `reconduct`) instead of aborted.

## Response code: always 200, failures in body

Like `conduct`, this is an orchestration endpoint: step-level failures + the
pause-to-Held outcome are NORMAL operational results that land in the response
body, not HTTP 4xx / 5xx. `held` distinguishes a paused (resumable) outcome
from a terminal `Aborted` one (both carry `succeeded=False` + `failure`).
Only true protocol / auth / validation faults map to HTTP error codes (422
for malformed JSON, 403 for authz deny).

## Pydantic wire types

The shared step-list body + per-step failure shape live in the BC-level
`cora.operation._conduct_wire` module (shared with `conduct_procedure`). This
slice owns only the try-conduct-specific request/response envelope, which adds
the `held` discriminator.
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
from cora.operation._conduct_wire import (
    STEP_BATCH_MAX,
    ConductorFailureResponse,
    StepRequest,
    failure_to_wire,
    step_from_wire,
)
from cora.operation.features.try_conduct_procedure.command import (
    TryConductProcedure,
    TryConductProcedureResult,
)
from cora.operation.features.try_conduct_procedure.handler import Handler


class TryConductProcedureRequest(BaseModel):
    """Body for `POST /procedures/{procedure_id}/try-conduct`."""

    steps: list[StepRequest] = Field(
        default_factory=list[StepRequest],
        max_length=STEP_BATCH_MAX,
        description=(
            f"Steps the Conductor walks in order (0-{STEP_BATCH_MAX}). "
            "Empty list is valid: start + complete fire with no steps."
        ),
    )

    model_config = {"extra": "forbid"}


class TryConductProcedureResponse(BaseModel):
    """Response body for the try_conduct_procedure slice.

    `succeeded` is the canonical pass/fail bit; `failure` is non-null iff
    `succeeded` is False. `held` is True iff a recoverable step failure paused
    the Procedure to `Held` (resumable via `reconduct`); a terminal `Aborted`
    outcome carries `succeeded=False` + `failure` + `held=False`.

    `actuation_kind` is the raw `ActuationKind` value the Conductor observed,
    or None when nothing instrumented was actuated. Read-only operator
    visibility; the gate that consumes it reads the value server-side off the
    Procedure stream, never back from this response.
    """

    procedure_id: UUID
    completed_count: int
    succeeded: bool
    held: bool = False
    failure: ConductorFailureResponse | None = None
    actuation_kind: str | None = None


def result_to_wire(result: TryConductProcedureResult) -> TryConductProcedureResponse:
    """Build a `TryConductProcedureResponse` from the slice's result.

    Public because `tool.py` calls it too.
    """
    return TryConductProcedureResponse(
        procedure_id=result.procedure_id,
        completed_count=result.completed_count,
        succeeded=result.succeeded,
        held=result.held,
        failure=failure_to_wire(result.failure) if result.failure is not None else None,
        actuation_kind=result.actuation_kind,
    )


def _get_handler(request: Request) -> Handler:
    handler: Handler = request.app.state.operation.try_conduct_procedure
    return handler


router = APIRouter(tags=["operation"])


@router.post(
    "/procedures/{procedure_id}/try-conduct",
    status_code=status.HTTP_200_OK,
    response_model=TryConductProcedureResponse,
    responses={
        status.HTTP_403_FORBIDDEN: {
            "model": ErrorResponse,
            "description": "Authorize port denied the command.",
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": (
                "Request body failed schema validation: unknown step kind, "
                "missing required field, batch over cap, invalid criterion shape."
            ),
        },
    },
    summary=(
        "Conduct a Procedure, pausing to Held on a recoverable failure: "
        "start -> walk steps -> complete (success) / pause to Held "
        "(recoverable setpoint or check failure) / abort (acquisition failure)."
    ),
)
async def post_procedures_try_conduct(
    procedure_id: Annotated[UUID, Path(description="Target procedure's id.")],
    body: TryConductProcedureRequest,
    handler: Annotated[Handler, Depends(_get_handler)],
    cid: Annotated[UUID, Depends(get_correlation_id)],
    principal_id: Annotated[UUID, Depends(get_principal_id)],
    surface_id: Annotated[UUID, Depends(get_surface_id)],
) -> TryConductProcedureResponse:
    """Conduct a Procedure, pausing to Held on a recoverable failure."""
    command = TryConductProcedure(
        procedure_id=procedure_id,
        steps=tuple(step_from_wire(s) for s in body.steps),
    )
    result = await handler(
        command,
        principal_id=principal_id,
        correlation_id=cid,
        surface_id=surface_id,
    )
    return result_to_wire(result)
