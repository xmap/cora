"""HTTP route for the `discard_dataset` slice.

Action endpoint at `POST /datasets/{dataset_id}/discard`. Body
carries `reason` (1-500 chars). 204 No Content on success.
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Path, Request, status
from pydantic import BaseModel, Field

from cora.data.features.discard_dataset.command import DiscardDataset
from cora.data.features.discard_dataset.handler import Handler
from cora.infrastructure.routing import (
    ErrorResponse,
    get_correlation_id,
    get_principal_id,
    get_surface_id,
)
from cora.shared.text_bounds import REASON_MAX_LENGTH


class DiscardDatasetRequest(BaseModel):
    """Body for `POST /datasets/{dataset_id}/discard`."""

    reason: str = Field(
        ...,
        min_length=1,
        max_length=REASON_MAX_LENGTH,
        description=(
            "Free-form reason for the discard (1-500 chars after trimming). "
            "Today the field is unstructured; structured taxonomy is "
            "future-additive on the same triggers as RunStopped/RunAborted/"
            "RunTruncated reasons."
        ),
    )


def _get_handler(request: Request) -> Handler:
    handler: Handler = request.app.state.data.discard_dataset
    return handler


router = APIRouter(tags=["data"])


@router.post(
    "/datasets/{dataset_id}/discard",
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
            "description": "No dataset exists with the given id.",
        },
        status.HTTP_409_CONFLICT: {
            "model": ErrorResponse,
            "description": (
                "Dataset is not in `Registered` status (discard requires it; "
                "re-discarding raises), OR a concurrent write to the same "
                "Dataset stream conflicted (optimistic concurrency)."
            ),
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": "Path parameter or request body failed schema validation.",
        },
    },
    summary="Discard a Dataset (Registered → Discarded)",
)
async def post_datasets_discard(
    dataset_id: Annotated[UUID, Path(description="Target dataset's id.")],
    body: DiscardDatasetRequest,
    handler: Annotated[Handler, Depends(_get_handler)],
    cid: Annotated[UUID, Depends(get_correlation_id)],
    principal_id: Annotated[UUID, Depends(get_principal_id)],
    surface_id: Annotated[UUID, Depends(get_surface_id)],
) -> None:
    await handler(
        DiscardDataset(dataset_id=dataset_id, reason=body.reason),
        principal_id=principal_id,
        correlation_id=cid,
        surface_id=surface_id,
    )
