"""MCP tool for the `close_visit_presence` slice."""

from collections.abc import Callable
from typing import Annotated, Any
from uuid import UUID

from mcp.server.fastmcp import Context, FastMCP
from pydantic import BaseModel, Field

from cora.infrastructure.mcp_principal import get_mcp_principal_id
from cora.infrastructure.observability import current_correlation_id
from cora.infrastructure.routing import get_mcp_surface_id
from cora.trust.features.close_visit_presence.command import CloseVisitPresence
from cora.trust.features.close_visit_presence.handler import Handler


class CloseVisitPresenceOutput(BaseModel):
    """Structured output of the `close_visit_presence` MCP tool."""

    visit_id: UUID
    actor_id: UUID


def register(mcp: FastMCP, *, get_handler: Callable[[], Handler]) -> None:
    """Register the `close_visit_presence` tool on the given MCP server."""

    @mcp.tool(
        name="close_visit_presence",
        description=(
            "Close ANOTHER actor's open presence entry on a Visit, for somebody "
            "who left without checking out. To close your own, use "
            "check_out_visit. The named actor must have an open entry. A Visit "
            "that reaches a terminal state closes every open entry on its own, "
            "so this is for the mid-Visit case."
        ),
    )
    async def close_visit_presence_tool(  # pyright: ignore[reportUnusedFunction]
        ctx: Context[Any, Any, Any],
        visit_id: Annotated[UUID, Field(description="Target Visit's id.")],
        actor_id: Annotated[UUID, Field(description="Actor whose open presence entry is closed.")],
    ) -> CloseVisitPresenceOutput:
        handler = get_handler()
        await handler(
            CloseVisitPresence(visit_id=visit_id, actor_id=actor_id),
            principal_id=get_mcp_principal_id(ctx),
            correlation_id=current_correlation_id(),
            surface_id=get_mcp_surface_id(),
        )
        return CloseVisitPresenceOutput(visit_id=visit_id, actor_id=actor_id)
