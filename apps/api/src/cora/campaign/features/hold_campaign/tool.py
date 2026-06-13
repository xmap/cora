"""MCP tool for the `hold_campaign` slice."""

from collections.abc import Callable
from typing import Annotated, Any
from uuid import UUID

from mcp.server.fastmcp import Context, FastMCP
from pydantic import BaseModel, Field

from cora.campaign.features.hold_campaign.command import HoldCampaign
from cora.campaign.features.hold_campaign.handler import Handler
from cora.infrastructure.mcp_principal import get_mcp_principal_id
from cora.infrastructure.observability import current_correlation_id
from cora.infrastructure.routing import get_mcp_surface_id
from cora.shared.text_bounds import REASON_MAX_LENGTH


class HoldCampaignOutput(BaseModel):
    """Structured output of the `hold_campaign` MCP tool."""

    campaign_id: UUID


def register(mcp: FastMCP, *, get_handler: Callable[[], Handler]) -> None:
    """Register the `hold_campaign` tool on the given MCP server."""

    @mcp.tool(
        name="hold_campaign",
        description=(
            "Hold an Active Campaign (Active -> Held). Single-source from "
            "Active. Operator-supplied reason is REQUIRED (audit-log "
            "breadcrumb). Held Campaigns still accept new member Runs."
        ),
    )
    async def hold_campaign_tool(  # pyright: ignore[reportUnusedFunction]
        ctx: Context[Any, Any, Any],
        campaign_id: Annotated[UUID, Field(description="Target Campaign's id.")],
        reason: Annotated[
            str,
            Field(
                min_length=1,
                max_length=REASON_MAX_LENGTH,
                description=("Operator-supplied reason for the hold (audit-log breadcrumb)."),
            ),
        ],
    ) -> HoldCampaignOutput:
        handler = get_handler()
        await handler(
            HoldCampaign(campaign_id=campaign_id, reason=reason),
            principal_id=get_mcp_principal_id(ctx),
            correlation_id=current_correlation_id(),
            surface_id=get_mcp_surface_id(),
        )
        return HoldCampaignOutput(campaign_id=campaign_id)
