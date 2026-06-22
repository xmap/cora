"""MCP tool for the `update_agent_budget` slice."""

from collections.abc import Callable
from typing import Annotated, Any
from uuid import UUID

from mcp.server.fastmcp import Context, FastMCP
from pydantic import BaseModel, Field

from cora.agent.features.update_agent_budget.command import UpdateAgentBudget
from cora.agent.features.update_agent_budget.handler import Handler
from cora.infrastructure.mcp_principal import get_mcp_principal_id
from cora.infrastructure.observability import current_correlation_id
from cora.infrastructure.routing import get_mcp_surface_id


class UpdateAgentBudgetOutput(BaseModel):
    """Structured output of the `update_agent_budget` MCP tool."""

    agent_id: UUID
    monthly_usd_cap: float | None
    daily_token_cap: int | None


def register(mcp: FastMCP, *, get_handler: Callable[[], Handler]) -> None:
    """Register the `update_agent_budget` tool on the given MCP server."""

    @mcp.tool(
        name="update_agent_budget",
        description=(
            "Update an Agent's declarative budget caps. PUT-semantics: the "
            "supplied caps ARE the post-update budget. Setting both caps to "
            "null clears the budget entirely. Allowed in Defined / Versioned / "
            "Suspended (only Deprecated blocks). Declaration-only at this "
            "iter; enforcement deferred to Budget BC."
        ),
    )
    async def update_agent_budget_tool(  # pyright: ignore[reportUnusedFunction]
        ctx: Context[Any, Any, Any],
        agent_id: Annotated[
            UUID, Field(description="Identifier of the Agent whose budget to update.")
        ],
        monthly_usd_cap: Annotated[
            float | None,
            Field(
                default=None,
                ge=0.0,
                description="Monthly USD cap (null to clear this field).",
            ),
        ] = None,
        daily_token_cap: Annotated[
            int | None,
            Field(
                default=None,
                ge=0,
                description="Daily token cap (null to clear this field).",
            ),
        ] = None,
    ) -> UpdateAgentBudgetOutput:
        handler = get_handler()
        await handler(
            UpdateAgentBudget(
                agent_id=agent_id,
                monthly_usd_cap=monthly_usd_cap,
                daily_token_cap=daily_token_cap,
            ),
            principal_id=get_mcp_principal_id(ctx),
            correlation_id=current_correlation_id(),
            surface_id=get_mcp_surface_id(),
        )
        return UpdateAgentBudgetOutput(
            agent_id=agent_id,
            monthly_usd_cap=monthly_usd_cap,
            daily_token_cap=daily_token_cap,
        )
