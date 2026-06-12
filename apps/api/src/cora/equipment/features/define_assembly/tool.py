"""MCP tool for the `define_assembly` slice."""

from collections.abc import Callable
from typing import Annotated, Any
from uuid import UUID

from mcp.server.fastmcp import Context, FastMCP
from pydantic import BaseModel, Field

from cora.equipment._bodies import DrawingBody, TemplateSlotBody, TemplateWireBody
from cora.equipment.aggregates.assembly import ASSEMBLY_NAME_MAX_LENGTH
from cora.equipment.features.define_assembly.command import DefineAssembly
from cora.equipment.features.define_assembly.handler import IdempotentHandler
from cora.infrastructure.mcp_principal import get_mcp_principal_id
from cora.infrastructure.observability import current_correlation_id
from cora.infrastructure.routing import get_mcp_surface_id


class DefineAssemblyOutput(BaseModel):
    assembly_id: UUID


def register(mcp: FastMCP, *, get_handler: Callable[[], IdempotentHandler]) -> None:
    @mcp.tool(
        name="define_assembly",
        description=(
            "Define a new Assembly composition blueprint. An Assembly "
            "is a content-addressed template that declares the slots "
            "(Family-typed) and signal wires of a reusable cluster of "
            "Assets (e.g., the MCTOptics detector fixture: microscope "
            "+ objectives + camera + scintillator, wired together). "
            "presents_as_family_id is the FamilyId the instantiated "
            "Assembly stands in for at Method.needed_families "
            "satisfaction time. Note: this MCP surface has no "
            "idempotency-key equivalent of the REST Idempotency-Key "
            "header; retries of a failed or lost call may create "
            "duplicate Assemblies."
        ),
    )
    async def define_assembly_tool(  # pyright: ignore[reportUnusedFunction]
        ctx: Context[Any, Any, Any],
        name: Annotated[
            str,
            Field(
                min_length=1,
                max_length=ASSEMBLY_NAME_MAX_LENGTH,
                description="Human-readable display name.",
            ),
        ],
        presents_as_family_id: Annotated[
            UUID,
            Field(description="FamilyId the instantiated Assembly stands in for."),
        ],
        required_slots: Annotated[
            list[TemplateSlotBody],
            Field(description="Slots that compose this Assembly."),
        ] = [],  # noqa: B006  (FastMCP requires a literal default; the route handler copies into a frozenset before storage)
        required_wires: Annotated[
            list[TemplateWireBody],
            Field(description="Slot-to-slot signal wires inside the Assembly."),
        ] = [],  # noqa: B006
        parameter_overrides_schema: Annotated[
            dict[str, Any] | None,
            Field(
                description=(
                    "Optional JSON Schema subset for parameter_overrides accepted at instantiation."
                ),
            ),
        ] = None,
        drawing: Annotated[
            DrawingBody | None,
            Field(description="Optional engineering reference for the assembly."),
        ] = None,
        version: Annotated[
            str | None,
            Field(description="Operator-curated free-form version label."),
        ] = None,
    ) -> DefineAssemblyOutput:
        handler = get_handler()
        assembly_id = await handler(
            DefineAssembly(
                name=name,
                presents_as_family_id=presents_as_family_id,
                required_slots=frozenset(s.to_domain() for s in required_slots),
                required_wires=frozenset(w.to_domain() for w in required_wires),
                parameter_overrides_schema=parameter_overrides_schema,
                drawing=drawing.to_domain() if drawing is not None else None,
                version=version,
            ),
            principal_id=get_mcp_principal_id(ctx),
            correlation_id=current_correlation_id(),
            surface_id=get_mcp_surface_id(),
        )
        return DefineAssemblyOutput(assembly_id=assembly_id)
