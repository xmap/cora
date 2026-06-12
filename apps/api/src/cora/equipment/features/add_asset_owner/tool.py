"""MCP tool for the `add_asset_owner` slice."""

from collections.abc import Callable
from typing import Annotated, Any
from uuid import UUID

from mcp.server.fastmcp import Context, FastMCP
from pydantic import Field

from cora.equipment._bodies import AssetOwnerBody
from cora.equipment.features.add_asset_owner.command import AddAssetOwner
from cora.equipment.features.add_asset_owner.handler import Handler
from cora.infrastructure.mcp_principal import get_mcp_principal_id
from cora.infrastructure.observability import current_correlation_id
from cora.infrastructure.routing import get_mcp_surface_id


def register(mcp: FastMCP, *, get_handler: Callable[[], Handler]) -> None:
    """Register the `add_asset_owner` tool on the given MCP server."""

    @mcp.tool(
        name="add_asset_owner",
        description=(
            "Add an institutional owner (PIDINST v1.0 Property 5) to "
            "an existing Asset's owners set. Strict-not-idempotent: "
            "rejects a duplicate name already on the asset. Rejects "
            "when the asset is Decommissioned."
        ),
    )
    async def add_asset_owner_tool(  # pyright: ignore[reportUnusedFunction]
        ctx: Context[Any, Any, Any],
        asset_id: Annotated[
            UUID,
            Field(description="Target asset's id."),
        ],
        owner: Annotated[
            AssetOwnerBody,
            Field(description="The institutional owner block to add."),
        ],
    ) -> None:
        handler = get_handler()
        await handler(
            AddAssetOwner(asset_id=asset_id, owner=owner.to_domain()),
            principal_id=get_mcp_principal_id(ctx),
            correlation_id=current_correlation_id(),
            surface_id=get_mcp_surface_id(),
        )
