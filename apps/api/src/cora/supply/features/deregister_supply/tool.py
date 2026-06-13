"""MCP tool for the `deregister_supply` slice."""

from collections.abc import Callable
from typing import Annotated, Any
from uuid import UUID

from mcp.server.fastmcp import Context, FastMCP
from pydantic import BaseModel, Field

from cora.infrastructure.mcp_principal import get_mcp_principal_id
from cora.infrastructure.observability import current_correlation_id
from cora.infrastructure.routing import get_mcp_surface_id
from cora.shared.text_bounds import REASON_MAX_LENGTH
from cora.supply.features.deregister_supply.command import DeregisterSupply
from cora.supply.features.deregister_supply.handler import Handler


class DeregisterSupplyOutput(BaseModel):
    """Structured output of the `deregister_supply` MCP tool."""

    supply_id: UUID


def register(mcp: FastMCP, *, get_handler: Callable[[], Handler]) -> None:
    """Register the `deregister_supply` tool on the given MCP server."""

    @mcp.tool(
        name="deregister_supply",
        description=(
            "Deregister a Supply (lifecycle terminal). Accepts any "
            "non-Decommissioned status. Strict-not-idempotent. The "
            "stream and projection row are preserved for audit; a "
            "subsequent register_supply with the same (scope, kind, name) "
            "creates a fresh supply_id."
        ),
    )
    async def deregister_supply_tool(  # pyright: ignore[reportUnusedFunction]
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
                    "Operator-supplied reason for the deregister transition (audit-log breadcrumb)."
                ),
            ),
        ],
    ) -> DeregisterSupplyOutput:
        handler = get_handler()
        await handler(
            DeregisterSupply(supply_id=supply_id, reason=reason),
            principal_id=get_mcp_principal_id(ctx),
            correlation_id=current_correlation_id(),
            surface_id=get_mcp_surface_id(),
        )
        return DeregisterSupplyOutput(supply_id=supply_id)
