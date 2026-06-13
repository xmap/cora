"""MCP tool for the `abandon_campaign` slice."""

from collections.abc import Callable
from typing import Annotated, Any
from uuid import UUID

from mcp.server.fastmcp import Context, FastMCP
from pydantic import BaseModel, Field

from cora.campaign.features.abandon_campaign.command import AbandonCampaign
from cora.campaign.features.abandon_campaign.handler import Handler
from cora.infrastructure.mcp_principal import get_mcp_principal_id
from cora.infrastructure.observability import current_correlation_id
from cora.infrastructure.routing import get_mcp_surface_id
from cora.shared.text_bounds import REASON_MAX_LENGTH


class AbandonCampaignOutput(BaseModel):
    """Structured output of the `abandon_campaign` MCP tool."""

    campaign_id: UUID


def register(mcp: FastMCP, *, get_handler: Callable[[], Handler]) -> None:
    """Register the `abandon_campaign` tool on the given MCP server."""

    @mcp.tool(
        name="abandon_campaign",
        description=(
            "Abandon a Campaign (Planned | Active | Held -> Abandoned). "
            "Early-terminal with REQUIRED reason. Member Runs are NOT "
            "cascaded (per-Run audit independence). Members are locked "
            "after abandon."
        ),
    )
    async def abandon_campaign_tool(  # pyright: ignore[reportUnusedFunction]
        ctx: Context[Any, Any, Any],
        campaign_id: Annotated[UUID, Field(description="Target Campaign's id.")],
        reason: Annotated[
            str,
            Field(
                min_length=1,
                max_length=REASON_MAX_LENGTH,
                description=(
                    "REQUIRED. Operator-supplied reason for the abandon "
                    "transition (audit-log breadcrumb)."
                ),
            ),
        ],
    ) -> AbandonCampaignOutput:
        handler = get_handler()
        await handler(
            AbandonCampaign(campaign_id=campaign_id, reason=reason),
            principal_id=get_mcp_principal_id(ctx),
            correlation_id=current_correlation_id(),
            surface_id=get_mcp_surface_id(),
        )
        return AbandonCampaignOutput(campaign_id=campaign_id)
