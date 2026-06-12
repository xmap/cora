"""MCP tool for the `mint_missing_asset_persistent_ids` slice.

Mirrors the REST route: sweeps Assets missing a persistent identifier and
mints one for each, returning a structured summary. Per-asset outcomes land
in the return value (not raised); the caller inspects the minted / skipped /
failed lists to decide whether to re-run.
"""

from collections.abc import Callable
from typing import Annotated, Any

from mcp.server.fastmcp import Context, FastMCP
from pydantic import Field

from cora.equipment.features.mint_missing_asset_persistent_ids.command import (
    MintMissingAssetPersistentIds,
)
from cora.equipment.features.mint_missing_asset_persistent_ids.handler import Handler
from cora.equipment.features.mint_missing_asset_persistent_ids.route import (
    MintMissingAssetPersistentIdsRequest,
    MintMissingAssetPersistentIdsResponse,
    result_to_wire,
)
from cora.infrastructure.mcp_principal import get_mcp_principal_id
from cora.infrastructure.observability import current_correlation_id
from cora.infrastructure.routing import get_mcp_surface_id


def register(mcp: FastMCP, *, get_handler: Callable[[], Handler]) -> None:
    """Register the `mint_missing_asset_persistent_ids` tool on the MCP server."""

    @mcp.tool(
        name="mint_missing_asset_persistent_ids",
        description=(
            "Bulk-mint persistent identifiers (PIDINST v1.0 Property 1) for every "
            "Asset that does not yet have one. Optionally scope to a facility and "
            "cap the batch via `limit`. Returns a summary; per-asset outcomes "
            "(minted / skipped / failed) DO NOT raise. Re-run-safe: only Assets "
            "missing an id are touched."
        ),
    )
    async def mint_missing_asset_persistent_ids_tool(  # pyright: ignore[reportUnusedFunction]
        ctx: Context[Any, Any, Any],
        body: Annotated[
            MintMissingAssetPersistentIdsRequest,
            Field(description="Mint scheme, optional facility scope, and batch limit."),
        ],
    ) -> MintMissingAssetPersistentIdsResponse:
        handler = get_handler()
        result = await handler(
            MintMissingAssetPersistentIds(
                scheme=body.scheme,
                facility_code=body.facility_code,
                limit=body.limit,
            ),
            principal_id=get_mcp_principal_id(ctx),
            correlation_id=current_correlation_id(),
            surface_id=get_mcp_surface_id(),
        )
        return result_to_wire(result)
