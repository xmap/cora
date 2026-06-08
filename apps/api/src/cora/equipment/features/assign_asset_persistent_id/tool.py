"""MCP tool for the `assign_asset_persistent_id` slice."""

from collections.abc import Callable
from typing import Annotated, Any
from uuid import UUID

from mcp.server.fastmcp import Context, FastMCP
from pydantic import Field

from cora.equipment.features.assign_asset_persistent_id.command import AssignAssetPersistentId
from cora.equipment.features.assign_asset_persistent_id.handler import Handler
from cora.infrastructure.mcp_principal import get_mcp_principal_id
from cora.infrastructure.observability import current_correlation_id
from cora.infrastructure.routing import get_mcp_surface_id
from cora.shared.identifier import PersistentIdentifierScheme


def register(mcp: FastMCP, *, get_handler: Callable[[], Handler]) -> None:
    """Register the `assign_asset_persistent_id` tool on the given MCP server."""

    @mcp.tool(
        name="assign_asset_persistent_id",
        description=(
            "Assign a persistent identifier (PIDINST v1.0 Property 1, "
            "DOI or Handle) to an existing Asset. Set-once: rejects "
            "when the Asset already carries a persistent_id. Rejects "
            "when the Asset is Decommissioned. Calls DataCite (or the "
            "configured DoiMinter adapter) to mint the identifier "
            "server-side; returns the assigned (scheme, value) pair."
        ),
    )
    async def assign_asset_persistent_id_tool(  # pyright: ignore[reportUnusedFunction]
        ctx: Context[Any, Any, Any],
        asset_id: Annotated[
            UUID,
            Field(description="Target asset's id."),
        ],
        scheme: Annotated[
            PersistentIdentifierScheme,
            Field(description="Closed PIDINST Property 1 scheme: DOI or HANDLE."),
        ],
        suffix: Annotated[
            str | None,
            Field(description="Optional operator-supplied local part."),
        ] = None,
    ) -> dict[str, str]:
        handler = get_handler()
        persistent_id = await handler(
            AssignAssetPersistentId(asset_id=asset_id, scheme=scheme, suffix=suffix),
            principal_id=get_mcp_principal_id(ctx),
            correlation_id=current_correlation_id(),
            surface_id=get_mcp_surface_id(),
        )
        return {"scheme": persistent_id.scheme.value, "value": persistent_id.value}
