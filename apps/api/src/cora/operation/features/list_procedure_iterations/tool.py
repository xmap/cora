"""MCP tool for the `list_procedure_iterations` query slice."""

from collections.abc import Callable
from datetime import datetime
from typing import Annotated, Any
from uuid import UUID

from mcp.server.fastmcp import Context, FastMCP
from pydantic import BaseModel, Field

from cora.infrastructure.mcp_principal import get_mcp_principal_id
from cora.infrastructure.observability import current_correlation_id
from cora.infrastructure.routing import get_mcp_surface_id
from cora.operation.features.list_procedure_iterations.handler import Handler
from cora.operation.features.list_procedure_iterations.query import ListProcedureIterations


class _ProcedureIterationDTO(BaseModel):
    """One convergence-loop iteration (MCP-tool DTO; mirrors HTTP shape)."""

    iteration_index: int
    started_at: datetime
    ended_at: datetime | None = None
    converged: bool | None = None
    reason: str | None = None


class _ListProcedureIterationsOutput(BaseModel):
    """MCP tool output: all iterations for one Procedure, ordered by index."""

    items: list[_ProcedureIterationDTO]


def register(mcp: FastMCP, *, get_handler: Callable[[], Handler]) -> None:
    """Register the `list_procedure_iterations` tool on the given MCP server."""

    @mcp.tool(
        name="list_procedure_iterations",
        description=(
            "List the convergence-loop iterations of a Procedure (index, "
            "started/ended, converged verdict, reason), ordered by index. "
            "Reads the proj_operation_procedure_iterations projection."
        ),
    )
    async def list_procedure_iterations_tool(  # pyright: ignore[reportUnusedFunction]
        ctx: Context[Any, Any, Any],
        procedure_id: Annotated[
            UUID,
            Field(description="Target procedure's id."),
        ],
    ) -> _ListProcedureIterationsOutput:
        handler = get_handler()
        result = await handler(
            ListProcedureIterations(procedure_id=procedure_id),
            principal_id=get_mcp_principal_id(ctx),
            correlation_id=current_correlation_id(),
            surface_id=get_mcp_surface_id(),
        )
        return _ListProcedureIterationsOutput(
            items=[
                _ProcedureIterationDTO(
                    iteration_index=item.iteration_index,
                    started_at=item.started_at,
                    ended_at=item.ended_at,
                    converged=item.converged,
                    reason=item.reason,
                )
                for item in result.items
            ]
        )
