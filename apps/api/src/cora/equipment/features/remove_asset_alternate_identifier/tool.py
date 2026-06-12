"""MCP tool for the `remove_asset_alternate_identifier` slice."""

from collections.abc import Callable
from typing import Annotated, Any
from uuid import UUID

from mcp.server.fastmcp import Context, FastMCP
from pydantic import Field

from cora.equipment._bodies import AlternateIdentifierBody
from cora.equipment.features.remove_asset_alternate_identifier.command import (
    RemoveAssetAlternateIdentifier,
)
from cora.equipment.features.remove_asset_alternate_identifier.handler import Handler
from cora.infrastructure.mcp_principal import get_mcp_principal_id
from cora.infrastructure.observability import current_correlation_id
from cora.infrastructure.routing import get_mcp_surface_id


def register(mcp: FastMCP, *, get_handler: Callable[[], Handler]) -> None:
    """Register the `remove_asset_alternate_identifier` tool on the given MCP server."""

    @mcp.tool(
        name="remove_asset_alternate_identifier",
        description=(
            "Remove an alternate identifier from an existing Asset's "
            "identifier set by exact (kind, value) pair. Strict-not-"
            "idempotent: rejects if the (kind, value) pair is not on "
            "the asset. Rejects when the asset is Decommissioned."
        ),
    )
    async def remove_asset_alternate_identifier_tool(  # pyright: ignore[reportUnusedFunction]
        ctx: Context[Any, Any, Any],
        asset_id: Annotated[
            UUID,
            Field(description="Target asset's id."),
        ],
        identifier: Annotated[
            AlternateIdentifierBody,
            Field(description="The alternate identifier to remove."),
        ],
    ) -> None:
        handler = get_handler()
        await handler(
            RemoveAssetAlternateIdentifier(
                asset_id=asset_id,
                alternate_identifier=identifier.to_domain(),
            ),
            principal_id=get_mcp_principal_id(ctx),
            correlation_id=current_correlation_id(),
            surface_id=get_mcp_surface_id(),
        )
