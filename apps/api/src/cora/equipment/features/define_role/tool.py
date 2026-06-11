"""MCP tool for the `define_role` slice.

Surfaces the same handler the REST route uses, exposed as a Model
Context Protocol tool.
"""

from collections.abc import Callable
from typing import Annotated, Any
from uuid import UUID

from mcp.server.fastmcp import Context, FastMCP
from pydantic import BaseModel, Field

from cora.equipment.aggregates.family import Affordance
from cora.equipment.aggregates.role import (
    ROLE_DOCSTRING_MAX_LENGTH,
    ROLE_NAME_MAX_LENGTH,
)
from cora.equipment.features.define_role.command import DefineRole
from cora.equipment.features.define_role.handler import IdempotentHandler
from cora.infrastructure.mcp_principal import get_mcp_principal_id
from cora.infrastructure.observability import current_correlation_id
from cora.infrastructure.routing import get_mcp_surface_id


class DefineRoleOutput(BaseModel):
    """Structured output of the `define_role` MCP tool."""

    role_id: UUID


def register(mcp: FastMCP, *, get_handler: Callable[[], IdempotentHandler]) -> None:
    """Register the `define_role` tool on the given MCP server."""

    @mcp.tool(
        name="define_role",
        description=(
            "Define a new global Role contract: the functional binding "
            "shape (Imager, Positioner, Controller, Detector, etc.) that "
            "a Method's RoleRequirement can target without pinning a "
            "specific Family. Roles are lightweight contracts: required "
            "and optional Affordances + produces/consumes SignalTypes + "
            "operator-facing docstring."
        ),
    )
    async def define_role_tool(  # pyright: ignore[reportUnusedFunction]
        ctx: Context[Any, Any, Any],
        name: Annotated[
            str,
            Field(
                min_length=1,
                max_length=ROLE_NAME_MAX_LENGTH,
                description="Display name for the new Role contract.",
            ),
        ],
        docstring: Annotated[
            str,
            Field(
                min_length=1,
                max_length=ROLE_DOCSTRING_MAX_LENGTH,
                description=("Operator-readable one-paragraph contract explanation."),
            ),
        ],
        required_affordances: Annotated[
            list[Affordance],
            Field(
                description=(
                    "Affordance value strings every satisfying Family MUST "
                    "advertise. Deduplicated server-side."
                ),
            ),
        ],
        optional_affordances: Annotated[
            list[Affordance],
            Field(
                description=(
                    "Affordance value strings a satisfying Family MAY "
                    "advertise. Deduplicated server-side. Must be disjoint "
                    "with required_affordances."
                ),
            ),
        ],
        produces: Annotated[
            list[str],
            Field(
                description=(
                    "Open-vocabulary SignalType labels satisfying Assets "
                    "emit. Trimmed and bound-checked server-side."
                ),
            ),
        ],
        consumes: Annotated[
            list[str],
            Field(
                description=(
                    "Open-vocabulary SignalType labels satisfying Assets "
                    "accept. Trimmed and bound-checked server-side."
                ),
            ),
        ],
    ) -> DefineRoleOutput:
        handler = get_handler()
        role_id = await handler(
            DefineRole(
                name=name,
                docstring=docstring,
                required_affordances=frozenset(required_affordances),
                optional_affordances=frozenset(optional_affordances),
                produces=frozenset(produces),
                consumes=frozenset(consumes),
            ),
            principal_id=get_mcp_principal_id(ctx),
            correlation_id=current_correlation_id(),
            surface_id=get_mcp_surface_id(),
        )
        return DefineRoleOutput(role_id=role_id)
