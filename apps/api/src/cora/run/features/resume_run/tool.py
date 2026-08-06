"""MCP tool for the `resume_run` slice."""

from collections.abc import Callable
from typing import Annotated, Any
from uuid import UUID

from mcp.server.fastmcp import Context, FastMCP
from pydantic import Field

from cora.infrastructure.mcp_principal import get_mcp_principal_id
from cora.infrastructure.observability import current_correlation_id
from cora.infrastructure.routing import get_mcp_surface_id
from cora.run.aggregates.run import HOLD_CAUSE_OPERATOR
from cora.run.features.resume_run.command import ResumeRun
from cora.run.features.resume_run.handler import Handler


def register(mcp: FastMCP, *, get_handler: Callable[[], Handler]) -> None:
    """Register the `resume_run` tool on the given MCP server."""

    @mcp.tool(
        name="resume_run",
        description=(
            "Resume a held Run (Held → Running). The inverse of hold_run. "
            "Resuming a `Running` Run raises; resuming a terminal Run raises."
        ),
    )
    async def resume_run_tool(  # pyright: ignore[reportUnusedFunction]
        ctx: Context[Any, Any, Any],
        run_id: Annotated[
            UUID,
            Field(description="Target run's id."),
        ],
        cause: Annotated[
            str,
            Field(
                description=(
                    "Which concern's hold claim this resume discharges. Must match the "
                    "cause the hold was placed under. Defaults to `operator`. A Run held "
                    "by the kill-switch carries `authority-revocation`."
                ),
            ),
        ] = HOLD_CAUSE_OPERATOR,
    ) -> None:
        handler = get_handler()
        await handler(
            ResumeRun(run_id=run_id, cause=cause),
            principal_id=get_mcp_principal_id(ctx),
            correlation_id=current_correlation_id(),
            surface_id=get_mcp_surface_id(),
        )
