"""HTTP route for the `deprecate_plan` slice.

Action endpoint at `POST /plans/{plan_id}/deprecate`. No body. 204
No Content on success.
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Body, Depends, Path, Request, status
from pydantic import BaseModel, Field

from cora.infrastructure.routing import (
    ErrorResponse,
    get_correlation_id,
    get_principal_id,
    get_surface_id,
)
from cora.recipe.features.deprecate_plan.command import DeprecatePlan
from cora.recipe.features.deprecate_plan.handler import Handler
from cora.shared.deprecation import DeprecationReason


class DeprecatePlanRequest(BaseModel):
    """Body for `POST /plans/{plan_id}/deprecate`."""

    reason: DeprecationReason = Field(
        ...,
        description=(
            "Why the template is no longer recommended. `Superseded`: a "
            "newer version replaces it, prior use stands. `Defective`: it "
            "was wrong, prior use is suspect. `Obsolete`: what it targeted "
            "no longer exists."
        ),
    )


def _get_handler(request: Request) -> Handler:
    handler: Handler = request.app.state.recipe.deprecate_plan
    return handler


router = APIRouter(tags=["recipe"])


@router.post(
    "/plans/{plan_id}/deprecate",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        status.HTTP_403_FORBIDDEN: {
            "model": ErrorResponse,
            "description": "Authorize port denied the command.",
        },
        status.HTTP_404_NOT_FOUND: {
            "model": ErrorResponse,
            "description": "No plan exists with the given id.",
        },
        status.HTTP_409_CONFLICT: {
            "model": ErrorResponse,
            "description": (
                "Plan is not in `Defined` or `Versioned` status "
                "(deprecate requires one of those — re-deprecating a "
                "Deprecated plan raises), OR a concurrent write to the "
                "same plan stream conflicted (optimistic concurrency)."
            ),
        },
    },
    summary="Mark an existing plan as deprecated",
)
async def post_plans_deprecate(
    body: Annotated[DeprecatePlanRequest, Body()],
    plan_id: Annotated[UUID, Path(description="Target plan's id.")],
    handler: Annotated[Handler, Depends(_get_handler)],
    cid: Annotated[UUID, Depends(get_correlation_id)],
    principal_id: Annotated[UUID, Depends(get_principal_id)],
    surface_id: Annotated[UUID, Depends(get_surface_id)],
) -> None:
    await handler(
        DeprecatePlan(plan_id=plan_id, reason=body.reason),
        principal_id=principal_id,
        correlation_id=cid,
        surface_id=surface_id,
    )
