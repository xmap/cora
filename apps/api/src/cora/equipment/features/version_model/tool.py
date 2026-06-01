"""MCP tool for the `version_model` slice."""

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
from cora.equipment.features.version_model.command import VersionModel
from cora.equipment.features.version_model.handler import Handler
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


def register(mcp: FastMCP, *, get_handler: Callable[[], Handler]) -> None:
    """Register the `version_model` tool on the given MCP server."""

    @mcp.tool(
        name="version_model",
        description=(
            "Issue a new version of a vendor-catalog Model with updated name, "
            "manufacturer, part number, family set, and version tag. Accepts "
            "both Defined and Versioned source states (subsequent revisions "
            "allowed). Deprecated Models cannot be re-versioned. A new version "
            "IS a new declaration; the supplied fields REPLACE the prior values "
            "wholesale."
        ),
    )
    async def version_model_tool(  # pyright: ignore[reportUnusedFunction]
        ctx: Context[Any, Any, Any],
        model_id: Annotated[
            UUID,
            Field(description="Target Model's id."),
        ],
        name: Annotated[
            str,
            Field(
                min_length=1,
                max_length=MODEL_NAME_MAX_LENGTH,
                description="Replacement display name for the new version.",
            ),
        ],
        manufacturer: Annotated[
            ManufacturerInput,
            Field(description="Replacement vendor identity (name plus optional identifier)."),
        ],
        part_number: Annotated[
            str,
            Field(
                min_length=1,
                max_length=MODEL_PART_NUMBER_MAX_LENGTH,
                description=(
                    "Replacement vendor SKU; case-sensitive (RV120CCHL and rv120cchl "
                    "are different Newport entries)."
                ),
            ),
        ],
        declared_families: Annotated[
            list[UUID],
            Field(
                min_length=1,
                description=(
                    "Replacement Family id set the catalog entry satisfies. At least "
                    "one required; deduplicated server-side."
                ),
            ),
        ],
        version_tag: Annotated[
            str,
            Field(
                min_length=1,
                max_length=MODEL_VERSION_TAG_MAX_LENGTH,
                description=(
                    "Operator-supplied label for this revision (for example 'v2', '2026-Q3')."
                ),
            ),
        ],
    ) -> None:
        handler = get_handler()
        await handler(
            VersionModel(
                model_id=model_id,
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
