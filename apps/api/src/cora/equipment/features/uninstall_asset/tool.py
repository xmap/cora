"""MCP tool for the `uninstall_asset` slice."""

from collections.abc import Callable
from typing import Annotated, Any
from uuid import UUID

from mcp.server.fastmcp import Context, FastMCP
from pydantic import Field

from cora.equipment.features.uninstall_asset.command import UninstallAsset
from cora.equipment.features.uninstall_asset.handler import Handler
from cora.infrastructure.mcp_principal import get_mcp_principal_id
from cora.infrastructure.observability import current_correlation_id
from cora.infrastructure.routing import get_mcp_surface_id
from cora.shared.text_bounds import REASON_MAX_LENGTH


def register(mcp: FastMCP, *, get_handler: Callable[[], Handler]) -> None:
    @mcp.tool(
        name="uninstall_asset",
        description=(
            "Uninstall whatever Asset is currently in a Mount's slot. "
            "The command takes the mount_id only (the slot knows what's "
            "there). Rejected if the Mount is Decommissioned OR if the "
            "slot is vacant (MountIsEmptyError)."
        ),
    )
    async def uninstall_asset_tool(  # pyright: ignore[reportUnusedFunction]
        ctx: Context[Any, Any, Any],
        mount_id: Annotated[UUID, Field(description="The Mount slot to vacate.")],
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
            UninstallAsset(mount_id=mount_id, reason=reason),
            principal_id=get_mcp_principal_id(ctx),
            correlation_id=current_correlation_id(),
            surface_id=get_mcp_surface_id(),
        )
