"""HTTP route for the `list_assets` query slice.

`GET /assets?cursor=...&limit=50&tier=Unit&lifecycle=Active&parent_id=<uuid>`
returns `{"items": [...], "next_cursor": "..." | null}`.
"""

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, status
from pydantic import BaseModel, Field

from cora.equipment.aggregates.asset import ASSET_NAME_MAX_LENGTH
from cora.equipment.features.list_assets.handler import Handler
from cora.equipment.features.list_assets.query import (
    AssetLifecycleFilter,
    AssetTierFilter,
    ListAssets,
)
from cora.infrastructure.routing import (
    ErrorResponse,
    get_correlation_id,
    get_principal_id,
    get_surface_id,
)


class AssetSummaryDTO(BaseModel):
    """One asset in a paginated list."""

    asset_id: UUID
    name: str = Field(..., max_length=ASSET_NAME_MAX_LENGTH)
    tier: AssetTierFilter
    lifecycle: AssetLifecycleFilter
    parent_id: UUID | None
    created_at: datetime


class AssetListResponse(BaseModel):
    """Page of assets plus opaque next-page cursor."""

    items: list[AssetSummaryDTO]
    next_cursor: str | None = None


def _get_handler(request: Request) -> Handler:
    handler: Handler = request.app.state.equipment.list_assets
    return handler


router = APIRouter(tags=["equipment"])


@router.get(
    "/assets",
    status_code=status.HTTP_200_OK,
    response_model=AssetListResponse,
    responses={
        status.HTTP_403_FORBIDDEN: {
            "model": ErrorResponse,
            "description": "Authorize port denied the query.",
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": (
                "Query parameters failed validation OR `cursor` was "
                "malformed (corrupt base64, missing separator, bad "
                "timestamp / UUID)."
            ),
        },
    },
    summary="List assets with cursor pagination + tier/lifecycle/parent filters",
)
async def list_assets(
    handler: Annotated[Handler, Depends(_get_handler)],
    cid: Annotated[UUID, Depends(get_correlation_id)],
    principal_id: Annotated[UUID, Depends(get_principal_id)],
    surface_id: Annotated[UUID, Depends(get_surface_id)],
    cursor: Annotated[
        str | None,
        Query(description="Opaque cursor from a previous page's `next_cursor`."),
    ] = None,
    limit: Annotated[
        int,
        Query(ge=1, le=100, description="Page size; capped at 100."),
    ] = 50,
    tier: Annotated[
        AssetTierFilter | None,
        Query(description="Optional operational tier filter."),
    ] = None,
    lifecycle: Annotated[
        AssetLifecycleFilter | None,
        Query(description="Optional lifecycle filter."),
    ] = None,
    parent_id: Annotated[
        UUID | None,
        Query(description="Direct-children-of filter (returns rows with parent_id = this)."),
    ] = None,
) -> AssetListResponse:
    page = await handler(
        ListAssets(
            cursor=cursor,
            limit=limit,
            tier=tier,
            lifecycle=lifecycle,
            parent_id=parent_id,
        ),
        principal_id=principal_id,
        correlation_id=cid,
        surface_id=surface_id,
    )
    return AssetListResponse(
        items=[
            AssetSummaryDTO(
                asset_id=item.asset_id,
                name=item.name,
                tier=item.tier,
                lifecycle=item.lifecycle,
                parent_id=item.parent_id,
                created_at=item.created_at,
            )
            for item in page.items
        ],
        next_cursor=page.next_cursor,
    )
