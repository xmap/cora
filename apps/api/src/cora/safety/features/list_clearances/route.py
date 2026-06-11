"""HTTP route for the `list_clearances` query slice.

`GET /clearances` accepts these optional query params: `cursor`,
`limit`, `template_id`, `template_code`, `status`, `risk_band`, `facility_code`,
`binds_to_subject_id`, `binds_to_asset_id`, `binds_to_run_id`,
`binds_to_procedure_id`. Returns `{"items": [...], "next_cursor": "..." | null}`.

**ExternalRefBinding refs (`{"scheme": "proposal", "value": "GUP-12345"}`
and similar anti-corruption refs for upstream-deferred concepts like
BTR / LabVisit / Session) are NOT filterable via this endpoint.** The
projection's 4 UUID[] columns only carry the typed CORA-aggregate
bindings (Subject / Asset / Run / Procedure). Clearances with only
ExternalRefBinding entries are returned only when filters other than
`binds_to_*_id` match (template_id / template_code / status / risk_band / facility_code).
Fetch by id via `get_clearance` when ExternalRefBinding inspection is
required.

**Reviewers chain is NOT in the response** (`last_reviewed_by`
is the only reviewer field surfaced; the full review_steps tuple lives on
the aggregate stream). Fetch by id via `get_clearance` when the chain
is needed.
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
from cora.safety.aggregates.clearance import ClearanceStatus
from cora.safety.aggregates.clearance.hazard_classification import RiskBand
from cora.safety.aggregates.clearance.state import (
    CLEARANCE_EXTERNAL_ID_MAX_LENGTH,
    CLEARANCE_TITLE_MAX_LENGTH,
)
from cora.safety.features.list_clearances.handler import Handler
from cora.safety.features.list_clearances.query import (
    ClearanceStatusFilter,
    ListClearances,
    RiskBandFilter,
)


class BindingsByKind(BaseModel):
    """Per-kind binding-id arrays surfaced on the list response.

    Four explicit `<kind>_ids` fields (matching the projection's UUID[]
    columns 1:1, mirroring the view-model's `subject_binding_ids` /
    `asset_binding_ids` / `run_binding_ids` / `procedure_binding_ids`
    plural shape) instead of a `dict[str, list[UUID]]`: OpenAPI codegen
    produces typed accessors; SDK consumers see the locked set of keys
    without `additionalProperties` ambiguity. ExternalRefBinding refs are
    NOT surfaced here (anti-corruption refs, not projected; see route
    summary).
    """

    subject_ids: list[UUID] = Field(default_factory=list[UUID])
    asset_ids: list[UUID] = Field(default_factory=list[UUID])
    run_ids: list[UUID] = Field(default_factory=list[UUID])
    procedure_ids: list[UUID] = Field(default_factory=list[UUID])


class ClearanceSummaryDTO(BaseModel):
    """One clearance in a paginated list."""

    clearance_id: UUID
    template_id: UUID
    template_code: str
    facility_code: str
    title: str = Field(..., max_length=CLEARANCE_TITLE_MAX_LENGTH)
    external_id: str | None = Field(default=None, max_length=CLEARANCE_EXTERNAL_ID_MAX_LENGTH)
    status: ClearanceStatus
    risk_band: RiskBand | None = None
    bindings: BindingsByKind
    parent_id: UUID | None = None
    registered_at: datetime
    last_status_changed_at: datetime | None = None
    last_status_reason: str | None = None
    last_reviewed_by: UUID | None = None
    valid_from: datetime | None = None
    valid_until: datetime | None = None
    next_review_due_at: datetime | None = None


class ClearanceListResponse(BaseModel):
    """Page of clearances plus opaque next-page cursor."""

    items: list[ClearanceSummaryDTO]
    next_cursor: str | None = None


def _get_handler(request: Request) -> Handler:
    handler: Handler = request.app.state.safety.list_clearances
    return handler


router = APIRouter(tags=["safety"])


@router.get(
    "/clearances",
    status_code=status.HTTP_200_OK,
    response_model=ClearanceListResponse,
    responses={
        status.HTTP_403_FORBIDDEN: {
            "model": ErrorResponse,
            "description": "Authorize port denied the query.",
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": "Query parameters failed validation OR `cursor` was malformed.",
        },
    },
    summary=(
        "List clearances with cursor pagination + template_id / template_code / "
        "status / risk_band / facility_code / binds_to_*_id filters. "
        "ExternalRefBinding refs "
        "not filterable; review_steps chain not surfaced (fetch get_clearance "
        "for both)."
    ),
)
async def list_clearances(
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
    template_id: Annotated[
        UUID | None,
        Query(description="Optional template-id filter (exact match)."),
    ] = None,
    template_code: Annotated[
        str | None,
        Query(
            min_length=1,
            max_length=50,
            description="Optional template-code filter (exact match, e.g. 'ESAF').",
        ),
    ] = None,
    status_filter: Annotated[
        ClearanceStatusFilter | None,
        Query(
            alias="status",
            description="Optional status filter (one of the 8 ClearanceStatus values).",
        ),
    ] = None,
    risk_band: Annotated[
        RiskBandFilter | None,
        Query(description="Optional risk-band filter (Green / Yellow / Red)."),
    ] = None,
    facility_code: Annotated[
        str | None,
        Query(
            min_length=1,
            max_length=32,
            pattern=r"^[a-z0-9-]{1,32}$",
            description=(
                "Optional facility filter; cross-deployment convergent slug "
                "(Federation Facility code)."
            ),
        ),
    ] = None,
    binds_to_subject_id: Annotated[
        UUID | None,
        Query(description="Filter clearances binding to this Subject id."),
    ] = None,
    binds_to_asset_id: Annotated[
        UUID | None,
        Query(description="Filter clearances binding to this Asset id."),
    ] = None,
    binds_to_run_id: Annotated[
        UUID | None,
        Query(description="Filter clearances binding to this Run id."),
    ] = None,
    binds_to_procedure_id: Annotated[
        UUID | None,
        Query(description="Filter clearances binding to this Procedure id."),
    ] = None,
) -> ClearanceListResponse:
    page = await handler(
        ListClearances(
            cursor=cursor,
            limit=limit,
            template_id=template_id,
            template_code=template_code,
            status=status_filter,
            risk_band=risk_band,
            facility_code=facility_code,
            binds_to_subject_id=binds_to_subject_id,
            binds_to_asset_id=binds_to_asset_id,
            binds_to_run_id=binds_to_run_id,
            binds_to_procedure_id=binds_to_procedure_id,
        ),
        principal_id=principal_id,
        correlation_id=cid,
        surface_id=surface_id,
    )
    return ClearanceListResponse(
        items=[
            ClearanceSummaryDTO(
                clearance_id=item.clearance_id,
                template_id=item.template_id,
                template_code=item.template_code,
                facility_code=item.facility_code,
                title=item.title,
                external_id=item.external_id,
                status=ClearanceStatus(item.status),
                risk_band=RiskBand(item.risk_band) if item.risk_band is not None else None,
                bindings=BindingsByKind(
                    subject_ids=item.subject_binding_ids,
                    asset_ids=item.asset_binding_ids,
                    run_ids=item.run_binding_ids,
                    procedure_ids=item.procedure_binding_ids,
                ),
                parent_id=item.parent_id,
                registered_at=item.registered_at,
                last_status_changed_at=item.last_status_changed_at,
                last_status_reason=item.last_status_reason,
                last_reviewed_by=item.last_reviewed_by,
                valid_from=item.valid_from,
                valid_until=item.valid_until,
                next_review_due_at=item.next_review_due_at,
            )
            for item in page.items
        ],
        next_cursor=page.next_cursor,
    )


__all__ = ["BindingsByKind", "ClearanceListResponse", "ClearanceSummaryDTO", "router"]
