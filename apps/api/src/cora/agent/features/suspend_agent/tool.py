"""MCP tool for the `suspend_agent` slice."""

from collections.abc import Callable
from typing import Annotated, Any
from uuid import UUID

from mcp.server.fastmcp import Context, FastMCP
from pydantic import BaseModel, Field

from cora.agent.features.suspend_agent.command import SuspendAgent
from cora.agent.features.suspend_agent.handler import Handler
from cora.infrastructure.mcp_principal import get_mcp_principal_id
from cora.infrastructure.observability import current_correlation_id
from cora.infrastructure.routing import get_mcp_surface_id
from cora.shared.text_bounds import REASON_MAX_LENGTH


class SuspendAgentOutput(BaseModel):
    """Structured output of the `suspend_agent` MCP tool."""

    agent_id: UUID


def register(mcp: FastMCP, *, get_handler: Callable[[], Handler]) -> None:
    """Register the `suspend_agent` tool on the given MCP server."""

    @mcp.tool(
        name="suspend_agent",
        description=(
            "Pause a Versioned Agent (Versioned -> Suspended). Non-terminal: "
            "returns to Versioned via `resume_agent`. REQUIRED `reason` (1-500 "
            "chars) carries operator context (cost-overrun, output-spike, "
            "model-regression) for the audit log."
        ),
    )
    async def suspend_agent_tool(  # pyright: ignore[reportUnusedFunction]
        ctx: Context[Any, Any, Any],
        agent_id: Annotated[UUID, Field(description="Identifier of the Agent to suspend.")],
        reason: Annotated[
            str,
            Field(
                min_length=1,
                max_length=REASON_MAX_LENGTH,
                description="Operator-supplied suspension reason.",
            ),
        ],
    ) -> SuspendAgentOutput:
        handler = get_handler()
        await handler(
            SuspendAgent(agent_id=agent_id, reason=reason),
            principal_id=get_mcp_principal_id(ctx),
            correlation_id=current_correlation_id(),
            surface_id=get_mcp_surface_id(),
        )
        return SuspendAgentOutput(agent_id=agent_id)
