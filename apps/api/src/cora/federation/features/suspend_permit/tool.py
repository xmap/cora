"""MCP tool for the `suspend_permit` slice.

Surfaces the same handler the REST route uses, exposed as a Model
Context Protocol tool."""

from collections.abc import Callable
from typing import Annotated, Any
from uuid import UUID

from mcp.server.fastmcp import Context, FastMCP
from pydantic import BaseModel, Field

from cora.federation.features.suspend_permit.command import SuspendPermit
from cora.federation.features.suspend_permit.handler import Handler
from cora.infrastructure.mcp_principal import get_mcp_principal_id
from cora.infrastructure.observability import current_correlation_id
from cora.infrastructure.routing import get_mcp_surface_id
from cora.shared.text_bounds import REASON_MAX_LENGTH


class SuspendPermitOutput(BaseModel):
    """Structured output of the `suspend_permit` MCP tool."""

    permit_id: UUID


def register(mcp: FastMCP, *, get_handler: Callable[[], Handler]) -> None:
    """Register the `suspend_permit` tool on the given MCP server."""

    @mcp.tool(
        name="suspend_permit",
        description=(
            "Suspend an Active Permit (Active -> Suspended). Single-source: "
            "requires Permit to be in 'Active' status. Reversible via "
            "'resume_permit'; for terminal removal use 'revoke_permit'."
        ),
    )
    async def suspend_permit_tool(  # pyright: ignore[reportUnusedFunction]
        ctx: Context[Any, Any, Any],
        permit_id: Annotated[
            UUID,
            Field(description="Target permit's id."),
        ],
        reason: Annotated[
            str | None,
            Field(
                default=None,
                max_length=REASON_MAX_LENGTH,
                description=(
                    "Optional operator-supplied reason for suspending the "
                    "permit (audit-log breadcrumb)."
                ),
            ),
        ] = None,
    ) -> SuspendPermitOutput:
        handler = get_handler()
        await handler(
            SuspendPermit(permit_id=permit_id, reason=reason),
            principal_id=get_mcp_principal_id(ctx),
            correlation_id=current_correlation_id(),
            surface_id=get_mcp_surface_id(),
        )
        return SuspendPermitOutput(permit_id=permit_id)
