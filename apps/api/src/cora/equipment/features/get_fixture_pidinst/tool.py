"""MCP tool for the `get_fixture_pidinst` query slice.

Surfaces the same handler the REST route uses. Returns a structured
`PidinstRecordOutput` on hit. On miss raises `FixtureNotFoundError`
which FastMCP wraps as `isError: true` with a text diagnostic,
matching the REST 404 / 409 / 422 behaviour in MCP's error idiom.

Per section 14.1 of project_fixture_pidinst_design: every read slice
ships both a REST route and an MCP tool; `get_*` is the read-tool
naming convention.
"""

from collections.abc import Callable
from typing import Annotated, Any
from uuid import UUID

from mcp.server.fastmcp import Context, FastMCP
from pydantic import BaseModel, Field

from cora.equipment._pidinst_serializer import to_fixture_pidinst_record
from cora.equipment.aggregates.fixture import FixtureNotFoundError
from cora.equipment.features.get_fixture_pidinst.handler import Handler
from cora.infrastructure.mcp_principal import get_mcp_principal_id
from cora.infrastructure.observability import current_correlation_id
from cora.infrastructure.routing import get_mcp_surface_id

_FIXTURE_LANDING_PAGE_FALLBACK = "https://cora.local/fixtures/{fixture_id}/landing"
_FIXTURE_PUBLISHER_FALLBACK = "CORA"


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
    """Structured output of the `get_fixture_pidinst` MCP tool.

    Mirrors the slice-C `PidinstRecord` shape at the wire boundary;
    aligns with the REST route's `PidinstRecordResponse`. Only the
    fields actually populated by this slice are surfaced explicitly;
    other PIDINST properties (RelatedIdentifier, MeasurementTechnique,
    MeasuredVariable) ship as empty lists in the response body.
    """

    fixture_id: UUID
    name: str
    schema_version: str
    landing_page_url: str
    identifier: PidinstIdentifierOutput
    owners: list[PidinstOwnerOutput]
    publisher: str
    publication_year: int | None


def register(mcp: FastMCP, *, get_handler: Callable[[], Handler]) -> None:
    """Register the `get_fixture_pidinst` tool on the given MCP server."""

    @mcp.tool(
        name="get_fixture_pidinst",
        description=(
            "Get the PIDINST v1.0 record for a Fixture: a structured "
            "instrument-metadata bundle (identifier + landing page + owners "
            "+ manufacturers via bound Models + HasComponent relations to "
            "bound Assets with minted PIDs). The record maps to DataCite "
            "Instrument resourceTypeGeneral. Use when an external metadata "
            "harvester or citation pipeline needs a citable description of "
            "the composite Fixture. Returns 200 on success, 404 if the "
            "fixture is unknown, 409 if Fixture state cannot satisfy the "
            "PIDINST mandatory cardinality (no bound Asset carries owners "
            "or manufacturers), 422 if the assembled view fails serializer "
            "preconditions."
        ),
    )
    async def get_fixture_pidinst_tool(  # pyright: ignore[reportUnusedFunction]
        ctx: Context[Any, Any, Any],
        fixture_id: Annotated[
            UUID,
            Field(description="Target fixture's id."),
        ],
    ) -> PidinstRecordOutput:
        handler = get_handler()
        view = await handler(
            fixture_id,
            principal_id=get_mcp_principal_id(ctx),
            correlation_id=current_correlation_id(),
            surface_id=get_mcp_surface_id(),
        )
        if view is None:
            raise FixtureNotFoundError(fixture_id)
        landing_page_url = _FIXTURE_LANDING_PAGE_FALLBACK.format(fixture_id=fixture_id)
        record = to_fixture_pidinst_record(
            view,
            landing_page_url=landing_page_url,
            publisher=_FIXTURE_PUBLISHER_FALLBACK,
        )
        return PidinstRecordOutput(
            fixture_id=fixture_id,
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
