"""HTTP route for the `decommission_asset` slice.

Action endpoint at `POST /assets/{asset_id}/decommission`. Same
action-endpoint pattern as `activate_asset`. 204 No Content on
success.
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Body, Depends, Path, Request, status
from pydantic import BaseModel, Field

from cora.equipment.features.decommission_asset.command import DecommissionAsset
from cora.equipment.features.decommission_asset.handler import Handler
from cora.infrastructure.routing import (
    ErrorResponse,
    get_correlation_id,
    get_principal_id,
    get_surface_id,
)
from cora.shared.text_bounds import REASON_MAX_LENGTH


class DecommissionAssetRequest(BaseModel):
    """Body for `POST /assets/{asset_id}/decommission`."""

    reason: str = Field(
        ...,
        min_length=1,
        max_length=REASON_MAX_LENGTH,
        description="Operator-supplied free-text reason for the audit log.",
    )


def _get_handler(request: Request) -> Handler:
    handler: Handler = request.app.state.equipment.decommission_asset
    return handler


router = APIRouter(tags=["equipment"])


@router.post(
    "/assets/{asset_id}/decommission",
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
                "Asset is not in `Commissioned`, `Active`, or `Maintenance` "
                "lifecycle (decommission requires one of these), OR the Asset "
                "is still bound into a Fixture (detach first), OR the Asset "
                "is still installed in a Mount (uninstall first), OR a "
                "concurrent write to the same asset stream conflicted "
                "(optimistic concurrency)."
            ),
        },
    },
    summary="Decommission an existing asset, retiring it from service",
)
async def post_assets_decommission(
    body: Annotated[DecommissionAssetRequest, Body()],
    asset_id: Annotated[UUID, Path(description="Target asset's id.")],
    handler: Annotated[Handler, Depends(_get_handler)],
    cid: Annotated[UUID, Depends(get_correlation_id)],
    principal_id: Annotated[UUID, Depends(get_principal_id)],
    surface_id: Annotated[UUID, Depends(get_surface_id)],
) -> None:
    await handler(
        DecommissionAsset(asset_id=asset_id, reason=body.reason),
        principal_id=principal_id,
        correlation_id=cid,
        surface_id=surface_id,
    )
