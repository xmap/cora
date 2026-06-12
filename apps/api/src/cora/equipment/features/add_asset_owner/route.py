"""HTTP route for the `add_asset_owner` slice.

Action endpoint at `POST /assets/{asset_id}/add-owner`. Body
carries the `AssetOwner` block (name + optional contact + paired
identifier/identifier_type). 201 Created on success, mirroring the
Asset BC's POST-style targeted-mutation convention; no DELETE verb
on the Asset aggregate.
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Path, Request, status
from pydantic import BaseModel, Field

from cora.equipment._bodies import AssetOwnerBody
from cora.equipment.features.add_asset_owner.command import AddAssetOwner
from cora.equipment.features.add_asset_owner.handler import Handler
from cora.infrastructure.routing import (
    ErrorResponse,
    get_correlation_id,
    get_principal_id,
    get_surface_id,
)


class AddAssetOwnerRequest(BaseModel):
    """Body for `POST /assets/{asset_id}/add-owner`.

    The full `AssetOwner` block is required. Pydantic enforces
    bounded-text length checks at the boundary; the AssetOwner VO
    re-validates (trim + length + pairing) inside the decider.
    """

    owner: AssetOwnerBody = Field(
        ...,
        description=(
            "The institutional owner block to add. Uniqueness keyed "
            "on `name` at the Asset scope; cross-Asset duplicates "
            "are NOT rejected in v1."
        ),
    )


def _get_handler(request: Request) -> Handler:
    handler: Handler = request.app.state.equipment.add_asset_owner
    return handler


router = APIRouter(tags=["equipment"])


@router.post(
    "/assets/{asset_id}/add-owner",
    status_code=status.HTTP_201_CREATED,
    responses={
        status.HTTP_400_BAD_REQUEST: {
            "model": ErrorResponse,
            "description": (
                "Owner VO validation failed: empty / whitespace-only "
                "name, contact, identifier, or identifier_type; or "
                "the identifier <-> identifier_type pairing invariant "
                "was violated (InvalidAssetOwnerIdentifierPairingError)."
            ),
        },
        status.HTTP_403_FORBIDDEN: {
            "model": ErrorResponse,
            "description": "Authorize policy denied the command.",
        },
        status.HTTP_404_NOT_FOUND: {
            "model": ErrorResponse,
            "description": "No asset exists with the given id.",
        },
        status.HTTP_409_CONFLICT: {
            "model": ErrorResponse,
            "description": (
                "Asset cannot accept the owner under current "
                "conditions: the asset is Decommissioned "
                "(AssetCannotAddOwnerError), OR an owner with the "
                "same name already exists on the asset "
                "(AssetOwnerAlreadyPresentError), OR a concurrent "
                "write to the same asset stream conflicted "
                "(optimistic concurrency)."
            ),
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": (
                "Path parameter or request body failed schema "
                "validation (missing field, malformed UUID, length "
                "out of bounds at the wire layer)."
            ),
        },
    },
    summary="Add an institutional owner to an existing Asset's owners set",
)
async def post_assets_add_owner(
    asset_id: Annotated[UUID, Path(description="Target asset's id.")],
    body: AddAssetOwnerRequest,
    handler: Annotated[Handler, Depends(_get_handler)],
    cid: Annotated[UUID, Depends(get_correlation_id)],
    principal_id: Annotated[UUID, Depends(get_principal_id)],
    surface_id: Annotated[UUID, Depends(get_surface_id)],
) -> None:
    await handler(
        AddAssetOwner(asset_id=asset_id, owner=body.owner.to_domain()),
        principal_id=principal_id,
        correlation_id=cid,
        surface_id=surface_id,
    )
