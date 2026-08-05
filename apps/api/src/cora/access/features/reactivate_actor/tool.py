"""MCP tool for the `reactivate_actor` slice.

Surfaces the same handler the REST route uses. Tool registration happens
at app construction; the handler is fetched at tool-call time via
`get_handler` so it sees the lifespan-wired bundle.
"""

from collections.abc import Callable
from typing import Annotated, Any
from uuid import UUID

from mcp.server.fastmcp import Context, FastMCP
from pydantic import Field

from cora.access.features.reactivate_actor.command import ReactivateActor
from cora.access.features.reactivate_actor.handler import Handler
from cora.infrastructure.mcp_principal import get_mcp_principal_id
from cora.infrastructure.observability import current_correlation_id
from cora.infrastructure.routing import get_mcp_surface_id


def register(mcp: FastMCP, *, get_handler: Callable[[], Handler]) -> None:
    """Register the `reactivate_actor` tool on the given MCP server.

    Domain / application errors raised by the handler propagate to
    FastMCP, which wraps them as structured `isError: true` responses.
    """

    @mcp.tool(
        name="reactivate_actor",
        description="Return a deactivated actor to service by id.",
    )
    async def reactivate_actor_tool(  # pyright: ignore[reportUnusedFunction]
        ctx: Context[Any, Any, Any],
        actor_id: Annotated[
            UUID,
            Field(description="Target actor's id."),
        ],
    ) -> None:
        handler = get_handler()
        await handler(
            ReactivateActor(actor_id=actor_id),
            principal_id=get_mcp_principal_id(ctx),
            correlation_id=current_correlation_id(),
            surface_id=get_mcp_surface_id(),
        )
