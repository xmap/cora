"""MCP tool for the `remove_model_family` slice.

Mirror of `add_model_family` MCP tool: single model_id arg plus an
extra UUID arg (family_id). Domain / application errors propagate
to FastMCP, which wraps them as `isError: true`.
"""

from collections.abc import Callable
from typing import Annotated, Any
from uuid import UUID

from mcp.server.fastmcp import Context, FastMCP
from pydantic import Field

from cora.equipment.features.remove_model_family.command import RemoveModelFamily
from cora.equipment.features.remove_model_family.handler import Handler
from cora.infrastructure.mcp_principal import get_mcp_principal_id
from cora.infrastructure.observability import current_correlation_id
from cora.infrastructure.routing import get_mcp_surface_id


def register(mcp: FastMCP, *, get_handler: Callable[[], Handler]) -> None:
    """Register the `remove_model_family` tool on the given MCP server."""

    @mcp.tool(
        name="remove_model_family",
        description=(
            "Remove a Family from a vendor-catalog Model declared_families set. "
            "Strict-not-idempotent: removing an absent family raises an error. "
            "Does not cascade through existing Assets bound to the Model."
        ),
    )
    async def remove_model_family_tool(  # pyright: ignore[reportUnusedFunction]
        ctx: Context[Any, Any, Any],
        model_id: Annotated[
            UUID,
            Field(description="Target Model's id."),
        ],
        family_id: Annotated[
            UUID,
            Field(description="Family id to remove from the Model.declared_families set."),
        ],
    ) -> None:
        handler = get_handler()
        await handler(
            RemoveModelFamily(model_id=model_id, family_id=family_id),
            principal_id=get_mcp_principal_id(ctx),
            correlation_id=current_correlation_id(),
            surface_id=get_mcp_surface_id(),
        )
