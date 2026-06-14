"""MCP tool for the `register_procedure_from_recipe` slice."""

from collections.abc import Callable
from typing import Annotated, Any
from uuid import UUID

from mcp.server.fastmcp import Context, FastMCP
from pydantic import BaseModel, Field

from cora.infrastructure.mcp_principal import get_mcp_principal_id
from cora.infrastructure.observability import current_correlation_id
from cora.infrastructure.routing import get_mcp_surface_id
from cora.operation.aggregates.procedure import (
    PROCEDURE_KIND_MAX_LENGTH,
    PROCEDURE_NAME_MAX_LENGTH,
)
from cora.operation.features.register_procedure_from_recipe.command import (
    RegisterProcedureFromRecipe,
)
from cora.operation.features.register_procedure_from_recipe.handler import (
    IdempotentHandler,
)


class RegisterProcedureFromRecipeOutput(BaseModel):
    """Structured output of the `register_procedure_from_recipe` MCP tool."""

    procedure_id: UUID


def register(mcp: FastMCP, *, get_handler: Callable[[], IdempotentHandler]) -> None:
    """Register the `register_procedure_from_recipe` tool on the given MCP server."""

    @mcp.tool(
        name="register_procedure_from_recipe",
        description=(
            "Register a new Procedure by expanding a Recipe with "
            "operator-supplied parameter bindings. The handler loads the "
            "Recipe, then the Recipe's Capability, re-validates BindingRef "
            "integrity against the CURRENT Capability schema, validates "
            "bindings, runs the expansion port twice for overflow + "
            "determinism gates, then emits ProcedureRegistered + "
            "RecipeExpansionRecorded provenance events."
        ),
    )
    async def register_procedure_from_recipe_tool(  # pyright: ignore[reportUnusedFunction]
        ctx: Context[Any, Any, Any],
        name: Annotated[
            str,
            Field(
                min_length=1,
                max_length=PROCEDURE_NAME_MAX_LENGTH,
                description="Operator-readable display name for the procedure.",
            ),
        ],
        kind: Annotated[
            str,
            Field(
                min_length=1,
                max_length=PROCEDURE_KIND_MAX_LENGTH,
                description="Free-form ISA-106 procedure-kind discriminator.",
            ),
        ],
        recipe_id: Annotated[
            UUID,
            Field(
                description=("Recipe whose templated steps will be expanded into this Procedure."),
            ),
        ],
        target_asset_ids: Annotated[
            list[UUID] | None,
            Field(
                default=None,
                description=("Asset ids this procedure acts on (may be omitted or empty)."),
            ),
        ] = None,
        parent_run_id: Annotated[
            UUID | None,
            Field(
                default=None,
                description=("Optional parent Run binding (None = standalone procedure)."),
            ),
        ] = None,
        bindings: Annotated[
            dict[str, Any] | None,
            Field(
                default=None,
                description=(
                    "Operator-supplied parameter values keyed by the "
                    "parameter names declared in the bound Recipe's "
                    "Capability's parameters_schema. Omit or pass {} "
                    "when the Recipe carries no BindingRefs."
                ),
            ),
        ] = None,
        max_consecutive_unconverged_iterations: Annotated[
            int | None,
            Field(
                ge=1,
                description=(
                    "Optional 'patience' cap: max consecutive unconverged "
                    "iterations before start_iteration refuses the next one "
                    "(409). Resets on a converged iteration. None = no cap."
                ),
            ),
        ] = None,
    ) -> RegisterProcedureFromRecipeOutput:
        handler = get_handler()
        procedure_id = await handler(
            RegisterProcedureFromRecipe(
                name=name,
                kind=kind,
                target_asset_ids=tuple(target_asset_ids or []),
                parent_run_id=parent_run_id,
                recipe_id=recipe_id,
                bindings=dict(bindings or {}),
                max_consecutive_unconverged_iterations=max_consecutive_unconverged_iterations,
            ),
            principal_id=get_mcp_principal_id(ctx),
            correlation_id=current_correlation_id(),
            surface_id=get_mcp_surface_id(),
        )
        return RegisterProcedureFromRecipeOutput(procedure_id=procedure_id)
