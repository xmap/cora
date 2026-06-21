"""MCP tool for the `publish_edition` slice."""

from collections.abc import Callable
from typing import Annotated, Any
from uuid import UUID

from mcp.server.fastmcp import Context, FastMCP
from pydantic import BaseModel, Field

from cora.data.features.publish_edition.command import PublishEdition
from cora.data.features.publish_edition.handler import Handler
from cora.infrastructure.mcp_principal import get_mcp_principal_id
from cora.infrastructure.observability import current_correlation_id
from cora.infrastructure.routing import get_mcp_surface_id


class PublishEditionOutput(BaseModel):
    """Structured output of the `publish_edition` MCP tool."""

    edition_id: UUID = Field(description="Identifier of the published Edition.")


def register(mcp: FastMCP, *, get_handler: Callable[[], Handler]) -> None:
    """Register the `publish_edition` tool on the given MCP server."""

    @mcp.tool(
        name="publish_edition",
        description=(
            "Publish a Sealed Edition: mint a persistent identifier (DOI) "
            "via the PersistentIdentifierMinter port, re-serialize the artifact with the "
            "minted PID baked in, and transition to Published."
        ),
    )
    async def publish_edition_tool(  # pyright: ignore[reportUnusedFunction]
        ctx: Context[Any, Any, Any],
        edition_id: Annotated[UUID, Field(description="The Edition to publish.")],
    ) -> PublishEditionOutput:
        handler = get_handler()
        await handler(
            PublishEdition(edition_id=edition_id),
            principal_id=get_mcp_principal_id(ctx),
            correlation_id=current_correlation_id(),
            surface_id=get_mcp_surface_id(),
        )
        return PublishEditionOutput(edition_id=edition_id)
