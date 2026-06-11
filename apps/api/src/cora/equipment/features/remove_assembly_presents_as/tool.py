"""MCP tool for the `remove_assembly_presents_as` slice."""

from collections.abc import Callable
from typing import Annotated, Any
from uuid import UUID

from mcp.server.fastmcp import Context, FastMCP
from pydantic import Field

from cora.equipment.features.remove_assembly_presents_as.command import (
    RemoveAssemblyPresentsAs,
)
from cora.equipment.features.remove_assembly_presents_as.handler import Handler
from cora.infrastructure.mcp_principal import get_mcp_principal_id
from cora.infrastructure.observability import current_correlation_id
from cora.infrastructure.routing import get_mcp_surface_id


def register(mcp: FastMCP, *, get_handler: Callable[[], Handler]) -> None:
    """Register the `remove_assembly_presents_as` tool on the given MCP server."""

    @mcp.tool(
        name="remove_assembly_presents_as",
        description=(
            "Remove a global Role contract from an Assembly's "
            "presents_as set. Strict-not-idempotent: removing a Role "
            "the Assembly does not advertise raises."
        ),
    )
    async def remove_assembly_presents_as_tool(  # pyright: ignore[reportUnusedFunction]
        ctx: Context[Any, Any, Any],
        assembly_id: Annotated[
            UUID,
            Field(description="Target Assembly's id."),
        ],
        role_id: Annotated[
            UUID,
            Field(description="Global Role contract id to withdraw."),
        ],
    ) -> None:
        handler = get_handler()
        await handler(
            RemoveAssemblyPresentsAs(assembly_id=assembly_id, role_id=role_id),
            principal_id=get_mcp_principal_id(ctx),
            correlation_id=current_correlation_id(),
            surface_id=get_mcp_surface_id(),
        )
