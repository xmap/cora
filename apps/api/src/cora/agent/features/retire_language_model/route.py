"""HTTP route for the `retire_language_model` slice.

Action endpoint at `POST /language-models/{language_model_id}/retire`.
Body optionally carries `reason` (1-500 chars after trim). 204 No
Content on success.
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Path, Request, status
from pydantic import BaseModel, Field

from cora.agent.features.retire_language_model.command import RetireLanguageModel
from cora.agent.features.retire_language_model.handler import Handler
from cora.infrastructure.routing import (
    ErrorResponse,
    get_correlation_id,
    get_principal_id,
    get_surface_id,
)
from cora.shared.text_bounds import REASON_MAX_LENGTH


class RetireLanguageModelRequest(BaseModel):
    """Body for `POST /language-models/{language_model_id}/retire`."""

    reason: str | None = Field(
        default=None,
        min_length=1,
        max_length=REASON_MAX_LENGTH,
        description=(
            "Optional vendor- or operator-sourced retirement reason (1-500 "
            "chars after trim). Pass null when an unannounced removal "
            "arrived with no vendor statement; any earlier announcement's "
            "reason is preserved on the folded state."
        ),
    )


def _get_handler(request: Request) -> Handler:
    handler: Handler = request.app.state.agent.retire_language_model
    return handler


router = APIRouter(tags=["agent"])


@router.post(
    "/language-models/{language_model_id}/retire",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        status.HTTP_400_BAD_REQUEST: {
            "model": ErrorResponse,
            "description": "Reason is empty / whitespace-only / over-cap after trim.",
        },
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
                "LanguageModel is not in Approved or RetirementAnnounced "
                "status (already terminal, or not yet approved)."
            ),
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": "Request body or path parameter failed schema validation.",
        },
    },
    summary=("Retire a LanguageModel (Approved | RetirementAnnounced -> Retired; terminal)"),
)
async def post_language_models_retire(
    language_model_id: Annotated[UUID, Path(description="Target LanguageModel's id.")],
    body: RetireLanguageModelRequest,
    handler: Annotated[Handler, Depends(_get_handler)],
    cid: Annotated[UUID, Depends(get_correlation_id)],
    principal_id: Annotated[UUID, Depends(get_principal_id)],
    surface_id: Annotated[UUID, Depends(get_surface_id)],
) -> None:
    await handler(
        RetireLanguageModel(language_model_id=language_model_id, reason=body.reason),
        principal_id=principal_id,
        correlation_id=cid,
        surface_id=surface_id,
    )
