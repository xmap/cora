"""MCP tool for the `add_asset_alternate_identifier` slice."""

from collections.abc import Callable
from typing import Annotated, Any
from uuid import UUID

from mcp.server.fastmcp import Context, FastMCP
from pydantic import Field

from cora.equipment.aggregates.asset import (
    ALTERNATE_IDENTIFIER_VALUE_MAX_LENGTH,
    AlternateIdentifier,
    AlternateIdentifierKind,
)
from cora.equipment.features.add_asset_alternate_identifier.command import (
    AddAssetAlternateIdentifier,
)
from cora.equipment.features.add_asset_alternate_identifier.handler import Handler
from cora.infrastructure.mcp_principal import get_mcp_principal_id
from cora.infrastructure.observability import current_correlation_id
from cora.infrastructure.routing import get_mcp_surface_id


def register(mcp: FastMCP, *, get_handler: Callable[[], Handler]) -> None:
    """Register the `add_asset_alternate_identifier` tool on the given MCP server."""

    @mcp.tool(
        name="add_asset_alternate_identifier",
        description=(
            "Add an alternate identifier (PIDINST v1.0 Property 13) "
            "to an existing Asset's identifier set by exact "
            "(kind, value) pair. Strict-not-idempotent: rejects a "
            "duplicate (kind, value) pair already on the asset. "
            "Rejects when the asset is Decommissioned."
        ),
    )
    async def add_asset_alternate_identifier_tool(  # pyright: ignore[reportUnusedFunction]
        ctx: Context[Any, Any, Any],
        asset_id: Annotated[
            UUID,
            Field(description="Target asset's id."),
        ],
        kind: Annotated[
            AlternateIdentifierKind,
            Field(
                description=(
                    "Identifier kind from the PIDINST v1.0 controlled "
                    "vocabulary: 'SerialNumber', 'InventoryNumber', "
                    "or 'Other'."
                ),
            ),
        ],
        value: Annotated[
            str,
            Field(
                min_length=1,
                max_length=ALTERNATE_IDENTIFIER_VALUE_MAX_LENGTH,
                description=("Identifier value, trimmed and bounded 1-200 chars after trim."),
            ),
        ],
    ) -> None:
        handler = get_handler()
        await handler(
            AddAssetAlternateIdentifier(
                asset_id=asset_id,
                alternate_identifier=AlternateIdentifier(kind=kind, value=value),
            ),
            principal_id=get_mcp_principal_id(ctx),
            correlation_id=current_correlation_id(),
            surface_id=get_mcp_surface_id(),
        )
