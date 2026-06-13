"""HTTP route for the `demote_dataset` slice (post-Q4 compensation primitive).

Action endpoint at `POST /datasets/{dataset_id}/demote`. Body carries
`reason` (1-500 chars). 204 No Content on success. Mirrors the
promote_dataset route shape.
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Path, Request, status
from pydantic import BaseModel, Field

from cora.data.features.demote_dataset.command import DemoteDataset
from cora.data.features.demote_dataset.handler import Handler
from cora.infrastructure.routing import (
    ErrorResponse,
    get_correlation_id,
    get_principal_id,
    get_surface_id,
)
from cora.shared.text_bounds import REASON_MAX_LENGTH


class DemoteDatasetRequest(BaseModel):
    """Body for `POST /datasets/{dataset_id}/demote`."""

    reason: str = Field(
        ...,
        min_length=1,
        max_length=REASON_MAX_LENGTH,
        description=(
            "Free-form reason for the demotion (1-500 chars after trimming). "
            "Captured verbatim in the audit log immutably. Operationally: "
            "'retracting authoritative status because <X>' (calibration error, "
            "methodology challenged, sample compromised, etc.). Today the field "
            "is unstructured; structured taxonomy is future-additive on the "
            "same triggers as DatasetPromoted reason."
        ),
    )


def _get_handler(request: Request) -> Handler:
    handler: Handler = request.app.state.data.demote_dataset
    return handler


router = APIRouter(tags=["data"])


@router.post(
    "/datasets/{dataset_id}/demote",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        status.HTTP_400_BAD_REQUEST: {
            "model": ErrorResponse,
            "description": (
                "Domain invariant violated: whitespace-only reason (InvalidDemotionReasonError)."
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
                "Demotion guard rejected: dataset is Discarded "
                "(DatasetCannotDemoteError); already in Retracted intent "
                "(DatasetAlreadyRetractedError, strict-not-idempotent); "
                "dataset is in Trial intent (DatasetCannotDemoteError; use "
                "discard_dataset for Trial cleanup); OR a concurrent write "
                "to the same Dataset stream conflicted (optimistic concurrency)."
            ),
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": "Path parameter or request body failed schema validation.",
        },
    },
    summary="Demote a Dataset (Production intent → Retracted intent)",
)
async def post_datasets_demote(
    dataset_id: Annotated[UUID, Path(description="Target dataset's id.")],
    body: DemoteDatasetRequest,
    handler: Annotated[Handler, Depends(_get_handler)],
    cid: Annotated[UUID, Depends(get_correlation_id)],
    principal_id: Annotated[UUID, Depends(get_principal_id)],
    surface_id: Annotated[UUID, Depends(get_surface_id)],
) -> None:
    await handler(
        DemoteDataset(dataset_id=dataset_id, reason=body.reason),
        principal_id=principal_id,
        correlation_id=cid,
        surface_id=surface_id,
    )
