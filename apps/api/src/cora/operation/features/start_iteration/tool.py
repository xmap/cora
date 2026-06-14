"""MCP tool for the `start_iteration` slice."""

from collections.abc import Callable
from typing import Annotated, Any
from uuid import UUID

from mcp.server.fastmcp import Context, FastMCP
from pydantic import Field

from cora.infrastructure.mcp_principal import get_mcp_principal_id
from cora.infrastructure.observability import current_correlation_id
from cora.infrastructure.routing import get_mcp_surface_id
from cora.operation.features.start_iteration.command import StartProcedureIteration
from cora.operation.features.start_iteration.handler import Handler


def register(mcp: FastMCP, *, get_handler: Callable[[], Handler]) -> None:
    """Register the `start_iteration` tool on the given MCP server."""

    @mcp.tool(
        name="start_iteration",
        description=(
            "Begin one convergence-loop iteration on a Running Procedure "
            "(for example an alignment sweep). Requires the Procedure to be in "
            "`Running` with no iteration already open. `iteration_index` is "
            "operator-supplied and must be the strict successor of the current "
            "count (1, 2, 3, ...). Optional: non-iterative Procedures never call "
            "this."
        ),
    )
    async def start_iteration_tool(  # pyright: ignore[reportUnusedFunction]
        ctx: Context[Any, Any, Any],
        procedure_id: Annotated[
            UUID,
            Field(description="Target procedure's id."),
        ],
        iteration_index: Annotated[
            int,
            Field(
                ge=1,
                description=(
                    "1-based index of the iteration to begin; the strict "
                    "successor of the current iteration_count."
                ),
            ),
        ],
    ) -> None:
        handler = get_handler()
        await handler(
            StartProcedureIteration(
                procedure_id=procedure_id,
                iteration_index=iteration_index,
            ),
            principal_id=get_mcp_principal_id(ctx),
            correlation_id=current_correlation_id(),
            surface_id=get_mcp_surface_id(),
        )
