"""HTTP route for the `mark_supply_recovering` slice."""

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
from cora.shared.text_bounds import REASON_MAX_LENGTH
from cora.supply.features.mark_supply_recovering.command import MarkSupplyRecovering
from cora.supply.features.mark_supply_recovering.handler import Handler


class MarkSupplyRecoveringRequest(BaseModel):
    """Body for `POST /supplies/{supply_id}/mark-recovering`.

    `reason` is operator-supplied free text (audit-log breadcrumb)
    explaining why the supply is being marked Recovering. Examples:
    "beam current detected at 50% nominal", "LN2 dewar refill in
    progress", "vacuum pump-down underway, awaiting target pressure".
    """

    reason: str = Field(
        ...,
        min_length=1,
        max_length=REASON_MAX_LENGTH,
        description=(
            "Operator-supplied reason for the mark-recovering transition (audit-log breadcrumb)."
        ),
    )


def _get_handler(request: Request) -> Handler:
    handler: Handler = request.app.state.supply.mark_supply_recovering
    return handler


router = APIRouter(tags=["supply"])


@router.post(
    "/supplies/{supply_id}/mark-recovering",
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
            "description": "No supply exists with the given id.",
        },
        status.HTTP_409_CONFLICT: {
            "model": ErrorResponse,
            "description": (
                "Supply is not Unavailable. Single-source: only an "
                "Unavailable supply can be marked Recovering."
            ),
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": (
                "Request body failed schema validation (missing reason, "
                "empty reason, or reason exceeds 500 chars)."
            ),
        },
    },
    summary="Mark a Supply as Recovering (observation suggests it may be coming back)",
)
async def post_supplies_mark_recovering(
    supply_id: Annotated[UUID, Path(description="Target supply's id.")],
    body: MarkSupplyRecoveringRequest,
    handler: Annotated[Handler, Depends(_get_handler)],
    cid: Annotated[UUID, Depends(get_correlation_id)],
    principal_id: Annotated[UUID, Depends(get_principal_id)],
    surface_id: Annotated[UUID, Depends(get_surface_id)],
) -> None:
    await handler(
        MarkSupplyRecovering(supply_id=supply_id, reason=body.reason),
        principal_id=principal_id,
        correlation_id=cid,
        surface_id=surface_id,
    )
