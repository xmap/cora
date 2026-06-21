"""HTTP route for the `assign_asset_persistent_id` slice.

Action endpoint at `POST /assets/{asset_id}/assign-persistent-identifier`.
Thin wire layer: forwards `(asset_id, scheme, suffix)` to the handler,
which resolves the `PersistentIdentifierMinter` call and runs the pure decider. The
route itself does NOT depend on the `PersistentIdentifierMinter` port (Lock 12 keeps
non-determinism in the handler closure only).

201 Created on success with `AssignAssetPersistentIdResponse(scheme, value)`
in the body so the operator learns the server-minted identifier
without a follow-up GET (Lock 17 deviation from the empty-201
convention for Asset mutations).
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Path, Request, status

from cora.equipment._bodies import (
    AssignAssetPersistentIdRequest,
    AssignAssetPersistentIdResponse,
)
from cora.equipment.features.assign_asset_persistent_id.command import AssignAssetPersistentId
from cora.equipment.features.assign_asset_persistent_id.handler import Handler
from cora.infrastructure.routing import (
    ErrorResponse,
    get_correlation_id,
    get_principal_id,
    get_surface_id,
)


def _get_handler(request: Request) -> Handler:
    handler: Handler = request.app.state.equipment.assign_asset_persistent_id
    return handler


router = APIRouter(tags=["equipment"])


@router.post(
    "/assets/{asset_id}/assign-persistent-identifier",
    status_code=status.HTTP_201_CREATED,
    response_model=AssignAssetPersistentIdResponse,
    responses={
        status.HTTP_400_BAD_REQUEST: {
            "model": ErrorResponse,
            "description": (
                "PersistentIdentifier VO validation failed: empty or "
                "whitespace-only value, or value over the max-length "
                "bound (InvalidPersistentIdentifierValueError)."
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
                "Asset cannot accept the persistent identifier under "
                "current conditions: the asset is Decommissioned "
                "(AssetPersistentIdAssignmentForbiddenError), OR the "
                "asset already carries a persistent_id (set-once: "
                "AssetPersistentIdAlreadyAssignedError), OR a "
                "concurrent write to the same asset stream conflicted "
                "(optimistic concurrency)."
            ),
        },
        status.HTTP_502_BAD_GATEWAY: {
            "model": ErrorResponse,
            "description": (
                "The external mint authority (DataCite or Handle.net) "
                "failed to assign a persistent identifier "
                "(PersistentIdentifierMintError)."
            ),
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": (
                "Path parameter or request body failed schema "
                "validation (missing field, malformed UUID, scheme "
                "outside the closed enum, suffix length out of bounds "
                "at the wire layer)."
            ),
        },
    },
    summary="Assign a PIDINST persistent identifier to an existing Asset",
)
async def post_assets_assign_persistent_identifier(
    asset_id: Annotated[UUID, Path(description="Target asset's id.")],
    body: AssignAssetPersistentIdRequest,
    handler: Annotated[Handler, Depends(_get_handler)],
    cid: Annotated[UUID, Depends(get_correlation_id)],
    principal_id: Annotated[UUID, Depends(get_principal_id)],
    surface_id: Annotated[UUID, Depends(get_surface_id)],
) -> AssignAssetPersistentIdResponse:
    persistent_id = await handler(
        AssignAssetPersistentId(
            asset_id=asset_id,
            scheme=body.scheme,
            suffix=body.suffix,
        ),
        principal_id=principal_id,
        correlation_id=cid,
        surface_id=surface_id,
    )
    return AssignAssetPersistentIdResponse(
        scheme=persistent_id.scheme.value,
        value=persistent_id.value,
    )
