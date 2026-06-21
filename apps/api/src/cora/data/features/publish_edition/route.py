"""HTTP route for the `publish_edition` slice.

`POST /editions/{edition_id}/publish` returns 200 on success.
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request, Response, status

from cora.data.features.publish_edition.command import PublishEdition
from cora.data.features.publish_edition.handler import Handler
from cora.infrastructure.routing import (
    ErrorResponse,
    get_correlation_id,
    get_principal_id,
    get_surface_id,
)


def _get_handler(request: Request) -> Handler:
    handler: Handler = request.app.state.data.publish_edition
    return handler


router = APIRouter(tags=["data"])


@router.post(
    "/editions/{edition_id}/publish",
    status_code=status.HTTP_200_OK,
    responses={
        status.HTTP_403_FORBIDDEN: {
            "model": ErrorResponse,
            "description": "Authorize port denied the command.",
        },
        status.HTTP_404_NOT_FOUND: {
            "model": ErrorResponse,
            "description": "Edition not found.",
        },
        status.HTTP_409_CONFLICT: {
            "model": ErrorResponse,
            "description": "Edition not in Sealed state.",
        },
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "model": ErrorResponse,
            "description": ("Defensive invariant violated (Sealed Edition has no content_hash)."),
        },
        status.HTTP_502_BAD_GATEWAY: {
            "model": ErrorResponse,
            "description": (
                "PersistentIdentifierMinter.mint or EditionSerializer.serialize failed."
            ),
        },
    },
    summary="Publish a Sealed Edition",
)
async def post_editions_publish(
    edition_id: UUID,
    handler: Annotated[Handler, Depends(_get_handler)],
    cid: Annotated[UUID, Depends(get_correlation_id)],
    principal_id: Annotated[UUID, Depends(get_principal_id)],
    surface_id: Annotated[UUID, Depends(get_surface_id)],
) -> Response:
    await handler(
        PublishEdition(edition_id=edition_id),
        principal_id=principal_id,
        correlation_id=cid,
        surface_id=surface_id,
    )
    return Response(status_code=status.HTTP_200_OK)
