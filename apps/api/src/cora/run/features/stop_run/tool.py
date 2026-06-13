"""MCP tool for the `stop_run` slice."""

from collections.abc import Callable
from typing import Annotated, Any
from uuid import UUID

from mcp.server.fastmcp import Context, FastMCP
from pydantic import Field

from cora.infrastructure.mcp_principal import get_mcp_principal_id
from cora.infrastructure.observability import current_correlation_id
from cora.infrastructure.routing import get_mcp_surface_id
from cora.run.features.stop_run.command import StopRun
from cora.run.features.stop_run.handler import Handler
from cora.shared.text_bounds import REASON_MAX_LENGTH


def register(mcp: FastMCP, *, get_handler: Callable[[], Handler]) -> None:
    """Register the `stop_run` tool on the given MCP server."""

    @mcp.tool(
        name="stop_run",
        description=(
            "Controlled early exit of a Run (Running | Held → Stopped). "
            "Distinct from abort: stop = data valid up to the stop point; "
            "abort = data flagged as potentially invalid. Stopping a "
            "terminal Run raises. Reason is free-form (1-500 chars), "
            "captured verbatim for audit."
        ),
    )
    async def stop_run_tool(  # pyright: ignore[reportUnusedFunction]
        ctx: Context[Any, Any, Any],
        run_id: Annotated[
            UUID,
            Field(description="Target run's id."),
        ],
        reason: Annotated[
            str,
            Field(
                min_length=1,
                max_length=REASON_MAX_LENGTH,
                description=("Free-form reason for the stop (1-500 chars after trimming)."),
            ),
        ],
    ) -> None:
        handler = get_handler()
        await handler(
            StopRun(run_id=run_id, reason=reason),
            principal_id=get_mcp_principal_id(ctx),
            correlation_id=current_correlation_id(),
            surface_id=get_mcp_surface_id(),
        )
