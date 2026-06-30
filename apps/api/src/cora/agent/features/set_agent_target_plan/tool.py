"""MCP tool for the `set_agent_target_plan` slice."""

from collections.abc import Callable
from typing import Annotated, Any
from uuid import UUID

from mcp.server.fastmcp import Context, FastMCP
from pydantic import BaseModel, Field

from cora.agent.features.set_agent_target_plan.command import SetAgentTargetPlan
from cora.agent.features.set_agent_target_plan.handler import Handler
from cora.infrastructure.mcp_principal import get_mcp_principal_id
from cora.infrastructure.observability import current_correlation_id
from cora.infrastructure.routing import get_mcp_surface_id


class SetAgentTargetPlanOutput(BaseModel):
    """Structured output of the `set_agent_target_plan` MCP tool."""

    agent_id: UUID
    target_plan_id: UUID | None


def register(mcp: FastMCP, *, get_handler: Callable[[], Handler]) -> None:
    """Register the `set_agent_target_plan` tool on the given MCP server."""

    @mcp.tool(
        name="set_agent_target_plan",
        description=(
            "Set or clear the recipe Plan an autonomous Agent (the "
            "RunInitiator) starts for each ready Subject. PUT-semantics: the "
            "supplied target_plan_id IS the post-set target; pass null to "
            "clear it. Allowed in Defined / Versioned / Suspended (only "
            "Deprecated blocks)."
        ),
    )
    async def set_agent_target_plan_tool(  # pyright: ignore[reportUnusedFunction]
        ctx: Context[Any, Any, Any],
        agent_id: Annotated[
            UUID, Field(description="Identifier of the Agent whose target Plan to set.")
        ],
        target_plan_id: Annotated[
            UUID | None,
            Field(
                default=None,
                description="The recipe Plan id to target (null to clear).",
            ),
        ] = None,
    ) -> SetAgentTargetPlanOutput:
        handler = get_handler()
        await handler(
            SetAgentTargetPlan(
                agent_id=agent_id,
                target_plan_id=target_plan_id,
            ),
            principal_id=get_mcp_principal_id(ctx),
            correlation_id=current_correlation_id(),
            surface_id=get_mcp_surface_id(),
        )
        return SetAgentTargetPlanOutput(
            agent_id=agent_id,
            target_plan_id=target_plan_id,
        )
