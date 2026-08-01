"""MCP tool for the `deprecate_method` slice."""

from collections.abc import Callable
from typing import Annotated, Any
from uuid import UUID

from mcp.server.fastmcp import Context, FastMCP
from pydantic import Field

from cora.infrastructure.mcp_principal import get_mcp_principal_id
from cora.infrastructure.observability import current_correlation_id
from cora.infrastructure.routing import get_mcp_surface_id
from cora.recipe.features.deprecate_method.command import DeprecateMethod
from cora.recipe.features.deprecate_method.handler import Handler
from cora.shared.deprecation import DeprecationReason


def register(mcp: FastMCP, *, get_handler: Callable[[], Handler]) -> None:
    """Register the `deprecate_method` tool on the given MCP server."""

    @mcp.tool(
        name="deprecate_method",
        description=(
            "Mark an existing method as deprecated. Accepts both "
            "Defined and Versioned source states. Re-deprecating an "
            "already-Deprecated method raises."
        ),
    )
    async def deprecate_method_tool(  # pyright: ignore[reportUnusedFunction]
        ctx: Context[Any, Any, Any],
        method_id: Annotated[
            UUID,
            Field(description="Target method's id."),
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
            DeprecateMethod(method_id=method_id, reason=reason),
            principal_id=get_mcp_principal_id(ctx),
            correlation_id=current_correlation_id(),
            surface_id=get_mcp_surface_id(),
        )
