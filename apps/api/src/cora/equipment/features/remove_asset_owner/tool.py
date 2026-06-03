"""MCP tool for the `remove_asset_owner` slice."""

from collections.abc import Callable
from typing import Annotated, Any
from uuid import UUID

from mcp.server.fastmcp import Context, FastMCP
from pydantic import Field

from cora.equipment.aggregates.asset import (
    ASSET_OWNER_NAME_MAX_LENGTH,
    AssetOwnerName,
)
from cora.equipment.features.remove_asset_owner.command import RemoveAssetOwner
from cora.equipment.features.remove_asset_owner.handler import Handler
from cora.infrastructure.mcp_principal import get_mcp_principal_id
from cora.infrastructure.observability import current_correlation_id
from cora.infrastructure.routing import get_mcp_surface_id


def register(mcp: FastMCP, *, get_handler: Callable[[], Handler]) -> None:
    """Register the `remove_asset_owner` tool on the given MCP server."""

    @mcp.tool(
        name="remove_asset_owner",
        description=(
            "Remove an institutional owner from an existing Asset's "
            "owners set by name. Strict-not-idempotent: rejects if "
            "no owner with the given name is on the asset. Rejects "
            "when the asset is Decommissioned. Allows removing the "
            "last owner (aggregate cardinality is 0-n)."
        ),
    )
    async def remove_asset_owner_tool(  # pyright: ignore[reportUnusedFunction]
        ctx: Context[Any, Any, Any],
        asset_id: Annotated[
            UUID,
            Field(description="Target asset's id."),
        ],
        owner_name: Annotated[
            str,
            Field(
                min_length=1,
                max_length=ASSET_OWNER_NAME_MAX_LENGTH,
                description="Name of the institutional owner to remove.",
            ),
        ],
    ) -> None:
        handler = get_handler()
        await handler(
            RemoveAssetOwner(
                asset_id=asset_id,
                owner_name=AssetOwnerName(owner_name),
            ),
            principal_id=get_mcp_principal_id(ctx),
            correlation_id=current_correlation_id(),
            surface_id=get_mcp_surface_id(),
        )
