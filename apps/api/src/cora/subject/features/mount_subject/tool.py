"""MCP tool for the `mount_subject` slice.

Surfaces the same handler the REST route uses. Subject_id + asset_id
arguments, no structured content (None on success). Domain /
application errors raised by the handler propagate to FastMCP, which
wraps them as `isError: true` responses.
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
from cora.subject.features.mount_subject.command import MountSubject
from cora.subject.features.mount_subject.handler import Handler


def register(mcp: FastMCP, *, get_handler: Callable[[], Handler]) -> None:
    """Register the `mount_subject` tool on the given MCP server."""

    @mcp.tool(
        name="mount_subject",
        description=(
            "Mount an existing subject onto a sample-environment Asset. "
            "Subject must be in `Received` state; Asset must be `Active`."
        ),
    )
    async def mount_subject_tool(  # pyright: ignore[reportUnusedFunction]
        ctx: Context[Any, Any, Any],
        subject_id: Annotated[
            UUID,
            Field(description="Target subject's id."),
        ],
        asset_id: Annotated[
            UUID,
            Field(description="Sample-environment Asset id (must be Active)."),
        ],
        reason: Annotated[
            str,
            Field(
                min_length=1,
                max_length=REASON_MAX_LENGTH,
                description="Operator-supplied reason for the mount (audit-log breadcrumb).",
            ),
        ],
    ) -> None:
        handler = get_handler()
        await handler(
            MountSubject(subject_id=subject_id, asset_id=asset_id, reason=reason),
            principal_id=get_mcp_principal_id(ctx),
            correlation_id=current_correlation_id(),
            surface_id=get_mcp_surface_id(),
        )
