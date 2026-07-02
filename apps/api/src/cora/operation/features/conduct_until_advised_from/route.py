"""HTTP route for the `conduct_until_advised_from` slice (steered RESUME wire).

`POST /procedures/{procedure_id}/conduct-until-advised-from` resumes a Held
GP-steered Procedure: it re-seeds the brain from the recorded closed passes and
continues the loop at the open frontier. Accepts the same steering config as
`conduct-until-advised` (objective, space, objective_capture_name, brain config,
optional budget); the re-establishment boundary is NOT a body field (it is
derived from the count of recorded closed passes). Returns 200 OK with a
`ConductUntilAdvisedFromResponse`.

## Recipe-driven: no `steps` in the body

Like `conduct-until-advised`, the steered axis is a `SteeringRef` setpoint only a
Recipe can express, so the endpoint carries no literal `steps`. The handler
re-expands the Procedure's pinned recipe block.

## Response codes

Orchestration endpoint: a pass fault, a brain fault, and the absolute ceiling
are NORMAL outcomes that land in the body (200). A resumed campaign whose brain
immediately re-advises Stop is also a normal 200 (completed, nothing to run).
Protocol / auth / validation / resumability faults map to HTTP codes: 403 authz
deny, 422 malformed body or steering-wire mismatch, 409 non-Held Procedure /
held parent Run, 404 unknown Procedure, 500 missing pinned steps (corruption).
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
from cora.operation.features.conduct_until_advised_from.command import (
    ConductUntilAdvisedFrom,
    ConductUntilAdvisedFromResult,
)
from cora.operation.features.conduct_until_advised_from.handler import Handler


class ConductUntilAdvisedFromRequest(BaseModel):
    """Body for `POST /procedures/{procedure_id}/conduct-until-advised-from`."""

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


class ConductUntilAdvisedFromResponse(BaseModel):
    """Response body for the conduct_until_advised_from slice.

    `succeeded` is True only when the resumed loop reached a brain-advised Stop
    and the Procedure completed. `re_establishment_boundary` echoes the derived
    count of closed passes the resume re-seeded from. `completed_count` is the
    final pass's successful step count (informational).
    """

    procedure_id: UUID
    completed_count: int
    succeeded: bool
    re_establishment_boundary: int
    failure: ConductorFailureResponse | None = None
    actuation_kind: str | None = None


def result_to_wire(result: ConductUntilAdvisedFromResult) -> ConductUntilAdvisedFromResponse:
    """Build a `ConductUntilAdvisedFromResponse` from the slice result.

    Public because `tool.py` calls it too.
    """
    return ConductUntilAdvisedFromResponse(
        procedure_id=result.procedure_id,
        completed_count=result.completed_count,
        succeeded=result.succeeded,
        re_establishment_boundary=result.re_establishment_boundary,
        failure=failure_to_wire(result.failure) if result.failure is not None else None,
        actuation_kind=result.actuation_kind,
    )


def command_from_wire(
    procedure_id: UUID, body: ConductUntilAdvisedFromRequest
) -> ConductUntilAdvisedFrom:
    """Build the command from the request body. Public: tool.py reuses it."""
    return ConductUntilAdvisedFrom(
        procedure_id=procedure_id,
        objective=objective_from_wire(body.objective),
        space=space_from_wire(body.space),
        objective_capture_name=body.objective_capture_name,
        decide=decide_from_wire(body.decide),
        budget=budget_from_wire(body.budget),
    )


def _get_handler(request: Request) -> Handler:
    handler: Handler = request.app.state.operation.conduct_until_advised_from
    return handler


router = APIRouter(tags=["operation"])


@router.post(
    "/procedures/{procedure_id}/conduct-until-advised-from",
    status_code=status.HTTP_200_OK,
    response_model=ConductUntilAdvisedFromResponse,
    responses={
        status.HTTP_403_FORBIDDEN: {
            "model": ErrorResponse,
            "description": "Authorize port denied the command.",
        },
        status.HTTP_404_NOT_FOUND: {
            "model": ErrorResponse,
            "description": "No Procedure with that id.",
        },
        status.HTTP_409_CONFLICT: {
            "model": ErrorResponse,
            "description": "Procedure is not Held, or its parent Run is Held.",
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": (
                "Request body failed schema validation, or the steering space / "
                "objective does not line up with the pinned recipe."
            ),
        },
    },
    summary=(
        "Resume a Held recipe-driven steered Procedure: re-seed the brain from "
        "the recorded closed passes and continue asking it where to measure next."
    ),
)
async def post_procedures_conduct_until_advised_from(
    procedure_id: Annotated[UUID, Path(description="Target procedure's id.")],
    body: ConductUntilAdvisedFromRequest,
    handler: Annotated[Handler, Depends(_get_handler)],
    cid: Annotated[UUID, Depends(get_correlation_id)],
    principal_id: Annotated[UUID, Depends(get_principal_id)],
    surface_id: Annotated[UUID, Depends(get_surface_id)],
) -> ConductUntilAdvisedFromResponse:
    """Resume a steered Procedure at the frontier. Loop failures land in the body."""
    result = await handler(
        command_from_wire(procedure_id, body),
        principal_id=principal_id,
        correlation_id=cid,
        surface_id=surface_id,
    )
    return result_to_wire(result)
