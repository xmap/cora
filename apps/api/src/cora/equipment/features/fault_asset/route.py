"""HTTP route for the `fault_asset` slice.

Action endpoint at `POST /assets/{asset_id}/fault`. Body carries
`reason`. 204 No Content on success.

Pydantic enforces `reason` is non-empty (1-500 chars) at the API
boundary. Same precedent as `relocate_asset` / `degrade_asset`.
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Path, Request, status
from pydantic import BaseModel, Field

from cora.equipment.features.fault_asset.command import FaultAsset
from cora.equipment.features.fault_asset.handler import Handler
from cora.infrastructure.routing import (
    ErrorResponse,
    get_correlation_id,
    get_principal_id,
    get_surface_id,
)
from cora.shared.text_bounds import REASON_MAX_LENGTH


class FaultAssetRequest(BaseModel):
    """Body for `POST /assets/{asset_id}/fault`.

    `reason` is operator-supplied free text (audit-log breadcrumb)
    explaining why the asset is being marked Faulted. Examples:
    "detector saturated, BIOS won't boot", "vacuum pump seized",
    "drive motor controller off-line per EPICS PV".
    """

    reason: str = Field(
        ...,
        min_length=1,
        max_length=REASON_MAX_LENGTH,
        description=("Operator-supplied reason for the fault transition (audit-log breadcrumb)."),
    )


def _get_handler(request: Request) -> Handler:
    handler: Handler = request.app.state.equipment.fault_asset
    return handler


router = APIRouter(tags=["equipment"])


@router.post(
    "/assets/{asset_id}/fault",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        status.HTTP_403_FORBIDDEN: {
            "model": ErrorResponse,
            "description": "Authorize port denied the command.",
        },
        status.HTTP_404_NOT_FOUND: {
            "model": ErrorResponse,
            "description": "No asset exists with the given id.",
        },
        status.HTTP_409_CONFLICT: {
            "model": ErrorResponse,
            "description": (
                "A concurrent write to the same asset stream conflicted (optimistic concurrency)."
            ),
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": (
                "Request body failed schema validation (missing reason, "
                "empty reason, or reason exceeds 500 chars)."
            ),
        },
    },
    summary="Mark an existing asset as Faulted (does not work, requires repair)",
)
async def post_assets_fault(
    asset_id: Annotated[UUID, Path(description="Target asset's id.")],
    body: FaultAssetRequest,
    handler: Annotated[Handler, Depends(_get_handler)],
    cid: Annotated[UUID, Depends(get_correlation_id)],
    principal_id: Annotated[UUID, Depends(get_principal_id)],
    surface_id: Annotated[UUID, Depends(get_surface_id)],
) -> None:
    await handler(
        FaultAsset(asset_id=asset_id, reason=body.reason),
        principal_id=principal_id,
        correlation_id=cid,
        surface_id=surface_id,
    )
