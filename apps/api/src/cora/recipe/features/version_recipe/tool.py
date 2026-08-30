"""MCP tool for the `version_recipe` slice."""

from collections.abc import Callable
from typing import Annotated, Any
from uuid import UUID

from mcp.server.fastmcp import Context, FastMCP
from pydantic import BaseModel, Field

from cora.infrastructure.mcp_principal import get_mcp_principal_id
from cora.infrastructure.observability import current_correlation_id
from cora.infrastructure.routing import get_mcp_surface_id
from cora.recipe.aggregates.recipe import (
    RECIPE_VERSION_TAG_MAX_LENGTH,
    steps_from_dict,
)
from cora.recipe.features.version_recipe.command import VersionRecipe
from cora.recipe.features.version_recipe.handler import Handler


class VersionRecipeOutput(BaseModel):
    """Structured output of the `version_recipe` MCP tool."""

    recipe_id: UUID


def register(mcp: FastMCP, *, get_handler: Callable[[], Handler]) -> None:
    """Register the `version_recipe` tool on the given MCP server."""

    @mcp.tool(
        name="version_recipe",
        description=(
            "Issue a new version label + replacement steps for an existing "
            "Recipe. capability_id is PRESERVED from the prior Recipe state "
            "(immutable across versions); steps replace wholesale. BindingRef "
            "integrity is re-validated against the CURRENT Capability schema "
            "to catch any Capability-re-version drift since the Recipe's "
            "last write."
        ),
    )
    async def version_recipe_tool(  # pyright: ignore[reportUnusedFunction]
        ctx: Context[Any, Any, Any],
        recipe_id: Annotated[UUID, Field(description="Target Recipe's id.")],
        version_tag: Annotated[
            str,
            Field(
                min_length=1,
                max_length=RECIPE_VERSION_TAG_MAX_LENGTH,
                description=(
                    "Operator-supplied label (for example 'v2', '2026-Q3'). "
                    "NOT UNIQUE across versions; same tag + same steps "
                    "re-emits as a re-attestation audit signal."
                ),
            ),
        ],
        steps: Annotated[
            dict[str, Any],
            Field(
                description=(
                    "Wire-format replacement step sequence: `{steps: [{kind: "
                    "setpoint|action|check, ...}]}`. Wholesale replace; prior "
                    "steps are dropped."
                ),
            ),
        ],
        closing_steps: Annotated[
            dict[str, Any] | None,
            Field(
                default=None,
                description=(
                    "Optional replacement closing-step sequence, same shape "
                    "as `steps` (wholesale replace alongside it). Omit or "
                    "pass None for no closing steps."
                ),
            ),
        ] = None,
    ) -> VersionRecipeOutput:
        handler = get_handler()
        await handler(
            VersionRecipe(
                recipe_id=recipe_id,
                version_tag=version_tag,
                steps=steps_from_dict(steps),
                closing_steps=steps_from_dict(
                    closing_steps if closing_steps is not None else {"steps": []}
                ),
            ),
            principal_id=get_mcp_principal_id(ctx),
            correlation_id=current_correlation_id(),
            surface_id=get_mcp_surface_id(),
        )
        return VersionRecipeOutput(recipe_id=recipe_id)
