"""HTTP route for the `check_out_visit` slice."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Path, Request, status
from pydantic import BaseModel

from cora.infrastructure.routing import (
    ErrorResponse,
    get_correlation_id,
    get_principal_id,
    get_surface_id,
)
from cora.trust.features.check_out_visit.command import CheckOutVisit
from cora.trust.features.check_out_visit.handler import Handler


class CheckOutVisitRequest(BaseModel):
    """Body for `POST /visits/{visit_id}/check-out`.

    Carries no actor: a caller checks itself out, and the actor is taken from
    the authenticated principal. `extra="forbid"` so a client still sending
    `actor_id` gets a 422 rather than a 204 that silently closed the caller's
    own entry instead of the one it named.
    """

    model_config = {"extra": "forbid"}


def _get_handler(request: Request) -> Handler:
    handler: Handler = request.app.state.trust.check_out_visit
    return handler


router = APIRouter(tags=["trust"])


@router.post(
    "/visits/{visit_id}/check-out",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        status.HTTP_403_FORBIDDEN: {
            "model": ErrorResponse,
            "description": "Authorize port denied the command.",
        },
        status.HTTP_404_NOT_FOUND: {
            "model": ErrorResponse,
            "description": (
                "No Visit exists with the given id, OR actor has no open presence entry."
            ),
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": "Request body failed schema validation.",
        },
    },
    summary="Check an actor out of a Visit",
)
async def post_visits_check_out(
    visit_id: Annotated[UUID, Path(description="Target Visit's id.")],
    body: CheckOutVisitRequest,
    handler: Annotated[Handler, Depends(_get_handler)],
    cid: Annotated[UUID, Depends(get_correlation_id)],
    principal_id: Annotated[UUID, Depends(get_principal_id)],
    surface_id: Annotated[UUID, Depends(get_surface_id)],
) -> None:
    await handler(
        CheckOutVisit(visit_id=visit_id),
        principal_id=principal_id,
        correlation_id=cid,
        surface_id=surface_id,
    )
