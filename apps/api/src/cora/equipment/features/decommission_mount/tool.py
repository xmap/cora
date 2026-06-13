"""MCP tool for the `decommission_mount` slice."""

from collections.abc import Callable
from typing import Annotated, Any
from uuid import UUID

from mcp.server.fastmcp import Context, FastMCP
from pydantic import Field

from cora.equipment.features.decommission_mount.command import DecommissionMount
from cora.equipment.features.decommission_mount.handler import Handler
from cora.infrastructure.mcp_principal import get_mcp_principal_id
from cora.infrastructure.observability import current_correlation_id
from cora.infrastructure.routing import get_mcp_surface_id
from cora.shared.text_bounds import REASON_MAX_LENGTH


def register(mcp: FastMCP, *, get_handler: Callable[[], Handler]) -> None:
    @mcp.tool(
        name="decommission_mount",
        description=(
            "Retire a mount (slot) from the beamline. Terminal lifecycle "
            "transition; cannot be undone. Rejected if the slot still has "
            "an installed Asset (uninstall first) OR if it has active "
            "child Mounts (decommission children first)."
        ),
    )
    async def decommission_mount_tool(  # pyright: ignore[reportUnusedFunction]
        ctx: Context[Any, Any, Any],
        mount_id: Annotated[UUID, Field(description="The Mount to decommission.")],
        reason: Annotated[
            str,
            Field(
                min_length=1,
                max_length=REASON_MAX_LENGTH,
                description="Operator-supplied free-text reason for the audit log.",
            ),
        ],
    ) -> None:
        handler = get_handler()
        await handler(
            DecommissionMount(mount_id=mount_id, reason=reason),
            principal_id=get_mcp_principal_id(ctx),
            correlation_id=current_correlation_id(),
            surface_id=get_mcp_surface_id(),
        )
