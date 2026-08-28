"""MCP tool for the `get_run_history` query slice."""

from collections.abc import Callable
from datetime import datetime
from typing import Annotated, Any
from uuid import UUID

from mcp.server.fastmcp import Context, FastMCP
from pydantic import BaseModel, Field

from cora.infrastructure.mcp_principal import get_mcp_principal_id
from cora.infrastructure.observability import current_correlation_id
from cora.infrastructure.routing import get_mcp_surface_id
from cora.run.features.get_run_history.handler import Handler
from cora.run.features.get_run_history.query import GetRunHistory


class RunHistoryEventOutput(BaseModel):
    """One event off the run's own stream, primitives only."""

    event_id: UUID
    event_type: str
    version: int
    occurred_at: datetime
    recorded_at: datetime
    payload: dict[str, Any]


class RunHistoryObservationOutput(BaseModel):
    """One observation-trail row, primitives only."""

    event_id: UUID
    channel_name: str
    value: float | None
    categorical_value: str | None
    units: str | None
    sampling_procedure: str
    sampled_at: datetime
    occurred_at: datetime
    recorded_at: datetime
    is_simulated: bool


class RunHistoryOutput(BaseModel):
    """Structured output of the `get_run_history` MCP tool."""

    run_id: UUID
    name: str
    status: str
    events: list[RunHistoryEventOutput]
    observations: list[RunHistoryObservationOutput]
    observations_truncated: bool


def register(mcp: FastMCP, *, get_handler: Callable[[], Handler]) -> None:
    """Register the `get_run_history` tool on the given MCP server."""

    @mcp.tool(
        name="get_run_history",
        description=(
            "Read one run's full exact-timestamped history: its own events "
            "plus its observation trail."
        ),
    )
    async def get_run_history_tool(  # pyright: ignore[reportUnusedFunction]
        ctx: Context[Any, Any, Any],
        run_id: Annotated[
            UUID,
            Field(description="Target run's id."),
        ],
    ) -> RunHistoryOutput:
        handler = get_handler()
        view = await handler(
            GetRunHistory(run_id=run_id),
            principal_id=get_mcp_principal_id(ctx),
            correlation_id=current_correlation_id(),
            surface_id=get_mcp_surface_id(),
        )
        if view is None:
            msg = f"Run {run_id} history not found"
            raise ValueError(msg)
        return RunHistoryOutput(
            run_id=view.run_id,
            name=view.name,
            status=view.status,
            events=[
                RunHistoryEventOutput(
                    event_id=e.event_id,
                    event_type=e.event_type,
                    version=e.version,
                    occurred_at=e.occurred_at,
                    recorded_at=e.recorded_at,
                    payload=e.payload,
                )
                for e in view.events
            ],
            observations=[
                RunHistoryObservationOutput(
                    event_id=o.event_id,
                    channel_name=o.channel_name,
                    value=o.value,
                    categorical_value=o.categorical_value,
                    units=o.units,
                    sampling_procedure=o.sampling_procedure,
                    sampled_at=o.sampled_at,
                    occurred_at=o.occurred_at,
                    recorded_at=o.recorded_at,
                    is_simulated=o.is_simulated,
                )
                for o in view.observations
            ],
            observations_truncated=view.observations_truncated,
        )
