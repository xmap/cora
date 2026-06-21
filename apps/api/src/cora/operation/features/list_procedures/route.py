"""HTTP route for the `list_procedures` query slice.

`GET /procedures` accepts these optional query params: `cursor`,
`limit`, `status`, `kind`, `parent_run_id`, `target_asset_id`.
Returns `{"items": [...], "next_cursor": "..." | null}`.
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
from cora.operation.aggregates.procedure import (
    PROCEDURE_KIND_MAX_LENGTH,
    PROCEDURE_NAME_MAX_LENGTH,
    ProcedureStatus,
)
from cora.operation.features.list_procedures.handler import Handler
from cora.operation.features.list_procedures.query import (
    ListProcedures,
    ProcedureStatusFilter,
)
from cora.shared.text_bounds import REASON_MAX_LENGTH


class ProcedureSummaryDTO(BaseModel):
    """One procedure in a paginated list."""

    procedure_id: UUID
    name: str = Field(..., max_length=PROCEDURE_NAME_MAX_LENGTH)
    kind: str = Field(..., max_length=PROCEDURE_KIND_MAX_LENGTH)
    target_asset_ids: list[UUID]
    parent_run_id: UUID | None = None
    status: ProcedureStatus
    activity_logbook_id: UUID | None = None
    registered_at: datetime
    last_status_changed_at: datetime | None = None
    last_status_reason: str | None = Field(default=None, max_length=REASON_MAX_LENGTH)
    interrupted_at: datetime | None = None
    iteration_count: int = 0


class ProcedureListResponse(BaseModel):
    """Page of procedures plus opaque next-page cursor."""

    items: list[ProcedureSummaryDTO]
    next_cursor: str | None = None


def _get_handler(request: Request) -> Handler:
    handler: Handler = request.app.state.operation.list_procedures
    return handler


router = APIRouter(tags=["operation"])


@router.get(
    "/procedures",
    status_code=status.HTTP_200_OK,
    response_model=ProcedureListResponse,
    responses={
        status.HTTP_403_FORBIDDEN: {
            "model": ErrorResponse,
            "description": "Authorize port denied the query.",
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": ("Query parameters failed validation OR `cursor` was malformed."),
        },
    },
    summary=(
        "List procedures with cursor pagination + status / kind / "
        "parent_run_id / target_asset_id filters"
    ),
)
async def list_procedures(
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
    status_filter: Annotated[
        ProcedureStatusFilter | None,
        Query(
            alias="status",
            description=(
                "Optional status filter (one of: Defined, Running, Held, "
                "Completed, Aborted, Truncated). Omit to return all statuses."
            ),
        ),
    ] = None,
    kind: Annotated[
        str | None,
        Query(
            min_length=1,
            max_length=PROCEDURE_KIND_MAX_LENGTH,
            description=(
                "Optional kind filter (free-form, exact match; for example "
                "'bakeout', 'alignment'). Omit to return all kinds."
            ),
        ),
    ] = None,
    parent_run_id: Annotated[
        UUID | None,
        Query(
            description=(
                "Optional Phase-of-Run filter; matches Procedures whose "
                "parent_run_id equals this UUID. Omit to return Procedures "
                "with any parent (including standalone)."
            ),
        ),
    ] = None,
    target_asset_id: Annotated[
        UUID | None,
        Query(
            description=(
                "Optional target-Asset filter; matches Procedures whose "
                "target_asset_ids array contains this UUID."
            ),
        ),
    ] = None,
) -> ProcedureListResponse:
    page = await handler(
        ListProcedures(
            cursor=cursor,
            limit=limit,
            status=status_filter,
            kind=kind,
            parent_run_id=parent_run_id,
            target_asset_id=target_asset_id,
        ),
        principal_id=principal_id,
        correlation_id=cid,
        surface_id=surface_id,
    )
    return ProcedureListResponse(
        items=[
            ProcedureSummaryDTO(
                procedure_id=item.procedure_id,
                name=item.name,
                kind=item.kind,
                target_asset_ids=item.target_asset_ids,
                parent_run_id=item.parent_run_id,
                status=ProcedureStatus(item.status),
                activity_logbook_id=item.activity_logbook_id,
                registered_at=item.registered_at,
                last_status_changed_at=item.last_status_changed_at,
                last_status_reason=item.last_status_reason,
                interrupted_at=item.interrupted_at,
                iteration_count=item.iteration_count,
            )
            for item in page.items
        ],
        next_cursor=page.next_cursor,
    )
