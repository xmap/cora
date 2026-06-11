"""MCP tool for the `list_assets` query slice."""

from collections.abc import Callable
from datetime import datetime
from typing import Annotated, Any
from uuid import UUID

from mcp.server.fastmcp import Context, FastMCP
from pydantic import BaseModel, Field

from cora.equipment.aggregates.asset import ASSET_NAME_MAX_LENGTH
from cora.equipment.features.list_assets.handler import Handler
from cora.equipment.features.list_assets.query import (
    AssetLifecycleFilter,
    AssetTierFilter,
    ListAssets,
)
from cora.infrastructure.mcp_principal import get_mcp_principal_id
from cora.infrastructure.observability import current_correlation_id
from cora.infrastructure.routing import get_mcp_surface_id


class AssetSummaryRow(BaseModel):
    asset_id: UUID
    name: str = Field(..., max_length=ASSET_NAME_MAX_LENGTH)
    tier: AssetTierFilter
    lifecycle: AssetLifecycleFilter
    parent_id: UUID | None
    created_at: datetime


class AssetListOutput(BaseModel):
    """Structured output of the `list_assets` MCP tool."""

    items: list[AssetSummaryRow]
    next_cursor: str | None = None


def register(mcp: FastMCP, *, get_handler: Callable[[], Handler]) -> None:
    """Register the `list_assets` tool on the given MCP server."""

    @mcp.tool(
        name="list_assets",
        description=(
            "Cursor-paginated list of assets. Optional filters: "
            "tier (Unit/Component/Device), "
            "lifecycle (Commissioned/Active/Maintenance/Decommissioned), "
            "parent_id (direct-children-of). Pass `cursor` from a "
            "previous page's `next_cursor` to fetch the next page."
        ),
    )
    async def list_assets_tool(  # pyright: ignore[reportUnusedFunction]
        ctx: Context[Any, Any, Any],
        cursor: Annotated[
            str | None,
            Field(description="Opaque cursor from a previous response."),
        ] = None,
        limit: Annotated[
            int,
            Field(ge=1, le=100, description="Page size cap (max 100)."),
        ] = 50,
        tier: Annotated[
            AssetTierFilter | None,
            Field(description="Optional operational tier filter."),
        ] = None,
        lifecycle: Annotated[
            AssetLifecycleFilter | None,
            Field(description="Optional lifecycle filter."),
        ] = None,
        parent_id: Annotated[
            UUID | None,
            Field(description="Direct-children-of filter."),
        ] = None,
    ) -> AssetListOutput:
        handler = get_handler()
        page = await handler(
            ListAssets(
                cursor=cursor,
                limit=limit,
                tier=tier,
                lifecycle=lifecycle,
                parent_id=parent_id,
            ),
            principal_id=get_mcp_principal_id(ctx),
            correlation_id=current_correlation_id(),
            surface_id=get_mcp_surface_id(),
        )
        return AssetListOutput(
            items=[
                AssetSummaryRow(
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
