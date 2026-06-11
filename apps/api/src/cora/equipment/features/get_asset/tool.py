"""MCP tool for the `get_asset` query slice.

Surfaces the same handler the REST route uses. Returns a structured
AssetOutput on hit. On miss raises an exception that FastMCP wraps
as `isError: true` with a text diagnostic — matches the REST 404
behaviour in MCP's error idiom (LLM consumers get a clear "asset
not found" message rather than null structuredContent they have to
interpret).
"""

from collections.abc import Callable
from typing import Annotated, Any
from uuid import UUID

from mcp.server.fastmcp import Context, FastMCP
from pydantic import BaseModel, Field

from cora.equipment.aggregates.asset import ASSET_NAME_MAX_LENGTH
from cora.equipment.features.get_asset.handler import Handler
from cora.equipment.features.get_asset.query import GetAsset
from cora.infrastructure.mcp_principal import get_mcp_principal_id
from cora.infrastructure.observability import current_correlation_id
from cora.infrastructure.routing import get_mcp_surface_id


class AssetPortOutput(BaseModel):
    """Structured output for a single Asset port (5h)."""

    name: str
    direction: str
    signal_type: str


class AssetOutput(BaseModel):
    """Structured output of the `get_asset` MCP tool."""

    id: UUID
    name: str = Field(..., max_length=ASSET_NAME_MAX_LENGTH)
    tier: str
    parent_id: UUID | None
    lifecycle: str
    condition: str
    family_ids: list[UUID]
    settings: dict[str, Any]
    ports: list[AssetPortOutput]


def register(mcp: FastMCP, *, get_handler: Callable[[], Handler]) -> None:
    """Register the `get_asset` tool on the given MCP server."""

    @mcp.tool(
        name="get_asset",
        description="Read the current state of an existing asset by id.",
    )
    async def get_asset_tool(  # pyright: ignore[reportUnusedFunction]
        ctx: Context[Any, Any, Any],
        asset_id: Annotated[
            UUID,
            Field(description="Target asset's id."),
        ],
    ) -> AssetOutput:
        handler = get_handler()
        asset = await handler(
            GetAsset(asset_id=asset_id),
            principal_id=get_mcp_principal_id(ctx),
            correlation_id=current_correlation_id(),
            surface_id=get_mcp_surface_id(),
        )
        if asset is None:
            msg = f"Asset {asset_id} not found"
            raise ValueError(msg)
        return AssetOutput(
            id=asset.id,
            name=asset.name.value,
            tier=asset.tier.value,
            parent_id=asset.parent_id,
            lifecycle=asset.lifecycle.value,
            condition=asset.condition.value,
            family_ids=sorted(asset.family_ids, key=str),
            settings=asset.settings,
            ports=[
                AssetPortOutput(
                    name=p.name,
                    direction=p.direction.value,
                    signal_type=p.signal_type,
                )
                for p in sorted(asset.ports, key=lambda port: port.name)
            ],
        )
