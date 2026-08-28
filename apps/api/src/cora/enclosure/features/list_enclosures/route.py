"""HTTP route for the `list_enclosures` query slice.

`GET /enclosures?cursor=...&limit=50&lifecycle=Active&permit_status=Permitted`
returns `{"items": [...], "next_cursor": "..." | null}`.
"""

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, status
from pydantic import BaseModel, Field

from cora.enclosure.aggregates.enclosure import ENCLOSURE_NAME_MAX_LENGTH
from cora.enclosure.features.list_enclosures.handler import Handler
from cora.enclosure.features.list_enclosures.query import (
    LifecycleFilter,
    ListEnclosures,
    PermitStatusFilter,
)
from cora.infrastructure.routing import (
    ErrorResponse,
    get_correlation_id,
    get_principal_id,
    get_surface_id,
)
from cora.shared.text_bounds import REASON_MAX_LENGTH


class EnclosureSummaryDTO(BaseModel):
    """One enclosure in a paginated list."""

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
            "CORA's ingest time of the last permit-status CHANGE, from the "
            "event's occurred_at. Advances only on a change: a stale value "
            "means 'no transition since', never 'not observed since'."
        ),
    )
    last_permit_status_reason: str | None = Field(default=None, max_length=REASON_MAX_LENGTH)
    last_trigger: str | None = Field(
        default=None,
        description="One of Operator / Monitor / Auto, or null before any observation.",
    )
    last_source_kind: str | None = None
    last_source_id: str | None = None
    last_source_observed_at: datetime | None = Field(
        default=None,
        description=(
            "The substrate's own time for the reading behind the last change, "
            "or null when the substrate reported none (the ordinary case at "
            "APS 2-BM). Never a substitute for last_permit_status_changed_at."
        ),
    )
    decommissioned_at: datetime | None = None
    decommissioned_by: UUID | None = None


class EnclosureListResponse(BaseModel):
    """Page of enclosures plus opaque next-page cursor."""

    items: list[EnclosureSummaryDTO]
    next_cursor: str | None = None


def _get_handler(request: Request) -> Handler:
    handler: Handler = request.app.state.enclosure.list_enclosures
    return handler


router = APIRouter(tags=["enclosure"])


@router.get(
    "/enclosures",
    status_code=status.HTTP_200_OK,
    response_model=EnclosureListResponse,
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
    summary="List enclosures: cursor pagination + lifecycle/permit_status/facility_code filters",
)
async def list_enclosures(
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
    lifecycle: Annotated[
        LifecycleFilter | None,
        Query(description="Optional lifecycle filter (Active / Decommissioned). Omit for all."),
    ] = None,
    permit_status: Annotated[
        PermitStatusFilter | None,
        Query(description="Optional permit-status filter (Unknown / Permitted / NotPermitted)."),
    ] = None,
    facility_code: Annotated[
        str | None,
        Query(
            min_length=1,
            max_length=32,
            pattern=r"^[a-z0-9-]{1,32}$",
            description="Optional facility filter; cross-deployment convergent slug.",
        ),
    ] = None,
) -> EnclosureListResponse:
    page = await handler(
        ListEnclosures(
            cursor=cursor,
            limit=limit,
            lifecycle=lifecycle,
            permit_status=permit_status,
            facility_code=facility_code,
        ),
        principal_id=principal_id,
        correlation_id=cid,
        surface_id=surface_id,
    )
    return EnclosureListResponse(
        items=[
            EnclosureSummaryDTO(
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


__all__ = ["EnclosureListResponse", "EnclosureSummaryDTO", "router"]
