"""HTTP route for the `decommission_frame` slice.

`DELETE /frames/{frame_id}` retires a frame from the coordinate
hierarchy. Carries an operator-supplied `reason` in the request
body. Returns 204 on success, 404 on unknown frame_id, 409 on
already-decommissioned, 409 on FrameInUseError (active consumers
present).
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request, status
from pydantic import BaseModel, Field

from cora.equipment.features.decommission_frame.command import DecommissionFrame
from cora.equipment.features.decommission_frame.handler import Handler
from cora.infrastructure.routing import (
    ErrorResponse,
    get_correlation_id,
    get_principal_id,
    get_surface_id,
)
from cora.shared.text_bounds import REASON_MAX_LENGTH


class DecommissionFrameRequest(BaseModel):
    """Body for `DELETE /frames/{frame_id}`."""

    reason: str = Field(
        ...,
        min_length=1,
        max_length=REASON_MAX_LENGTH,
        description=(
            "Operator-supplied free-text reason captured on the "
            "FrameDecommissioned event payload for audit."
        ),
    )


def _get_handler(request: Request) -> Handler:
    handler: Handler = request.app.state.equipment.decommission_frame
    return handler


router = APIRouter(tags=["equipment"])


@router.delete(
    "/frames/{frame_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
    responses={
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
                "Frame cannot be decommissioned: already Decommissioned, "
                "OR still referenced by one or more active Mount or "
                "child Frame consumers (FrameInUseError)."
            ),
        },
    },
    summary="Decommission a frame (terminal lifecycle)",
)
async def delete_frame(
    frame_id: UUID,
    body: DecommissionFrameRequest,
    handler: Annotated[Handler, Depends(_get_handler)],
    cid: Annotated[UUID, Depends(get_correlation_id)],
    principal_id: Annotated[UUID, Depends(get_principal_id)],
    surface_id: Annotated[UUID, Depends(get_surface_id)],
) -> None:
    await handler(
        DecommissionFrame(frame_id=frame_id, reason=body.reason),
        principal_id=principal_id,
        correlation_id=cid,
        surface_id=surface_id,
    )
