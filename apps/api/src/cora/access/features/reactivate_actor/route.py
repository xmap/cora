"""HTTP route for the `reactivate_actor` slice.

Action endpoint at `POST /actors/{actor_id}/reactivate`, the counterpart
`deactivate_actor`'s route docstring reserved when it chose an action
endpoint over `DELETE /actors/{actor_id}` precisely so this one would
have a natural home. The verb in the URL matches the command name,
keeping intent explicit for both human and OpenAPI consumers.

204 No Content on success (action verb, no body to return).
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Path, Request, status

from cora.access.features.reactivate_actor.command import ReactivateActor
from cora.access.features.reactivate_actor.handler import Handler
from cora.infrastructure.routing import (
    ErrorResponse,
    get_correlation_id,
    get_principal_id,
    get_surface_id,
)


def _get_handler(request: Request) -> Handler:
    handler: Handler = request.app.state.access.reactivate_actor
    return handler


router = APIRouter(tags=["access"])


@router.post(
    "/actors/{actor_id}/reactivate",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        status.HTTP_403_FORBIDDEN: {
            "model": ErrorResponse,
            "description": "Authorize port denied the command.",
        },
        status.HTTP_404_NOT_FOUND: {
            "model": ErrorResponse,
            "description": "No actor exists with the given id.",
        },
        status.HTTP_409_CONFLICT: {
            "model": ErrorResponse,
            "description": (
                "Actor is already active, OR a concurrent write to the "
                "same actor stream conflicted (optimistic concurrency)."
            ),
        },
    },
    summary="Return a deactivated actor to service",
)
async def post_actors_reactivate(
    actor_id: Annotated[UUID, Path(description="Target actor's id.")],
    handler: Annotated[Handler, Depends(_get_handler)],
    cid: Annotated[UUID, Depends(get_correlation_id)],
    principal_id: Annotated[UUID, Depends(get_principal_id)],
    surface_id: Annotated[UUID, Depends(get_surface_id)],
) -> None:
    await handler(
        ReactivateActor(actor_id=actor_id),
        principal_id=principal_id,
        correlation_id=cid,
        surface_id=surface_id,
    )
