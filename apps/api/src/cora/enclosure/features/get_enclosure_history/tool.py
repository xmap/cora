"""MCP tool for the `get_enclosure_history` query slice."""

from collections.abc import Callable
from datetime import datetime
from typing import Annotated, Any
from uuid import UUID

from mcp.server.fastmcp import Context, FastMCP
from pydantic import BaseModel, Field

from cora.enclosure.features.get_enclosure_history.handler import Handler
from cora.enclosure.features.get_enclosure_history.query import GetEnclosureHistory
from cora.infrastructure.mcp_principal import get_mcp_principal_id
from cora.infrastructure.observability import current_correlation_id
from cora.infrastructure.routing import get_mcp_surface_id


class EnclosureHistoryEventOutput(BaseModel):
    """One event off the enclosure's own stream, primitives only."""

    event_id: UUID
    event_type: str
    version: int
    occurred_at: datetime
    recorded_at: datetime
    payload: dict[str, Any]


class EnclosureHistoryOutput(BaseModel):
    """Structured output of the `get_enclosure_history` MCP tool."""

    enclosure_id: UUID
    name: str
    permit_status: str
    lifecycle: str
    events: list[EnclosureHistoryEventOutput]
    events_truncated: bool


def register(mcp: FastMCP, *, get_handler: Callable[[], Handler]) -> None:
    """Register the `get_enclosure_history` tool on the given MCP server."""

    @mcp.tool(
        name="get_enclosure_history",
        description=("Read one enclosure's full exact-timestamped permit/lifecycle history."),
    )
    async def get_enclosure_history_tool(  # pyright: ignore[reportUnusedFunction]
        ctx: Context[Any, Any, Any],
        enclosure_id: Annotated[
            UUID,
            Field(description="Target enclosure's id."),
        ],
    ) -> EnclosureHistoryOutput:
        handler = get_handler()
        view = await handler(
            GetEnclosureHistory(enclosure_id=enclosure_id),
            principal_id=get_mcp_principal_id(ctx),
            correlation_id=current_correlation_id(),
            surface_id=get_mcp_surface_id(),
        )
        if view is None:
            msg = f"Enclosure {enclosure_id} history not found"
            raise ValueError(msg)
        return EnclosureHistoryOutput(
            enclosure_id=view.enclosure_id,
            name=view.name,
            permit_status=view.permit_status,
            lifecycle=view.lifecycle,
            events=[
                EnclosureHistoryEventOutput(
                    event_id=e.event_id,
                    event_type=e.event_type,
                    version=e.version,
                    occurred_at=e.occurred_at,
                    recorded_at=e.recorded_at,
                    payload=e.payload,
                )
                for e in view.events
            ],
            events_truncated=view.events_truncated,
        )
