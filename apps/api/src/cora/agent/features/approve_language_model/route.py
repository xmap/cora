"""HTTP route for the `approve_language_model` slice.

Action endpoint at `POST /language-models/{language_model_id}/approve`.
Empty body. 204 No Content on success.
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Path, Request, status

from cora.agent.features.approve_language_model.command import ApproveLanguageModel
from cora.agent.features.approve_language_model.handler import Handler
from cora.infrastructure.routing import (
    ErrorResponse,
    get_correlation_id,
    get_principal_id,
    get_surface_id,
)


def _get_handler(request: Request) -> Handler:
    handler: Handler = request.app.state.agent.approve_language_model
    return handler


router = APIRouter(tags=["agent"])


@router.post(
    "/language-models/{language_model_id}/approve",
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
                "LanguageModel is not in Defined status (approve_language_model "
                "is single-source from Defined only)."
            ),
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": "Path parameter failed schema validation.",
        },
    },
    summary="Approve a Defined LanguageModel (Defined -> Approved)",
)
async def post_language_models_approve(
    language_model_id: Annotated[UUID, Path(description="Target LanguageModel's id.")],
    handler: Annotated[Handler, Depends(_get_handler)],
    cid: Annotated[UUID, Depends(get_correlation_id)],
    principal_id: Annotated[UUID, Depends(get_principal_id)],
    surface_id: Annotated[UUID, Depends(get_surface_id)],
) -> None:
    await handler(
        ApproveLanguageModel(language_model_id=language_model_id),
        principal_id=principal_id,
        correlation_id=cid,
        surface_id=surface_id,
    )
