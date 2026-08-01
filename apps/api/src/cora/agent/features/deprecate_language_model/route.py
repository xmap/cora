"""HTTP route for the `deprecate_language_model` slice.

Action endpoint at
`POST /language-models/{language_model_id}/deprecate`. Body carries
REQUIRED `reason`, a closed `DeprecationReason` (Superseded /
Defective / Obsolete). 204 No Content on success.
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Path, Request, status
from pydantic import BaseModel, Field

from cora.agent.features.deprecate_language_model.command import DeprecateLanguageModel
from cora.agent.features.deprecate_language_model.handler import Handler
from cora.infrastructure.routing import (
    ErrorResponse,
    get_correlation_id,
    get_principal_id,
    get_surface_id,
)
from cora.shared.deprecation import DeprecationReason


class DeprecateLanguageModelRequest(BaseModel):
    """Body for `POST /language-models/{language_model_id}/deprecate`."""

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
    handler: Handler = request.app.state.agent.deprecate_language_model
    return handler


router = APIRouter(tags=["agent"])


@router.post(
    "/language-models/{language_model_id}/deprecate",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        status.HTTP_403_FORBIDDEN: {
            "model": ErrorResponse,
            "description": "Authorize port denied the command.",
        },
        status.HTTP_404_NOT_FOUND: {
            "model": ErrorResponse,
            "description": "No LanguageModel exists with the given id.",
        },
        status.HTTP_409_CONFLICT: {
            "model": ErrorResponse,
            "description": (
                "LanguageModel is already terminal (Retired or Deprecated; strict-not-idempotent)."
            ),
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": "Request body or path parameter failed schema validation.",
        },
    },
    summary=(
        "Deprecate a LanguageModel (Defined | Approved | RetirementAnnounced "
        "-> Deprecated; terminal)"
    ),
)
async def post_language_models_deprecate(
    language_model_id: Annotated[UUID, Path(description="Target LanguageModel's id.")],
    body: DeprecateLanguageModelRequest,
    handler: Annotated[Handler, Depends(_get_handler)],
    cid: Annotated[UUID, Depends(get_correlation_id)],
    principal_id: Annotated[UUID, Depends(get_principal_id)],
    surface_id: Annotated[UUID, Depends(get_surface_id)],
) -> None:
    await handler(
        DeprecateLanguageModel(language_model_id=language_model_id, reason=body.reason),
        principal_id=principal_id,
        correlation_id=cid,
        surface_id=surface_id,
    )
