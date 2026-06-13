"""MCP tool for the `reject_clearance` slice."""

from collections.abc import Callable
from typing import Annotated, Any
from uuid import UUID

from mcp.server.fastmcp import Context, FastMCP
from pydantic import BaseModel, Field

from cora.infrastructure.mcp_principal import get_mcp_principal_id
from cora.infrastructure.observability import current_correlation_id
from cora.infrastructure.routing import get_mcp_surface_id
from cora.safety.features.reject_clearance.command import RejectClearance
from cora.safety.features.reject_clearance.handler import Handler
from cora.shared.text_bounds import REASON_MAX_LENGTH


class RejectClearanceOutput(BaseModel):
    """Structured output of the `reject_clearance` MCP tool."""

    clearance_id: UUID


def register(mcp: FastMCP, *, get_handler: Callable[[], Handler]) -> None:
    """Register the `reject_clearance` tool on the given MCP server."""

    @mcp.tool(
        name="reject_clearance",
        description=(
            "Reject an UnderReview clearance (UnderReview -> Rejected). "
            "Terminal-bad: rejected clearances cannot be revived; a new "
            "clearance must be registered if the operator wants to retry. "
            "Single-source: requires 'UnderReview' status."
        ),
    )
    async def reject_clearance_tool(  # pyright: ignore[reportUnusedFunction]
        ctx: Context[Any, Any, Any],
        clearance_id: Annotated[UUID, Field(description="Target clearance's id.")],
        reason: Annotated[
            str,
            Field(
                min_length=1,
                max_length=REASON_MAX_LENGTH,
                description="Free-form reason for the rejection (audit breadcrumb).",
            ),
        ],
    ) -> RejectClearanceOutput:
        handler = get_handler()
        await handler(
            RejectClearance(
                clearance_id=clearance_id,
                reason=reason,
            ),
            principal_id=get_mcp_principal_id(ctx),
            correlation_id=current_correlation_id(),
            surface_id=get_mcp_surface_id(),
        )
        return RejectClearanceOutput(clearance_id=clearance_id)
