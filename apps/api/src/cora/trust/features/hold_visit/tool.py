"""MCP tool for the `hold_visit` slice."""

from collections.abc import Callable
from typing import Annotated, Any
from uuid import UUID

from mcp.server.fastmcp import Context, FastMCP
from pydantic import BaseModel, Field

from cora.infrastructure.mcp_principal import get_mcp_principal_id
from cora.infrastructure.observability import current_correlation_id
from cora.infrastructure.routing import get_mcp_surface_id
from cora.shared.text_bounds import REASON_MAX_LENGTH
from cora.trust.features.hold_visit.command import HoldVisit
from cora.trust.features.hold_visit.handler import Handler


class HoldVisitOutput(BaseModel):
    """Structured output of the `hold_visit` MCP tool."""

    visit_id: UUID


def register(mcp: FastMCP, *, get_handler: Callable[[], Handler]) -> None:
    """Register the `hold_visit` tool on the given MCP server."""

    @mcp.tool(
        name="hold_visit",
        description=(
            "Hold an InProgress Visit (InProgress -> OnHold). OnHold is "
            "reserved for genuine envelope pauses: beam dump, equipment "
            "fault, safety hold, extended user break. NOT for nested-child "
            "commissioning. Reason REQUIRED. Reason MUST NOT contain PII."
        ),
    )
    async def hold_visit_tool(  # pyright: ignore[reportUnusedFunction]
        ctx: Context[Any, Any, Any],
        visit_id: Annotated[UUID, Field(description="Target Visit's id.")],
        reason: Annotated[
            str,
            Field(
                min_length=1,
                max_length=REASON_MAX_LENGTH,
                description="Operator-supplied reason for the hold (no PII).",
            ),
        ],
    ) -> HoldVisitOutput:
        handler = get_handler()
        await handler(
            HoldVisit(visit_id=visit_id, reason=reason),
            principal_id=get_mcp_principal_id(ctx),
            correlation_id=current_correlation_id(),
            surface_id=get_mcp_surface_id(),
        )
        return HoldVisitOutput(visit_id=visit_id)
