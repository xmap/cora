"""MCP tool for the `discard_subject` slice.

Mirror of the other terminal disposition MCP tools (return / store).
Subject_id + reason arguments, no structured content on success.
Domain / application errors propagate to FastMCP, which wraps them
as `isError: true`.
"""

from collections.abc import Callable
from typing import Annotated, Any
from uuid import UUID

from mcp.server.fastmcp import Context, FastMCP
from pydantic import Field

from cora.infrastructure.mcp_principal import get_mcp_principal_id
from cora.infrastructure.observability import current_correlation_id
from cora.infrastructure.routing import get_mcp_surface_id
from cora.shared.text_bounds import REASON_MAX_LENGTH
from cora.subject.features.discard_subject.command import DiscardSubject
from cora.subject.features.discard_subject.handler import Handler


def register(mcp: FastMCP, *, get_handler: Callable[[], Handler]) -> None:
    """Register the `discard_subject` tool on the given MCP server."""

    @mcp.tool(
        name="discard_subject",
        description=(
            "Destroy / discard an existing (Removed) subject. Re-discarding "
            "raises. Reason is free-form (1-500 chars), captured verbatim for "
            "GDPR + sample-handling audit."
        ),
    )
    async def discard_subject_tool(  # pyright: ignore[reportUnusedFunction]
        ctx: Context[Any, Any, Any],
        subject_id: Annotated[
            UUID,
            Field(description="Target subject's id."),
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
            DiscardSubject(subject_id=subject_id, reason=reason),
            principal_id=get_mcp_principal_id(ctx),
            correlation_id=current_correlation_id(),
            surface_id=get_mcp_surface_id(),
        )
