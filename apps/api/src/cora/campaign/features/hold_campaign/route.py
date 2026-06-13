"""HTTP route for the `hold_campaign` slice.

Action endpoint at `POST /campaigns/{campaign_id}/hold`. Body carries
`reason`. 204 No Content on success.
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Path, Request, status
from pydantic import BaseModel, Field

from cora.campaign.features.hold_campaign.command import HoldCampaign
from cora.campaign.features.hold_campaign.handler import Handler
from cora.infrastructure.routing import (
    ErrorResponse,
    get_correlation_id,
    get_principal_id,
    get_surface_id,
)
from cora.shared.text_bounds import REASON_MAX_LENGTH


class HoldCampaignRequest(BaseModel):
    """Body for `POST /campaigns/{campaign_id}/hold`.

    `reason` is operator-supplied free text (audit-log breadcrumb)
    explaining why the Campaign is being paused. Examples: "beam
    interruption", "operator break", "instrument alignment after
    thermal soak".
    """

    reason: str = Field(
        ...,
        min_length=1,
        max_length=REASON_MAX_LENGTH,
        description=("Operator-supplied reason for the hold (audit-log breadcrumb)."),
    )


def _get_handler(request: Request) -> Handler:
    handler: Handler = request.app.state.campaign.hold_campaign
    return handler


router = APIRouter(tags=["campaign"])


@router.post(
    "/campaigns/{campaign_id}/hold",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        status.HTTP_400_BAD_REQUEST: {
            "model": ErrorResponse,
            "description": "Domain invariant violated (whitespace-only reason).",
        },
        status.HTTP_403_FORBIDDEN: {
            "model": ErrorResponse,
            "description": "Authorize port denied the command.",
        },
        status.HTTP_404_NOT_FOUND: {
            "model": ErrorResponse,
            "description": "No Campaign exists with the given id.",
        },
        status.HTTP_409_CONFLICT: {
            "model": ErrorResponse,
            "description": (
                "Campaign is not in Active status (hold_campaign is "
                "single-source from Active only)."
            ),
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": (
                "Request body failed schema validation (missing reason, "
                "empty reason, or reason exceeds 500 chars)."
            ),
        },
    },
    summary="Hold an Active Campaign (Active -> Held)",
)
async def post_campaigns_hold(
    campaign_id: Annotated[UUID, Path(description="Target Campaign's id.")],
    body: HoldCampaignRequest,
    handler: Annotated[Handler, Depends(_get_handler)],
    cid: Annotated[UUID, Depends(get_correlation_id)],
    principal_id: Annotated[UUID, Depends(get_principal_id)],
    surface_id: Annotated[UUID, Depends(get_surface_id)],
) -> None:
    await handler(
        HoldCampaign(campaign_id=campaign_id, reason=body.reason),
        principal_id=principal_id,
        correlation_id=cid,
        surface_id=surface_id,
    )
