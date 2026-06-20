"""MCP tool for the `update_method_launch_spec` slice.

Mirrors the REST route (shares the wire shape + converter)."""

from collections.abc import Callable
from typing import Annotated, Any
from uuid import UUID

from mcp.server.fastmcp import Context, FastMCP
from pydantic import Field

from cora.infrastructure.mcp_principal import get_mcp_principal_id
from cora.infrastructure.observability import current_correlation_id
from cora.infrastructure.routing import get_mcp_surface_id
from cora.recipe.features.update_method_launch_spec.command import UpdateMethodLaunchSpec
from cora.recipe.features.update_method_launch_spec.handler import Handler
from cora.recipe.features.update_method_launch_spec.route import (
    LaunchSpecRequest,
    launch_spec_from_request,
)


def register(mcp: FastMCP, *, get_handler: Callable[[], Handler]) -> None:
    """Register the `update_method_launch_spec` MCP tool."""

    @mcp.tool(
        name="update_method_launch_spec",
        description=(
            "Set, replace, or clear a Method's vetted launch_spec (the argv "
            "recipe a conduct caller selects instead of raw command). Each "
            "arg NAMES a parameters_schema key; no template strings. Pass "
            "null for launch_spec to clear it."
        ),
    )
    async def update_method_launch_spec_tool(  # pyright: ignore[reportUnusedFunction]
        ctx: Context[Any, Any, Any],
        method_id: Annotated[UUID, Field(description="Target method's id.")],
        launch_spec: Annotated[
            LaunchSpecRequest | None,
            Field(description="The vetted launch recipe, or null to clear."),
        ],
    ) -> None:
        handler = get_handler()
        await handler(
            UpdateMethodLaunchSpec(
                method_id=method_id,
                launch_spec=launch_spec_from_request(launch_spec),
            ),
            principal_id=get_mcp_principal_id(ctx),
            correlation_id=current_correlation_id(),
            surface_id=get_mcp_surface_id(),
        )
