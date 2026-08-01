"""MCP tool for the `deprecate_capability` slice."""

from collections.abc import Callable
from typing import Annotated, Any
from uuid import UUID

from mcp.server.fastmcp import Context, FastMCP
from pydantic import Field

from cora.infrastructure.mcp_principal import get_mcp_principal_id
from cora.infrastructure.observability import current_correlation_id
from cora.infrastructure.routing import get_mcp_surface_id
from cora.recipe.features.deprecate_capability.command import DeprecateCapability
from cora.recipe.features.deprecate_capability.handler import Handler
from cora.shared.deprecation import DeprecationReason


def register(mcp: FastMCP, *, get_handler: Callable[[], Handler]) -> None:
    """Register the `deprecate_capability` tool on the given MCP server."""

    @mcp.tool(
        name="deprecate_capability",
        description=(
            "Mark an existing Capability as Deprecated. Multi-source: "
            "Defined or Versioned → Deprecated. Existing Methods / "
            "Procedures referencing the deprecated Capability are NOT "
            "auto-invalidated (advisory at BC layer). Optional "
            "replaced_by_capability_id points at a successor (LOINC "
            "MAP_TO precedent)."
        ),
    )
    async def deprecate_capability_tool(  # pyright: ignore[reportUnusedFunction]
        ctx: Context[Any, Any, Any],
        capability_id: Annotated[
            UUID,
            Field(description="Target Capability's id."),
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
        replaced_by_capability_id: Annotated[
            UUID | None,
            Field(
                default=None,
                description=(
                    "Optional pointer to a successor Capability. None "
                    "means deprecated-without-replacement."
                ),
            ),
        ] = None,
    ) -> None:
        handler = get_handler()
        await handler(
            DeprecateCapability(
                capability_id=capability_id,
                reason=reason,
                replaced_by_capability_id=replaced_by_capability_id,
            ),
            principal_id=get_mcp_principal_id(ctx),
            correlation_id=current_correlation_id(),
            surface_id=get_mcp_surface_id(),
        )
