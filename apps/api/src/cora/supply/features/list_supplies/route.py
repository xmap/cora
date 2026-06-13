"""HTTP route for the `list_supplies` query slice.

`GET /supplies` with optional query params:
  `cursor`, `limit`, `facility_code`, `containing_asset_id`, `kind`, `status`.
Returns `{"items": [...], "next_cursor": "..." | null}`.

The prior `?scope=` filter was retired in favor of
`?facility_code=` + `?containing_asset_id=` per
[[project_supply_sector_disposition]] Option A; the SupplyScope
retirement cleanup then dropped the `scope` value from the
projection and the returned item DTOs entirely.
"""

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, status
from pydantic import BaseModel, Field

from cora.infrastructure.routing import (
    ErrorResponse,
    get_correlation_id,
    get_principal_id,
    get_surface_id,
)
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


class SupplySummaryDTO(BaseModel):
    """One supply in a paginated list."""

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


class SupplyListResponse(BaseModel):
    """Page of supplies plus opaque next-page cursor."""

    items: list[SupplySummaryDTO]
    next_cursor: str | None = None


def _get_handler(request: Request) -> Handler:
    handler: Handler = request.app.state.supply.list_supplies
    return handler


router = APIRouter(tags=["supply"])


@router.get(
    "/supplies",
    status_code=status.HTTP_200_OK,
    response_model=SupplyListResponse,
    responses={
        status.HTTP_403_FORBIDDEN: {
            "model": ErrorResponse,
            "description": "Authorize port denied the query.",
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": (
                "Query parameters failed validation OR `cursor` was "
                "malformed (corrupt base64, missing separator, bad "
                "timestamp / UUID)."
            ),
        },
    },
    summary="List supplies with cursor pagination + facility/containing-asset/kind/status filters",
)
async def list_supplies(
    handler: Annotated[Handler, Depends(_get_handler)],
    cid: Annotated[UUID, Depends(get_correlation_id)],
    principal_id: Annotated[UUID, Depends(get_principal_id)],
    surface_id: Annotated[UUID, Depends(get_surface_id)],
    cursor: Annotated[
        str | None,
        Query(description="Opaque cursor from a previous page's `next_cursor`."),
    ] = None,
    limit: Annotated[
        int,
        Query(ge=1, le=100, description="Page size; capped at 100."),
    ] = 50,
    facility_code: Annotated[
        str | None,
        Query(
            min_length=1,
            max_length=FACILITY_CODE_MAX_LENGTH,
            pattern=r"^[a-z0-9-]{1,32}$",
            description=(
                "Optional cross-deployment Facility-code filter (exact match; "
                "for example 'aps'). Lowercase ASCII alphanumeric plus dash, "
                "1-32 chars. Omit to return all facilities."
            ),
        ),
    ] = None,
    containing_asset_id: Annotated[
        UUID | None,
        Query(
            description=(
                "Optional containing-Asset-id filter (exact match against the "
                "Equipment BC Asset id; non-null projection rows only). Omit to "
                "return both facility-scope and contained Supplies."
            ),
        ),
    ] = None,
    kind: Annotated[
        str | None,
        Query(
            min_length=1,
            max_length=SUPPLY_KIND_MAX_LENGTH,
            description=(
                "Optional kind filter (free-form, exact match; for example "
                "'LiquidNitrogen'). Omit to return all kinds."
            ),
        ),
    ] = None,
    status_filter: Annotated[
        SupplyStatusFilter | None,
        Query(
            alias="status",
            description=(
                "Optional status filter (one of: Unknown, Available, Degraded, "
                "Unavailable, Recovering, Decommissioned). Omit to return all "
                "statuses including Decommissioned (no default-exclude; matches "
                "Asset / Subject sibling-BC convention)."
            ),
        ),
    ] = None,
) -> SupplyListResponse:
    page = await handler(
        ListSupplies(
            cursor=cursor,
            limit=limit,
            facility_code=facility_code,
            containing_asset_id=containing_asset_id,
            kind=kind,
            status=status_filter,
        ),
        principal_id=principal_id,
        correlation_id=cid,
        surface_id=surface_id,
    )
    return SupplyListResponse(
        items=[
            SupplySummaryDTO(
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
