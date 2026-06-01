"""MCP tool for the `define_model` slice.

Surfaces the same handler the REST route uses, exposed as a Model
Context Protocol tool.
"""

from collections.abc import Callable
from typing import Annotated, Any
from uuid import UUID

from mcp.server.fastmcp import Context, FastMCP
from pydantic import BaseModel, Field

from cora.equipment.aggregates.model import (
    MANUFACTURER_IDENTIFIER_MAX_LENGTH,
    MANUFACTURER_NAME_MAX_LENGTH,
    MODEL_NAME_MAX_LENGTH,
    MODEL_PART_NUMBER_MAX_LENGTH,
    MODEL_VERSION_TAG_MAX_LENGTH,
    Manufacturer,
    ManufacturerIdentifier,
    ManufacturerIdentifierType,
    ManufacturerName,
)
from cora.equipment.features.define_model.command import DefineModel
from cora.equipment.features.define_model.handler import IdempotentHandler
from cora.infrastructure.mcp_principal import get_mcp_principal_id
from cora.infrastructure.observability import current_correlation_id
from cora.infrastructure.routing import get_mcp_surface_id


class ManufacturerInput(BaseModel):
    """MCP tool input mirror of the Manufacturer VO.

    `identifier` and `identifier_type` are both optional but must be
    supplied together (pairing invariant; enforced at the VO).
    """

    name: str = Field(
        ...,
        min_length=1,
        max_length=MANUFACTURER_NAME_MAX_LENGTH,
        description="Display name of the manufacturer.",
    )
    identifier: str | None = Field(
        default=None,
        min_length=1,
        max_length=MANUFACTURER_IDENTIFIER_MAX_LENGTH,
        description=(
            "Optional opaque identifier value. If supplied, identifier_type "
            "is required (and vice versa)."
        ),
    )
    identifier_type: ManufacturerIdentifierType | None = Field(
        default=None,
        description="Closed scheme for the optional manufacturer identifier.",
    )

    def to_vo(self) -> Manufacturer:
        identifier = (
            ManufacturerIdentifier(self.identifier) if self.identifier is not None else None
        )
        return Manufacturer(
            name=ManufacturerName(self.name),
            identifier=identifier,
            identifier_type=self.identifier_type,
        )


class DefineModelOutput(BaseModel):
    """Structured output of the `define_model` MCP tool."""

    model_id: UUID


def register(mcp: FastMCP, *, get_handler: Callable[[], IdempotentHandler]) -> None:
    """Register the `define_model` tool on the given MCP server."""

    @mcp.tool(
        name="define_model",
        description=(
            "Define a new vendor-catalog Model with manufacturer, part number, "
            "and the set of Family ids it satisfies."
        ),
    )
    async def define_model_tool(  # pyright: ignore[reportUnusedFunction]
        ctx: Context[Any, Any, Any],
        name: Annotated[
            str,
            Field(
                min_length=1,
                max_length=MODEL_NAME_MAX_LENGTH,
                description="Display name for the new Model.",
            ),
        ],
        manufacturer: Annotated[
            ManufacturerInput,
            Field(description="Vendor identity (name plus optional identifier)."),
        ],
        part_number: Annotated[
            str,
            Field(
                min_length=1,
                max_length=MODEL_PART_NUMBER_MAX_LENGTH,
                description=(
                    "Vendor SKU; case-sensitive (RV120CCHL and rv120cchl are "
                    "different Newport entries)."
                ),
            ),
        ],
        declared_families: Annotated[
            list[UUID],
            Field(
                min_length=1,
                description=(
                    "Family ids the catalog entry satisfies. At least one required; "
                    "deduplicated server-side."
                ),
            ),
        ],
        version_tag: Annotated[
            str | None,
            Field(
                default=None,
                min_length=1,
                max_length=MODEL_VERSION_TAG_MAX_LENGTH,
                description="Optional initial revision label (e.g., 'rev-A').",
            ),
        ] = None,
    ) -> DefineModelOutput:
        handler = get_handler()
        model_id = await handler(
            DefineModel(
                name=name,
                manufacturer=manufacturer.to_vo(),
                part_number=part_number,
                declared_families=frozenset(declared_families),
                version_tag=version_tag,
            ),
            principal_id=get_mcp_principal_id(ctx),
            correlation_id=current_correlation_id(),
            surface_id=get_mcp_surface_id(),
        )
        return DefineModelOutput(model_id=model_id)
