"""HTTP route for the `mark_supply_available` slice.

Action endpoint at `POST /supplies/{supply_id}/mark-available`. Body
carries `reason`. 204 No Content on success.

Pydantic enforces `reason` is non-empty (1-500 chars) at the API
boundary; the decider trusts its inputs and only enforces domain
invariants. Same precedent as `degrade_asset` / `relocate_asset`.
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
from cora.supply.features.mark_supply_available.command import MarkSupplyAvailable
from cora.supply.features.mark_supply_available.handler import Handler


class MarkSupplyAvailableRequest(BaseModel):
    """Body for `POST /supplies/{supply_id}/mark-available`.

    `reason` is operator-supplied free text (audit-log breadcrumb)
    explaining the first-observation declaration. Examples:
    "operator walkdown confirms LN2 dewar pressure nominal", "control
    room reports beam delivered after morning startup", "first-time
    commissioning verified by ops".
    """

    reason: str = Field(
        ...,
        min_length=1,
        max_length=REASON_MAX_LENGTH,
        description=(
            "Operator-supplied reason for declaring the supply Available "
            "for the first time (audit-log breadcrumb)."
        ),
    )


def _get_handler(request: Request) -> Handler:
    handler: Handler = request.app.state.supply.mark_supply_available
    return handler


router = APIRouter(tags=["supply"])


@router.post(
    "/supplies/{supply_id}/mark-available",
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
                "Supply is not in `Unknown` status (mark_supply_available is "
                "single-source from Unknown only; recovery acknowledgement uses "
                "restore_supply)."
            ),
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": (
                "Request body failed schema validation (missing reason, "
                "empty reason, or reason exceeds 500 chars)."
            ),
        },
    },
    summary="Mark a registered Supply Available (first observation; Unknown -> Available)",
)
async def post_supplies_mark_available(
    supply_id: Annotated[UUID, Path(description="Target supply's id.")],
    body: MarkSupplyAvailableRequest,
    handler: Annotated[Handler, Depends(_get_handler)],
    cid: Annotated[UUID, Depends(get_correlation_id)],
    principal_id: Annotated[UUID, Depends(get_principal_id)],
    surface_id: Annotated[UUID, Depends(get_surface_id)],
) -> None:
    await handler(
        MarkSupplyAvailable(supply_id=supply_id, reason=body.reason),
        principal_id=principal_id,
        correlation_id=cid,
        surface_id=surface_id,
    )
