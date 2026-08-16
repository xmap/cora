"""MCP tool for the `get_run` query slice.

`capture_code` / `observed_capture_path` (slice 13) are resolved
inside `get_run`'s own `Handler` (`handler.py`'s `RunView`), mirroring
`get_actor`'s `ActorView` exactly: this tool only destructures the
already-composed view into its structured output, the same shape
every other field already follows.
"""

from collections.abc import Callable
from typing import Annotated, Any
from uuid import UUID

from mcp.server.fastmcp import Context, FastMCP
from pydantic import BaseModel, Field

from cora.infrastructure.mcp_principal import get_mcp_principal_id
from cora.infrastructure.observability import current_correlation_id
from cora.infrastructure.routing import get_mcp_surface_id
from cora.run.aggregates.run import RUN_NAME_MAX_LENGTH
from cora.run.features.get_run.handler import Handler
from cora.run.features.get_run.query import GetRun


class RunOutput(BaseModel):
    """Structured output of the `get_run` MCP tool."""

    id: UUID
    name: str = Field(..., max_length=RUN_NAME_MAX_LENGTH)
    plan_id: UUID
    subject_id: UUID | None
    raid: str | None
    status: str
    override_parameters: dict[str, Any] = Field(default_factory=dict)
    effective_parameters: dict[str, Any] = Field(default_factory=dict)
    trigger_source: str | None = None
    campaign_id: UUID | None = None
    capture_code: str | None = None
    observed_capture_path: str | None = None


def register(mcp: FastMCP, *, get_handler: Callable[[], Handler]) -> None:
    """Register the `get_run` tool on the given MCP server."""

    @mcp.tool(
        name="get_run",
        description="Read the current state of an existing run by id.",
    )
    async def get_run_tool(  # pyright: ignore[reportUnusedFunction]
        ctx: Context[Any, Any, Any],
        run_id: Annotated[
            UUID,
            Field(description="Target run's id."),
        ],
    ) -> RunOutput:
        handler = get_handler()
        view = await handler(
            GetRun(run_id=run_id),
            principal_id=get_mcp_principal_id(ctx),
            correlation_id=current_correlation_id(),
            surface_id=get_mcp_surface_id(),
        )
        if view is None:
            msg = f"Run {run_id} not found"
            raise ValueError(msg)
        run = view.run
        return RunOutput(
            id=run.id,
            name=run.name.value,
            plan_id=run.plan_id,
            subject_id=run.subject_id,
            raid=run.raid,
            status=run.status.value,
            override_parameters=run.override_parameters,
            effective_parameters=run.effective_parameters,
            trigger_source=run.trigger_source,
            campaign_id=run.campaign_id,
            capture_code=view.capture_code,
            observed_capture_path=view.observed_capture_path,
        )
