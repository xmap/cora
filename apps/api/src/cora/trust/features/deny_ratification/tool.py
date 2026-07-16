"""MCP tool for the `deny_ratification` slice."""

from collections.abc import Callable
from typing import Annotated, Any
from uuid import UUID

from mcp.server.fastmcp import Context, FastMCP
from pydantic import BaseModel, Field

from cora.infrastructure.mcp_principal import get_mcp_principal_id
from cora.infrastructure.observability import current_correlation_id
from cora.infrastructure.routing import get_mcp_surface_id
from cora.shared.text_bounds import REASON_MAX_LENGTH
from cora.trust.features.deny_ratification.command import DenyRatification
from cora.trust.features.deny_ratification.handler import Handler


class DenyRatificationOutput(BaseModel):
    """Structured output of the `deny_ratification` MCP tool."""

    ratification_id: UUID


def register(mcp: FastMCP, *, get_handler: Callable[[], Handler]) -> None:
    """Register the `deny_ratification` tool on the given MCP server."""

    @mcp.tool(
        name="deny_ratification",
        description=(
            "Deny (refuse) a Requested Ratification (Requested -> Denied). The "
            "denying principal must be independent of the requester (four-eyes). "
            "Reason REQUIRED. Reason MUST NOT contain PII."
        ),
    )
    async def deny_ratification_tool(  # pyright: ignore[reportUnusedFunction]
        ctx: Context[Any, Any, Any],
        ratification_id: Annotated[UUID, Field(description="Target Ratification's id.")],
        reason: Annotated[
            str,
            Field(
                min_length=1,
                max_length=REASON_MAX_LENGTH,
                description="Operator-supplied reason for the denial (no PII).",
            ),
        ],
    ) -> DenyRatificationOutput:
        handler = get_handler()
        await handler(
            DenyRatification(ratification_id=ratification_id, reason=reason),
            principal_id=get_mcp_principal_id(ctx),
            correlation_id=current_correlation_id(),
            surface_id=get_mcp_surface_id(),
        )
        return DenyRatificationOutput(ratification_id=ratification_id)
