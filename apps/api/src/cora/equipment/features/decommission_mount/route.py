"""HTTP route for the `decommission_mount` slice."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request, status
from pydantic import BaseModel, Field

from cora.equipment.features.decommission_mount.command import DecommissionMount
from cora.equipment.features.decommission_mount.handler import Handler
from cora.infrastructure.routing import (
    ErrorResponse,
    get_correlation_id,
    get_principal_id,
    get_surface_id,
)
from cora.shared.text_bounds import REASON_MAX_LENGTH


class DecommissionMountRequest(BaseModel):
    reason: str = Field(
        ...,
        min_length=1,
        max_length=REASON_MAX_LENGTH,
        description="Operator-supplied free-text reason for the audit log.",
    )


def _get_handler(request: Request) -> Handler:
    handler: Handler = request.app.state.equipment.decommission_mount
    return handler


router = APIRouter(tags=["equipment"])


@router.delete(
    "/mounts/{mount_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
    responses={
        status.HTTP_403_FORBIDDEN: {"model": ErrorResponse},
        status.HTTP_404_NOT_FOUND: {"model": ErrorResponse},
        status.HTTP_409_CONFLICT: {
            "model": ErrorResponse,
            "description": (
                "Mount cannot be decommissioned: already Decommissioned, "
                "still has an installed Asset (uninstall first), OR "
                "still has active child Mounts (decommission children first)."
            ),
        },
    },
    summary="Decommission a mount (terminal lifecycle)",
)
async def delete_mount(
    mount_id: UUID,
    body: DecommissionMountRequest,
    handler: Annotated[Handler, Depends(_get_handler)],
    cid: Annotated[UUID, Depends(get_correlation_id)],
    principal_id: Annotated[UUID, Depends(get_principal_id)],
    surface_id: Annotated[UUID, Depends(get_surface_id)],
) -> None:
    await handler(
        DecommissionMount(mount_id=mount_id, reason=body.reason),
        principal_id=principal_id,
        correlation_id=cid,
        surface_id=surface_id,
    )
