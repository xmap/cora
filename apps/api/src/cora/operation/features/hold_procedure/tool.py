"""MCP tool for the `hold_procedure` slice."""

from collections.abc import Callable
from typing import Annotated, Any
from uuid import UUID

from mcp.server.fastmcp import Context, FastMCP
from pydantic import Field

from cora.infrastructure.mcp_principal import get_mcp_principal_id
from cora.infrastructure.observability import current_correlation_id
from cora.infrastructure.routing import get_mcp_surface_id
from cora.operation.features.hold_procedure.command import HoldProcedure
from cora.operation.features.hold_procedure.handler import Handler
from cora.shared.text_bounds import REASON_MAX_LENGTH


def register(mcp: FastMCP, *, get_handler: Callable[[], Handler]) -> None:
    """Register the `hold_procedure` tool on the given MCP server."""

    @mcp.tool(
        name="hold_procedure",
        description=(
            "Pause an actively-running Procedure conduct (Running -> Held) so it "
            "can be re-established and resumed later. The inverse of resume_procedure. "
            "Requires the Procedure to currently be in `Running`. Holding a "
            "`Defined` / `Held` / terminal Procedure raises. Reason is required "
            "(1-500 chars), captured verbatim for audit."
        ),
    )
    async def hold_procedure_tool(  # pyright: ignore[reportUnusedFunction]
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
                description="Free-form reason for the hold (1-500 chars after trimming).",
            ),
        ],
    ) -> None:
        handler = get_handler()
        await handler(
            HoldProcedure(procedure_id=procedure_id, reason=reason),
            principal_id=get_mcp_principal_id(ctx),
            correlation_id=current_correlation_id(),
            surface_id=get_mcp_surface_id(),
        )
