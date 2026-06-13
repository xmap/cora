"""MCP tool for the `restore_asset` slice.

Mirror of `degrade_asset` MCP tool with target Nominal.
"""

from collections.abc import Callable
from typing import Annotated, Any
from uuid import UUID

from mcp.server.fastmcp import Context, FastMCP
from pydantic import Field

from cora.equipment.features.restore_asset.command import RestoreAsset
from cora.equipment.features.restore_asset.handler import Handler
from cora.infrastructure.mcp_principal import get_mcp_principal_id
from cora.infrastructure.observability import current_correlation_id
from cora.infrastructure.routing import get_mcp_surface_id
from cora.shared.text_bounds import REASON_MAX_LENGTH


def register(mcp: FastMCP, *, get_handler: Callable[[], Handler]) -> None:
    """Register the `restore_asset` tool on the given MCP server."""

    @mcp.tool(
        name="restore_asset",
        description=(
            "Mark an existing asset as Nominal (fully repaired). "
            "Target-state semantics: moves to Nominal from any source "
            "condition. Lifecycle is independent and unaffected. No-op "
            "when the asset is already Nominal. For partial repairs "
            "(Faulted -> Degraded), use degrade_asset, not this tool."
        ),
    )
    async def restore_asset_tool(  # pyright: ignore[reportUnusedFunction]
        ctx: Context[Any, Any, Any],
        asset_id: Annotated[
            UUID,
            Field(description="Target asset's id."),
        ],
        reason: Annotated[
            str,
            Field(
                min_length=1,
                max_length=REASON_MAX_LENGTH,
                description=(
                    "Operator-supplied reason for the restore transition (audit-log breadcrumb)."
                ),
            ),
        ],
    ) -> None:
        handler = get_handler()
        await handler(
            RestoreAsset(asset_id=asset_id, reason=reason),
            principal_id=get_mcp_principal_id(ctx),
            correlation_id=current_correlation_id(),
            surface_id=get_mcp_surface_id(),
        )
