"""HTTP route for the `deprecate_model` slice.

Action endpoint at `POST /models/{model_id}/deprecation`. Body carries
the required `reason`, a closed `DeprecationReason` (Superseded / Defective / Obsolete).
204 No Content on success. Once deprecated the Model rejects further
versioning or family edits at the decider; existing Assets bound to
the Model continue to function (deprecation is an authoring signal,
not a runtime gate).
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Path, Request, status
from pydantic import BaseModel, Field

from cora.equipment.features.deprecate_model.command import DeprecateModel
from cora.equipment.features.deprecate_model.handler import Handler
from cora.infrastructure.routing import (
    ErrorResponse,
    get_correlation_id,
    get_principal_id,
    get_surface_id,
)
from cora.shared.deprecation import DeprecationReason


class DeprecateModelRequest(BaseModel):
    """Body for `POST /models/{model_id}/deprecation`.

    `reason` is the closed `DeprecationReason` enum. An unknown value is
    rejected by Pydantic as a 422 before the handler runs. Vendor detail
    that used to ride in free text (a part number, an EOL date) belongs
    on the Model's own fields or a Caution, not on the terminal event.
    """

    reason: DeprecationReason = Field(
        ...,
        description=(
            "Why the template is no longer recommended. `Superseded`: a "
            "newer version replaces it, prior use stands. `Defective`: it "
            "was wrong, prior use is suspect. `Obsolete`: what it targeted "
            "no longer exists."
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
