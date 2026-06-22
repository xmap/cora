"""MCP tool for the `record_visit_arrival` slice."""

from collections.abc import Callable
from typing import Annotated, Any
from uuid import UUID

from mcp.server.fastmcp import Context, FastMCP
from pydantic import BaseModel, Field

from cora.infrastructure.mcp_principal import get_mcp_principal_id
from cora.infrastructure.observability import current_correlation_id
from cora.infrastructure.routing import get_mcp_surface_id
from cora.trust.features.record_visit_arrival.command import RecordVisitArrival
from cora.trust.features.record_visit_arrival.handler import Handler


class RecordVisitArrivalOutput(BaseModel):
    """Structured output of the `record_visit_arrival` MCP tool."""

    visit_id: UUID


def register(mcp: FastMCP, *, get_handler: Callable[[], Handler]) -> None:
    """Register the `record_visit_arrival` tool on the given MCP server."""

    @mcp.tool(
        name="record_visit_arrival",
        description=(
            "Arrive at a Planned Visit (Planned -> Arrived). Explicit "
            "operator gesture; distinct from check_in."
        ),
    )
    async def record_visit_arrival_tool(  # pyright: ignore[reportUnusedFunction]
        ctx: Context[Any, Any, Any],
        visit_id: Annotated[UUID, Field(description="Target Visit's id.")],
    ) -> RecordVisitArrivalOutput:
        handler = get_handler()
        await handler(
            RecordVisitArrival(visit_id=visit_id),
            principal_id=get_mcp_principal_id(ctx),
            correlation_id=current_correlation_id(),
            surface_id=get_mcp_surface_id(),
        )
        return RecordVisitArrivalOutput(visit_id=visit_id)
