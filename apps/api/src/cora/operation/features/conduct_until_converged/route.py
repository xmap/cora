"""HTTP route for the `conduct_until_converged` slice (slice 6c).

`POST /procedures/{procedure_id}/conduct-until-converged` accepts a JSON body
carrying the convergence predicate (the captures-slot name + the criterion) and
an optional per-pass step list (empty for a recipe-driven Procedure, which the
handler re-expands). Returns 200 OK with a `ConductUntilConvergedResponse`
summarising the outcome.

## Compute-driven convergence is reachable over the wire (via the recipe path)

The literal `steps` array in the HTTP / MCP body is validation-only: its
discriminated union deliberately admits setpoint / action / check steps but NOT
capture / compute steps (the wire surface stays a hand-built per-pass block).
That does NOT make compute-driven convergence unreachable over the wire: the
recipe path carries it. Register a Procedure from a recipe that carries a
`RecipeComputeStep` (with a `capture_name`) via `POST /procedures/from-recipe`,
then call this endpoint with `steps: []`. The handler re-expands the pinned
recipe each pass (`resolve_and_pin_conduct_steps` with the same `expansion_port`
that `conduct_procedure` uses), so the recipe's compute step runs and deposits
its produced value into the captures bus the criterion reads. The literal
HTTP / MCP step array intentionally excludes capture / compute steps; the
recipe is the channel for them.

## Response code: always 200, failures in body

Like `conduct_procedure`, this is an orchestration endpoint. A never-converged
cap-abort and an in-pass fault are NORMAL operational outcomes that the
operator triages; they land in the response body as a structured failure
summary, not as an HTTP 4xx / 5xx. Only protocol / auth / validation faults map
to HTTP error codes (422 malformed body, 403 authz deny).

## Pydantic wire types

The criterion wire union + per-step failure shape live in the BC-level
`cora.operation._conduct_wire` module (a slice cannot import a sibling slice).
This slice owns only its request / response envelope.
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
    CriterionRequest,
    StepRequest,
    criterion_from_wire,
    failure_to_wire,
    step_from_wire,
)
from cora.operation.features.conduct_until_converged.command import (
    ConductUntilConverged,
    ConductUntilConvergedResult,
)
from cora.operation.features.conduct_until_converged.handler import Handler


class ConductUntilConvergedRequest(BaseModel):
    """Body for `POST /procedures/{procedure_id}/conduct-until-converged`."""

    convergence_capture_name: str = Field(
        ...,
        min_length=1,
        description=(
            "Captures-slot name the per-pass deposit fills; the loop reads it "
            "after each successful pass and evaluates the criterion against it."
        ),
    )
    criterion: CriterionRequest = Field(
        ...,
        description=(
            "Convergence criterion (equals or within_tolerance) evaluated "
            "against the captured value after each pass."
        ),
    )
    steps: list[StepRequest] = Field(
        default_factory=list[StepRequest],
        max_length=STEP_BATCH_MAX,
        description=(
            "Per-pass step block the loop re-walks (0-"
            f"{STEP_BATCH_MAX}). Empty for a recipe-driven Procedure: the "
            "handler re-expands the pinned one-pass recipe each conduct."
        ),
    )
    max_consecutive_unconverged_iterations: int | None = Field(
        default=None,
        ge=1,
        description=(
            "Optional patience cap (>= 1). When omitted the loop honors the "
            "cap the Procedure declared at register time."
        ),
    )

    model_config = {"extra": "forbid"}


class ConductUntilConvergedResponse(BaseModel):
    """Response body for the conduct_until_converged slice.

    `succeeded` is True only when the loop converged and completed the
    Procedure; a cap-abort or an in-pass fault surfaces `succeeded=False`
    with `failure` carrying the cause. `completed_count` is the final pass's
    successful step count (informational).
    """

    procedure_id: UUID
    completed_count: int
    succeeded: bool
    failure: ConductorFailureResponse | None = None
    actuation_kind: str | None = None


def result_to_wire(result: ConductUntilConvergedResult) -> ConductUntilConvergedResponse:
    """Build a `ConductUntilConvergedResponse` from the slice result.

    Public because `tool.py` calls it too.
    """
    return ConductUntilConvergedResponse(
        procedure_id=result.procedure_id,
        completed_count=result.completed_count,
        succeeded=result.succeeded,
        failure=failure_to_wire(result.failure) if result.failure is not None else None,
        actuation_kind=result.actuation_kind,
    )


def _get_handler(request: Request) -> Handler:
    handler: Handler = request.app.state.operation.conduct_until_converged
    return handler


router = APIRouter(tags=["operation"])


@router.post(
    "/procedures/{procedure_id}/conduct-until-converged",
    status_code=status.HTTP_200_OK,
    response_model=ConductUntilConvergedResponse,
    responses={
        status.HTTP_403_FORBIDDEN: {
            "model": ErrorResponse,
            "description": "Authorize port denied the command.",
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": (
                "Request body failed schema validation: missing criterion, "
                "unknown step kind, batch over cap, invalid cap."
            ),
        },
    },
    summary=(
        "Conduct a Procedure in an AUTO convergence loop: iterate measure-correct "
        "passes until the criterion is met or the patience cap trips."
    ),
)
async def post_procedures_conduct_until_converged(
    procedure_id: Annotated[UUID, Path(description="Target procedure's id.")],
    body: ConductUntilConvergedRequest,
    handler: Annotated[Handler, Depends(_get_handler)],
    cid: Annotated[UUID, Depends(get_correlation_id)],
    principal_id: Annotated[UUID, Depends(get_principal_id)],
    surface_id: Annotated[UUID, Depends(get_surface_id)],
) -> ConductUntilConvergedResponse:
    """Conduct a Procedure as a convergence loop. Failures land in the body."""
    command = ConductUntilConverged(
        procedure_id=procedure_id,
        convergence_capture_name=body.convergence_capture_name,
        criterion=criterion_from_wire(body.criterion),
        steps=tuple(step_from_wire(s) for s in body.steps),
        max_consecutive_unconverged_iterations=body.max_consecutive_unconverged_iterations,
    )
    result = await handler(
        command,
        principal_id=principal_id,
        correlation_id=cid,
        surface_id=surface_id,
    )
    return result_to_wire(result)
