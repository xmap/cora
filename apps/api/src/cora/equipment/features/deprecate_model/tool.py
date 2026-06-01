"""MCP tool for the `deprecate_model` slice."""

from collections.abc import Callable
from typing import Annotated, Any
from uuid import UUID

from mcp.server.fastmcp import Context, FastMCP
from pydantic import Field

from cora.equipment.aggregates.model import MODEL_DEPRECATION_REASON_MAX_LENGTH
from cora.equipment.features.deprecate_model.command import DeprecateModel
from cora.equipment.features.deprecate_model.handler import Handler
from cora.infrastructure.mcp_principal import get_mcp_principal_id
from cora.infrastructure.observability import current_correlation_id
from cora.infrastructure.routing import get_mcp_surface_id


def register(mcp: FastMCP, *, get_handler: Callable[[], Handler]) -> None:
    """Register the `deprecate_model` tool on the given MCP server."""

    @mcp.tool(
        name="deprecate_model",
        description=(
            "Deprecate a vendor-catalog Model with a reason. Existing "
            "Assets bound to this Model continue to function; "
            "deprecation is an authoring signal."
        ),
    )
    async def deprecate_model_tool(  # pyright: ignore[reportUnusedFunction]
        ctx: Context[Any, Any, Any],
        model_id: Annotated[
            UUID,
            Field(description="Target Model's id."),
        ],
        reason: Annotated[
            str,
            Field(
                min_length=1,
                max_length=MODEL_DEPRECATION_REASON_MAX_LENGTH,
                description=(
                    "Operator-supplied rationale for retiring this Model "
                    "(for example 'superseded by RV120CCHL', 'vendor EOL 2026'). "
                    "Free text; trimmed server-side."
                ),
            ),
        ],
    ) -> None:
        handler = get_handler()
        await handler(
            DeprecateModel(
                model_id=model_id,
                reason=reason,
            ),
            principal_id=get_mcp_principal_id(ctx),
            correlation_id=current_correlation_id(),
            surface_id=get_mcp_surface_id(),
        )
