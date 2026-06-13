"""MCP tool for the `decommission_frame` slice."""

from collections.abc import Callable
from typing import Annotated, Any
from uuid import UUID

from mcp.server.fastmcp import Context, FastMCP
from pydantic import Field

from cora.equipment.features.decommission_frame.command import DecommissionFrame
from cora.equipment.features.decommission_frame.handler import Handler
from cora.infrastructure.mcp_principal import get_mcp_principal_id
from cora.infrastructure.observability import current_correlation_id
from cora.infrastructure.routing import get_mcp_surface_id
from cora.shared.text_bounds import REASON_MAX_LENGTH


def register(mcp: FastMCP, *, get_handler: Callable[[], Handler]) -> None:
    """Register the `decommission_frame` tool on the given MCP server."""

    @mcp.tool(
        name="decommission_frame",
        description=(
            "Retire a frame from the coordinate hierarchy. "
            "Terminal lifecycle transition; cannot be undone. "
            "Rejected if any active Mount or child Frame still "
            "references this frame (FrameInUseError)."
        ),
    )
    async def decommission_frame_tool(  # pyright: ignore[reportUnusedFunction]
        ctx: Context[Any, Any, Any],
        frame_id: Annotated[
            UUID,
            Field(description="The Frame to decommission."),
        ],
        reason: Annotated[
            str,
            Field(
                min_length=1,
                max_length=REASON_MAX_LENGTH,
                description=(
                    "Operator-supplied free-text reason captured on "
                    "the FrameDecommissioned event payload for audit."
                ),
            ),
        ],
    ) -> None:
        handler = get_handler()
        await handler(
            DecommissionFrame(frame_id=frame_id, reason=reason),
            principal_id=get_mcp_principal_id(ctx),
            correlation_id=current_correlation_id(),
            surface_id=get_mcp_surface_id(),
        )
