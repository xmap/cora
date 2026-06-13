"""MCP tool for the `degrade_supply` slice."""

from collections.abc import Callable
from typing import Annotated, Any
from uuid import UUID

from mcp.server.fastmcp import Context, FastMCP
from pydantic import BaseModel, Field

from cora.infrastructure.mcp_principal import get_mcp_principal_id
from cora.infrastructure.observability import current_correlation_id
from cora.infrastructure.routing import get_mcp_surface_id
from cora.shared.text_bounds import REASON_MAX_LENGTH
from cora.supply.features.degrade_supply.command import DegradeSupply
from cora.supply.features.degrade_supply.handler import Handler


class DegradeSupplyOutput(BaseModel):
    """Structured output of the `degrade_supply` MCP tool."""

    supply_id: UUID


def register(mcp: FastMCP, *, get_handler: Callable[[], Handler]) -> None:
    """Register the `degrade_supply` tool on the given MCP server."""

    @mcp.tool(
        name="degrade_supply",
        description=(
            "Mark a Supply as Degraded (resource up but below nominal "
            "capacity). Multi-source: accepts Unknown / Available / "
            "Recovering. An Unavailable supply cannot transition directly "
            "to Degraded (must go via mark_supply_recovering first)."
        ),
    )
    async def degrade_supply_tool(  # pyright: ignore[reportUnusedFunction]
        ctx: Context[Any, Any, Any],
        supply_id: Annotated[
            UUID,
            Field(description="Target supply's id."),
        ],
        reason: Annotated[
            str,
            Field(
                min_length=1,
                max_length=REASON_MAX_LENGTH,
                description=(
                    "Operator-supplied reason for the degrade transition (audit-log breadcrumb)."
                ),
            ),
        ],
    ) -> DegradeSupplyOutput:
        handler = get_handler()
        await handler(
            DegradeSupply(supply_id=supply_id, reason=reason),
            principal_id=get_mcp_principal_id(ctx),
            correlation_id=current_correlation_id(),
            surface_id=get_mcp_surface_id(),
        )
        return DegradeSupplyOutput(supply_id=supply_id)
