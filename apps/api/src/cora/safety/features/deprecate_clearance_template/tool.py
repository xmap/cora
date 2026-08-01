"""MCP tool for the `deprecate_clearance_template` slice."""

from collections.abc import Callable
from typing import Annotated, Any
from uuid import UUID

from mcp.server.fastmcp import Context, FastMCP
from pydantic import BaseModel, Field

from cora.infrastructure.mcp_principal import get_mcp_principal_id
from cora.infrastructure.observability import current_correlation_id
from cora.infrastructure.routing import get_mcp_surface_id
from cora.safety.features.deprecate_clearance_template.command import (
    DeprecateClearanceTemplate,
)
from cora.safety.features.deprecate_clearance_template.handler import Handler
from cora.shared.deprecation import DeprecationReason


class DeprecateClearanceTemplateOutput(BaseModel):
    """Structured output of the `deprecate_clearance_template` MCP tool."""

    template_id: UUID


def register(mcp: FastMCP, *, get_handler: Callable[[], Handler]) -> None:
    """Register the `deprecate_clearance_template` tool on the given MCP server."""

    @mcp.tool(
        name="deprecate_clearance_template",
        description=(
            "Deprecate an Active clearance template (Active -> Deprecated). "
            "Existing clearances of this template remain valid; the template "
            "is no longer offered for new clearance proposals. Requires "
            "template to be in 'Active' status."
        ),
    )
    async def deprecate_clearance_template_tool(  # pyright: ignore[reportUnusedFunction]
        ctx: Context[Any, Any, Any],
        template_id: Annotated[UUID, Field(description="Target template's id.")],
        reason: Annotated[
            DeprecationReason,
            Field(
                description=(
                    "Why the template is no longer recommended. `Superseded`: a "
                    "newer version replaces it, prior use stands. `Defective`: it "
                    "was wrong, prior use is suspect. `Obsolete`: what it targeted "
                    "no longer exists."
                ),
            ),
        ],
    ) -> DeprecateClearanceTemplateOutput:
        handler = get_handler()
        await handler(
            DeprecateClearanceTemplate(template_id=template_id, reason=reason),
            principal_id=get_mcp_principal_id(ctx),
            correlation_id=current_correlation_id(),
            surface_id=get_mcp_surface_id(),
        )
        return DeprecateClearanceTemplateOutput(template_id=template_id)
