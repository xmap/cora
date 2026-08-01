"""MCP tool for the `update_allocation_ceiling` slice."""

from collections.abc import Callable
from typing import Annotated, Any
from uuid import UUID

from mcp.server.fastmcp import Context, FastMCP
from pydantic import BaseModel, Field

from cora.budget.features.update_allocation_ceiling.command import UpdateAllocationCeiling
from cora.budget.features.update_allocation_ceiling.handler import Handler
from cora.infrastructure.mcp_principal import get_mcp_principal_id
from cora.infrastructure.observability import current_correlation_id
from cora.infrastructure.routing import get_mcp_surface_id


class UpdateAllocationCeilingOutput(BaseModel):
    """Structured output of the `update_allocation_ceiling` MCP tool."""

    allocation_id: UUID


def register(mcp: FastMCP, *, get_handler: Callable[[], Handler]) -> None:
    """Register the `update_allocation_ceiling` tool on the given MCP server."""

    @mcp.tool(
        name="update_allocation_ceiling",
        description=(
            "Update an Allocation's USD ceiling (PUT semantics: the supplied "
            "ceiling IS the post-update ceiling, not a delta). The "
            "cost-overrun tighten lever. Allowed from Granted or Active "
            "only; a sealed or voided envelope's books cannot be rewritten."
        ),
    )
    async def update_allocation_ceiling_tool(  # pyright: ignore[reportUnusedFunction]
        ctx: Context[Any, Any, Any],
        allocation_id: Annotated[
            UUID, Field(description="Identifier of the Allocation to update.")
        ],
        ceiling_usd: Annotated[
            float,
            Field(
                gt=0.0,
                description="The post-update USD ceiling. Finite and greater than 0.",
            ),
        ],
    ) -> UpdateAllocationCeilingOutput:
        handler = get_handler()
        await handler(
            UpdateAllocationCeiling(allocation_id=allocation_id, ceiling_usd=ceiling_usd),
            principal_id=get_mcp_principal_id(ctx),
            correlation_id=current_correlation_id(),
            surface_id=get_mcp_surface_id(),
        )
        return UpdateAllocationCeilingOutput(allocation_id=allocation_id)
