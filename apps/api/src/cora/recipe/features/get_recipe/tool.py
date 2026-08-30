"""MCP tool for the `get_recipe` query slice."""

from collections.abc import Callable
from datetime import datetime
from typing import Annotated, Any
from uuid import UUID

from mcp.server.fastmcp import Context, FastMCP
from pydantic import BaseModel, Field

from cora.infrastructure.mcp_principal import get_mcp_principal_id
from cora.infrastructure.observability import current_correlation_id
from cora.infrastructure.routing import get_mcp_surface_id
from cora.recipe.aggregates.recipe import RECIPE_NAME_MAX_LENGTH, steps_to_dict
from cora.recipe.features.get_recipe.handler import Handler
from cora.recipe.features.get_recipe.query import GetRecipe


class RecipeOutput(BaseModel):
    """Structured output of the `get_recipe` MCP tool.

    `created_at` / `versioned_at` / `deprecated_at` mirror the REST
    `RecipeResponse` (Path C): sourced from the
    `proj_recipe_recipe_summary` projection. Null semantics: read
    together with `status`. A populated `status` with a null timestamp
    means the projection has not yet folded that lifecycle event,
    never a missing transition. A not-found Recipe raises (MCP
    `isError: true`) rather than returning null timestamps.
    """

    id: UUID
    name: str = Field(..., max_length=RECIPE_NAME_MAX_LENGTH)
    capability_id: UUID
    status: str
    version: str | None
    steps: dict[str, Any]
    closing_steps: dict[str, Any]
    replaced_by_recipe_id: UUID | None
    created_at: datetime | None = None
    versioned_at: datetime | None = None
    deprecated_at: datetime | None = None


def register(mcp: FastMCP, *, get_handler: Callable[[], Handler]) -> None:
    """Register the `get_recipe` tool on the given MCP server."""

    @mcp.tool(
        name="get_recipe",
        description="Read the current state of an existing Recipe by id.",
    )
    async def get_recipe_tool(  # pyright: ignore[reportUnusedFunction]
        ctx: Context[Any, Any, Any],
        recipe_id: Annotated[
            UUID,
            Field(description="Target Recipe's id."),
        ],
    ) -> RecipeOutput:
        handler = get_handler()
        view = await handler(
            GetRecipe(recipe_id=recipe_id),
            principal_id=get_mcp_principal_id(ctx),
            correlation_id=current_correlation_id(),
            surface_id=get_mcp_surface_id(),
        )
        if view is None:
            msg = f"Recipe {recipe_id} not found"
            raise ValueError(msg)
        recipe = view.recipe
        timestamps = view.timestamps
        return RecipeOutput(
            id=recipe.id,
            name=recipe.name.value,
            capability_id=recipe.capability_id,
            status=recipe.status.value,
            version=recipe.version,
            steps=steps_to_dict(recipe.steps),
            closing_steps=steps_to_dict(recipe.closing_steps),
            replaced_by_recipe_id=recipe.replaced_by_recipe_id,
            created_at=timestamps.created_at if timestamps is not None else None,
            versioned_at=timestamps.versioned_at if timestamps is not None else None,
            deprecated_at=timestamps.deprecated_at if timestamps is not None else None,
        )
