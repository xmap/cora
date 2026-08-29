"""MCP tool for the `define_recipe` slice."""

from collections.abc import Callable
from typing import Annotated, Any
from uuid import UUID

from mcp.server.fastmcp import Context, FastMCP
from pydantic import BaseModel, Field

from cora.infrastructure.mcp_principal import get_mcp_principal_id
from cora.infrastructure.observability import current_correlation_id
from cora.infrastructure.routing import get_mcp_surface_id
from cora.recipe.aggregates.recipe import RECIPE_NAME_MAX_LENGTH, steps_from_dict
from cora.recipe.features.define_recipe.command import DefineRecipe
from cora.recipe.features.define_recipe.handler import IdempotentHandler


class DefineRecipeOutput(BaseModel):
    """Structured output of the `define_recipe` MCP tool."""

    recipe_id: UUID


def register(mcp: FastMCP, *, get_handler: Callable[[], IdempotentHandler]) -> None:
    """Register the `define_recipe` tool on the given MCP server."""

    @mcp.tool(
        name="define_recipe",
        description=(
            "Define a new Recipe against an existing Capability. Recipe "
            "carries the templated step sequence the Operation BC Conductor "
            "walks after operator-supplied parameter bindings are resolved "
            "at register_procedure_from_recipe time. capability_id is "
            "REQUIRED and IMMUTABLE across versions; every BindingRef.name "
            "in steps must resolve in the referenced Capability's "
            "parameters_schema."
        ),
    )
    async def define_recipe_tool(  # pyright: ignore[reportUnusedFunction]
        ctx: Context[Any, Any, Any],
        name: Annotated[
            str,
            Field(
                min_length=1,
                max_length=RECIPE_NAME_MAX_LENGTH,
                description="Display name for the new Recipe.",
            ),
        ],
        capability_id: Annotated[
            UUID,
            Field(
                description=(
                    "Capability this Recipe realizes. REQUIRED + IMMUTABLE across versions."
                ),
            ),
        ],
        steps: Annotated[
            dict[str, Any],
            Field(
                description=(
                    "Wire-format step sequence: `{steps: [{kind: setpoint|"
                    "action|check, ...}]}`. BindingRef sentinels carry "
                    "`{__binding__: name}` at parameterized positions."
                ),
            ),
        ],
        closing_steps: Annotated[
            dict[str, Any] | None,
            Field(
                default=None,
                description=(
                    "Optional closing-step sequence, same shape as `steps`. "
                    "The Conductor walks these after `steps` ends on a real "
                    "terminal (Completed or Aborted), never on a Held pause. "
                    "Omit or pass None for no closing steps (the common case)."
                ),
            ),
        ] = None,
    ) -> DefineRecipeOutput:
        handler = get_handler()
        recipe_id = await handler(
            DefineRecipe(
                name=name,
                capability_id=capability_id,
                steps=steps_from_dict(steps),
                closing_steps=steps_from_dict(
                    closing_steps if closing_steps is not None else {"steps": []}
                ),
            ),
            principal_id=get_mcp_principal_id(ctx),
            correlation_id=current_correlation_id(),
            surface_id=get_mcp_surface_id(),
        )
        return DefineRecipeOutput(recipe_id=recipe_id)
