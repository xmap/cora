"""MCP tool for `update_capability_suggested_roles`."""

from collections.abc import Callable
from typing import Annotated, Any
from uuid import UUID

from mcp.server.fastmcp import Context, FastMCP
from pydantic import Field

from cora.infrastructure.mcp_principal import get_mcp_principal_id
from cora.infrastructure.observability import current_correlation_id
from cora.infrastructure.routing import get_mcp_surface_id
from cora.recipe.features.update_capability_suggested_roles.command import (
    UpdateCapabilitySuggestedRoles,
)
from cora.recipe.features.update_capability_suggested_roles.handler import Handler


def register(mcp: FastMCP, *, get_handler: Callable[[], Handler]) -> None:
    """Register the `update_capability_suggested_roles` tool on the given MCP server."""

    @mcp.tool(
        name="update_capability_suggested_roles",
        description=(
            "Author the editorial suggested_role_ids set on a Capability "
            "(Layer 3 sub-slice 3E; documentation-only per memo Lock "
            "10). Wholesale-replace shape. Every role_id is verified "
            "to resolve via the Role projection at the handler edge. "
            "Restricted to Defined + Versioned Capability status."
        ),
    )
    async def update_capability_suggested_roles_tool(  # pyright: ignore[reportUnusedFunction]
        ctx: Context[Any, Any, Any],
        capability_id: Annotated[
            UUID,
            Field(description="Target Capability's id."),
        ],
        suggested_role_ids: Annotated[
            list[UUID],
            Field(
                description=(
                    "FULL replacement set of Role contract ids. "
                    "Deduplicated server-side. Empty clears the set."
                ),
            ),
        ],
    ) -> None:
        handler = get_handler()
        await handler(
            UpdateCapabilitySuggestedRoles(
                capability_id=capability_id,
                suggested_role_ids=frozenset(suggested_role_ids),
            ),
            principal_id=get_mcp_principal_id(ctx),
            correlation_id=current_correlation_id(),
            surface_id=get_mcp_surface_id(),
        )
