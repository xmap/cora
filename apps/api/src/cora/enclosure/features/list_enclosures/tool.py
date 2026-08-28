"""MCP tool for the `list_enclosures` query slice."""

from collections.abc import Callable
from datetime import datetime
from typing import Annotated, Any
from uuid import UUID

from mcp.server.fastmcp import Context, FastMCP
from pydantic import BaseModel, Field

from cora.enclosure.aggregates.enclosure import ENCLOSURE_NAME_MAX_LENGTH
from cora.enclosure.features.list_enclosures.handler import Handler
from cora.enclosure.features.list_enclosures.query import (
    LifecycleFilter,
    ListEnclosures,
    PermitStatusFilter,
)
from cora.infrastructure.mcp_principal import get_mcp_principal_id
from cora.infrastructure.observability import current_correlation_id
from cora.infrastructure.routing import get_mcp_surface_id
from cora.shared.text_bounds import REASON_MAX_LENGTH


class EnclosureSummaryRow(BaseModel):
    enclosure_id: UUID
    name: str = Field(..., max_length=ENCLOSURE_NAME_MAX_LENGTH)
    facility_code: str
    lifecycle: LifecycleFilter
    permit_status: PermitStatusFilter
    registered_at: datetime
    registered_by: UUID
    last_permit_status_changed_at: datetime | None = Field(
        default=None,
        description=(
            "CORA's ingest time of the last permit-status CHANGE. Advances "
            "only on a change: a stale value means 'no transition since'."
        ),
    )
    last_permit_status_reason: str | None = Field(default=None, max_length=REASON_MAX_LENGTH)
    last_trigger: str | None = None
    last_source_kind: str | None = None
    last_source_id: str | None = None
    last_source_observed_at: datetime | None = Field(
        default=None,
        description=(
            "The substrate's own time for the last reading, or null when "
            "the substrate reported none. Never a substitute for "
            "last_permit_status_changed_at."
        ),
    )
    decommissioned_at: datetime | None = None
    decommissioned_by: UUID | None = None


class EnclosureListOutput(BaseModel):
    """Structured output of the `list_enclosures` MCP tool."""

    items: list[EnclosureSummaryRow]
    next_cursor: str | None = None


def register(mcp: FastMCP, *, get_handler: Callable[[], Handler]) -> None:
    """Register the `list_enclosures` tool on the given MCP server."""

    @mcp.tool(
        name="list_enclosures",
        description=(
            "Cursor-paginated list of enclosures (interlock-gated containment "
            "volumes, e.g. hutches). Optional `lifecycle` filter accepts: "
            "Active, Decommissioned. Optional `permit_status` filter accepts: "
            "Unknown, Permitted, NotPermitted. Optional `facility_code` filter "
            "narrows to one Facility. Pass `cursor` from a previous page's "
            "`next_cursor` to fetch the next page."
        ),
    )
    async def list_enclosures_tool(  # pyright: ignore[reportUnusedFunction]
        ctx: Context[Any, Any, Any],
        cursor: Annotated[
            str | None,
            Field(description="Opaque cursor from a previous response."),
        ] = None,
        limit: Annotated[
            int,
            Field(ge=1, le=100, description="Page size cap (max 100)."),
        ] = 50,
        lifecycle: Annotated[
            LifecycleFilter | None,
            Field(description="Optional lifecycle filter; omit to list all."),
        ] = None,
        permit_status: Annotated[
            PermitStatusFilter | None,
            Field(description="Optional permit-status filter; omit to list all."),
        ] = None,
        facility_code: Annotated[
            str | None,
            Field(description="Optional facility-code filter."),
        ] = None,
    ) -> EnclosureListOutput:
        handler = get_handler()
        page = await handler(
            ListEnclosures(
                cursor=cursor,
                limit=limit,
                lifecycle=lifecycle,
                permit_status=permit_status,
                facility_code=facility_code,
            ),
            principal_id=get_mcp_principal_id(ctx),
            correlation_id=current_correlation_id(),
            surface_id=get_mcp_surface_id(),
        )
        return EnclosureListOutput(
            items=[
                EnclosureSummaryRow(
                    enclosure_id=item.enclosure_id,
                    name=item.name,
                    facility_code=item.facility_code,
                    lifecycle=item.lifecycle,
                    permit_status=item.permit_status,
                    registered_at=item.registered_at,
                    registered_by=item.registered_by,
                    last_permit_status_changed_at=item.last_permit_status_changed_at,
                    last_permit_status_reason=item.last_permit_status_reason,
                    last_trigger=item.last_trigger,
                    last_source_kind=item.last_source_kind,
                    last_source_id=item.last_source_id,
                    last_source_observed_at=item.last_source_observed_at,
                    decommissioned_at=item.decommissioned_at,
                    decommissioned_by=item.decommissioned_by,
                )
                for item in page.items
            ],
            next_cursor=page.next_cursor,
        )
