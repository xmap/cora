"""MCP tool for the `deprecate_assembly` slice."""

from collections.abc import Callable
from typing import Annotated, Any
from uuid import UUID

from mcp.server.fastmcp import Context, FastMCP
from pydantic import Field

from cora.equipment.features.deprecate_assembly.command import DeprecateAssembly
from cora.equipment.features.deprecate_assembly.handler import Handler
from cora.infrastructure.mcp_principal import get_mcp_principal_id
from cora.infrastructure.observability import current_correlation_id
from cora.infrastructure.routing import get_mcp_surface_id
from cora.shared.text_bounds import REASON_MAX_LENGTH


def register(mcp: FastMCP, *, get_handler: Callable[[], Handler]) -> None:
    """Register the `deprecate_assembly` tool on the given MCP server."""

    @mcp.tool(
        name="deprecate_assembly",
        description=(
            "Mark an existing Assembly as deprecated (terminal). "
            "Accepts both Defined and Versioned source states. "
            "Re-deprecating an already-Deprecated Assembly raises. "
            "Once Deprecated, future instantiate_assembly calls "
            "reject; new revisions must fork via define_assembly "
            "with a fresh id."
        ),
    )
    async def deprecate_assembly_tool(  # pyright: ignore[reportUnusedFunction]
        ctx: Context[Any, Any, Any],
        assembly_id: Annotated[
            UUID,
            Field(description="Target Assembly's id."),
        ],
        reason: Annotated[
            str,
            Field(
                min_length=1,
                max_length=REASON_MAX_LENGTH,
                description="Operator-supplied audit-log breadcrumb.",
            ),
        ],
    ) -> None:
        handler = get_handler()
        await handler(
            DeprecateAssembly(assembly_id=assembly_id, reason=reason),
            principal_id=get_mcp_principal_id(ctx),
            correlation_id=current_correlation_id(),
            surface_id=get_mcp_surface_id(),
        )
