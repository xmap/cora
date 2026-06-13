"""HTTP route for the `reject_clearance` slice.

Action endpoint at `POST /clearances/{clearance_id}/reject`. Body
carries `reason`. The rejecting-actor id is captured from the
request's authenticated principal via the event envelope
(`StoredEvent.principal_id`); no actor field appears on the command
or event payload. 204 No Content on success.
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Path, Request, status
from pydantic import BaseModel, Field

from cora.infrastructure.routing import (
    ErrorResponse,
    get_correlation_id,
    get_principal_id,
    get_surface_id,
)
from cora.safety.features.reject_clearance.command import RejectClearance
from cora.safety.features.reject_clearance.handler import Handler
from cora.shared.text_bounds import REASON_MAX_LENGTH


class RejectClearanceRequest(BaseModel):
    """Body for `POST /clearances/{clearance_id}/reject`."""

    reason: str = Field(
        ...,
        min_length=1,
        max_length=REASON_MAX_LENGTH,
        description=(
            "Operator-supplied free-form reason for the rejection. Audit "
            "breadcrumb explaining why the reviewer rejected the clearance."
        ),
    )


def _get_handler(request: Request) -> Handler:
    handler: Handler = request.app.state.safety.reject_clearance
    return handler


router = APIRouter(tags=["safety"])


@router.post(
    "/clearances/{clearance_id}/reject",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        status.HTTP_400_BAD_REQUEST: {
            "model": ErrorResponse,
            "description": "Domain invariant violated (for example whitespace-only reason).",
        },
        status.HTTP_403_FORBIDDEN: {
            "model": ErrorResponse,
            "description": "Authorize port denied the command.",
        },
        status.HTTP_404_NOT_FOUND: {
            "model": ErrorResponse,
            "description": "No clearance exists with the given id.",
        },
        status.HTTP_409_CONFLICT: {
            "model": ErrorResponse,
            "description": (
                "Clearance is not in UnderReview status (reject_clearance "
                "is single-source from UnderReview only)."
            ),
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": (
                "Request body failed schema validation (missing reason, "
                "empty reason, or reason exceeds 500 chars)."
            ),
        },
    },
    summary="Reject an UnderReview clearance (UnderReview -> Rejected)",
)
async def post_clearances_reject(
    clearance_id: Annotated[UUID, Path(description="Target clearance's id.")],
    body: RejectClearanceRequest,
    handler: Annotated[Handler, Depends(_get_handler)],
    cid: Annotated[UUID, Depends(get_correlation_id)],
    principal_id: Annotated[UUID, Depends(get_principal_id)],
    surface_id: Annotated[UUID, Depends(get_surface_id)],
) -> None:
    await handler(
        RejectClearance(
            clearance_id=clearance_id,
            reason=body.reason,
        ),
        principal_id=principal_id,
        correlation_id=cid,
        surface_id=surface_id,
    )
