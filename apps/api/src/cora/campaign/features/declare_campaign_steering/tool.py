"""MCP tool for the `declare_campaign_steering` slice.

Reuses the Pydantic wire models + converters defined in this slice's
`route.py` (one shape across HTTP + MCP, beside the slice rather than in
a BC-level seam module since the shapes are slice-local).
"""

from collections.abc import Callable
from typing import Annotated, Any
from uuid import UUID

from mcp.server.fastmcp import Context, FastMCP
from pydantic import BaseModel, Field

from cora.campaign.features.declare_campaign_steering.command import DeclareCampaignSteering
from cora.campaign.features.declare_campaign_steering.handler import Handler
from cora.campaign.features.declare_campaign_steering.route import (
    SteeringObjectiveRequest,
    SteeringSpaceRequest,
    objective_from_wire,
    space_from_wire,
)
from cora.infrastructure.mcp_principal import get_mcp_principal_id
from cora.infrastructure.observability import current_correlation_id
from cora.infrastructure.routing import get_mcp_surface_id


class DeclareCampaignSteeringOutput(BaseModel):
    """Structured output of the `declare_campaign_steering` MCP tool."""

    campaign_id: UUID


def register(mcp: FastMCP, *, get_handler: Callable[[], Handler]) -> None:
    """Register the `declare_campaign_steering` tool on the given MCP server."""

    @mcp.tool(
        name="declare_campaign_steering",
        description=(
            "Declare a Campaign's steering INTENT: an objective (what good "
            "means) plus a search space (where a future across-Run steerer "
            "may look). PUT semantics (a re-declare overwrites the prior "
            "intent). Allowed on a Planned or Active Campaign only."
        ),
    )
    async def declare_campaign_steering_tool(  # pyright: ignore[reportUnusedFunction]
        ctx: Context[Any, Any, Any],
        campaign_id: Annotated[UUID, Field(description="Target Campaign's id.")],
        objective: Annotated[
            SteeringObjectiveRequest,
            Field(description="What good means (objective sense + optional target)."),
        ],
        space: Annotated[
            SteeringSpaceRequest,
            Field(description="The feasible search space (>= 1 axis)."),
        ],
    ) -> DeclareCampaignSteeringOutput:
        handler = get_handler()
        await handler(
            DeclareCampaignSteering(
                campaign_id=campaign_id,
                objective=objective_from_wire(objective),
                space=space_from_wire(space),
            ),
            principal_id=get_mcp_principal_id(ctx),
            correlation_id=current_correlation_id(),
            surface_id=get_mcp_surface_id(),
        )
        return DeclareCampaignSteeringOutput(campaign_id=campaign_id)
