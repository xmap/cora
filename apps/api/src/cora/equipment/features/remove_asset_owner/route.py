"""HTTP route for the `remove_asset_owner` slice.

Action endpoint at `POST /assets/{asset_id}/remove-owner`. Body
carries the `owner_name` string. 204 No Content on success. Mirror
of `add_asset_owner` route shape; POST verb consistent with the
Asset BC's no-DELETE convention for targeted-mutation slices.
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Path, Request, status
from pydantic import BaseModel, Field

from cora.equipment.aggregates.asset import (
    ASSET_OWNER_NAME_MAX_LENGTH,
    AssetOwnerName,
)
from cora.equipment.features.remove_asset_owner.command import RemoveAssetOwner
from cora.equipment.features.remove_asset_owner.handler import Handler
from cora.infrastructure.routing import (
    ErrorResponse,
    get_correlation_id,
    get_principal_id,
    get_surface_id,
)


class RemoveAssetOwnerRequest(BaseModel):
    """Body for `POST /assets/{asset_id}/remove-owner`.

    Carries only `owner_name` (Lock 5: removal keys on name, not
    on the full VO).
    """

    owner_name: str = Field(
        ...,
        min_length=1,
        max_length=ASSET_OWNER_NAME_MAX_LENGTH,
        description=(
            "Name of the institutional owner to remove. Matched "
            "against the asset's stored owners by exact name."
        ),
    )


def _get_handler(request: Request) -> Handler:
    handler: Handler = request.app.state.equipment.remove_asset_owner
    return handler


router = APIRouter(tags=["equipment"])


@router.post(
    "/assets/{asset_id}/remove-owner",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        status.HTTP_400_BAD_REQUEST: {
            "model": ErrorResponse,
            "description": (
                "Owner name is empty / whitespace-only / exceeds the "
                "configured max length after trimming "
                "(InvalidAssetOwnerNameError)."
            ),
        },
        status.HTTP_403_FORBIDDEN: {
            "model": ErrorResponse,
            "description": "Authorize policy denied the command.",
        },
        status.HTTP_404_NOT_FOUND: {
            "model": ErrorResponse,
            "description": (
                "No asset exists with the given id "
                "(AssetNotFoundError), OR no owner with the given "
                "name exists on the asset "
                "(AssetOwnerNotPresentError; strict-not-idempotent)."
            ),
        },
        status.HTTP_409_CONFLICT: {
            "model": ErrorResponse,
            "description": (
                "Asset cannot remove the owner under current "
                "conditions: the asset is Decommissioned "
                "(AssetCannotAddOwnerError; the shared lifecycle-"
                "guard class is used by BOTH add and remove), OR a "
                "concurrent write to the same asset stream "
                "conflicted (optimistic concurrency)."
            ),
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": (
                "Path parameter or request body failed schema "
                "validation (missing field, malformed UUID)."
            ),
        },
    },
    summary="Remove an institutional owner from an existing Asset's owners set",
)
async def post_assets_remove_owner(
    asset_id: Annotated[UUID, Path(description="Target asset's id.")],
    body: RemoveAssetOwnerRequest,
    handler: Annotated[Handler, Depends(_get_handler)],
    cid: Annotated[UUID, Depends(get_correlation_id)],
    principal_id: Annotated[UUID, Depends(get_principal_id)],
    surface_id: Annotated[UUID, Depends(get_surface_id)],
) -> None:
    await handler(
        RemoveAssetOwner(
            asset_id=asset_id,
            owner_name=AssetOwnerName(body.owner_name),
        ),
        principal_id=principal_id,
        correlation_id=cid,
        surface_id=surface_id,
    )
