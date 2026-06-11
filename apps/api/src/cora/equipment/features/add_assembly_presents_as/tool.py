"""MCP tool for the `add_assembly_presents_as` slice."""

from collections.abc import Callable
from typing import Annotated, Any
from uuid import UUID

from mcp.server.fastmcp import Context, FastMCP
from pydantic import Field

from cora.equipment.features.add_assembly_presents_as.command import AddAssemblyPresentsAs
from cora.equipment.features.add_assembly_presents_as.handler import Handler
from cora.infrastructure.mcp_principal import get_mcp_principal_id
from cora.infrastructure.observability import current_correlation_id
from cora.infrastructure.routing import get_mcp_surface_id


def register(mcp: FastMCP, *, get_handler: Callable[[], Handler]) -> None:
    """Register the `add_assembly_presents_as` tool on the given MCP server."""

    @mcp.tool(
        name="add_assembly_presents_as",
        description=(
            "Add a global Role contract to an Assembly's presents_as "
            "set. Existence of the Role is verified at the handler "
            "edge. Strict-not-idempotent: re-adding a Role already "
            "advertised raises. The affordance-superset gate is NOT "
            "enforced at template time."
        ),
    )
    async def add_assembly_presents_as_tool(  # pyright: ignore[reportUnusedFunction]
        ctx: Context[Any, Any, Any],
        assembly_id: Annotated[
            UUID,
            Field(description="Target Assembly's id."),
        ],
        role_id: Annotated[
            UUID,
            Field(description="Global Role contract id to advertise."),
        ],
    ) -> None:
        handler = get_handler()
        await handler(
            AddAssemblyPresentsAs(assembly_id=assembly_id, role_id=role_id),
            principal_id=get_mcp_principal_id(ctx),
            correlation_id=current_correlation_id(),
            surface_id=get_mcp_surface_id(),
        )
