"""HTTP route for the `get_asset` query slice.

`GET /assets/{asset_id}` returns 200 + AssetResponse on hit, 404 on
miss. The handler returns `Asset | None`; the route maps None to 404
via HTTPException (idiomatic in routes; the BC's exception-handler
infrastructure stays focused on domain / application errors raised
deeper in the stack).

Response carries the full Asset state including the hierarchy
(`parent_id` is `UUID | None` — null only for facility-rooted Assets),
the `lifecycle` enum string, the `condition` enum string (5g-b),
the `settings` dict (5g-c), and the `ports` list (5h).
"""

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Path, Request, status
from pydantic import BaseModel, Field

from cora.equipment.aggregates.asset import ASSET_NAME_MAX_LENGTH
from cora.equipment.features.get_asset.handler import Handler
from cora.equipment.features.get_asset.query import GetAsset
from cora.infrastructure.routing import (
    ErrorResponse,
    get_correlation_id,
    get_principal_id,
    get_surface_id,
)


class AssetPortDTO(BaseModel):
    """Read-side DTO for a single Asset port (5h)."""

    name: str
    direction: str
    signal_type: str


class AssetResponse(BaseModel):
    """Read-side DTO at the API boundary.

    Carries primitives, not domain VOs. Decouples the wire format
    from the domain model so the two can evolve independently.
    `tier`, `lifecycle`, and `condition` are the StrEnum string
    values (PascalCase per the BC map). `parent_id` is null only for
    facility-rooted Assets. `family_ids` serializes as a sorted list
    of UUIDs (frozenset semantics in domain state, list at the JSON
    boundary; sorted by UUID string form for response determinism).
    `settings` is the operator-supplied dict (operationally typed by
    Family schemas at write time). `ports` (5h) serializes as a
    list sorted by port name.
    """

    id: UUID
    name: str = Field(..., max_length=ASSET_NAME_MAX_LENGTH)
    tier: str
    parent_id: UUID | None
    lifecycle: str
    condition: str
    family_ids: list[UUID]
    settings: dict[str, Any]
    ports: list[AssetPortDTO]


def _get_handler(request: Request) -> Handler:
    handler: Handler = request.app.state.equipment.get_asset
    return handler


router = APIRouter(tags=["equipment"])


@router.get(
    "/assets/{asset_id}",
    status_code=status.HTTP_200_OK,
    response_model=AssetResponse,
    responses={
        status.HTTP_404_NOT_FOUND: {
            "model": ErrorResponse,
            "description": "No asset exists with the given id.",
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": "Path parameter failed schema validation.",
        },
    },
    summary="Get an asset by id",
)
async def get_assets(
    asset_id: Annotated[UUID, Path(description="Target asset's id.")],
    handler: Annotated[Handler, Depends(_get_handler)],
    cid: Annotated[UUID, Depends(get_correlation_id)],
    principal_id: Annotated[UUID, Depends(get_principal_id)],
    surface_id: Annotated[UUID, Depends(get_surface_id)],
) -> AssetResponse:
    asset = await handler(
        GetAsset(asset_id=asset_id),
        principal_id=principal_id,
        correlation_id=cid,
        surface_id=surface_id,
    )
    if asset is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Asset {asset_id} not found",
        )
    return AssetResponse(
        id=asset.id,
        name=asset.name.value,
        tier=asset.tier.value,
        parent_id=asset.parent_id,
        lifecycle=asset.lifecycle.value,
        condition=asset.condition.value,
        family_ids=sorted(asset.family_ids, key=str),
        settings=asset.settings,
        ports=[
            AssetPortDTO(
                name=p.name,
                direction=p.direction.value,
                signal_type=p.signal_type,
            )
            for p in sorted(asset.ports, key=lambda port: port.name)
        ],
    )
