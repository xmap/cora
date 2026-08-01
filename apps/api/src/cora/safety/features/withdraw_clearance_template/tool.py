"""MCP tool for the `withdraw_clearance_template` slice."""

from collections.abc import Callable
from typing import Annotated, Any
from uuid import UUID

from mcp.server.fastmcp import Context, FastMCP
from pydantic import BaseModel, Field

from cora.infrastructure.mcp_principal import get_mcp_principal_id
from cora.infrastructure.observability import current_correlation_id
from cora.infrastructure.routing import get_mcp_surface_id
from cora.safety.features.withdraw_clearance_template.command import (
    WithdrawClearanceTemplate,
)
from cora.safety.features.withdraw_clearance_template.handler import Handler
from cora.shared.text_bounds import REASON_MAX_LENGTH


class WithdrawClearanceTemplateOutput(BaseModel):
    """Structured output of the `withdraw_clearance_template` MCP tool."""

    template_id: UUID


def register(mcp: FastMCP, *, get_handler: Callable[[], Handler]) -> None:
    """Register the `withdraw_clearance_template` tool on the given MCP server."""

    @mcp.tool(
        name="withdraw_clearance_template",
        description=(
            "Withdraw a clearance template (Draft, Active, or Deprecated -> "
            "Withdrawn). Withdrawn is terminal: no further transitions are "
            "permitted. Requires template to be in 'Draft', 'Active', or "
            "'Deprecated' status."
        ),
    )
    async def withdraw_clearance_template_tool(  # pyright: ignore[reportUnusedFunction]
        ctx: Context[Any, Any, Any],
        template_id: Annotated[UUID, Field(description="Target template's id.")],
        reason: Annotated[
            str,
            Field(
                min_length=1,
                max_length=REASON_MAX_LENGTH,
                description=(
                    "Why the template is being withdrawn. Free text: withdrawal "
                    "causes are open-ended (superseded by a facility policy "
                    "change, drafted in error, the hazard class no longer "
                    "applies), unlike deprecation, where the reason decides "
                    "whether prior data is trustworthy and the set is closed."
                ),
            ),
        ],
    ) -> WithdrawClearanceTemplateOutput:
        handler = get_handler()
        await handler(
            WithdrawClearanceTemplate(template_id=template_id, reason=reason),
            principal_id=get_mcp_principal_id(ctx),
            correlation_id=current_correlation_id(),
            surface_id=get_mcp_surface_id(),
        )
        return WithdrawClearanceTemplateOutput(template_id=template_id)
