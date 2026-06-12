"""MCP tool for the `update_frame_placement` slice.

Surfaces the same handler the REST route uses, exposed as a Model
Context Protocol tool.
"""

from collections.abc import Callable
from typing import Annotated, Any
from uuid import UUID

from mcp.server.fastmcp import Context, FastMCP
from pydantic import Field

from cora.equipment._bodies import PlacementBody
from cora.equipment.features.update_frame_placement.command import UpdateFramePlacement
from cora.equipment.features.update_frame_placement.handler import Handler
from cora.infrastructure.mcp_principal import get_mcp_principal_id
from cora.infrastructure.observability import current_correlation_id
from cora.infrastructure.routing import get_mcp_surface_id


def register(mcp: FastMCP, *, get_handler: Callable[[], Handler]) -> None:
    """Register the `update_frame_placement` tool on the given MCP server."""

    @mcp.tool(
        name="update_frame_placement",
        description=(
            "Update a frame's placement. "
            "new_placement.parent_frame_id MUST equal the Frame's "
            "existing parent_id (update_frame_placement cannot reparent). "
            "Placement tolerance fields must be >= 0 (negative values "
            "are rejected as InvalidPlacementError). Idempotent: "
            "submitting an UpdateFramePlacement with the current placement is "
            "a no-op (no event emitted)."
        ),
    )
    async def update_frame_placement_tool(  # pyright: ignore[reportUnusedFunction]
        ctx: Context[Any, Any, Any],
        frame_id: Annotated[
            UUID,
            Field(description="The Frame to update."),
        ],
        new_placement: Annotated[
            PlacementBody,
            Field(description="The new placement."),
        ],
        survey: Annotated[
            dict[str, Any] | None,
            Field(
                description=(
                    "Optional re-survey provenance carried verbatim "
                    "onto the FramePlacementUpdated event payload."
                ),
            ),
        ] = None,
    ) -> None:
        handler = get_handler()
        await handler(
            UpdateFramePlacement(
                frame_id=frame_id,
                new_placement=new_placement.to_domain(),
                survey=survey,
            ),
            principal_id=get_mcp_principal_id(ctx),
            correlation_id=current_correlation_id(),
            surface_id=get_mcp_surface_id(),
        )
