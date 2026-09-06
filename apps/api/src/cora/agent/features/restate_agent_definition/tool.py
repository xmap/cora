"""MCP tool for the `restate_agent_definition` slice."""

from collections.abc import Callable
from typing import Annotated, Any
from uuid import UUID

from mcp.server.fastmcp import Context, FastMCP
from pydantic import BaseModel, Field

from cora.agent._brain_wire import brain_from_body
from cora.agent.features.restate_agent_definition.command import RestateAgentDefinition
from cora.agent.features.restate_agent_definition.handler import Handler
from cora.agent.features.restate_agent_definition.route import RestatedBrainRequest
from cora.infrastructure.mcp_principal import get_mcp_principal_id
from cora.infrastructure.observability import current_correlation_id
from cora.infrastructure.routing import get_mcp_surface_id
from cora.shared.text_bounds import REASON_MAX_LENGTH


class RestateAgentDefinitionOutput(BaseModel):
    """Structured output of the `restate_agent_definition` MCP tool."""

    agent_id: UUID
    name: str | None
    brain_kind: str | None


def register(mcp: FastMCP, *, get_handler: Callable[[], Handler]) -> None:
    """Register the `restate_agent_definition` tool on the given MCP server."""

    @mcp.tool(
        name="restate_agent_definition",
        description=(
            "Restate an existing Agent's name and/or brain by appending a "
            "correction to its stream. Events are INSERT-only, so this is how "
            "an Agent defined before brains had kinds says what it thinks "
            "with. An omitted field stays UNCHANGED (not cleared); supply a "
            "name, a brain, or both, plus a reason. Allowed in Defined / "
            "Versioned / Suspended (only Deprecated blocks)."
        ),
    )
    async def restate_agent_definition_tool(  # pyright: ignore[reportUnusedFunction]
        ctx: Context[Any, Any, Any],
        agent_id: Annotated[UUID, Field(description="Identifier of the Agent to restate.")],
        reason: Annotated[
            str,
            Field(
                min_length=1,
                max_length=REASON_MAX_LENGTH,
                description="Why this restatement is being appended.",
            ),
        ],
        name: Annotated[
            str | None,
            Field(default=None, description="New display name; omit to leave unchanged."),
        ] = None,
        brain: Annotated[
            RestatedBrainRequest | None,
            Field(default=None, description="New brain; omit to leave unchanged."),
        ] = None,
    ) -> RestateAgentDefinitionOutput:
        if name is None and brain is None:
            msg = "supply a name, a brain, or both"
            raise ValueError(msg)
        handler = get_handler()
        await handler(
            RestateAgentDefinition(
                agent_id=agent_id,
                reason=reason,
                name=name,
                brain=brain_from_body(brain),
            ),
            principal_id=get_mcp_principal_id(ctx),
            correlation_id=current_correlation_id(),
            surface_id=get_mcp_surface_id(),
        )
        return RestateAgentDefinitionOutput(
            agent_id=agent_id,
            name=name,
            brain_kind=brain.kind if brain is not None else None,
        )
