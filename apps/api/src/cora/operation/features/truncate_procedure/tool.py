"""MCP tool for the `truncate_procedure` slice."""

from collections.abc import Callable
from datetime import datetime
from typing import Annotated, Any
from uuid import UUID

from mcp.server.fastmcp import Context, FastMCP
from pydantic import Field

from cora.infrastructure.mcp_principal import get_mcp_principal_id
from cora.infrastructure.observability import current_correlation_id
from cora.infrastructure.routing import get_mcp_surface_id
from cora.operation.features.truncate_procedure.command import TruncateProcedure
from cora.operation.features.truncate_procedure.handler import Handler
from cora.shared.text_bounds import REASON_MAX_LENGTH


def register(mcp: FastMCP, *, get_handler: Callable[[], Handler]) -> None:
    """Register the `truncate_procedure` tool on the given MCP server."""

    @mcp.tool(
        name="truncate_procedure",
        description=(
            "Cleanup terminal for a Procedure that became de-facto dead "
            "through interruption (power loss, process crash, hardware "
            "fault, weekend interruption). Requires the Procedure to "
            "currently be in `Running`. Truncating a Defined / Completed / "
            "Aborted / Truncated Procedure raises. Reason is free-form "
            "(1-500 chars). Optional `interrupted_at` is the operator's "
            "best guess at when the actual interruption happened (must "
            "not be in the future)."
        ),
    )
    async def truncate_procedure_tool(  # pyright: ignore[reportUnusedFunction]
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
                description=("Free-form reason for the truncation (1-500 chars after trimming)."),
            ),
        ],
        interrupted_at: Annotated[
            datetime | None,
            Field(
                default=None,
                description=(
                    "Operator's best guess at when the actual interruption "
                    "occurred (ISO-8601, timezone-aware). Optional; null "
                    "when unknown. Must not be in the future."
                ),
            ),
        ] = None,
    ) -> None:
        handler = get_handler()
        await handler(
            TruncateProcedure(
                procedure_id=procedure_id,
                reason=reason,
                interrupted_at=interrupted_at,
            ),
            principal_id=get_mcp_principal_id(ctx),
            correlation_id=current_correlation_id(),
            surface_id=get_mcp_surface_id(),
        )
