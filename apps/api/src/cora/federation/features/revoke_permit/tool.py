"""MCP tool for the `revoke_permit` slice.

Surfaces the same handler the REST route uses, exposed as a Model
Context Protocol tool.
"""

from collections.abc import Callable
from typing import Annotated, Any
from uuid import UUID

from mcp.server.fastmcp import Context, FastMCP
from pydantic import BaseModel, Field

from cora.federation.features.revoke_permit.command import RevokePermit
from cora.federation.features.revoke_permit.handler import Handler
from cora.infrastructure.mcp_principal import get_mcp_principal_id
from cora.infrastructure.observability import current_correlation_id
from cora.infrastructure.routing import get_mcp_surface_id
from cora.shared.text_bounds import REASON_MAX_LENGTH


class RevokePermitOutput(BaseModel):
    """Structured output of the `revoke_permit` MCP tool."""

    permit_id: UUID


def register(mcp: FastMCP, *, get_handler: Callable[[], Handler]) -> None:
    """Register the `revoke_permit` tool on the given MCP server."""

    @mcp.tool(
        name="revoke_permit",
        description=(
            "Revoke a Permit (terminal: any non-Revoked status -> Revoked). "
            "Accepts Defined, Active, or Suspended. Strict-not-idempotent: "
            "revoking an already-Revoked permit raises. Once Revoked the "
            "permit cannot be revived; mint a fresh permit via define_permit "
            "if the federation flow must resume."
        ),
    )
    async def revoke_permit_tool(  # pyright: ignore[reportUnusedFunction]
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
                    "Optional operator-supplied reason for revoking the permit "
                    "(audit-log breadcrumb)."
                ),
            ),
        ] = None,
    ) -> RevokePermitOutput:
        handler = get_handler()
        await handler(
            RevokePermit(permit_id=permit_id, reason=reason),
            principal_id=get_mcp_principal_id(ctx),
            correlation_id=current_correlation_id(),
            surface_id=get_mcp_surface_id(),
        )
        return RevokePermitOutput(permit_id=permit_id)
