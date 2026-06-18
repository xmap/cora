"""MCP tool for the `define_method` slice.

Surfaces the same handler the REST route uses, exposed as a Model
Context Protocol tool."""

from collections.abc import Callable
from typing import Annotated, Any
from uuid import UUID

from mcp.server.fastmcp import Context, FastMCP
from pydantic import BaseModel, Field

from cora.infrastructure.mcp_principal import get_mcp_principal_id
from cora.infrastructure.observability import current_correlation_id
from cora.infrastructure.routing import get_mcp_surface_id
from cora.recipe.aggregates.method import (
    METHOD_NAME_MAX_LENGTH,
    METHOD_NEEDED_SUPPLY_KIND_MAX_LENGTH,
    ExecutionPattern,
)
from cora.recipe.features.define_method.command import DefineMethod
from cora.recipe.features.define_method.handler import IdempotentHandler


class DefineMethodOutput(BaseModel):
    """Structured output of the `define_method` MCP tool."""

    method_id: UUID


def register(mcp: FastMCP, *, get_handler: Callable[[], IdempotentHandler]) -> None:
    """Register the `define_method` tool on the given MCP server."""

    @mcp.tool(
        name="define_method",
        description=(
            "Define a new abstract technique-class recipe (Method). "
            "needed_family_ids is a list of Family ids the Method "
            "requires; may be empty for purely procedural Methods. "
            "needed_supplies is a list of Supply.kind STRINGS "
            "(for example 'PhotonBeam', 'LiquidNitrogen'); may be empty."
        ),
    )
    async def define_method_tool(  # pyright: ignore[reportUnusedFunction]
        ctx: Context[Any, Any, Any],
        name: Annotated[
            str,
            Field(
                min_length=1,
                max_length=METHOD_NAME_MAX_LENGTH,
                description="Display name for the new method.",
            ),
        ],
        capability_id: Annotated[
            UUID,
            Field(
                description=(
                    "Universal Capability template this Method realizes. "
                    "REQUIRED per Pattern P (6l-strict). The bound "
                    "Capability must declare `Method` in its "
                    "executor_shapes set; otherwise 409."
                ),
            ),
        ],
        execution_pattern: Annotated[
            ExecutionPattern,
            Field(
                description=(
                    "Workload-execution shape (Batch, Iterative, or "
                    "Streaming). REQUIRED. An Iterative Method must later "
                    "declare a max_iter-shape or tol-shape stopping key in "
                    "its parameters_schema."
                ),
            ),
        ],
        needed_family_ids: Annotated[
            list[UUID],
            Field(
                description=(
                    "Family ids this Method requires. May be empty. "
                    "Eventual-consistency: ids are NOT verified against "
                    "the Family stream at decide time."
                ),
            ),
        ],
        needed_supplies: Annotated[
            list[
                Annotated[
                    str,
                    Field(
                        min_length=1,
                        max_length=METHOD_NEEDED_SUPPLY_KIND_MAX_LENGTH,
                    ),
                ]
            ],
            Field(
                description=(
                    "Supply.kind strings this Method requires (NOT Supply "
                    "instance UUIDs). May be empty. Eventual-consistency: "
                    "kinds are NOT verified against the Supply stream."
                ),
            ),
        ]
        | None = None,
        needed_assembly_ids: Annotated[
            list[UUID],
            Field(
                description=(
                    "Equipment Assembly ids this Method requires "
                    "(composition blueprints). May be empty. Eventual-"
                    "consistency: ids are NOT verified against the "
                    "Assembly stream at decide time."
                ),
            ),
        ]
        | None = None,
        monotone_quality: Annotated[
            bool,
            Field(
                description=(
                    "Anytime-algorithm claim; meaningful only for "
                    "Iterative Methods. True on a non-Iterative Method "
                    "is rejected (400)."
                ),
            ),
        ] = False,
        resumable_from_checkpoint: Annotated[
            bool,
            Field(
                description=(
                    "Executor can resume from a checkpoint. Independent of "
                    "execution_pattern (streaming replay and self-checkpointing "
                    "batch may also resume)."
                ),
            ),
        ] = False,
    ) -> DefineMethodOutput:
        handler = get_handler()
        method_id = await handler(
            DefineMethod(
                name=name,
                capability_id=capability_id,
                execution_pattern=execution_pattern,
                needed_family_ids=frozenset(needed_family_ids),
                needed_supplies=frozenset(needed_supplies or []),
                needed_assembly_ids=frozenset(needed_assembly_ids or []),
                monotone_quality=monotone_quality,
                resumable_from_checkpoint=resumable_from_checkpoint,
            ),
            principal_id=get_mcp_principal_id(ctx),
            correlation_id=current_correlation_id(),
            surface_id=get_mcp_surface_id(),
        )
        return DefineMethodOutput(method_id=method_id)
