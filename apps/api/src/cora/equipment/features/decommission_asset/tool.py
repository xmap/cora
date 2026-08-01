"""MCP tool for the `decommission_asset` slice.

Mirror of `activate_asset` MCP tool. Takes asset_id plus a required
free-text `reason`,
no structured content on success. Domain / application errors
propagate to FastMCP, which wraps them as `isError: true`.
"""

from collections.abc import Callable
from typing import Annotated, Any
from uuid import UUID

from mcp.server.fastmcp import Context, FastMCP
from pydantic import Field

from cora.equipment.features.decommission_asset.command import DecommissionAsset
from cora.equipment.features.decommission_asset.handler import Handler
from cora.infrastructure.mcp_principal import get_mcp_principal_id
from cora.infrastructure.observability import current_correlation_id
from cora.infrastructure.routing import get_mcp_surface_id
from cora.shared.text_bounds import REASON_MAX_LENGTH


def register(mcp: FastMCP, *, get_handler: Callable[[], Handler]) -> None:
    """Register the `decommission_asset` tool on the given MCP server."""

    @mcp.tool(
        name="decommission_asset",
        description="Decommission an existing asset, retiring it from service.",
    )
    async def decommission_asset_tool(  # pyright: ignore[reportUnusedFunction]
        ctx: Context[Any, Any, Any],
        asset_id: Annotated[
            UUID,
            Field(description="Target asset's id."),
        ],
        reason: Annotated[
            str,
            Field(
                min_length=1,
                max_length=REASON_MAX_LENGTH,
                description="Operator-supplied free-text reason for the audit log.",
            ),
        ],
    ) -> None:
        handler = get_handler()
        await handler(
            DecommissionAsset(asset_id=asset_id, reason=reason),
            principal_id=get_mcp_principal_id(ctx),
            correlation_id=current_correlation_id(),
            surface_id=get_mcp_surface_id(),
        )
