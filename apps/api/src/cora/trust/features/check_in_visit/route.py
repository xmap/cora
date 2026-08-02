"""HTTP route for the `check_in_visit` slice.

Action endpoint at `POST /visits/{visit_id}/check-in`. Body carries `mode`
only; the actor is the authenticated principal. 204 on success.
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
from cora.trust.aggregates.visit import PresenceMode
from cora.trust.features.check_in_visit.command import CheckInVisit
from cora.trust.features.check_in_visit.handler import Handler


class CheckInVisitRequest(BaseModel):
    """Body for `POST /visits/{visit_id}/check-in`.

    Carries no actor: a caller checks itself in, and the actor is taken from
    the authenticated principal. `extra="forbid"` so a client still sending
    `actor_id` gets a 422 rather than a 204 that silently recorded the caller
    instead of the actor it named.
    """

    model_config = {"extra": "forbid"}

    mode: PresenceMode = Field(
        ..., description="physical (on-site) or remote (e.g., PI driving via API)."
    )


def _get_handler(request: Request) -> Handler:
    handler: Handler = request.app.state.trust.check_in_visit
    return handler


router = APIRouter(tags=["trust"])


@router.post(
    "/visits/{visit_id}/check-in",
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
            "description": (
                "Visit is not in {Arrived, InProgress, OnHold} status OR actor "
                "already has an open presence entry (check out first)."
            ),
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": "Request body failed schema validation.",
        },
    },
    summary="Check the calling principal in to a Visit (physical or remote)",
)
async def post_visits_check_in(
    visit_id: Annotated[UUID, Path(description="Target Visit's id.")],
    body: CheckInVisitRequest,
    handler: Annotated[Handler, Depends(_get_handler)],
    cid: Annotated[UUID, Depends(get_correlation_id)],
    principal_id: Annotated[UUID, Depends(get_principal_id)],
    surface_id: Annotated[UUID, Depends(get_surface_id)],
) -> None:
    await handler(
        CheckInVisit(visit_id=visit_id, mode=body.mode),
        principal_id=principal_id,
        correlation_id=cid,
        surface_id=surface_id,
    )
