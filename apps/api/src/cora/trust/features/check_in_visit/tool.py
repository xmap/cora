"""MCP tool for the `check_in_visit` slice."""

from collections.abc import Callable
from typing import Annotated, Any
from uuid import UUID

from mcp.server.fastmcp import Context, FastMCP
from pydantic import BaseModel, Field

from cora.infrastructure.mcp_principal import get_mcp_principal_id
from cora.infrastructure.observability import current_correlation_id
from cora.infrastructure.routing import get_mcp_surface_id
from cora.trust.aggregates.visit import PresenceMode
from cora.trust.features.check_in_visit.command import CheckInVisit
from cora.trust.features.check_in_visit.handler import Handler


class CheckInVisitOutput(BaseModel):
    """Structured output of the `check_in_visit` MCP tool."""

    visit_id: UUID
    actor_id: UUID


def register(mcp: FastMCP, *, get_handler: Callable[[], Handler]) -> None:
    """Register the `check_in_visit` tool on the given MCP server."""

    @mcp.tool(
        name="check_in_visit",
        description=(
            "Check an actor in to a Visit (physical on-site or remote). "
            "Visit must be Arrived / InProgress / OnHold (presence is "
            "orthogonal to lifecycle; operator must record_visit_arrival first). "
            "Actor cannot have an existing open presence entry."
        ),
    )
    async def check_in_visit_tool(  # pyright: ignore[reportUnusedFunction]
        ctx: Context[Any, Any, Any],
        visit_id: Annotated[UUID, Field(description="Target Visit's id.")],
        actor_id: Annotated[UUID, Field(description="Actor checking in.")],
        mode: Annotated[
            PresenceMode,
            Field(description="physical (on-site) or remote (e.g., remote API driver)."),
        ],
    ) -> CheckInVisitOutput:
        handler = get_handler()
        await handler(
            CheckInVisit(visit_id=visit_id, actor_id=actor_id, mode=mode),
            principal_id=get_mcp_principal_id(ctx),
            correlation_id=current_correlation_id(),
            surface_id=get_mcp_surface_id(),
        )
        return CheckInVisitOutput(visit_id=visit_id, actor_id=actor_id)
