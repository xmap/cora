"""HTTP route for the `update_mount_placement` slice."""

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Request, status
from pydantic import BaseModel, Field

from cora.equipment._bodies import PlacementBody
from cora.equipment.features.update_mount_placement.command import UpdateMountPlacement
from cora.equipment.features.update_mount_placement.handler import Handler
from cora.infrastructure.routing import (
    ErrorResponse,
    get_correlation_id,
    get_principal_id,
    get_surface_id,
)


class UpdateMountPlacementRequest(BaseModel):
    new_placement: PlacementBody = Field(..., description="The new placement.")
    survey: dict[str, Any] | None = Field(
        None,
        description=("Optional re-survey provenance carried onto the event payload."),
    )


def _get_handler(request: Request) -> Handler:
    handler: Handler = request.app.state.equipment.update_mount_placement
    return handler


router = APIRouter(tags=["equipment"])


@router.patch(
    "/mounts/{mount_id}/placement",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
    responses={
        status.HTTP_400_BAD_REQUEST: {
            "model": ErrorResponse,
            "description": (
                "Placement VO rejection: non-finite (NaN / Inf) coordinate "
                "or tolerance, or negative tolerance on any axis."
            ),
        },
        status.HTTP_403_FORBIDDEN: {
            "model": ErrorResponse,
            "description": "Authorize port denied the command.",
        },
        status.HTTP_404_NOT_FOUND: {
            "model": ErrorResponse,
            "description": "Mount does not exist (MountNotFoundError).",
        },
        status.HTTP_409_CONFLICT: {
            "model": ErrorResponse,
            "description": (
                "Mount is Decommissioned (MountCannotUpdateError) OR the "
                "new placement attempts to reparent to a different Frame "
                "(reparenting requires a separate slice; not in v1). "
                "Submitting a placement equal to the current value is "
                "an idempotent no-op (204)."
            ),
        },
    },
    summary="Update a mount's placement relative to its parent frame",
)
async def patch_mount_placement(
    mount_id: UUID,
    body: UpdateMountPlacementRequest,
    handler: Annotated[Handler, Depends(_get_handler)],
    cid: Annotated[UUID, Depends(get_correlation_id)],
    principal_id: Annotated[UUID, Depends(get_principal_id)],
    surface_id: Annotated[UUID, Depends(get_surface_id)],
) -> None:
    await handler(
        UpdateMountPlacement(
            mount_id=mount_id,
            new_placement=body.new_placement.to_domain(),
            survey=body.survey,
        ),
        principal_id=principal_id,
        correlation_id=cid,
        surface_id=surface_id,
    )
