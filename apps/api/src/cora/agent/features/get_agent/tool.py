"""MCP tool for the `get_agent` query slice.

Surfaces the same handler the REST route uses. On miss raises
ValueError so FastMCP wraps the response as `isError: true`.

`defined_at` / `versioned_at` / `deprecated_at` mirror the REST
`AgentResponse` (Path C): sourced from
the `proj_agent_summary` projection. Null semantics: read
together with `status` — a populated `status` with a null timestamp
means the projection has not yet folded that lifecycle event,
never a missing transition. A not-found Agent raises (MCP
`isError: true`) rather than returning null timestamps.
"""

from collections.abc import Callable
from datetime import datetime
from typing import Annotated, Any
from uuid import UUID

from mcp.server.fastmcp import Context, FastMCP
from pydantic import BaseModel, Field

from cora.agent.aggregates.agent import AgentStatus
from cora.agent.features.get_agent.handler import Handler
from cora.agent.features.get_agent.query import GetAgent
from cora.infrastructure.mcp_principal import get_mcp_principal_id
from cora.infrastructure.observability import current_correlation_id
from cora.infrastructure.routing import get_mcp_surface_id
from cora.shared.deprecation import DeprecationReason


class ModelRefOutput(BaseModel):
    """Sub-output for the typed ModelRef VO."""

    provider: str
    model: str
    snapshot_pin: str | None = None


class AgentOutput(BaseModel):
    """Structured output of the `get_agent` MCP tool (on hit).

    `defined_at` is nullable (changed from required during lifecycle
    widening): the projection can lag right after a fresh
    `define_agent`. Once the projection has folded `AgentDefined`,
    `defined_at` is non-null on every response.
    """

    id: UUID
    kind: str
    name: str
    version: str
    model_ref: ModelRefOutput
    status: AgentStatus
    defined_at: datetime | None = None
    description: str | None = None
    canonical_uri: str | None = None
    prompt_template_id: UUID | None = None
    capabilities: list[str]
    versioned_at: datetime | None = None
    deprecated_at: datetime | None = None
    deprecation_reason: DeprecationReason | None = None


def register(mcp: FastMCP, *, get_handler: Callable[[], Handler]) -> None:
    """Register the `get_agent` tool on the given MCP server."""

    @mcp.tool(
        name="get_agent",
        description=(
            "Look up an Agent by id. Returns kind, name, version, model_ref, "
            "optional description / canonical_uri / prompt_template_id / "
            "capabilities, and current FSM status (Defined / Versioned / "
            "Deprecated) plus per-transition timestamps."
        ),
    )
    async def get_agent_tool(  # pyright: ignore[reportUnusedFunction]
        ctx: Context[Any, Any, Any],
        agent_id: Annotated[
            UUID,
            Field(description="Identifier of the Agent to fetch."),
        ],
    ) -> AgentOutput:
        handler = get_handler()
        view = await handler(
            GetAgent(agent_id=agent_id),
            principal_id=get_mcp_principal_id(ctx),
            correlation_id=current_correlation_id(),
            surface_id=get_mcp_surface_id(),
        )
        if view is None:
            msg = f"Agent {agent_id} not found"
            raise ValueError(msg)
        agent = view.agent
        timestamps = view.timestamps
        return AgentOutput(
            id=agent.id,
            kind=agent.kind.value,
            name=agent.name.value,
            version=agent.version.value,
            model_ref=ModelRefOutput(
                provider=agent.model_ref.provider,
                model=agent.model_ref.model,
                snapshot_pin=agent.model_ref.snapshot_pin,
            ),
            status=agent.status,
            defined_at=timestamps.created_at if timestamps is not None else None,
            description=agent.description.value if agent.description is not None else None,
            canonical_uri=agent.canonical_uri.value if agent.canonical_uri is not None else None,
            prompt_template_id=agent.prompt_template_id,
            capabilities=sorted(c.value for c in agent.capabilities),
            versioned_at=timestamps.versioned_at if timestamps is not None else None,
            deprecated_at=timestamps.deprecated_at if timestamps is not None else None,
            deprecation_reason=agent.deprecation_reason,
        )
