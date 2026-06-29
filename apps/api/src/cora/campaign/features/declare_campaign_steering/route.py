"""HTTP route for the `declare_campaign_steering` slice.

Action endpoint at `POST /campaigns/{campaign_id}/declare-steering`. Body
carries the steering objective + search space. 204 No Content on success.

The Pydantic wire models mirror `cora.operation._advise_wire`
(`SteeringObjectiveRequest` / `SteeringSpaceRequest` /
`SteeringAxisRequest`); they are defined local to this slice because a
Campaign slice cannot import `cora.operation._advise_wire` (tach forbids
`cora.campaign` from depending on `cora.operation`). The domain VOs are
imported from `cora.shared.steering`, the allowed shared dependency.
"""

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Path, Request, status
from pydantic import BaseModel, Field

from cora.campaign.features.declare_campaign_steering.command import DeclareCampaignSteering
from cora.campaign.features.declare_campaign_steering.handler import Handler
from cora.infrastructure.routing import (
    ErrorResponse,
    get_correlation_id,
    get_principal_id,
    get_surface_id,
)
from cora.shared.steering import (
    SteeringAxis,
    SteeringObjective,
    SteeringObjectiveKind,
    SteeringSpace,
)


class SteeringObjectiveRequest(BaseModel):
    """JSON wire shape for a `SteeringObjective`."""

    kind: SteeringObjectiveKind = Field(
        ...,
        description=(
            "What good means: Minimize / Maximize / Satisfy / Explore. A "
            "Satisfy objective drives toward target_value on "
            "target_measurement_name."
        ),
    )
    target_measurement_name: str | None = Field(
        default=None,
        description="Name of the objective measurement the steerer reads (None for pure Explore).",
    )
    target_value: float | None = Field(
        default=None,
        description="Setpoint the objective drives toward (used by Satisfy; None otherwise).",
    )

    model_config = {"extra": "forbid"}


class SteeringAxisRequest(BaseModel):
    """JSON wire shape for a `SteeringAxis`."""

    name: str = Field(
        ...,
        min_length=1,
        description="Axis label the across-Run steerer proposes coordinates for.",
    )
    lower: float | None = Field(default=None, description="Lower bound for a continuous axis.")
    upper: float | None = Field(default=None, description="Upper bound for a continuous axis.")
    choices: list[Any] = Field(
        default_factory=list,
        description="Enumerated values for a discrete/categorical axis (empty for continuous).",
    )

    model_config = {"extra": "forbid"}


class SteeringSpaceRequest(BaseModel):
    """JSON wire shape for a `SteeringSpace`."""

    axes: list[SteeringAxisRequest] = Field(
        ...,
        min_length=1,
        description="The feasible set the across-Run steerer may propose within.",
    )

    model_config = {"extra": "forbid"}


class DeclareCampaignSteeringRequest(BaseModel):
    """Body for `POST /campaigns/{campaign_id}/declare-steering`.

    Declares the Campaign's steering INTENT: what good means + where a
    future across-Run steerer may look. PUT semantics: a re-declare
    overwrites the prior intent wholesale.
    """

    objective: SteeringObjectiveRequest = Field(
        ...,
        description="What good means (objective sense + optional target).",
    )
    space: SteeringSpaceRequest = Field(
        ...,
        description="The feasible search space (>= 1 axis).",
    )

    model_config = {"extra": "forbid"}


def objective_from_wire(wire: SteeringObjectiveRequest) -> SteeringObjective:
    """Build a `SteeringObjective` from its Pydantic wire model."""
    return SteeringObjective(
        kind=wire.kind,
        target_measurement_name=wire.target_measurement_name,
        target_value=wire.target_value,
    )


def space_from_wire(wire: SteeringSpaceRequest) -> SteeringSpace:
    """Build a `SteeringSpace` from its Pydantic wire model (lists -> tuples)."""
    return SteeringSpace(
        axes=tuple(
            SteeringAxis(
                name=axis.name,
                lower=axis.lower,
                upper=axis.upper,
                choices=tuple(axis.choices),
            )
            for axis in wire.axes
        )
    )


def _get_handler(request: Request) -> Handler:
    handler: Handler = request.app.state.campaign.declare_campaign_steering
    return handler


router = APIRouter(tags=["campaign"])


@router.post(
    "/campaigns/{campaign_id}/declare-steering",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        status.HTTP_400_BAD_REQUEST: {
            "model": ErrorResponse,
            "description": (
                "Domain invariant violated (empty search space, or a Satisfy "
                "objective missing its target_value / target_measurement_name)."
            ),
        },
        status.HTTP_403_FORBIDDEN: {
            "model": ErrorResponse,
            "description": "Authorize port denied the command.",
        },
        status.HTTP_404_NOT_FOUND: {
            "model": ErrorResponse,
            "description": "No Campaign exists with the given id.",
        },
        status.HTTP_409_CONFLICT: {
            "model": ErrorResponse,
            "description": (
                "Campaign is not in Planned or Active status "
                "(declare_campaign_steering requires Planned | Active)."
            ),
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": "Request body failed schema validation.",
        },
    },
    summary="Declare a Campaign's steering intent (objective + search space)",
)
async def post_campaigns_declare_steering(
    campaign_id: Annotated[UUID, Path(description="Target Campaign's id.")],
    body: DeclareCampaignSteeringRequest,
    handler: Annotated[Handler, Depends(_get_handler)],
    cid: Annotated[UUID, Depends(get_correlation_id)],
    principal_id: Annotated[UUID, Depends(get_principal_id)],
    surface_id: Annotated[UUID, Depends(get_surface_id)],
) -> None:
    await handler(
        DeclareCampaignSteering(
            campaign_id=campaign_id,
            objective=objective_from_wire(body.objective),
            space=space_from_wire(body.space),
        ),
        principal_id=principal_id,
        correlation_id=cid,
        surface_id=surface_id,
    )
