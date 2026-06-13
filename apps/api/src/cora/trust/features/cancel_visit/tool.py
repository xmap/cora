"""MCP tool for the `cancel_visit` slice."""

from collections.abc import Callable
from typing import Annotated, Any
from uuid import UUID

from mcp.server.fastmcp import Context, FastMCP
from pydantic import BaseModel, Field

from cora.infrastructure.mcp_principal import get_mcp_principal_id
from cora.infrastructure.observability import current_correlation_id
from cora.infrastructure.routing import get_mcp_surface_id
from cora.shared.text_bounds import REASON_MAX_LENGTH
from cora.trust.features.cancel_visit.command import CancelVisit
from cora.trust.features.cancel_visit.handler import Handler


class CancelVisitOutput(BaseModel):
    """Structured output of the `cancel_visit` MCP tool."""

    visit_id: UUID


def register(mcp: FastMCP, *, get_handler: Callable[[], Handler]) -> None:
    """Register the `cancel_visit` tool on the given MCP server."""

    @mcp.tool(
        name="cancel_visit",
        description=(
            "Cancel a pre-work Visit (Planned | Arrived -> Cancelled). "
            "HL7 v2 A11 precedent (cancel-admit, distinct from A13 cancel-"
            "discharge / abort). InProgress / OnHold must use abort_visit "
            "instead. Reason REQUIRED. No PII."
        ),
    )
    async def cancel_visit_tool(  # pyright: ignore[reportUnusedFunction]
        ctx: Context[Any, Any, Any],
        visit_id: Annotated[UUID, Field(description="Target Visit's id.")],
        reason: Annotated[
            str,
            Field(
                min_length=1,
                max_length=REASON_MAX_LENGTH,
                description="Operator-supplied reason for the cancellation.",
            ),
        ],
    ) -> CancelVisitOutput:
        handler = get_handler()
        await handler(
            CancelVisit(visit_id=visit_id, reason=reason),
            principal_id=get_mcp_principal_id(ctx),
            correlation_id=current_correlation_id(),
            surface_id=get_mcp_surface_id(),
        )
        return CancelVisitOutput(visit_id=visit_id)
