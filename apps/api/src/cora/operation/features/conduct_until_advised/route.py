"""HTTP route for the `conduct_until_advised` slice (steered loop wire).

`POST /procedures/{procedure_id}/conduct-until-advised` accepts a JSON body
carrying the steering objective, the search space, the objective captures-slot
name, the brain-selection config, and an optional informational budget. Returns
200 OK with a `ConductUntilAdvisedResponse` summarising the outcome.

## Recipe-driven: no `steps` in the body

Unlike `conduct_until_converged`, this endpoint carries NO literal `steps`
array. The steered axis is a `SteeringRef` setpoint, which only a Recipe can
express (the literal HTTP step union has no SteeringRef arm). Register a
Procedure from a recipe whose per-pass block carries a `SteeringRef` setpoint
(plus the objective deposit) via `POST /procedures/from-recipe`, then call this
endpoint. The handler re-expands the pinned recipe each pass.

## Response code: always 200, failures in body

Like `conduct_until_converged`, this is an orchestration endpoint. A pass fault,
a brain fault, and the absolute iteration ceiling are NORMAL operational
outcomes the operator triages; they land in the response body as a structured
failure summary, not as an HTTP 4xx / 5xx. Only protocol / auth / validation
faults map to HTTP error codes (422 malformed body, 403 authz deny).

## Pydantic wire types

The Steering wire mirrors + converters live in the BC-level
`cora.operation._advise_wire` module (a slice cannot import a sibling slice);
the per-step failure shape is reused from `cora.operation._conduct_wire`. This
slice owns only its request / response envelope.
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
from cora.operation._advise_wire import (
    DecideConfigRequest,
    SteeringBudgetRequest,
    SteeringObjectiveRequest,
    SteeringSpaceRequest,
    budget_from_wire,
    decide_from_wire,
    objective_from_wire,
    space_from_wire,
)
from cora.operation._conduct_wire import ConductorFailureResponse, failure_to_wire
from cora.operation.features.conduct_until_advised.command import (
    ConductUntilAdvised,
    ConductUntilAdvisedResult,
)
from cora.operation.features.conduct_until_advised.handler import Handler


class ConductUntilAdvisedRequest(BaseModel):
    """Body for `POST /procedures/{procedure_id}/conduct-until-advised`."""

    objective: SteeringObjectiveRequest = Field(
        ...,
        description="What good means: the steering objective the brain weighs.",
    )
    space: SteeringSpaceRequest = Field(
        ...,
        description="The feasible search space (axes + bounds / choices) the brain proposes in.",
    )
    objective_capture_name: str = Field(
        ...,
        min_length=1,
        description=(
            "Captures-slot name the per-pass deposit fills; the loop surfaces it "
            "to the brain as the objective scalar after each pass."
        ),
    )
    decide: DecideConfigRequest = Field(
        default_factory=DecideConfigRequest,
        description="The in-CORA brain selection (substrate + grid resolution).",
    )
    budget: SteeringBudgetRequest | None = Field(
        default=None,
        description="Optional informational budget surfaced to the brain (not enforced here).",
    )

    model_config = {"extra": "forbid"}


class ConductUntilAdvisedResponse(BaseModel):
    """Response body for the conduct_until_advised slice.

    `succeeded` is True only when the brain advised Stop and the Procedure
    completed; a pass / brain fault or the absolute ceiling surfaces
    `succeeded=False` with `failure` carrying the cause. `completed_count` is
    the final pass's successful step count (informational).
    """

    procedure_id: UUID
    completed_count: int
    succeeded: bool
    failure: ConductorFailureResponse | None = None
    actuation_kind: str | None = None


def result_to_wire(result: ConductUntilAdvisedResult) -> ConductUntilAdvisedResponse:
    """Build a `ConductUntilAdvisedResponse` from the slice result.

    Public because `tool.py` calls it too.
    """
    return ConductUntilAdvisedResponse(
        procedure_id=result.procedure_id,
        completed_count=result.completed_count,
        succeeded=result.succeeded,
        failure=failure_to_wire(result.failure) if result.failure is not None else None,
        actuation_kind=result.actuation_kind,
    )


def command_from_wire(procedure_id: UUID, body: ConductUntilAdvisedRequest) -> ConductUntilAdvised:
    """Build the command from the request body. Public: tool.py reuses it."""
    return ConductUntilAdvised(
        procedure_id=procedure_id,
        objective=objective_from_wire(body.objective),
        space=space_from_wire(body.space),
        objective_capture_name=body.objective_capture_name,
        decide=decide_from_wire(body.decide),
        budget=budget_from_wire(body.budget),
    )


def _get_handler(request: Request) -> Handler:
    handler: Handler = request.app.state.operation.conduct_until_advised
    return handler


router = APIRouter(tags=["operation"])


@router.post(
    "/procedures/{procedure_id}/conduct-until-advised",
    status_code=status.HTTP_200_OK,
    response_model=ConductUntilAdvisedResponse,
    responses={
        status.HTTP_403_FORBIDDEN: {
            "model": ErrorResponse,
            "description": "Authorize port denied the command.",
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": (
                "Request body failed schema validation: missing objective / space, "
                "empty space, unknown objective kind, invalid budget."
            ),
        },
    },
    summary=(
        "Conduct a recipe-driven Procedure in a steered loop: measure, ask the "
        "brain where to go next, repeat until it advises Stop."
    ),
)
async def post_procedures_conduct_until_advised(
    procedure_id: Annotated[UUID, Path(description="Target procedure's id.")],
    body: ConductUntilAdvisedRequest,
    handler: Annotated[Handler, Depends(_get_handler)],
    cid: Annotated[UUID, Depends(get_correlation_id)],
    principal_id: Annotated[UUID, Depends(get_principal_id)],
    surface_id: Annotated[UUID, Depends(get_surface_id)],
) -> ConductUntilAdvisedResponse:
    """Conduct a Procedure as a steered loop. Failures land in the body."""
    result = await handler(
        command_from_wire(procedure_id, body),
        principal_id=principal_id,
        correlation_id=cid,
        surface_id=surface_id,
    )
    return result_to_wire(result)
