"""MCP tool for the `abort_visit` slice."""

from collections.abc import Callable
from typing import Annotated, Any
from uuid import UUID

from mcp.server.fastmcp import Context, FastMCP
from pydantic import BaseModel, Field

from cora.infrastructure.mcp_principal import get_mcp_principal_id
from cora.infrastructure.observability import current_correlation_id
from cora.infrastructure.routing import get_mcp_surface_id
from cora.shared.text_bounds import REASON_MAX_LENGTH
from cora.trust.features.abort_visit.command import AbortVisit
from cora.trust.features.abort_visit.handler import Handler


class AbortVisitOutput(BaseModel):
    """Structured output of the `abort_visit` MCP tool."""

    visit_id: UUID


def register(mcp: FastMCP, *, get_handler: Callable[[], Handler]) -> None:
    """Register the `abort_visit` tool on the given MCP server."""

    @mcp.tool(
        name="abort_visit",
        description=(
            "Abort a mid-work Visit (InProgress | OnHold -> Aborted). HL7 "
            "v2 A13 precedent (cancel-discharge, distinct from A11 cancel-"
            "admit / cancel_visit). Pre-work Visits must use cancel_visit "
            "instead. Reason REQUIRED. No PII."
        ),
    )
    async def abort_visit_tool(  # pyright: ignore[reportUnusedFunction]
        ctx: Context[Any, Any, Any],
        visit_id: Annotated[UUID, Field(description="Target Visit's id.")],
        reason: Annotated[
            str,
            Field(
                min_length=1,
                max_length=REASON_MAX_LENGTH,
                description="Operator-supplied reason for the abort.",
            ),
        ],
    ) -> AbortVisitOutput:
        handler = get_handler()
        await handler(
            AbortVisit(visit_id=visit_id, reason=reason),
            principal_id=get_mcp_principal_id(ctx),
            correlation_id=current_correlation_id(),
            surface_id=get_mcp_surface_id(),
        )
        return AbortVisitOutput(visit_id=visit_id)
