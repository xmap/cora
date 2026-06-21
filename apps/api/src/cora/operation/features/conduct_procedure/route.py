"""HTTP route for the `conduct_procedure` slice.

`POST /procedures/{procedure_id}/conduct` accepts a JSON body carrying
the step list the Conductor walks. Returns 200 OK with a
`ConductProcedureResponse` body summarising the outcome (procedure_id +
completed_count + succeeded + optional failure detail).

## Response code: always 200, failures in body

`ConductProcedure` is an orchestration endpoint, not a CRUD call.
Step-level failures (a setpoint write that the IOC rejected, a
check that did not pass, an action body that raised) are NORMAL
operational outcomes that the operator needs to triage. They land
in the response body as a structured failure summary, not as HTTP
4xx / 5xx. This mirrors how CI / build-runner APIs report job
results: a failed run is a 200 OK carrying a failed status.

Only true protocol / auth / validation faults map to HTTP error
codes (422 for malformed JSON, 403 for authz deny). Everything
downstream of "authorized request with valid body" is captured in
the result body so a single client code-path covers every outcome
without parsing HTTP status codes.

## Pydantic wire types

The shared step-list body + per-step failure shape live in the BC-level
`cora.operation._conduct_wire` module (reused by `try_conduct_procedure`,
which a slice cannot import directly). This slice owns only the
conduct-specific request/response envelope.
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
from cora.operation.features.conduct_procedure.command import (
    ConductProcedure,
    ConductProcedureResult,
)
from cora.operation.features.conduct_procedure.handler import Handler


class ConductProcedureRequest(BaseModel):
    """Body for `POST /procedures/{procedure_id}/conduct`."""

    steps: list[StepRequest] = Field(
        default_factory=list[StepRequest],
        max_length=STEP_BATCH_MAX,
        description=(
            f"Steps the Conductor walks in order (0-{STEP_BATCH_MAX}). "
            "Empty list is valid: start + complete fire with no steps."
        ),
    )

    model_config = {"extra": "forbid"}


class ConductProcedureResponse(BaseModel):
    """Response body for the conduct_procedure slice.

    `succeeded` is the canonical pass/fail bit; `failure` is non-null
    iff `succeeded` is False. `completed_count` is informational
    (the number of steps that ran successfully before halt, if any).

    `actuation_kind` is the raw `ActuationKind` value (Physical /
    Simulated / Hybrid) the Conductor observed, or None when nothing
    instrumented was actuated. Read-only operator visibility; the gate
    that consumes it reads the value server-side off the Procedure
    stream, never back from this response.
    """

    procedure_id: UUID
    completed_count: int
    succeeded: bool
    failure: ConductorFailureResponse | None = None
    actuation_kind: str | None = None


def result_to_wire(result: ConductProcedureResult) -> ConductProcedureResponse:
    """Build a `ConductProcedureResponse` from the slice's `ConductProcedureResult`.

    Public because `tool.py` calls it too.
    """
    return ConductProcedureResponse(
        procedure_id=result.procedure_id,
        completed_count=result.completed_count,
        succeeded=result.succeeded,
        failure=failure_to_wire(result.failure) if result.failure is not None else None,
        actuation_kind=result.actuation_kind,
    )


def _get_handler(request: Request) -> Handler:
    handler: Handler = request.app.state.operation.conduct_procedure
    return handler


router = APIRouter(tags=["operation"])


@router.post(
    "/procedures/{procedure_id}/conduct",
    status_code=status.HTTP_200_OK,
    response_model=ConductProcedureResponse,
    responses={
        status.HTTP_403_FORBIDDEN: {
            "model": ErrorResponse,
            "description": "Authorize port denied the command.",
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": (
                "Request body failed schema validation: unknown step "
                "kind, missing required field, batch over cap, invalid "
                "criterion shape."
            ),
        },
    },
    summary=(
        "Conduct a Procedure: start -> walk steps via ControlPort + actions + "
        "checks -> complete (success) or abort (failure)."
    ),
)
async def post_procedures_conduct(
    procedure_id: Annotated[UUID, Path(description="Target procedure's id.")],
    body: ConductProcedureRequest,
    handler: Annotated[Handler, Depends(_get_handler)],
    cid: Annotated[UUID, Depends(get_correlation_id)],
    principal_id: Annotated[UUID, Depends(get_principal_id)],
    surface_id: Annotated[UUID, Depends(get_surface_id)],
) -> ConductProcedureResponse:
    """Conduct a Procedure end-to-end. Failures land in the response body."""
    command = ConductProcedure(
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
