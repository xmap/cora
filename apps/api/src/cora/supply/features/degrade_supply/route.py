"""HTTP route for the `degrade_supply` slice.

Action endpoint at `POST /supplies/{supply_id}/degrade`. Body
carries `reason`. 204 No Content on success.
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
from cora.shared.text_bounds import REASON_MAX_LENGTH
from cora.supply.features.degrade_supply.command import DegradeSupply
from cora.supply.features.degrade_supply.handler import Handler


class DegradeSupplyRequest(BaseModel):
    """Body for `POST /supplies/{supply_id}/degrade`.

    `reason` is operator-supplied free text (audit-log breadcrumb)
    explaining why the supply is being marked Degraded. Examples:
    "photon beam at half-current after partial top-up", "LN2 dewar
    pressure margin dropped to 20%", "compressed-air pressure drop
    detected by gauge X-12".
    """

    reason: str = Field(
        ...,
        min_length=1,
        max_length=REASON_MAX_LENGTH,
        description=("Operator-supplied reason for the degrade transition (audit-log breadcrumb)."),
    )


def _get_handler(request: Request) -> Handler:
    handler: Handler = request.app.state.supply.degrade_supply
    return handler


router = APIRouter(tags=["supply"])


@router.post(
    "/supplies/{supply_id}/degrade",
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
                "Supply is not in a degradable status. Source set: "
                "{Unknown, Available, Recovering}. An Unavailable supply "
                "cannot transition directly to Degraded (must go via "
                "mark_supply_recovering first)."
            ),
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": (
                "Request body failed schema validation (missing reason, "
                "empty reason, or reason exceeds 500 chars)."
            ),
        },
    },
    summary="Mark a Supply as Degraded (resource up but below nominal capacity)",
)
async def post_supplies_degrade(
    supply_id: Annotated[UUID, Path(description="Target supply's id.")],
    body: DegradeSupplyRequest,
    handler: Annotated[Handler, Depends(_get_handler)],
    cid: Annotated[UUID, Depends(get_correlation_id)],
    principal_id: Annotated[UUID, Depends(get_principal_id)],
    surface_id: Annotated[UUID, Depends(get_surface_id)],
) -> None:
    await handler(
        DegradeSupply(supply_id=supply_id, reason=body.reason),
        principal_id=principal_id,
        correlation_id=cid,
        surface_id=surface_id,
    )
