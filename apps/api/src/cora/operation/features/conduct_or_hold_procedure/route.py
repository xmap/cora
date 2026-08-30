"""HTTP route for the `conduct_or_hold_procedure` slice.

`POST /procedures/{procedure_id}/conduct-or-hold` accepts the same step-list body
as conduct, but on a RECOVERABLE step failure (a setpoint / check) the
Procedure is PAUSED to `Held` (resumable via `conduct_from`) instead of aborted.

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
slice owns only the conduct-or-hold-specific request/response envelope, which adds
the `held` discriminator.
"""

from typing import Annotated, Any
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
    closing_failures_to_wire,
    failure_to_wire,
    step_from_wire,
    substrate_writes_to_wire,
)
from cora.operation.features.conduct_or_hold_procedure.command import (
    ConductOrHoldProcedure,
    ConductOrHoldProcedureResult,
)
from cora.operation.features.conduct_or_hold_procedure.handler import Handler


class ConductOrHoldProcedureRequest(BaseModel):
    """Body for `POST /procedures/{procedure_id}/conduct-or-hold`."""

    steps: list[StepRequest] = Field(
        default_factory=list[StepRequest],
        max_length=STEP_BATCH_MAX,
        description=(
            f"Steps the Conductor walks in order (0-{STEP_BATCH_MAX}). "
            "Empty list is valid: start + complete fire with no steps."
        ),
    )

    model_config = {"extra": "forbid"}


class ConductOrHoldProcedureResponse(BaseModel):
    """Response body for the conduct_or_hold_procedure slice.

    `succeeded` is the canonical pass/fail bit; `failure` is non-null iff
    `succeeded` is False. `held` is True iff a recoverable step failure paused
    the Procedure to `Held` (resumable via `conduct_from`); a terminal `Aborted`
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
    substrate_writes: dict[str, int | float | bool | str | list[Any]] = Field(
        default_factory=dict[str, int | float | bool | str | list[Any]],
        description=(
            "Every control address this conduct wrote, in first-write "
            "order, carrying the last value written to each. Present on a "
            "HELD outcome too: a paused Procedure's recipe closing steps "
            "have not run, so this is what was left set."
        ),
    )
    closing_failures: list[ConductorFailureResponse] = Field(
        default_factory=list[ConductorFailureResponse],
        description=(
            "Every closing step that failed. Always empty on `held=True`: "
            "closing runs only on a real terminal, never on Held. Never "
            "flips `succeeded`."
        ),
    )


def result_to_wire(result: ConductOrHoldProcedureResult) -> ConductOrHoldProcedureResponse:
    """Build a `ConductOrHoldProcedureResponse` from the slice's result.

    Public because `tool.py` calls it too.
    """
    return ConductOrHoldProcedureResponse(
        procedure_id=result.procedure_id,
        completed_count=result.completed_count,
        succeeded=result.succeeded,
        held=result.held,
        failure=failure_to_wire(result.failure) if result.failure is not None else None,
        actuation_kind=result.actuation_kind,
        substrate_writes=substrate_writes_to_wire(result.substrate_writes),
        closing_failures=closing_failures_to_wire(result.closing_failures),
    )


def _get_handler(request: Request) -> Handler:
    handler: Handler = request.app.state.operation.conduct_or_hold_procedure
    return handler


router = APIRouter(tags=["operation"])


@router.post(
    "/procedures/{procedure_id}/conduct-or-hold",
    status_code=status.HTTP_200_OK,
    response_model=ConductOrHoldProcedureResponse,
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
async def post_procedures_conduct_or_hold(
    procedure_id: Annotated[UUID, Path(description="Target procedure's id.")],
    body: ConductOrHoldProcedureRequest,
    handler: Annotated[Handler, Depends(_get_handler)],
    cid: Annotated[UUID, Depends(get_correlation_id)],
    principal_id: Annotated[UUID, Depends(get_principal_id)],
    surface_id: Annotated[UUID, Depends(get_surface_id)],
) -> ConductOrHoldProcedureResponse:
    """Conduct a Procedure, pausing to Held on a recoverable failure."""
    command = ConductOrHoldProcedure(
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
