"""MCP tool for the `void_visit` slice."""

from collections.abc import Callable
from typing import Annotated, Any
from uuid import UUID

from mcp.server.fastmcp import Context, FastMCP
from pydantic import BaseModel, Field

from cora.infrastructure.mcp_principal import get_mcp_principal_id
from cora.infrastructure.observability import current_correlation_id
from cora.infrastructure.routing import get_mcp_surface_id
from cora.shared.text_bounds import REASON_MAX_LENGTH
from cora.trust.features.void_visit.command import VoidVisit
from cora.trust.features.void_visit.handler import Handler


class VoidVisitOutput(BaseModel):
    """Structured output of the `void_visit` MCP tool."""

    visit_id: UUID


def register(mcp: FastMCP, *, get_handler: Callable[[], Handler]) -> None:
    """Register the `void_visit` tool on the given MCP server."""

    @mcp.tool(
        name="void_visit",
        description=(
            "Void a Visit (any non-terminal -> Voided). FHIR R5 entered-in-"
            "error analog: 'this Visit should never have existed' (BSS "
            "double-registration, duplicate, etc.). Distinct from "
            "cancel_visit (real allocation, pre-work) and abort_visit (real "
            "work stopped). Reason REQUIRED. No PII."
        ),
    )
    async def void_visit_tool(  # pyright: ignore[reportUnusedFunction]
        ctx: Context[Any, Any, Any],
        visit_id: Annotated[UUID, Field(description="Target Visit's id.")],
        reason: Annotated[
            str,
            Field(
                min_length=1,
                max_length=REASON_MAX_LENGTH,
                description="Operator-supplied reason for voiding.",
            ),
        ],
    ) -> VoidVisitOutput:
        handler = get_handler()
        await handler(
            VoidVisit(visit_id=visit_id, reason=reason),
            principal_id=get_mcp_principal_id(ctx),
            correlation_id=current_correlation_id(),
            surface_id=get_mcp_surface_id(),
        )
        return VoidVisitOutput(visit_id=visit_id)
