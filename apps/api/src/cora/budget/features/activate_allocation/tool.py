"""MCP tool for the `activate_allocation` slice."""

from collections.abc import Callable
from typing import Annotated, Any
from uuid import UUID

from mcp.server.fastmcp import Context, FastMCP
from pydantic import BaseModel, Field

from cora.budget.features.activate_allocation.command import ActivateAllocation
from cora.budget.features.activate_allocation.handler import Handler
from cora.infrastructure.mcp_principal import get_mcp_principal_id
from cora.infrastructure.observability import current_correlation_id
from cora.infrastructure.routing import get_mcp_surface_id


class ActivateAllocationOutput(BaseModel):
    """Structured output of the `activate_allocation` MCP tool."""

    allocation_id: UUID


def register(mcp: FastMCP, *, get_handler: Callable[[], Handler]) -> None:
    """Register the `activate_allocation` tool on the given MCP server."""

    @mcp.tool(
        name="activate_allocation",
        description=(
            "Activate a Granted Allocation (Granted -> Active). Opens the "
            "spend window: from this moment the envelope check arms and "
            "total spend folds from the activation timestamp. Source set is "
            "{Granted} only; activating from any other status raises an "
            "error."
        ),
    )
    async def activate_allocation_tool(  # pyright: ignore[reportUnusedFunction]
        ctx: Context[Any, Any, Any],
        allocation_id: Annotated[
            UUID, Field(description="Identifier of the Allocation to activate.")
        ],
    ) -> ActivateAllocationOutput:
        handler = get_handler()
        await handler(
            ActivateAllocation(allocation_id=allocation_id),
            principal_id=get_mcp_principal_id(ctx),
            correlation_id=current_correlation_id(),
            surface_id=get_mcp_surface_id(),
        )
        return ActivateAllocationOutput(allocation_id=allocation_id)
