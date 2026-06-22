"""HTTP route for the `record_visit_arrival` slice.

Action endpoint at `POST /visits/{visit_id}/record-arrival`. No body. 204 on success.
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
from cora.trust.features.record_visit_arrival.command import RecordVisitArrival
from cora.trust.features.record_visit_arrival.handler import Handler


def _get_handler(request: Request) -> Handler:
    handler: Handler = request.app.state.trust.record_visit_arrival
    return handler


router = APIRouter(tags=["trust"])


@router.post(
    "/visits/{visit_id}/record-arrival",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        status.HTTP_403_FORBIDDEN: {
            "model": ErrorResponse,
            "description": "Authorize port denied the command.",
        },
        status.HTTP_404_NOT_FOUND: {
            "model": ErrorResponse,
            "description": "No Visit exists with the given id.",
        },
        status.HTTP_409_CONFLICT: {
            "model": ErrorResponse,
            "description": "Visit is not in Planned status.",
        },
    },
    summary="Record arrival at a Planned Visit (Planned -> Arrived)",
)
async def post_visits_record_arrival(
    visit_id: Annotated[UUID, Path(description="Target Visit's id.")],
    handler: Annotated[Handler, Depends(_get_handler)],
    cid: Annotated[UUID, Depends(get_correlation_id)],
    principal_id: Annotated[UUID, Depends(get_principal_id)],
    surface_id: Annotated[UUID, Depends(get_surface_id)],
) -> None:
    await handler(
        RecordVisitArrival(visit_id=visit_id),
        principal_id=principal_id,
        correlation_id=cid,
        surface_id=surface_id,
    )
