"""MCP tool for the `dismount_subject` slice."""

from collections.abc import Callable
from typing import Annotated, Any
from uuid import UUID

from mcp.server.fastmcp import Context, FastMCP
from pydantic import Field

from cora.infrastructure.mcp_principal import get_mcp_principal_id
from cora.infrastructure.observability import current_correlation_id
from cora.infrastructure.routing import get_mcp_surface_id
from cora.shared.text_bounds import REASON_MAX_LENGTH
from cora.subject.features.dismount_subject.command import DismountSubject
from cora.subject.features.dismount_subject.handler import Handler


def register(mcp: FastMCP, *, get_handler: Callable[[], Handler]) -> None:
    """Register the `dismount_subject` tool on the given MCP server."""

    @mcp.tool(
        name="dismount_subject",
        description=(
            "Dismount a Subject from its current sample-environment "
            "Asset. Subject must be in `Mounted` or `Measured` "
            "state. Returns Subject to `Received` so it can be "
            "re-mounted (multi-stage workflow). Distinct from "
            "remove_subject which is terminal-leading."
        ),
    )
    async def dismount_subject_tool(  # pyright: ignore[reportUnusedFunction]
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
                description="Operator-supplied reason for the dismount (audit-log breadcrumb).",
            ),
        ],
    ) -> None:
        handler = get_handler()
        await handler(
            DismountSubject(subject_id=subject_id, reason=reason),
            principal_id=get_mcp_principal_id(ctx),
            correlation_id=current_correlation_id(),
            surface_id=get_mcp_surface_id(),
        )
