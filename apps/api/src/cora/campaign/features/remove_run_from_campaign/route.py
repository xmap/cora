"""HTTP route for the `remove_run_from_campaign` slice.

Action endpoint at `POST /campaigns/{campaign_id}/runs/{run_id}/remove`.
Body carries `reason`. 204 No Content on success.
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Path, Request, status
from pydantic import BaseModel, Field

from cora.campaign.features.remove_run_from_campaign.command import RemoveRunFromCampaign
from cora.campaign.features.remove_run_from_campaign.handler import Handler
from cora.infrastructure.routing import (
    ErrorResponse,
    get_correlation_id,
    get_principal_id,
    get_surface_id,
)
from cora.shared.text_bounds import REASON_MAX_LENGTH


class RemoveRunFromCampaignRequest(BaseModel):
    """Body for `POST /campaigns/{campaign_id}/runs/{run_id}/remove`.

    `reason` is REQUIRED -- ungrouping is meaningful and operators must
    say why. Per-membership audit breadcrumb; not the Campaign's
    `last_status_reason` (that field is for status transitions only).
    """

    reason: str = Field(
        ...,
        min_length=1,
        max_length=REASON_MAX_LENGTH,
        description=(
            "Operator-supplied reason for removing the Run from the Campaign "
            "(per-membership audit breadcrumb, REQUIRED)."
        ),
    )


def _get_handler(request: Request) -> Handler:
    handler: Handler = request.app.state.campaign.remove_run_from_campaign
    return handler


router = APIRouter(tags=["campaign"])


@router.post(
    "/campaigns/{campaign_id}/runs/{run_id}/remove",
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
            "description": "Campaign or Run does not exist.",
        },
        status.HTTP_409_CONFLICT: {
            "model": ErrorResponse,
            "description": (
                "Campaign is in a terminal status (Closed / Abandoned), OR "
                "the Run is not a member of this Campaign, OR an optimistic-"
                "concurrency conflict on either stream."
            ),
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": (
                "Request body failed schema validation (missing reason, "
                "empty reason, or reason exceeds 500 chars)."
            ),
        },
    },
    summary="Remove a Run from a Campaign (atomic two-stream write)",
)
async def post_campaign_runs_remove(
    campaign_id: Annotated[UUID, Path(description="Target Campaign's id.")],
    run_id: Annotated[UUID, Path(description="Run to remove from the Campaign.")],
    body: RemoveRunFromCampaignRequest,
    handler: Annotated[Handler, Depends(_get_handler)],
    cid: Annotated[UUID, Depends(get_correlation_id)],
    principal_id: Annotated[UUID, Depends(get_principal_id)],
    surface_id: Annotated[UUID, Depends(get_surface_id)],
) -> None:
    await handler(
        RemoveRunFromCampaign(
            campaign_id=campaign_id,
            run_id=run_id,
            reason=body.reason,
        ),
        principal_id=principal_id,
        correlation_id=cid,
        surface_id=surface_id,
    )
