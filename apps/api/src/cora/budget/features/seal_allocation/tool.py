"""MCP tool for the `seal_allocation` slice."""

from collections.abc import Callable
from typing import Annotated, Any
from uuid import UUID

from mcp.server.fastmcp import Context, FastMCP
from pydantic import BaseModel, Field

from cora.budget.features.seal_allocation.command import SealAllocation
from cora.budget.features.seal_allocation.handler import Handler
from cora.infrastructure.mcp_principal import get_mcp_principal_id
from cora.infrastructure.observability import current_correlation_id
from cora.infrastructure.routing import get_mcp_surface_id
from cora.shared.text_bounds import REASON_MAX_LENGTH


class SealAllocationOutput(BaseModel):
    """Structured output of the `seal_allocation` MCP tool."""

    allocation_id: UUID


def register(mcp: FastMCP, *, get_handler: Callable[[], Handler]) -> None:
    """Register the `seal_allocation` tool on the given MCP server."""

    @mcp.tool(
        name="seal_allocation",
        description=(
            "Seal an Active Allocation (Active -> Sealed, terminal): close "
            "the envelope's books with a final-spend snapshot the server "
            "computes from the inference ledger over the envelope's own "
            "window. Optional reason for an early close. Source set is "
            "{Active} only; void a dormant grant instead."
        ),
    )
    async def seal_allocation_tool(  # pyright: ignore[reportUnusedFunction]
        ctx: Context[Any, Any, Any],
        allocation_id: Annotated[UUID, Field(description="Identifier of the Allocation to seal.")],
        reason: Annotated[
            str | None,
            Field(
                default=None,
                min_length=1,
                max_length=REASON_MAX_LENGTH,
                description="Optional closing note. Null to omit.",
            ),
        ] = None,
    ) -> SealAllocationOutput:
        handler = get_handler()
        await handler(
            SealAllocation(allocation_id=allocation_id, reason=reason),
            principal_id=get_mcp_principal_id(ctx),
            correlation_id=current_correlation_id(),
            surface_id=get_mcp_surface_id(),
        )
        return SealAllocationOutput(allocation_id=allocation_id)
