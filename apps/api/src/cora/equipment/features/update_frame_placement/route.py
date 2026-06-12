"""HTTP route for the `update_frame_placement` slice.

`PATCH /frames/{frame_id}/placement` mutates the Frame's
`placement`. Re-uses the `PlacementBody`
Pydantic mirror from the register_frame slice for wire-shape parity.
"""

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Request, status
from pydantic import BaseModel, Field

from cora.equipment._bodies import PlacementBody
from cora.equipment.features.update_frame_placement.command import UpdateFramePlacement
from cora.equipment.features.update_frame_placement.handler import Handler
from cora.infrastructure.routing import (
    ErrorResponse,
    get_correlation_id,
    get_principal_id,
    get_surface_id,
)


class UpdateFramePlacementRequest(BaseModel):
    """Body for `PATCH /frames/{frame_id}/placement`.

    `new_placement.parent_frame_id` MUST equal the Frame's existing
    `parent_id` (you cannot reparent via update_frame_placement); the
    decider enforces this with InvalidFrameRootError -> 400.

    `survey` is an optional opaque payload (instrument, technician,
    residual provenance) carried verbatim onto the FramePlacementUpdated
    event. The VO shape is intentionally open until the first
    survey adapter lands.
    """

    new_placement: PlacementBody = Field(
        ...,
        description="The new placement.",
    )
    survey: dict[str, Any] | None = Field(
        None,
        description=(
            "Optional re-survey provenance carried verbatim onto "
            "the event payload. Shape is open until the first "
            "survey adapter lands."
        ),
    )


def _get_handler(request: Request) -> Handler:
    handler: Handler = request.app.state.equipment.update_frame_placement
    return handler


router = APIRouter(tags=["equipment"])


@router.patch(
    "/frames/{frame_id}/placement",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
    responses={
        status.HTTP_400_BAD_REQUEST: {
            "model": ErrorResponse,
            "description": (
                "Domain invariant violated: negative tolerance via "
                "Placement VO OR new_placement.parent_frame_id does not "
                "match the Frame's parent_id."
            ),
        },
        status.HTTP_403_FORBIDDEN: {
            "model": ErrorResponse,
            "description": "Authorize port denied the command.",
        },
        status.HTTP_404_NOT_FOUND: {
            "model": ErrorResponse,
            "description": "No Frame exists with the given frame_id.",
        },
        status.HTTP_409_CONFLICT: {
            "model": ErrorResponse,
            "description": (
                "Frame cannot be updated: currently Decommissioned, "
                "or the Frame is a root frame (root frames have no "
                "placement to update)."
            ),
        },
    },
    summary="Update a frame's placement relative to its parent",
)
async def patch_frame_placement(
    frame_id: UUID,
    body: UpdateFramePlacementRequest,
    handler: Annotated[Handler, Depends(_get_handler)],
    cid: Annotated[UUID, Depends(get_correlation_id)],
    principal_id: Annotated[UUID, Depends(get_principal_id)],
    surface_id: Annotated[UUID, Depends(get_surface_id)],
) -> None:
    placement = body.new_placement.to_domain()
    await handler(
        UpdateFramePlacement(
            frame_id=frame_id,
            new_placement=placement,
            survey=body.survey,
        ),
        principal_id=principal_id,
        correlation_id=cid,
        surface_id=surface_id,
    )
