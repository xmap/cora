"""MCP tool for the `get_asset_pidinst` query slice.

Surfaces the same handler the REST route uses. Returns a structured
`PidinstRecordOutput` on hit. On miss raises an exception that
FastMCP wraps as `isError: true` with a text diagnostic, matching
the REST 404 / 409 / 422 behaviour in MCP's error idiom.

Slice E.1 ships this tool to honor the BC-wide slice-contract
convention (every read slice exposes both REST + MCP). The earlier
memo posture of "no MCP exposure in E.1" was wrong: every sibling
read slice (`get_asset`, `get_asset_integration_view`, `get_family`,
`get_model`) ships a tool.py + tools-registration entry, and the
`test_slice_has_required_files` + `test_slice_tool_registered_in_tools`
architecture fitnesses enforce the convention.
"""

from collections.abc import Callable
from typing import Annotated, Any
from uuid import UUID

from mcp.server.fastmcp import Context, FastMCP
from pydantic import BaseModel, Field

from cora.equipment.features.get_asset_pidinst.handler import Handler
from cora.equipment.features.get_asset_pidinst.query import GetAssetPidinst
from cora.infrastructure.mcp_principal import get_mcp_principal_id
from cora.infrastructure.observability import current_correlation_id
from cora.infrastructure.routing import get_mcp_surface_id


class PidinstIdentifierOutput(BaseModel):
    """PIDINST property 1 Identifier."""

    scheme: str
    value: str


class PidinstOwnerOutput(BaseModel):
    """One entry in PIDINST property 5 Owner."""

    name: str
    contact: str | None = None
    identifier: str | None = None
    identifier_type: str | None = None


class PidinstRecordOutput(BaseModel):
    """Structured output of the `get_asset_pidinst` MCP tool.

    Mirrors the slice-C `PidinstRecord` shape at the wire boundary;
    aligns with the REST route's `PidinstRecordResponse`. Only the
    fields actually populated in slice E.1 are surfaced explicitly;
    other PIDINST properties (RelatedIdentifier, MeasurementTechnique,
    MeasuredVariable) are slice-F or slice-G concerns and ship as
    empty lists in the response body.
    """

    asset_id: UUID
    name: str
    schema_version: str
    landing_page_url: str
    identifier: PidinstIdentifierOutput
    owners: list[PidinstOwnerOutput]
    publisher: str
    publication_year: int | None


def register(mcp: FastMCP, *, get_handler: Callable[[], Handler]) -> None:
    """Register the `get_asset_pidinst` tool on the given MCP server."""

    @mcp.tool(
        name="get_asset_pidinst",
        description=(
            "Get the PIDINST v1.0 record for an Asset: a structured "
            "instrument-metadata bundle (identifier + landing page + owners "
            "+ manufacturer via Model + measurement context) that maps to "
            "DataCite Instrument resourceTypeGeneral. Use when an external "
            "metadata harvester or citation pipeline needs a citable "
            "description of the instrument. Returns 200 on success, 404 if "
            "the asset is unknown, 409 if the asset's state cannot satisfy "
            "the PIDINST mandatory cardinality (no owners, no model), 422 "
            "if the assembled view fails serializer preconditions."
        ),
    )
    async def get_asset_pidinst_tool(  # pyright: ignore[reportUnusedFunction]
        ctx: Context[Any, Any, Any],
        asset_id: Annotated[
            UUID,
            Field(description="Target asset's id."),
        ],
    ) -> PidinstRecordOutput:
        handler = get_handler()
        record = await handler(
            GetAssetPidinst(asset_id=asset_id),
            principal_id=get_mcp_principal_id(ctx),
            correlation_id=current_correlation_id(),
            surface_id=get_mcp_surface_id(),
        )
        return PidinstRecordOutput(
            asset_id=asset_id,
            name=record.name,
            schema_version=record.schema_version.value,
            landing_page_url=record.landing_page,
            identifier=PidinstIdentifierOutput(
                scheme=record.identifier.scheme.value,
                value=record.identifier.value,
            ),
            owners=[
                PidinstOwnerOutput(
                    name=owner.name,
                    contact=owner.contact,
                    identifier=owner.identifier,
                    identifier_type=owner.identifier_type,
                )
                for owner in record.owners
            ],
            publisher=record.publisher,
            publication_year=record.publication_year,
        )
