"""MCP tool for the `abort_procedure` slice."""

from collections.abc import Callable
from typing import Annotated, Any
from uuid import UUID

from mcp.server.fastmcp import Context, FastMCP
from pydantic import Field

from cora.infrastructure.mcp_principal import get_mcp_principal_id
from cora.infrastructure.observability import current_correlation_id
from cora.infrastructure.routing import get_mcp_surface_id
from cora.operation.features.abort_procedure.command import AbortProcedure
from cora.operation.features.abort_procedure.handler import Handler
from cora.shared.text_bounds import REASON_MAX_LENGTH


def register(mcp: FastMCP, *, get_handler: Callable[[], Handler]) -> None:
    """Register the `abort_procedure` tool on the given MCP server."""

    @mcp.tool(
        name="abort_procedure",
        description=(
            "Mark an existing Procedure as aborted (emergency-exit terminal). "
            "Requires the Procedure to currently be in `Running`. "
            "Aborting a `Defined` / `Completed` / `Aborted` Procedure raises. "
            "Reason is free-form (1-500 chars), captured verbatim for audit."
        ),
    )
    async def abort_procedure_tool(  # pyright: ignore[reportUnusedFunction]
        ctx: Context[Any, Any, Any],
        procedure_id: Annotated[
            UUID,
            Field(description="Target procedure's id."),
        ],
        reason: Annotated[
            str,
            Field(
                min_length=1,
                max_length=REASON_MAX_LENGTH,
                description=("Free-form reason for the abort (1-500 chars after trimming)."),
            ),
        ],
    ) -> None:
        handler = get_handler()
        await handler(
            AbortProcedure(procedure_id=procedure_id, reason=reason),
            principal_id=get_mcp_principal_id(ctx),
            correlation_id=current_correlation_id(),
            surface_id=get_mcp_surface_id(),
        )
