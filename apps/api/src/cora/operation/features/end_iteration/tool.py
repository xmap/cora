"""MCP tool for the `end_iteration` slice."""

from collections.abc import Callable
from typing import Annotated, Any
from uuid import UUID

from mcp.server.fastmcp import Context, FastMCP
from pydantic import Field

from cora.infrastructure.mcp_principal import get_mcp_principal_id
from cora.infrastructure.observability import current_correlation_id
from cora.infrastructure.routing import get_mcp_surface_id
from cora.operation.features.end_iteration.command import EndProcedureIteration
from cora.operation.features.end_iteration.handler import Handler
from cora.shared.text_bounds import REASON_MAX_LENGTH


def register(mcp: FastMCP, *, get_handler: Callable[[], Handler]) -> None:
    """Register the `end_iteration` tool on the given MCP server."""

    @mcp.tool(
        name="end_iteration",
        description=(
            "Close the currently-open convergence-loop iteration on a Running "
            "Procedure. `iteration_index` must match the open iteration. "
            "`converged` records the verdict (true / false / omit for none); "
            "`reason` is an optional free-form note (1-500 chars)."
        ),
    )
    async def end_iteration_tool(  # pyright: ignore[reportUnusedFunction]
        ctx: Context[Any, Any, Any],
        procedure_id: Annotated[
            UUID,
            Field(description="Target procedure's id."),
        ],
        iteration_index: Annotated[
            int,
            Field(
                ge=1,
                description="1-based index of the iteration to close; must match the open one.",
            ),
        ],
        converged: Annotated[
            bool | None,
            Field(description="Convergence verdict: true, false, or null (no verdict)."),
        ] = None,
        reason: Annotated[
            str | None,
            Field(
                min_length=1,
                max_length=REASON_MAX_LENGTH,
                description="Optional free-form note about how the iteration ended.",
            ),
        ] = None,
    ) -> None:
        handler = get_handler()
        await handler(
            EndProcedureIteration(
                procedure_id=procedure_id,
                iteration_index=iteration_index,
                converged=converged,
                reason=reason,
            ),
            principal_id=get_mcp_principal_id(ctx),
            correlation_id=current_correlation_id(),
            surface_id=get_mcp_surface_id(),
        )
