"""MCP tool for the `update_mount_placement` slice."""

from collections.abc import Callable
from typing import Annotated, Any
from uuid import UUID

from mcp.server.fastmcp import Context, FastMCP
from pydantic import Field

from cora.equipment._bodies import PlacementBody
from cora.equipment.features.update_mount_placement.command import UpdateMountPlacement
from cora.equipment.features.update_mount_placement.handler import Handler
from cora.infrastructure.mcp_principal import get_mcp_principal_id
from cora.infrastructure.observability import current_correlation_id
from cora.infrastructure.routing import get_mcp_surface_id


def register(mcp: FastMCP, *, get_handler: Callable[[], Handler]) -> None:
    @mcp.tool(
        name="update_mount_placement",
        description=(
            "Update a mount's placement relative to its parent Frame. "
            "new_placement.parent_frame_id MUST equal the existing "
            "parent_frame_id (update_mount_placement cannot reparent). "
            "Placement tolerance fields must be >= 0. Idempotent: "
            "submitting an UpdateMountPlacement with the current placement "
            "is a no-op (no event emitted)."
        ),
    )
    async def update_mount_placement_tool(  # pyright: ignore[reportUnusedFunction]
        ctx: Context[Any, Any, Any],
        mount_id: Annotated[UUID, Field(description="The Mount to update.")],
        new_placement: Annotated[PlacementBody, Field(description="The new placement.")],
        survey: Annotated[
            dict[str, Any] | None,
            Field(description="Optional re-survey provenance."),
        ] = None,
    ) -> None:
        handler = get_handler()
        await handler(
            UpdateMountPlacement(
                mount_id=mount_id,
                new_placement=new_placement.to_domain(),
                survey=survey,
            ),
            principal_id=get_mcp_principal_id(ctx),
            correlation_id=current_correlation_id(),
            surface_id=get_mcp_surface_id(),
        )
