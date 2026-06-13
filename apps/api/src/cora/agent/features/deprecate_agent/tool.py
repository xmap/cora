"""MCP tool for the `deprecate_agent` slice."""

from collections.abc import Callable
from typing import Annotated, Any
from uuid import UUID

from mcp.server.fastmcp import Context, FastMCP
from pydantic import BaseModel, Field

from cora.agent.features.deprecate_agent.command import DeprecateAgent
from cora.agent.features.deprecate_agent.handler import Handler
from cora.infrastructure.mcp_principal import get_mcp_principal_id
from cora.infrastructure.observability import current_correlation_id
from cora.infrastructure.routing import get_mcp_surface_id
from cora.shared.text_bounds import REASON_MAX_LENGTH


class DeprecateAgentOutput(BaseModel):
    """Structured output of the `deprecate_agent` MCP tool."""

    agent_id: UUID


def register(mcp: FastMCP, *, get_handler: Callable[[], Handler]) -> None:
    """Register the `deprecate_agent` tool on the given MCP server."""

    @mcp.tool(
        name="deprecate_agent",
        description=(
            "Deprecate an Agent (Defined | Versioned -> Deprecated). Terminal: "
            "deprecated Agents cannot be revived. Optional `reason` (1-500 "
            "chars) carries an operator-supplied explanation."
        ),
    )
    async def deprecate_agent_tool(  # pyright: ignore[reportUnusedFunction]
        ctx: Context[Any, Any, Any],
        agent_id: Annotated[UUID, Field(description="Identifier of the Agent to deprecate.")],
        reason: Annotated[
            str | None,
            Field(
                default=None,
                min_length=1,
                max_length=REASON_MAX_LENGTH,
                description="Optional deprecation reason.",
            ),
        ] = None,
    ) -> DeprecateAgentOutput:
        handler = get_handler()
        await handler(
            DeprecateAgent(agent_id=agent_id, reason=reason),
            principal_id=get_mcp_principal_id(ctx),
            correlation_id=current_correlation_id(),
            surface_id=get_mcp_surface_id(),
        )
        return DeprecateAgentOutput(agent_id=agent_id)
