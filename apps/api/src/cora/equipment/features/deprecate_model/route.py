"""HTTP route for the `deprecate_model` slice.

Action endpoint at `POST /models/{model_id}/deprecation`. Body carries
the operator-supplied `reason` (1-500 chars, trimmed at the VO).
204 No Content on success. Once deprecated the Model rejects further
versioning or family edits at the decider; existing Assets bound to
the Model continue to function (deprecation is an authoring signal,
not a runtime gate).
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Path, Request, status
from pydantic import BaseModel, Field

from cora.equipment.aggregates.model import MODEL_DEPRECATION_REASON_MAX_LENGTH
from cora.equipment.features.deprecate_model.command import DeprecateModel
from cora.equipment.features.deprecate_model.handler import Handler
from cora.infrastructure.routing import (
    ErrorResponse,
    get_correlation_id,
    get_principal_id,
    get_surface_id,
)


class DeprecateModelRequest(BaseModel):
    """Body for `POST /models/{model_id}/deprecation`.

    `reason` is operator free text recording why the catalog entry is
    being retired (for example "superseded by part RV120CCHL", "vendor
    EOL 2026"). Trimmed and length-validated at the
    `ModelDeprecationReason` VO; whitespace-only is rejected as a
    domain invariant violation (400).
    """

    reason: str = Field(
        ...,
        min_length=1,
        max_length=MODEL_DEPRECATION_REASON_MAX_LENGTH,
        description=(
            "Operator-supplied rationale for retiring this Model "
            "(for example 'superseded by RV120CCHL', 'vendor EOL 2026'). "
            "Free text; trimmed server-side."
        ),
    )


def _get_handler(request: Request) -> Handler:
    handler: Handler = request.app.state.equipment.deprecate_model
    return handler


router = APIRouter(tags=["equipment"])


@router.post(
    "/models/{model_id}/deprecation",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        status.HTTP_400_BAD_REQUEST: {
            "model": ErrorResponse,
            "description": (
                "Domain invariant violated (for example whitespace-only reason after trimming)."
            ),
        },
        status.HTTP_403_FORBIDDEN: {
            "model": ErrorResponse,
            "description": "Authorize port denied the command.",
        },
        status.HTTP_404_NOT_FOUND: {
            "model": ErrorResponse,
            "description": "No model exists with the given id.",
        },
        status.HTTP_409_CONFLICT: {
            "model": ErrorResponse,
            "description": (
                "Model is already in `Deprecated` status (deprecate "
                "requires `Defined` or `Versioned`), OR a concurrent "
                "write to the same model stream conflicted (optimistic "
                "concurrency)."
            ),
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": "Path parameter or request body failed schema validation.",
        },
    },
    summary="Mark an existing Model as deprecated",
)
async def post_models_deprecation(
    model_id: Annotated[UUID, Path(description="Target model's id.")],
    body: DeprecateModelRequest,
    handler: Annotated[Handler, Depends(_get_handler)],
    cid: Annotated[UUID, Depends(get_correlation_id)],
    principal_id: Annotated[UUID, Depends(get_principal_id)],
    surface_id: Annotated[UUID, Depends(get_surface_id)],
) -> None:
    await handler(
        DeprecateModel(
            model_id=model_id,
            reason=body.reason,
        ),
        principal_id=principal_id,
        correlation_id=cid,
        surface_id=surface_id,
    )
