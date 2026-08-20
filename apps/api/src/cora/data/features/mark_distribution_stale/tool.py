"""MCP tool for the `mark_distribution_stale` slice."""

from collections.abc import Callable
from typing import Annotated, Any
from uuid import UUID

from mcp.server.fastmcp import Context, FastMCP
from pydantic import Field

from cora.data.features.mark_distribution_stale.command import MarkDistributionStale
from cora.data.features.mark_distribution_stale.handler import Handler
from cora.infrastructure.mcp_principal import get_mcp_principal_id
from cora.infrastructure.observability import current_correlation_id
from cora.infrastructure.routing import get_mcp_surface_id
from cora.shared.text_bounds import REASON_MAX_LENGTH


def register(mcp: FastMCP, *, get_handler: Callable[[], Handler]) -> None:
    """Register the `mark_distribution_stale` tool on the given MCP server."""

    @mcp.tool(
        name="mark_distribution_stale",
        description=(
            "Mark one storage-tier copy of a Dataset Stale, recording that its "
            "bytes are known to be gone or no longer trusted (a storage array "
            "failure, a bit-rot finding, or any other grounds an operator has). "
            "Unlike discard_distribution, this records a fact about the world "
            "that already happened, not a deliberate act CORA can refuse: there "
            "is no redundancy guard and no parent-Dataset guard, and marking an "
            "already-Stale copy stale again succeeds. The only refusal is a "
            "Discarded copy (terminal). Reason is free-form (1-500 chars), "
            "captured verbatim for audit."
        ),
    )
    async def mark_distribution_stale_tool(  # pyright: ignore[reportUnusedFunction]
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
                description="Free-form reason the bytes are no longer trusted (1-500 chars).",
            ),
        ],
    ) -> None:
        handler = get_handler()
        await handler(
            MarkDistributionStale(distribution_id=distribution_id, reason=reason),
            principal_id=get_mcp_principal_id(ctx),
            correlation_id=current_correlation_id(),
            surface_id=get_mcp_surface_id(),
        )
