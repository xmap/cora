"""HTTP route for the `restore_asset` slice.

Action endpoint at `POST /assets/{asset_id}/restore`. Body carries
`reason`. 204 No Content on success.

Distinct from `POST /assets/{asset_id}/exit-maintenance`
which moves lifecycle (Maintenance -> Active); this endpoint moves
condition (any -> Nominal).
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Path, Request, status
from pydantic import BaseModel, Field

from cora.equipment.features.restore_asset.command import RestoreAsset
from cora.equipment.features.restore_asset.handler import Handler
from cora.infrastructure.routing import (
    ErrorResponse,
    get_correlation_id,
    get_principal_id,
    get_surface_id,
)
from cora.shared.text_bounds import REASON_MAX_LENGTH


class RestoreAssetRequest(BaseModel):
    """Body for `POST /assets/{asset_id}/restore`.

    `reason` is operator-supplied free text (audit-log breadcrumb)
    explaining the repair. Examples: "replaced flat cable", "cleaned
    sample stage and recalibrated", "vacuum pump rebuild complete".
    """

    reason: str = Field(
        ...,
        min_length=1,
        max_length=REASON_MAX_LENGTH,
        description=("Operator-supplied reason for the restore transition (audit-log breadcrumb)."),
    )


def _get_handler(request: Request) -> Handler:
    handler: Handler = request.app.state.equipment.restore_asset
    return handler


router = APIRouter(tags=["equipment"])


@router.post(
    "/assets/{asset_id}/restore",
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
    summary="Mark an existing asset as Nominal (fully repaired)",
)
async def post_assets_restore(
    asset_id: Annotated[UUID, Path(description="Target asset's id.")],
    body: RestoreAssetRequest,
    handler: Annotated[Handler, Depends(_get_handler)],
    cid: Annotated[UUID, Depends(get_correlation_id)],
    principal_id: Annotated[UUID, Depends(get_principal_id)],
    surface_id: Annotated[UUID, Depends(get_surface_id)],
) -> None:
    await handler(
        RestoreAsset(asset_id=asset_id, reason=body.reason),
        principal_id=principal_id,
        correlation_id=cid,
        surface_id=surface_id,
    )
