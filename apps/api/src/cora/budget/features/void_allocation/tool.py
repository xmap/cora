"""MCP tool for the `void_allocation` slice."""

from collections.abc import Callable
from typing import Annotated, Any
from uuid import UUID

from mcp.server.fastmcp import Context, FastMCP
from pydantic import BaseModel, Field

from cora.budget.features.void_allocation.command import VoidAllocation
from cora.budget.features.void_allocation.handler import Handler
from cora.infrastructure.mcp_principal import get_mcp_principal_id
from cora.infrastructure.observability import current_correlation_id
from cora.infrastructure.routing import get_mcp_surface_id
from cora.shared.text_bounds import REASON_MAX_LENGTH


class VoidAllocationOutput(BaseModel):
    """Structured output of the `void_allocation` MCP tool."""

    allocation_id: UUID


def register(mcp: FastMCP, *, get_handler: Callable[[], Handler]) -> None:
    """Register the `void_allocation` tool on the given MCP server."""

    @mcp.tool(
        name="void_allocation",
        description=(
            "Void a Granted or Active Allocation (-> Voided, terminal): the "
            "operator withdraws a mistaken grant. Required reason (a "
            "governance act the audit log must carry context for). Distinct "
            "from seal_allocation, which closes an open window's books with "
            "a spend snapshot."
        ),
    )
    async def void_allocation_tool(  # pyright: ignore[reportUnusedFunction]
        ctx: Context[Any, Any, Any],
        allocation_id: Annotated[UUID, Field(description="Identifier of the Allocation to void.")],
        reason: Annotated[
            str,
            Field(
                min_length=1,
                max_length=REASON_MAX_LENGTH,
                description="Why the grant is withdrawn. Required.",
            ),
        ],
    ) -> VoidAllocationOutput:
        handler = get_handler()
        await handler(
            VoidAllocation(allocation_id=allocation_id, reason=reason),
            principal_id=get_mcp_principal_id(ctx),
            correlation_id=current_correlation_id(),
            surface_id=get_mcp_surface_id(),
        )
        return VoidAllocationOutput(allocation_id=allocation_id)
