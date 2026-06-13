"""HTTP route for the `relocate_asset` slice.

Action endpoint at `POST /assets/{asset_id}/relocate`. Body
carries `to_parent_id` and `reason`. 204 No Content on success.

Pydantic enforces `reason` is non-empty (1-500 chars) at the API
boundary; the decider trusts its inputs and only enforces domain
invariants.
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Path, Request, status
from pydantic import BaseModel, Field

from cora.equipment.features.relocate_asset.command import RelocateAsset
from cora.equipment.features.relocate_asset.handler import Handler
from cora.infrastructure.routing import (
    ErrorResponse,
    get_correlation_id,
    get_principal_id,
    get_surface_id,
)
from cora.shared.text_bounds import REASON_MAX_LENGTH


class RelocateAssetRequest(BaseModel):
    """Body for `POST /assets/{asset_id}/relocate`.

    `to_parent_id` is required (non-null); root Assets (parent_id=None)
    cannot relocate, and non-root Assets always have a parent. Per
    eventual-consistency stance, the parent's existence is NOT
    verified by the decider.

    `reason` is operator-supplied free text (audit-log breadcrumb).
    """

    to_parent_id: UUID = Field(
        ...,
        description=(
            "New parent in the hierarchy tree. Must be non-null. "
            "Eventual-consistency: parent's existence is NOT verified."
        ),
    )
    reason: str = Field(
        ...,
        min_length=1,
        max_length=REASON_MAX_LENGTH,
        description=(
            "Operator-supplied reason for the relocation (audit-log "
            "breadcrumb), for example 'site reorganization', 'moved to BL2-IBP'."
        ),
    )


def _get_handler(request: Request) -> Handler:
    handler: Handler = request.app.state.equipment.relocate_asset
    return handler


router = APIRouter(tags=["equipment"])


@router.post(
    "/assets/{asset_id}/relocate",
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
                "Asset cannot be relocated under current conditions "
                "(asset is a root / Decommissioned, target is the "
                "asset itself, or target equals current parent), OR a "
                "concurrent write to the same asset stream conflicted "
                "(optimistic concurrency)."
            ),
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": (
                "Request body failed schema validation (missing fields, "
                "malformed UUID, empty reason)."
            ),
        },
    },
    summary="Move an existing asset under a new parent in the hierarchy",
)
async def post_assets_relocate(
    asset_id: Annotated[UUID, Path(description="Target asset's id.")],
    body: RelocateAssetRequest,
    handler: Annotated[Handler, Depends(_get_handler)],
    cid: Annotated[UUID, Depends(get_correlation_id)],
    principal_id: Annotated[UUID, Depends(get_principal_id)],
    surface_id: Annotated[UUID, Depends(get_surface_id)],
) -> None:
    await handler(
        RelocateAsset(
            asset_id=asset_id,
            to_parent_id=body.to_parent_id,
            reason=body.reason,
        ),
        principal_id=principal_id,
        correlation_id=cid,
        surface_id=surface_id,
    )
