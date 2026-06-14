"""MCP tool for the `version_assembly` slice."""

from collections.abc import Callable
from typing import Annotated, Any
from uuid import UUID

from mcp.server.fastmcp import Context, FastMCP
from pydantic import BaseModel, Field

from cora.equipment._bodies import (
    DrawingBody,
    SubAssemblyLinkBody,
    TemplateSlotBody,
    TemplateWireBody,
)
from cora.equipment.aggregates.assembly import ASSEMBLY_NAME_MAX_LENGTH
from cora.equipment.features.version_assembly.command import VersionAssembly
from cora.equipment.features.version_assembly.handler import Handler
from cora.infrastructure.mcp_principal import get_mcp_principal_id
from cora.infrastructure.observability import current_correlation_id
from cora.infrastructure.routing import get_mcp_surface_id


class VersionAssemblyOutput(BaseModel):
    """Empty output - the version succeeded if no isError surfaces."""


def register(mcp: FastMCP, *, get_handler: Callable[[], Handler]) -> None:
    @mcp.tool(
        name="version_assembly",
        description=(
            "Publish a new revision snapshot of an existing Assembly. "
            "Replace-on-version: the args carry the FULL canonical "
            "structural subset (slots, wires, schema, drawing, version "
            "label, presents_as_family_id), NOT a diff. Multi-source "
            "FSM: Defined and Versioned both accept new revisions; "
            "Deprecated rejects (operators must fork via define_assembly "
            "with a fresh id). Re-attesting the same content produces "
            "a fresh event with the same content_hash."
        ),
    )
    async def version_assembly_tool(  # pyright: ignore[reportUnusedFunction]
        ctx: Context[Any, Any, Any],
        assembly_id: Annotated[
            UUID,
            Field(description="The target Assembly's UUID."),
        ],
        name: Annotated[
            str,
            Field(
                min_length=1,
                max_length=ASSEMBLY_NAME_MAX_LENGTH,
                description="Display name for this revision.",
            ),
        ],
        presents_as_family_id: Annotated[
            UUID,
            Field(description="FamilyId the instantiated Assembly stands in for."),
        ],
        required_slots: Annotated[
            list[TemplateSlotBody],
            Field(description="Full slot set for this revision."),
        ] = [],  # noqa: B006
        required_wires: Annotated[
            list[TemplateWireBody],
            Field(description="Full wire set for this revision."),
        ] = [],  # noqa: B006
        required_sub_assemblies: Annotated[
            list[SubAssemblyLinkBody],
            Field(
                description=(
                    "Full sub-assembly-link set for this revision "
                    "(replace-on-version); each pins a child Assembly's content_hash."
                ),
            ),
        ] = [],  # noqa: B006
        parameter_overrides_schema: Annotated[
            dict[str, Any] | None,
            Field(
                description="Optional JSON Schema subset for parameter_overrides.",
            ),
        ] = None,
        drawing: Annotated[
            DrawingBody | None,
            Field(description="Optional engineering reference for this revision."),
        ] = None,
        version: Annotated[
            str | None,
            Field(description="Operator-curated free-form version label."),
        ] = None,
    ) -> VersionAssemblyOutput:
        handler = get_handler()
        await handler(
            VersionAssembly(
                assembly_id=assembly_id,
                name=name,
                presents_as_family_id=presents_as_family_id,
                required_slots=frozenset(s.to_domain() for s in required_slots),
                required_wires=frozenset(w.to_domain() for w in required_wires),
                required_sub_assemblies=frozenset(r.to_domain() for r in required_sub_assemblies),
                parameter_overrides_schema=parameter_overrides_schema,
                drawing=drawing.to_domain() if drawing is not None else None,
                version=version,
            ),
            principal_id=get_mcp_principal_id(ctx),
            correlation_id=current_correlation_id(),
            surface_id=get_mcp_surface_id(),
        )
        return VersionAssemblyOutput()
