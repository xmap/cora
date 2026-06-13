"""HTTP route for the `promote_dataset` slice.

Action endpoint at `POST /datasets/{dataset_id}/promote`. Body
carries `reason` (1-500 chars). 204 No Content on success. Mirrors
the discard_dataset route shape.
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Path, Request, status
from pydantic import BaseModel, Field

from cora.data.features.promote_dataset.command import PromoteDataset
from cora.data.features.promote_dataset.handler import Handler
from cora.infrastructure.routing import (
    ErrorResponse,
    get_correlation_id,
    get_principal_id,
    get_surface_id,
)
from cora.shared.text_bounds import REASON_MAX_LENGTH


class PromoteDatasetRequest(BaseModel):
    """Body for `POST /datasets/{dataset_id}/promote`."""

    reason: str = Field(
        ...,
        min_length=1,
        max_length=REASON_MAX_LENGTH,
        description=(
            "Free-form reason for the promotion (1-500 chars after trimming). "
            "Captured verbatim in the audit log immutably. Operationally: "
            "'this is the publication-grade dataset because <X>'. Today the "
            "field is unstructured; structured taxonomy is future-additive "
            "on the same triggers as DatasetDiscarded reason."
        ),
    )


def _get_handler(request: Request) -> Handler:
    handler: Handler = request.app.state.data.promote_dataset
    return handler


router = APIRouter(tags=["data"])


@router.post(
    "/datasets/{dataset_id}/promote",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        status.HTTP_400_BAD_REQUEST: {
            "model": ErrorResponse,
            "description": (
                "Domain invariant violated: whitespace-only reason (InvalidPromotionReasonError)."
            ),
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
                "Promotion guard rejected: dataset is Discarded "
                "(DatasetCannotPromoteError); already in Production intent "
                "(DatasetAlreadyPromotedError, strict-not-idempotent); "
                "producing Run did not Complete (DatasetCannotPromoteError); "
                "one or more derived_from Datasets are still Trial "
                "(DatasetCannotPromoteError); OR a concurrent write to the "
                "same Dataset stream conflicted (optimistic concurrency)."
            ),
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": "Path parameter or request body failed schema validation.",
        },
    },
    summary="Promote a Dataset (Trial intent → Production intent)",
)
async def post_datasets_promote(
    dataset_id: Annotated[UUID, Path(description="Target dataset's id.")],
    body: PromoteDatasetRequest,
    handler: Annotated[Handler, Depends(_get_handler)],
    cid: Annotated[UUID, Depends(get_correlation_id)],
    principal_id: Annotated[UUID, Depends(get_principal_id)],
    surface_id: Annotated[UUID, Depends(get_surface_id)],
) -> None:
    await handler(
        PromoteDataset(dataset_id=dataset_id, reason=body.reason),
        principal_id=principal_id,
        correlation_id=cid,
        surface_id=surface_id,
    )
