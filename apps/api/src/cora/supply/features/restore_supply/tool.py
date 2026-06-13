"""MCP tool for the `restore_supply` slice."""

from collections.abc import Callable
from typing import Annotated, Any
from uuid import UUID

from mcp.server.fastmcp import Context, FastMCP
from pydantic import BaseModel, Field

from cora.infrastructure.mcp_principal import get_mcp_principal_id
from cora.infrastructure.observability import current_correlation_id
from cora.infrastructure.routing import get_mcp_surface_id
from cora.shared.text_bounds import REASON_MAX_LENGTH
from cora.supply.features.restore_supply.command import RestoreSupply
from cora.supply.features.restore_supply.handler import Handler


class RestoreSupplyOutput(BaseModel):
    """Structured output of the `restore_supply` MCP tool."""

    supply_id: UUID


def register(mcp: FastMCP, *, get_handler: Callable[[], Handler]) -> None:
    """Register the `restore_supply` tool on the given MCP server."""

    @mcp.tool(
        name="restore_supply",
        description=(
            "Operator confirms a Recovering Supply is fully back "
            "(Recovering -> Available). Single-source: only a "
            "Recovering supply can be restored. For first-observation "
            "Unknown -> Available, use mark_supply_available."
        ),
    )
    async def restore_supply_tool(  # pyright: ignore[reportUnusedFunction]
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
                    "Operator-supplied reason for the restore acknowledgement "
                    "(audit-log breadcrumb)."
                ),
            ),
        ],
    ) -> RestoreSupplyOutput:
        handler = get_handler()
        await handler(
            RestoreSupply(supply_id=supply_id, reason=reason),
            principal_id=get_mcp_principal_id(ctx),
            correlation_id=current_correlation_id(),
            surface_id=get_mcp_surface_id(),
        )
        return RestoreSupplyOutput(supply_id=supply_id)
