"""HTTP route for the `uninstall_asset` slice."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request, status
from pydantic import BaseModel, Field

from cora.equipment.features.uninstall_asset.command import UninstallAsset
from cora.equipment.features.uninstall_asset.handler import Handler
from cora.infrastructure.routing import (
    ErrorResponse,
    get_correlation_id,
    get_principal_id,
    get_surface_id,
)
from cora.shared.text_bounds import REASON_MAX_LENGTH


class UninstallAssetRequest(BaseModel):
    reason: str = Field(
        ...,
        min_length=1,
        max_length=REASON_MAX_LENGTH,
        description="Operator-supplied free-text reason for the audit log.",
    )


def _get_handler(request: Request) -> Handler:
    handler: Handler = request.app.state.equipment.uninstall_asset
    return handler


router = APIRouter(tags=["equipment"])


@router.delete(
    "/mounts/{mount_id}/installed-asset",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
    responses={
        status.HTTP_403_FORBIDDEN: {"model": ErrorResponse},
        status.HTTP_404_NOT_FOUND: {"model": ErrorResponse},
        status.HTTP_409_CONFLICT: {
            "model": ErrorResponse,
            "description": (
                "Mount cannot uninstall: already Decommissioned, OR slot "
                "is vacant (MountIsEmptyError), OR the installed Asset is "
                "still bound to a Fixture (detach first)."
            ),
        },
    },
    summary="Uninstall the currently-installed Asset from a mount slot",
)
async def delete_mount_installed_asset(
    mount_id: UUID,
    body: UninstallAssetRequest,
    handler: Annotated[Handler, Depends(_get_handler)],
    cid: Annotated[UUID, Depends(get_correlation_id)],
    principal_id: Annotated[UUID, Depends(get_principal_id)],
    surface_id: Annotated[UUID, Depends(get_surface_id)],
) -> None:
    await handler(
        UninstallAsset(mount_id=mount_id, reason=body.reason),
        principal_id=principal_id,
        correlation_id=cid,
        surface_id=surface_id,
    )
