"""MCP tool for the `revoke_tool_from_agent` slice."""

from collections.abc import Callable
from typing import Annotated, Any
from uuid import UUID

from mcp.server.fastmcp import Context, FastMCP
from pydantic import BaseModel, Field

from cora.agent.aggregates.agent import AGENT_TOOL_NAME_MAX_LENGTH
from cora.agent.features.revoke_tool_from_agent.command import RevokeToolFromAgent
from cora.agent.features.revoke_tool_from_agent.handler import Handler
from cora.infrastructure.mcp_principal import get_mcp_principal_id
from cora.infrastructure.observability import current_correlation_id
from cora.infrastructure.routing import get_mcp_surface_id


class RevokeToolFromAgentOutput(BaseModel):
    """Structured output of the `revoke_tool_from_agent` MCP tool."""

    agent_id: UUID
    tool_name: str


def register(mcp: FastMCP, *, get_handler: Callable[[], Handler]) -> None:
    """Register the `revoke_tool_from_agent` tool on the given MCP server."""

    @mcp.tool(
        name="revoke_tool_from_agent",
        description=(
            "Remove one MCP tool from an Agent's declared tool set. Recorded "
            "only: not enforced at invocation yet, so this changes recorded "
            "intent, not runtime behavior. Allowed in Defined / Versioned / "
            "Suspended (only Deprecated blocks). Idempotent: revoking a tool "
            "the Agent doesn't have emits no event."
        ),
    )
    async def revoke_tool_from_agent_tool(  # pyright: ignore[reportUnusedFunction]
        ctx: Context[Any, Any, Any],
        agent_id: Annotated[
            UUID, Field(description="Identifier of the Agent to revoke the tool from.")
        ],
        tool_name: Annotated[
            str,
            Field(
                min_length=1,
                max_length=AGENT_TOOL_NAME_MAX_LENGTH,
                description="MCP tool name to remove (1-100 chars).",
            ),
        ],
    ) -> RevokeToolFromAgentOutput:
        handler = get_handler()
        await handler(
            RevokeToolFromAgent(agent_id=agent_id, tool_name=tool_name),
            principal_id=get_mcp_principal_id(ctx),
            correlation_id=current_correlation_id(),
            surface_id=get_mcp_surface_id(),
        )
        return RevokeToolFromAgentOutput(agent_id=agent_id, tool_name=tool_name)
