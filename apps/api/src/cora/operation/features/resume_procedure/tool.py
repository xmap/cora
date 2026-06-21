"""MCP tool for the `resume_procedure` slice."""

from collections.abc import Callable
from typing import Annotated, Any
from uuid import UUID

from mcp.server.fastmcp import Context, FastMCP
from pydantic import Field

from cora.infrastructure.mcp_principal import get_mcp_principal_id
from cora.infrastructure.observability import current_correlation_id
from cora.infrastructure.routing import get_mcp_surface_id
from cora.operation.features.resume_procedure.command import ResumeProcedure
from cora.operation.features.resume_procedure.handler import Handler


def register(mcp: FastMCP, *, get_handler: Callable[[], Handler]) -> None:
    """Register the `resume_procedure` tool on the given MCP server."""

    @mcp.tool(
        name="resume_procedure",
        description=(
            "Resume a held Procedure conduct (Held -> Running). The inverse of "
            "hold_procedure. Requires the Procedure to currently be in `Held`. "
            "Resuming a `Running` / `Defined` / terminal Procedure raises. "
            "re_establishment_boundary (>= 0) is the step-list index the resume "
            "re-drives setpoints / re-runs checks from."
        ),
    )
    async def resume_procedure_tool(  # pyright: ignore[reportUnusedFunction]
        ctx: Context[Any, Any, Any],
        procedure_id: Annotated[
            UUID,
            Field(description="Target procedure's id."),
        ],
        re_establishment_boundary: Annotated[
            int,
            Field(
                ge=0,
                description=(
                    "Index in the pinned resolved step list the resume re-drives "
                    "setpoints / re-runs checks from (>= 0; 0 = from the first step)."
                ),
            ),
        ],
    ) -> None:
        handler = get_handler()
        await handler(
            ResumeProcedure(
                procedure_id=procedure_id,
                re_establishment_boundary=re_establishment_boundary,
            ),
            principal_id=get_mcp_principal_id(ctx),
            correlation_id=current_correlation_id(),
            surface_id=get_mcp_surface_id(),
        )
