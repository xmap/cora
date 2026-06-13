"""MCP tool for the `mark_supply_recovering` slice."""

from collections.abc import Callable
from typing import Annotated, Any
from uuid import UUID

from mcp.server.fastmcp import Context, FastMCP
from pydantic import BaseModel, Field

from cora.infrastructure.mcp_principal import get_mcp_principal_id
from cora.infrastructure.observability import current_correlation_id
from cora.infrastructure.routing import get_mcp_surface_id
from cora.shared.text_bounds import REASON_MAX_LENGTH
from cora.supply.features.mark_supply_recovering.command import MarkSupplyRecovering
from cora.supply.features.mark_supply_recovering.handler import Handler


class MarkSupplyRecoveringOutput(BaseModel):
    """Structured output of the `mark_supply_recovering` MCP tool."""

    supply_id: UUID


def register(mcp: FastMCP, *, get_handler: Callable[[], Handler]) -> None:
    """Register the `mark_supply_recovering` tool on the given MCP server."""

    @mcp.tool(
        name="mark_supply_recovering",
        description=(
            "Mark a Supply as Recovering (observation suggests it may be "
            "coming back). Single-source: only an Unavailable supply can "
            "be marked Recovering. Recovery -> Available requires an "
            "explicit `restore_supply` (operator acknowledgement)."
        ),
    )
    async def mark_supply_recovering_tool(  # pyright: ignore[reportUnusedFunction]
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
                    "Operator-supplied reason for the mark-recovering transition "
                    "(audit-log breadcrumb)."
                ),
            ),
        ],
    ) -> MarkSupplyRecoveringOutput:
        handler = get_handler()
        await handler(
            MarkSupplyRecovering(supply_id=supply_id, reason=reason),
            principal_id=get_mcp_principal_id(ctx),
            correlation_id=current_correlation_id(),
            surface_id=get_mcp_surface_id(),
        )
        return MarkSupplyRecoveringOutput(supply_id=supply_id)
