"""MCP tool for the `list_supplies` query slice."""

from collections.abc import Callable
from datetime import datetime
from typing import Annotated, Any
from uuid import UUID

from mcp.server.fastmcp import Context, FastMCP
from pydantic import BaseModel, Field

from cora.infrastructure.mcp_principal import get_mcp_principal_id
from cora.infrastructure.observability import current_correlation_id
from cora.infrastructure.routing import get_mcp_surface_id
from cora.shared.facility_code import FACILITY_CODE_MAX_LENGTH
from cora.shared.text_bounds import REASON_MAX_LENGTH
from cora.supply.aggregates.supply import (
    SUPPLY_KIND_MAX_LENGTH,
    SUPPLY_NAME_MAX_LENGTH,
    SupplyStatus,
    TriggerSource,
)
from cora.supply.features.list_supplies.handler import Handler
from cora.supply.features.list_supplies.query import (
    ListSupplies,
    SupplyStatusFilter,
)


class SupplySummaryRow(BaseModel):
    supply_id: UUID
    kind: str = Field(..., max_length=SUPPLY_KIND_MAX_LENGTH)
    name: str = Field(..., max_length=SUPPLY_NAME_MAX_LENGTH)
    facility_code: str = Field(
        ...,
        min_length=1,
        max_length=FACILITY_CODE_MAX_LENGTH,
        pattern=r"^[a-z0-9-]{1,32}$",
    )
    containing_asset_id: UUID | None = Field(
        default=None,
        description=(
            "Id of the containing Asset (Equipment BC) when the Supply is bound "
            "to a Sector / Beamline / Unit; null for facility-scope resources."
        ),
    )
    status: SupplyStatus
    registered_at: datetime
    last_status_changed_at: datetime | None = None
    last_status_reason: str | None = Field(default=None, max_length=REASON_MAX_LENGTH)
    last_trigger: TriggerSource | None = None


class SupplyListOutput(BaseModel):
    """Structured output of the `list_supplies` MCP tool."""

    items: list[SupplySummaryRow]
    next_cursor: str | None = None


def register(mcp: FastMCP, *, get_handler: Callable[[], Handler]) -> None:
    """Register the `list_supplies` tool on the given MCP server."""

    @mcp.tool(
        name="list_supplies",
        description=(
            "Cursor-paginated list of supplies. Optional filters: "
            "`facility_code` (cross-deployment slug, exact match, for example "
            "'aps'), `containing_asset_id` (UUID of the containing Equipment "
            "Asset; null-asset rows excluded), `kind` (free-form exact match, "
            "for example 'LiquidNitrogen'), `status` (Unknown / Available / "
            "Degraded / Unavailable / Recovering / Decommissioned). Pass "
            "`cursor` from a previous page's `next_cursor` to fetch the next "
            "page."
        ),
    )
    async def list_supplies_tool(  # pyright: ignore[reportUnusedFunction]
        ctx: Context[Any, Any, Any],
        cursor: Annotated[
            str | None,
            Field(description="Opaque cursor from a previous response."),
        ] = None,
        limit: Annotated[
            int,
            Field(ge=1, le=100, description="Page size cap (max 100)."),
        ] = 50,
        facility_code: Annotated[
            str | None,
            Field(
                min_length=1,
                max_length=FACILITY_CODE_MAX_LENGTH,
                pattern=r"^[a-z0-9-]{1,32}$",
                description=(
                    "Optional facility-code filter (exact match, lowercase ASCII "
                    "alphanumeric plus dash, 1-32 chars); omit to list all."
                ),
            ),
        ] = None,
        containing_asset_id: Annotated[
            UUID | None,
            Field(
                description=(
                    "Optional containing-Asset-id filter (exact match; non-null "
                    "projection rows only); omit to include facility-scope."
                ),
            ),
        ] = None,
        kind: Annotated[
            str | None,
            Field(
                min_length=1,
                max_length=SUPPLY_KIND_MAX_LENGTH,
                description="Optional kind filter (exact match); omit to list all.",
            ),
        ] = None,
        status: Annotated[
            SupplyStatusFilter | None,
            Field(description="Optional status filter; omit to list all."),
        ] = None,
    ) -> SupplyListOutput:
        handler = get_handler()
        page = await handler(
            ListSupplies(
                cursor=cursor,
                limit=limit,
                facility_code=facility_code,
                containing_asset_id=containing_asset_id,
                kind=kind,
                status=status,
            ),
            principal_id=get_mcp_principal_id(ctx),
            correlation_id=current_correlation_id(),
            surface_id=get_mcp_surface_id(),
        )
        return SupplyListOutput(
            items=[
                SupplySummaryRow(
                    supply_id=item.supply_id,
                    kind=item.kind,
                    name=item.name,
                    facility_code=item.facility_code,
                    containing_asset_id=item.containing_asset_id,
                    status=SupplyStatus(item.status),
                    registered_at=item.registered_at,
                    last_status_changed_at=item.last_status_changed_at,
                    last_status_reason=item.last_status_reason,
                    last_trigger=(
                        TriggerSource(item.last_trigger) if item.last_trigger is not None else None
                    ),
                )
                for item in page.items
            ],
            next_cursor=page.next_cursor,
        )
