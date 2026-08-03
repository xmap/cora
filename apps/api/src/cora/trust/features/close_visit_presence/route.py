"""HTTP route for the `close_visit_presence` slice.

Action endpoint at `POST /visits/{visit_id}/close-presence`. Body names the
actor whose entry is being closed. 204 on success.
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
from cora.trust.features.close_visit_presence.command import CloseVisitPresence
from cora.trust.features.close_visit_presence.handler import Handler


class CloseVisitPresenceRequest(BaseModel):
    """Body for `POST /visits/{visit_id}/close-presence`.

    Unlike check-in and check-out, this one DOES name an actor, because
    closing somebody else's record is the whole point of the command. The
    caller is still the envelope's `principal_id`, so the record shows both
    who was present and who ended it.
    """

    model_config = {"extra": "forbid"}

    actor_id: UUID = Field(..., description="Actor whose open presence entry is closed.")


def _get_handler(request: Request) -> Handler:
    handler: Handler = request.app.state.trust.close_visit_presence
    return handler


router = APIRouter(tags=["trust"])


@router.post(
    "/visits/{visit_id}/close-presence",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        status.HTTP_403_FORBIDDEN: {
            "model": ErrorResponse,
            "description": "Authorize port denied the command.",
        },
        status.HTTP_404_NOT_FOUND: {
            "model": ErrorResponse,
            "description": (
                "No Visit exists with the given id, OR the named actor has no open presence entry."
            ),
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": "Request body failed schema validation.",
        },
    },
    summary="Close another actor's presence entry on a Visit",
)
async def post_visits_close_presence(
    visit_id: Annotated[UUID, Path(description="Target Visit's id.")],
    body: CloseVisitPresenceRequest,
    handler: Annotated[Handler, Depends(_get_handler)],
    cid: Annotated[UUID, Depends(get_correlation_id)],
    principal_id: Annotated[UUID, Depends(get_principal_id)],
    surface_id: Annotated[UUID, Depends(get_surface_id)],
) -> None:
    await handler(
        CloseVisitPresence(visit_id=visit_id, actor_id=body.actor_id),
        principal_id=principal_id,
        correlation_id=cid,
        surface_id=surface_id,
    )
