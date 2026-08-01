"""MCP tool for the `update_agent_target_plan` slice."""

from collections.abc import Callable
from typing import Annotated, Any
from uuid import UUID

from mcp.server.fastmcp import Context, FastMCP
from pydantic import BaseModel, Field

from cora.agent.features.update_agent_target_plan.command import UpdateAgentTargetPlan
from cora.agent.features.update_agent_target_plan.handler import Handler
from cora.infrastructure.mcp_principal import get_mcp_principal_id
from cora.infrastructure.observability import current_correlation_id
from cora.infrastructure.routing import get_mcp_surface_id


class UpdateAgentTargetPlanOutput(BaseModel):
    """Structured output of the `update_agent_target_plan` MCP tool."""

    agent_id: UUID
    target_plan_id: UUID | None


def register(mcp: FastMCP, *, get_handler: Callable[[], Handler]) -> None:
    """Register the `update_agent_target_plan` tool on the given MCP server."""

    @mcp.tool(
        name="update_agent_target_plan",
        description=(
            "Update or clear the recipe Plan an autonomous Agent (the "
            "RunInitiator) starts for each ready Subject. PUT-semantics: the "
            "supplied target_plan_id IS the post-update target; pass null to "
            "clear it. Allowed in Defined / Versioned / Suspended (only "
            "Deprecated blocks)."
        ),
    )
    async def update_agent_target_plan_tool(  # pyright: ignore[reportUnusedFunction]
        ctx: Context[Any, Any, Any],
        agent_id: Annotated[
            UUID, Field(description="Identifier of the Agent whose target Plan to update.")
        ],
        target_plan_id: Annotated[
            UUID | None,
            Field(
                default=None,
                description="The recipe Plan id to target (null to clear).",
            ),
        ] = None,
    ) -> UpdateAgentTargetPlanOutput:
        handler = get_handler()
        await handler(
            UpdateAgentTargetPlan(
                agent_id=agent_id,
                target_plan_id=target_plan_id,
            ),
            principal_id=get_mcp_principal_id(ctx),
            correlation_id=current_correlation_id(),
            surface_id=get_mcp_surface_id(),
        )
        return UpdateAgentTargetPlanOutput(
            agent_id=agent_id,
            target_plan_id=target_plan_id,
        )
