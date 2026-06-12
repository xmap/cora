"""MCP tool for the `register_mount` slice."""

from collections.abc import Callable
from typing import Annotated, Any
from uuid import UUID

from mcp.server.fastmcp import Context, FastMCP
from pydantic import BaseModel, Field

from cora.equipment._bodies import DrawingBody, PlacementBody
from cora.equipment.aggregates.mount import SLOT_CODE_MAX_LENGTH
from cora.equipment.features.register_mount.command import RegisterMount
from cora.equipment.features.register_mount.handler import IdempotentHandler
from cora.infrastructure.mcp_principal import get_mcp_principal_id
from cora.infrastructure.observability import current_correlation_id
from cora.infrastructure.routing import get_mcp_surface_id


class RegisterMountOutput(BaseModel):
    mount_id: UUID


def register(mcp: FastMCP, *, get_handler: Callable[[], IdempotentHandler]) -> None:
    @mcp.tool(
        name="register_mount",
        description=(
            "Register a new mount (named slot) in the beamline. slot_code "
            "is the external alias (e.g., '02-BM-A-K-01'); placement "
            "describes the slot's position relative to a Frame; drawing "
            "is optional engineering documentation for the slot itself. "
            "Placement tolerance fields must be >= 0. Note: this MCP "
            "surface has no idempotency-key equivalent of the REST "
            "Idempotency-Key header; retries of a failed or lost call "
            "may create duplicate mounts."
        ),
    )
    async def register_mount_tool(  # pyright: ignore[reportUnusedFunction]
        ctx: Context[Any, Any, Any],
        slot_code: Annotated[
            str,
            Field(
                min_length=1,
                max_length=SLOT_CODE_MAX_LENGTH,
                description="External alias (e.g., '02-BM-A-K-01').",
            ),
        ],
        parent_id: Annotated[
            UUID | None,
            Field(description="Parent slot in the hierarchy; null for top-level."),
        ],
        placement: Annotated[
            PlacementBody,
            Field(description="Slot pose relative to a Frame."),
        ],
        drawing: Annotated[
            DrawingBody | None,
            Field(description="Optional engineering drawing reference for the slot."),
        ] = None,
    ) -> RegisterMountOutput:
        handler = get_handler()
        mount_id = await handler(
            RegisterMount(
                slot_code=slot_code,
                parent_id=parent_id,
                placement=placement.to_domain(),
                drawing=drawing.to_domain() if drawing is not None else None,
            ),
            principal_id=get_mcp_principal_id(ctx),
            correlation_id=current_correlation_id(),
            surface_id=get_mcp_surface_id(),
        )
        return RegisterMountOutput(mount_id=mount_id)
