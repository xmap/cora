"""HTTP route for the `add_asset_alternate_identifier` slice.

Action endpoint at `POST /assets/{asset_id}/add-alternate-identifier`.
Body carries `kind` (closed StrEnum) and `value` (trimmed bounded text).
204 No Content on success. Same POST-style action pattern as
`add_asset_port` / `remove_asset_alternate_identifier`; consistent
with every other Asset targeted-mutation slice (no DELETE verb is
used anywhere on the Asset aggregate).
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Path, Request, status
from pydantic import BaseModel, Field

from cora.equipment.aggregates.asset import (
    ALTERNATE_IDENTIFIER_VALUE_MAX_LENGTH,
    AlternateIdentifier,
    AlternateIdentifierKind,
)
from cora.equipment.features.add_asset_alternate_identifier.command import (
    AddAssetAlternateIdentifier,
)
from cora.equipment.features.add_asset_alternate_identifier.handler import Handler
from cora.infrastructure.routing import (
    ErrorResponse,
    get_correlation_id,
    get_principal_id,
    get_surface_id,
)


class AddAssetAlternateIdentifierRequest(BaseModel):
    """Body for `POST /assets/{asset_id}/add-alternate-identifier`.

    Both fields required. Pydantic enforces non-empty value at the
    boundary; the `AlternateIdentifier` VO then trims and re-validates
    length within the decider (the VO construction site).
    """

    kind: AlternateIdentifierKind = Field(
        ...,
        description=(
            "Identifier kind from the PIDINST v1.0 controlled vocabulary: "
            "'SerialNumber', 'InventoryNumber', or 'Other'."
        ),
    )
    value: str = Field(
        ...,
        min_length=1,
        max_length=ALTERNATE_IDENTIFIER_VALUE_MAX_LENGTH,
        description=(
            "Identifier value (free text, trimmed, 1-200 chars). "
            "Uniqueness keyed on the (kind, value) pair at the Asset "
            "scope ONLY; cross-Asset duplicates are NOT rejected in v1."
        ),
    )


def _get_handler(request: Request) -> Handler:
    handler: Handler = request.app.state.equipment.add_asset_alternate_identifier
    return handler


router = APIRouter(tags=["equipment"])


@router.post(
    "/assets/{asset_id}/add-alternate-identifier",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        status.HTTP_400_BAD_REQUEST: {
            "model": ErrorResponse,
            "description": (
                "Identifier value is empty / whitespace-only / exceeds "
                "the configured max length after trimming "
                "(InvalidAlternateIdentifierValueError)."
            ),
        },
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
                "Asset cannot accept the alternate identifier under "
                "current conditions (asset is Decommissioned, OR an "
                "alternate identifier with the same (kind, value) pair "
                "already exists on the asset), OR a concurrent write "
                "to the same asset stream conflicted (optimistic "
                "concurrency)."
            ),
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": (
                "Path parameter or request body failed schema "
                "validation (missing field, invalid kind enum, etc.)."
            ),
        },
    },
    summary="Add an alternate identifier to an existing Asset's identifier set",
)
async def post_assets_add_alternate_identifier(
    asset_id: Annotated[UUID, Path(description="Target asset's id.")],
    body: AddAssetAlternateIdentifierRequest,
    handler: Annotated[Handler, Depends(_get_handler)],
    cid: Annotated[UUID, Depends(get_correlation_id)],
    principal_id: Annotated[UUID, Depends(get_principal_id)],
    surface_id: Annotated[UUID, Depends(get_surface_id)],
) -> None:
    await handler(
        AddAssetAlternateIdentifier(
            asset_id=asset_id,
            alternate_identifier=AlternateIdentifier(kind=body.kind, value=body.value),
        ),
        principal_id=principal_id,
        correlation_id=cid,
        surface_id=surface_id,
    )
