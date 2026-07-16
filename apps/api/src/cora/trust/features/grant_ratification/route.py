"""HTTP route for the `grant_ratification` slice.

Action endpoint at `POST /ratifications/{ratification_id}/grant`. No body.
204 on success.
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Path, Request, status

from cora.infrastructure.routing import (
    ErrorResponse,
    get_correlation_id,
    get_principal_id,
    get_surface_id,
)
from cora.trust.features.grant_ratification.command import GrantRatification
from cora.trust.features.grant_ratification.handler import Handler


def _get_handler(request: Request) -> Handler:
    handler: Handler = request.app.state.trust.grant_ratification
    return handler


router = APIRouter(tags=["trust"])


@router.post(
    "/ratifications/{ratification_id}/grant",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        status.HTTP_403_FORBIDDEN: {
            "model": ErrorResponse,
            "description": "Authorize port denied the command.",
        },
        status.HTTP_404_NOT_FOUND: {
            "model": ErrorResponse,
            "description": "No Ratification exists with the given id.",
        },
        status.HTTP_409_CONFLICT: {
            "model": ErrorResponse,
            "description": "Ratification is not in Requested status, or grantor is the requester.",
        },
    },
    summary="Grant (co-sign) a Requested Ratification (Requested -> Granted)",
)
async def post_ratifications_grant(
    ratification_id: Annotated[UUID, Path(description="Target Ratification's id.")],
    handler: Annotated[Handler, Depends(_get_handler)],
    cid: Annotated[UUID, Depends(get_correlation_id)],
    principal_id: Annotated[UUID, Depends(get_principal_id)],
    surface_id: Annotated[UUID, Depends(get_surface_id)],
) -> None:
    await handler(
        GrantRatification(ratification_id=ratification_id),
        principal_id=principal_id,
        correlation_id=cid,
        surface_id=surface_id,
    )
