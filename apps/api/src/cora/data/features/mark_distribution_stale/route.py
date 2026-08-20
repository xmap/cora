"""HTTP route for the `mark_distribution_stale` slice.

Action endpoint at `POST /distributions/{distribution_id}/mark-stale`.
Body carries `reason` (1-500 chars). 204 No Content on success.
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Path, Request, status
from pydantic import BaseModel, Field

from cora.data.features.mark_distribution_stale.command import MarkDistributionStale
from cora.data.features.mark_distribution_stale.handler import Handler
from cora.infrastructure.routing import (
    ErrorResponse,
    get_correlation_id,
    get_principal_id,
    get_surface_id,
)
from cora.shared.text_bounds import REASON_MAX_LENGTH


class MarkDistributionStaleRequest(BaseModel):
    """Body for `POST /distributions/{distribution_id}/mark-stale`."""

    reason: str = Field(
        ...,
        min_length=1,
        max_length=REASON_MAX_LENGTH,
        description=(
            "Free-form reason the bytes at this location are no longer trusted "
            "(1-500 chars after trimming). Today the field is unstructured; "
            "structured taxonomy is future-additive on the same triggers as the "
            "Dataset discard reason."
        ),
    )


def _get_handler(request: Request) -> Handler:
    handler: Handler = request.app.state.data.mark_distribution_stale
    return handler


router = APIRouter(tags=["data"])


@router.post(
    "/distributions/{distribution_id}/mark-stale",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        status.HTTP_400_BAD_REQUEST: {
            "model": ErrorResponse,
            "description": "Domain invariant violated: whitespace-only reason.",
        },
        status.HTTP_403_FORBIDDEN: {
            "model": ErrorResponse,
            "description": "Authorize port denied the command.",
        },
        status.HTTP_404_NOT_FOUND: {
            "model": ErrorResponse,
            "description": "No distribution exists with the given id.",
        },
        status.HTTP_409_CONFLICT: {
            "model": ErrorResponse,
            "description": (
                "Mark-stale guard violated: the copy is already Discarded "
                "(Discarded is terminal); OR a concurrent write to the same "
                "Distribution stream conflicted (optimistic concurrency)."
            ),
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": "Path parameter or request body failed schema validation.",
        },
    },
    summary="Mark a Distribution copy Stale (record its bytes are no longer trusted)",
)
async def post_distributions_mark_stale(
    distribution_id: Annotated[UUID, Path(description="Target distribution's id.")],
    body: MarkDistributionStaleRequest,
    handler: Annotated[Handler, Depends(_get_handler)],
    cid: Annotated[UUID, Depends(get_correlation_id)],
    principal_id: Annotated[UUID, Depends(get_principal_id)],
    surface_id: Annotated[UUID, Depends(get_surface_id)],
) -> None:
    await handler(
        MarkDistributionStale(distribution_id=distribution_id, reason=body.reason),
        principal_id=principal_id,
        correlation_id=cid,
        surface_id=surface_id,
    )
