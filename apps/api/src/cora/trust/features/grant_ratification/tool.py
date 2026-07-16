"""MCP tool for the `grant_ratification` slice."""

from collections.abc import Callable
from typing import Annotated, Any
from uuid import UUID

from mcp.server.fastmcp import Context, FastMCP
from pydantic import BaseModel, Field

from cora.infrastructure.mcp_principal import get_mcp_principal_id
from cora.infrastructure.observability import current_correlation_id
from cora.infrastructure.routing import get_mcp_surface_id
from cora.trust.features.grant_ratification.command import GrantRatification
from cora.trust.features.grant_ratification.handler import Handler


class GrantRatificationOutput(BaseModel):
    """Structured output of the `grant_ratification` MCP tool."""

    ratification_id: UUID


def register(mcp: FastMCP, *, get_handler: Callable[[], Handler]) -> None:
    """Register the `grant_ratification` tool on the given MCP server."""

    @mcp.tool(
        name="grant_ratification",
        description=(
            "Grant (co-sign) a Requested Ratification (Requested -> Granted). "
            "The granting principal must be independent of the requester: a "
            "principal cannot co-sign its own pending action (four-eyes)."
        ),
    )
    async def grant_ratification_tool(  # pyright: ignore[reportUnusedFunction]
        ctx: Context[Any, Any, Any],
        ratification_id: Annotated[UUID, Field(description="Target Ratification's id.")],
    ) -> GrantRatificationOutput:
        handler = get_handler()
        await handler(
            GrantRatification(ratification_id=ratification_id),
            principal_id=get_mcp_principal_id(ctx),
            correlation_id=current_correlation_id(),
            surface_id=get_mcp_surface_id(),
        )
        return GrantRatificationOutput(ratification_id=ratification_id)
