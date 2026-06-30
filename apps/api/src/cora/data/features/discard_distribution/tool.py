"""MCP tool for the `discard_distribution` slice."""

from collections.abc import Callable
from typing import Annotated, Any
from uuid import UUID

from mcp.server.fastmcp import Context, FastMCP
from pydantic import Field

from cora.data.features.discard_distribution.command import DiscardDistribution
from cora.data.features.discard_distribution.handler import Handler
from cora.infrastructure.mcp_principal import get_mcp_principal_id
from cora.infrastructure.observability import current_correlation_id
from cora.infrastructure.routing import get_mcp_surface_id
from cora.shared.text_bounds import REASON_MAX_LENGTH


def register(mcp: FastMCP, *, get_handler: Callable[[], Handler]) -> None:
    """Register the `discard_distribution` tool on the given MCP server."""

    @mcp.tool(
        name="discard_distribution",
        description=(
            "Discard one storage-tier copy of a Dataset (mark a Distribution "
            "Discarded). Use when the bytes for this copy are being reclaimed "
            "and the metadata record should reflect that. Allowed only when a "
            "sibling copy of the same Dataset is Verified on a different storage "
            "tier and the parent Dataset is not Discarded. Metadata-only: the "
            "Data BC does NOT delete the bytes; that is an out-of-band operator "
            "workflow. Re-discarding raises. Reason is free-form (1-500 chars), "
            "captured verbatim for audit."
        ),
    )
    async def discard_distribution_tool(  # pyright: ignore[reportUnusedFunction]
        ctx: Context[Any, Any, Any],
        distribution_id: Annotated[
            UUID,
            Field(description="Target distribution's id."),
        ],
        reason: Annotated[
            str,
            Field(
                min_length=1,
                max_length=REASON_MAX_LENGTH,
                description="Free-form reason for the discard (1-500 chars after trimming).",
            ),
        ],
    ) -> None:
        handler = get_handler()
        await handler(
            DiscardDistribution(distribution_id=distribution_id, reason=reason),
            principal_id=get_mcp_principal_id(ctx),
            correlation_id=current_correlation_id(),
            surface_id=get_mcp_surface_id(),
        )
