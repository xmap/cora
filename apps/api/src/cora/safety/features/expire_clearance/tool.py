"""MCP tool for the `expire_clearance` slice."""

from collections.abc import Callable
from typing import Annotated, Any
from uuid import UUID

from mcp.server.fastmcp import Context, FastMCP
from pydantic import BaseModel, Field

from cora.infrastructure.mcp_principal import get_mcp_principal_id
from cora.infrastructure.observability import current_correlation_id
from cora.infrastructure.routing import get_mcp_surface_id
from cora.safety.features.expire_clearance.command import ExpireClearance
from cora.safety.features.expire_clearance.handler import Handler
from cora.shared.text_bounds import REASON_MAX_LENGTH


class ExpireClearanceOutput(BaseModel):
    """Structured output of the `expire_clearance` MCP tool."""

    clearance_id: UUID


def register(mcp: FastMCP, *, get_handler: Callable[[], Handler]) -> None:
    """Register the `expire_clearance` tool on the given MCP server."""

    @mcp.tool(
        name="expire_clearance",
        description=(
            "Expire an Active clearance (Active -> Expired). Terminal-good: "
            "expired clearances cannot be revived; an amended child "
            "clearance (amend_clearance) is the path forward. "
            "Single-source: requires 'Active' status."
        ),
    )
    async def expire_clearance_tool(  # pyright: ignore[reportUnusedFunction]
        ctx: Context[Any, Any, Any],
        clearance_id: Annotated[UUID, Field(description="Target clearance's id.")],
        reason: Annotated[
            str,
            Field(
                min_length=1,
                max_length=REASON_MAX_LENGTH,
                description="Free-form reason for the expiration (audit breadcrumb).",
            ),
        ],
    ) -> ExpireClearanceOutput:
        handler = get_handler()
        await handler(
            ExpireClearance(
                clearance_id=clearance_id,
                reason=reason,
            ),
            principal_id=get_mcp_principal_id(ctx),
            correlation_id=current_correlation_id(),
            surface_id=get_mcp_surface_id(),
        )
        return ExpireClearanceOutput(clearance_id=clearance_id)
