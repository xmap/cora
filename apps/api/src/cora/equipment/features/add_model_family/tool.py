"""MCP tool for the `add_model_family` slice.

Mirror of `add_asset_family` MCP tool: single model_id arg plus an
extra UUID arg (family_id). Domain / application errors propagate
to FastMCP, which wraps them as `isError: true`.
"""

from collections.abc import Callable
from typing import Annotated, Any
from uuid import UUID

from mcp.server.fastmcp import Context, FastMCP
from pydantic import Field

from cora.equipment.features.add_model_family.command import AddModelFamily
from cora.equipment.features.add_model_family.handler import Handler
from cora.infrastructure.mcp_principal import get_mcp_principal_id
from cora.infrastructure.observability import current_correlation_id
from cora.infrastructure.routing import get_mcp_surface_id


def register(mcp: FastMCP, *, get_handler: Callable[[], Handler]) -> None:
    """Register the `add_model_family` tool on the given MCP server."""

    @mcp.tool(
        name="add_model_family",
        description=(
            "Add a Family to a vendor-catalog Model declared_families set. "
            "Strict-not-idempotent: re-adding a present family raises an error."
        ),
    )
    async def add_model_family_tool(  # pyright: ignore[reportUnusedFunction]
        ctx: Context[Any, Any, Any],
        model_id: Annotated[
            UUID,
            Field(description="Target Model's id."),
        ],
        family_id: Annotated[
            UUID,
            Field(
                description=("Family id to add. Cross-BC existence is verified at the handler."),
            ),
        ],
    ) -> None:
        handler = get_handler()
        await handler(
            AddModelFamily(model_id=model_id, family_id=family_id),
            principal_id=get_mcp_principal_id(ctx),
            correlation_id=current_correlation_id(),
            surface_id=get_mcp_surface_id(),
        )
