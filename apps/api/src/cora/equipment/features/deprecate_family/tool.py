"""MCP tool for the `deprecate_family` slice."""

from collections.abc import Callable
from typing import Annotated, Any
from uuid import UUID

from mcp.server.fastmcp import Context, FastMCP
from pydantic import Field

from cora.equipment.features.deprecate_family.command import DeprecateFamily
from cora.equipment.features.deprecate_family.handler import Handler
from cora.infrastructure.mcp_principal import get_mcp_principal_id
from cora.infrastructure.observability import current_correlation_id
from cora.infrastructure.routing import get_mcp_surface_id
from cora.shared.deprecation import DeprecationReason


def register(mcp: FastMCP, *, get_handler: Callable[[], Handler]) -> None:
    """Register the `deprecate_family` tool on the given MCP server."""

    @mcp.tool(
        name="deprecate_family",
        description=(
            "Mark an existing family as deprecated. Accepts both "
            "Defined and Versioned source states. Re-deprecating an "
            "already-Deprecated family raises."
        ),
    )
    async def deprecate_family_tool(  # pyright: ignore[reportUnusedFunction]
        ctx: Context[Any, Any, Any],
        family_id: Annotated[
            UUID,
            Field(description="Target family's id."),
        ],
        reason: Annotated[
            DeprecationReason,
            Field(
                description=(
                    "Why the template is no longer recommended. `Superseded`: a "
                    "newer version replaces it, prior use stands. `Defective`: it "
                    "was wrong, prior use is suspect. `Obsolete`: what it targeted "
                    "no longer exists."
                ),
            ),
        ],
    ) -> None:
        handler = get_handler()
        await handler(
            DeprecateFamily(family_id=family_id, reason=reason),
            principal_id=get_mcp_principal_id(ctx),
            correlation_id=current_correlation_id(),
            surface_id=get_mcp_surface_id(),
        )
