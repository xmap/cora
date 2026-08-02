"""MCP tool for the `check_out_visit` slice."""

from collections.abc import Callable
from typing import Annotated, Any
from uuid import UUID

from mcp.server.fastmcp import Context, FastMCP
from pydantic import BaseModel, Field

from cora.infrastructure.mcp_principal import get_mcp_principal_id
from cora.infrastructure.observability import current_correlation_id
from cora.infrastructure.routing import get_mcp_surface_id
from cora.trust.features.check_out_visit.command import CheckOutVisit
from cora.trust.features.check_out_visit.handler import Handler


class CheckOutVisitOutput(BaseModel):
    """Structured output of the `check_out_visit` MCP tool."""

    visit_id: UUID
    actor_id: UUID


def register(mcp: FastMCP, *, get_handler: Callable[[], Handler]) -> None:
    """Register the `check_out_visit` tool on the given MCP server."""

    @mcp.tool(
        name="check_out_visit",
        description=(
            "Check an actor out of a Visit. Closes the actor's open "
            "presence entry. Multi-shift is supported: the same actor may "
            "check in / out repeatedly in one Visit -- each cycle is a "
            "separate PresenceEntry."
        ),
    )
    async def check_out_visit_tool(  # pyright: ignore[reportUnusedFunction]
        ctx: Context[Any, Any, Any],
        visit_id: Annotated[UUID, Field(description="Target Visit's id.")],
    ) -> CheckOutVisitOutput:
        principal_id = get_mcp_principal_id(ctx)
        handler = get_handler()
        await handler(
            CheckOutVisit(visit_id=visit_id),
            principal_id=principal_id,
            correlation_id=current_correlation_id(),
            surface_id=get_mcp_surface_id(),
        )
        return CheckOutVisitOutput(visit_id=visit_id, actor_id=principal_id)
