"""MCP tool for the `mark_supply_unavailable` slice."""

from collections.abc import Callable
from typing import Annotated, Any
from uuid import UUID

from mcp.server.fastmcp import Context, FastMCP
from pydantic import BaseModel, Field

from cora.infrastructure.mcp_principal import get_mcp_principal_id
from cora.infrastructure.observability import current_correlation_id
from cora.infrastructure.routing import get_mcp_surface_id
from cora.shared.text_bounds import REASON_MAX_LENGTH
from cora.supply.features.mark_supply_unavailable.command import MarkSupplyUnavailable
from cora.supply.features.mark_supply_unavailable.handler import Handler


class MarkSupplyUnavailableOutput(BaseModel):
    """Structured output of the `mark_supply_unavailable` MCP tool."""

    supply_id: UUID


def register(mcp: FastMCP, *, get_handler: Callable[[], Handler]) -> None:
    """Register the `mark_supply_unavailable` tool on the given MCP server."""

    @mcp.tool(
        name="mark_supply_unavailable",
        description=(
            "Mark a Supply as Unavailable (resource is down). Widest "
            "source set: accepts Unknown / Available / Degraded / "
            "Recovering. Strict-not-idempotent."
        ),
    )
    async def mark_supply_unavailable_tool(  # pyright: ignore[reportUnusedFunction]
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
                    "Operator-supplied reason for the mark-unavailable transition "
                    "(audit-log breadcrumb)."
                ),
            ),
        ],
    ) -> MarkSupplyUnavailableOutput:
        handler = get_handler()
        await handler(
            MarkSupplyUnavailable(supply_id=supply_id, reason=reason),
            principal_id=get_mcp_principal_id(ctx),
            correlation_id=current_correlation_id(),
            surface_id=get_mcp_surface_id(),
        )
        return MarkSupplyUnavailableOutput(supply_id=supply_id)
