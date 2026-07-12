"""HTTP route for the `announce_language_model_retirement` slice.

Action endpoint at
`POST /language-models/{language_model_id}/announce-retirement`. Body
carries REQUIRED `reason` (1-500 chars after trim) and optional
`effective_at` (the vendor's announced cutoff). 204 No Content on
success.
"""

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Path, Request, status
from pydantic import BaseModel, Field

from cora.agent.features.announce_language_model_retirement.command import (
    AnnounceLanguageModelRetirement,
)
from cora.agent.features.announce_language_model_retirement.handler import Handler
from cora.infrastructure.routing import (
    ErrorResponse,
    get_correlation_id,
    get_principal_id,
    get_surface_id,
)
from cora.shared.text_bounds import REASON_MAX_LENGTH


class AnnounceLanguageModelRetirementRequest(BaseModel):
    """Body for `POST /language-models/{language_model_id}/announce-retirement`."""

    reason: str = Field(
        min_length=1,
        max_length=REASON_MAX_LENGTH,
        description=(
            "Vendor-sourced retirement reason (1-500 chars after trim). "
            "REQUIRED: the announcement always carries vendor context the "
            "audit log should keep."
        ),
    )
    effective_at: datetime | None = Field(
        default=None,
        description=(
            "The vendor's announced cutoff. Pass null when the vendor gave a warning but no date."
        ),
    )


def _get_handler(request: Request) -> Handler:
    handler: Handler = request.app.state.agent.announce_language_model_retirement
    return handler


router = APIRouter(tags=["agent"])


@router.post(
    "/language-models/{language_model_id}/announce-retirement",
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
                "LanguageModel is not in Approved status "
                "(announce_language_model_retirement is single-source from "
                "Approved only)."
            ),
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": "Request body or path parameter failed schema validation.",
        },
    },
    summary=("Announce a LanguageModel's retirement (Approved -> RetirementAnnounced)"),
)
async def post_language_models_announce_retirement(
    language_model_id: Annotated[UUID, Path(description="Target LanguageModel's id.")],
    body: AnnounceLanguageModelRetirementRequest,
    handler: Annotated[Handler, Depends(_get_handler)],
    cid: Annotated[UUID, Depends(get_correlation_id)],
    principal_id: Annotated[UUID, Depends(get_principal_id)],
    surface_id: Annotated[UUID, Depends(get_surface_id)],
) -> None:
    await handler(
        AnnounceLanguageModelRetirement(
            language_model_id=language_model_id,
            reason=body.reason,
            effective_at=body.effective_at,
        ),
        principal_id=principal_id,
        correlation_id=cid,
        surface_id=surface_id,
    )
