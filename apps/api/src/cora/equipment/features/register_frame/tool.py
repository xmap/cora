"""MCP tool for the `register_frame` slice.

Surfaces the same handler the REST route uses, exposed as a Model
Context Protocol tool. Re-uses the route's `PlacementBody` Pydantic
mirror so the MCP wire shape and HTTP wire shape stay in lock-step.
"""

from collections.abc import Callable
from typing import Annotated, Any
from uuid import UUID

from mcp.server.fastmcp import Context, FastMCP
from pydantic import BaseModel, Field

from cora.equipment._bodies import PlacementBody
from cora.equipment.aggregates.frame import FRAME_NAME_MAX_LENGTH
from cora.equipment.features.register_frame.command import RegisterFrame
from cora.equipment.features.register_frame.handler import IdempotentHandler
from cora.infrastructure.mcp_principal import get_mcp_principal_id
from cora.infrastructure.observability import current_correlation_id
from cora.infrastructure.routing import get_mcp_surface_id


class RegisterFrameOutput(BaseModel):
    """Structured output of the `register_frame` MCP tool."""

    frame_id: UUID


def register(mcp: FastMCP, *, get_handler: Callable[[], IdempotentHandler]) -> None:
    """Register the `register_frame` tool on the given MCP server."""

    @mcp.tool(
        name="register_frame",
        description=(
            "Register a new coordinate frame with the given name, "
            "optional parent frame, and optional placement relative "
            "to that parent. For root frames pass both parent_id "
            "and placement as null; for child "
            "frames both are required and placement.parent_frame_id must "
            "equal parent_id. Placement tolerance fields must "
            "be >= 0 (negative values are rejected as InvalidPlacementError). "
            "Note: this MCP surface has no idempotency-key equivalent "
            "of the REST Idempotency-Key header; retries of a failed "
            "or lost call may create duplicate frames."
        ),
    )
    async def register_frame_tool(  # pyright: ignore[reportUnusedFunction]
        ctx: Context[Any, Any, Any],
        name: Annotated[
            str,
            Field(
                min_length=1,
                max_length=FRAME_NAME_MAX_LENGTH,
                description="Display name for the new frame.",
            ),
        ],
        parent_id: Annotated[
            UUID | None,
            Field(
                description=(
                    "Immediate parent in the frame tree. Must be null "
                    "for root frames; required for all others."
                ),
            ),
        ],
        placement: Annotated[
            PlacementBody | None,
            Field(
                description=(
                    "Pose of this frame's origin relative to its "
                    "parent. Must be null for root frames; required "
                    "for child frames."
                ),
            ),
        ],
    ) -> RegisterFrameOutput:
        handler = get_handler()
        domain_placement = placement.to_domain() if placement is not None else None
        frame_id = await handler(
            RegisterFrame(
                name=name,
                parent_id=parent_id,
                placement=domain_placement,
            ),
            principal_id=get_mcp_principal_id(ctx),
            correlation_id=current_correlation_id(),
            surface_id=get_mcp_surface_id(),
        )
        return RegisterFrameOutput(frame_id=frame_id)
