"""MCP tool for the `remove_run_from_campaign` slice."""

from collections.abc import Callable
from typing import Annotated, Any
from uuid import UUID

from mcp.server.fastmcp import Context, FastMCP
from pydantic import BaseModel, Field

from cora.campaign.features.remove_run_from_campaign.command import RemoveRunFromCampaign
from cora.campaign.features.remove_run_from_campaign.handler import Handler
from cora.infrastructure.mcp_principal import get_mcp_principal_id
from cora.infrastructure.observability import current_correlation_id
from cora.infrastructure.routing import get_mcp_surface_id
from cora.shared.text_bounds import REASON_MAX_LENGTH


class RemoveRunFromCampaignOutput(BaseModel):
    """Structured output of the `remove_run_from_campaign` MCP tool."""

    campaign_id: UUID
    run_id: UUID


def register(mcp: FastMCP, *, get_handler: Callable[[], Handler]) -> None:
    """Register the `remove_run_from_campaign` tool on the given MCP server."""

    @mcp.tool(
        name="remove_run_from_campaign",
        description=(
            "Remove a Run from a Campaign (atomic two-stream write). Campaign "
            "must be in Planned, Active, or Held; Run must be a current "
            "member. Operator-supplied reason is REQUIRED (per-membership "
            "audit breadcrumb). Writes both streams via "
            "EventStore.append_streams (all-or-nothing)."
        ),
    )
    async def remove_run_from_campaign_tool(  # pyright: ignore[reportUnusedFunction]
        ctx: Context[Any, Any, Any],
        campaign_id: Annotated[UUID, Field(description="Target Campaign's id.")],
        run_id: Annotated[UUID, Field(description="Run to remove from the Campaign.")],
        reason: Annotated[
            str,
            Field(
                min_length=1,
                max_length=REASON_MAX_LENGTH,
                description=(
                    "Operator-supplied reason for the removal (per-membership audit breadcrumb)."
                ),
            ),
        ],
    ) -> RemoveRunFromCampaignOutput:
        handler = get_handler()
        await handler(
            RemoveRunFromCampaign(
                campaign_id=campaign_id,
                run_id=run_id,
                reason=reason,
            ),
            principal_id=get_mcp_principal_id(ctx),
            correlation_id=current_correlation_id(),
            surface_id=get_mcp_surface_id(),
        )
        return RemoveRunFromCampaignOutput(campaign_id=campaign_id, run_id=run_id)
