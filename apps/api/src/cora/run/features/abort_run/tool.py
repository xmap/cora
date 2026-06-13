"""MCP tool for the `abort_run` slice."""

from collections.abc import Callable
from typing import Annotated, Any
from uuid import UUID

from mcp.server.fastmcp import Context, FastMCP
from pydantic import Field

from cora.infrastructure.mcp_principal import get_mcp_principal_id
from cora.infrastructure.observability import current_correlation_id
from cora.infrastructure.routing import get_mcp_surface_id
from cora.run.features.abort_run.command import AbortRun
from cora.run.features.abort_run.handler import Handler
from cora.shared.text_bounds import REASON_MAX_LENGTH


def register(mcp: FastMCP, *, get_handler: Callable[[], Handler]) -> None:
    """Register the `abort_run` tool on the given MCP server."""

    @mcp.tool(
        name="abort_run",
        description=(
            "Mark an existing Run as aborted (emergency-exit terminal). "
            "Requires the Run to currently be in `Running`. "
            "Aborting a `Completed` or `Aborted` Run raises. "
            "Reason is free-form (1-500 chars), captured verbatim "
            "for audit."
        ),
    )
    async def abort_run_tool(  # pyright: ignore[reportUnusedFunction]
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
                description=("Free-form reason for the abort (1-500 chars after trimming)."),
            ),
        ],
        decided_by_decision_id: Annotated[
            UUID | None,
            Field(
                default=None,
                description=(
                    "Optional Decision id that justified this abort. "
                    "Maps to prov:wasInformedBy at the future PROV-O "
                    "export adapter. Not verified at the write path. "
                    "Decision→Run linkage."
                ),
            ),
        ] = None,
    ) -> None:
        handler = get_handler()
        await handler(
            AbortRun(
                run_id=run_id,
                reason=reason,
                decided_by_decision_id=decided_by_decision_id,
            ),
            principal_id=get_mcp_principal_id(ctx),
            correlation_id=current_correlation_id(),
            surface_id=get_mcp_surface_id(),
        )
