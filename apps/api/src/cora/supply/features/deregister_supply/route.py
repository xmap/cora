"""HTTP route for the `deregister_supply` slice."""

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
from cora.supply.features.deregister_supply.command import DeregisterSupply
from cora.supply.features.deregister_supply.handler import Handler


class DeregisterSupplyRequest(BaseModel):
    """Body for `POST /supplies/{supply_id}/deregister`.

    `reason` is operator-supplied free text (audit-log breadcrumb)
    explaining why the supply is being deregistered. Examples:
    "typo on scope at registration; re-registering correctly",
    "beamline retired", "duplicate of supply <id>".
    """

    reason: str = Field(
        ...,
        min_length=1,
        max_length=REASON_MAX_LENGTH,
        description=(
            "Operator-supplied reason for the deregister transition (audit-log breadcrumb)."
        ),
    )


def _get_handler(request: Request) -> Handler:
    handler: Handler = request.app.state.supply.deregister_supply
    return handler


router = APIRouter(tags=["supply"])


@router.post(
    "/supplies/{supply_id}/deregister",
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
            "description": ("Supply is already Decommissioned (strict-not-idempotent)."),
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": (
                "Request body failed schema validation (missing reason, "
                "empty reason, or reason exceeds 500 chars)."
            ),
        },
    },
    summary="Deregister a Supply (lifecycle terminal: any -> Decommissioned)",
)
async def post_supplies_deregister(
    supply_id: Annotated[UUID, Path(description="Target supply's id.")],
    body: DeregisterSupplyRequest,
    handler: Annotated[Handler, Depends(_get_handler)],
    cid: Annotated[UUID, Depends(get_correlation_id)],
    principal_id: Annotated[UUID, Depends(get_principal_id)],
    surface_id: Annotated[UUID, Depends(get_surface_id)],
) -> None:
    await handler(
        DeregisterSupply(supply_id=supply_id, reason=body.reason),
        principal_id=principal_id,
        correlation_id=cid,
        surface_id=surface_id,
    )
