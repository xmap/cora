"""HTTP route for the `list_runs` query slice.

`GET /runs?cursor=...&limit=50&status=Running&plan_id=<uuid>` returns
`{"items": [...], "next_cursor": "..." | null}`.
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
from cora.run.aggregates.run import RUN_NAME_MAX_LENGTH
from cora.run.features.list_runs.handler import Handler
from cora.run.features.list_runs.query import ListRuns, RunStatusFilter

_RAID_MAX_LENGTH = 2048


class RunSummaryDTO(BaseModel):
    """One run in a paginated list."""

    run_id: UUID
    name: str = Field(..., max_length=RUN_NAME_MAX_LENGTH)
    plan_id: UUID
    subject_id: UUID | None
    raid: str | None = Field(default=None, max_length=_RAID_MAX_LENGTH)
    status: RunStatusFilter
    created_at: datetime
    override_parameters_present: bool = Field(
        default=False,
        description=(
            "True iff RunStarted's override_parameters payload was "
            "non-empty (operator customized parameters at start time). "
            "The full overrides + effective_parameters "
            "dicts are loaded on demand via `get_run`."
        ),
    )
    campaign_id: UUID | None = Field(
        default=None,
        description=(
            "Campaign this Run is a member of. Set at start time "
            "(StartRun.campaign_id) or post-hoc "
            "(add_run_to_campaign). NULL for standalone Runs. "
            "Campaign membership snapshot."
        ),
    )
    capture_code: str | None = Field(
        default=None,
        description=(
            "Deployment-declared capture identifier a witnessed genesis "
            "stamps onto external_refs (slice 13). NULL for a Conducted "
            "Run. NOT the observed capture file path: that value is "
            "personal data and is resolved per-run via `GET "
            "/runs/{run_id}`, never surfaced on this bulk list."
        ),
    )


class RunListResponse(BaseModel):
    """Page of runs plus opaque next-page cursor."""

    items: list[RunSummaryDTO]
    next_cursor: str | None = None


def _get_handler(request: Request) -> Handler:
    handler: Handler = request.app.state.run.list_runs
    return handler


router = APIRouter(tags=["run"])


@router.get(
    "/runs",
    status_code=status.HTTP_200_OK,
    response_model=RunListResponse,
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
    summary="List runs with cursor pagination + status/plan_id/campaign_id filters",
)
async def list_runs(
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
        RunStatusFilter | None,
        Query(
            alias="status",
            description=(
                "Optional status filter (Running / Held / Completed / "
                "Aborted / Stopped / Truncated). Omit for all."
            ),
        ),
    ] = None,
    plan_id: Annotated[
        UUID | None,
        Query(description="Optional Plan-id filter."),
    ] = None,
    campaign_id: Annotated[
        UUID | None,
        Query(
            description=(
                "Optional Campaign-id filter: returns Runs that are members of the given Campaign."
            ),
        ),
    ] = None,
) -> RunListResponse:
    page = await handler(
        ListRuns(
            cursor=cursor,
            limit=limit,
            status=status_filter,
            plan_id=plan_id,
            campaign_id=campaign_id,
        ),
        principal_id=principal_id,
        correlation_id=cid,
        surface_id=surface_id,
    )
    return RunListResponse(
        items=[
            RunSummaryDTO(
                run_id=item.run_id,
                name=item.name,
                plan_id=item.plan_id,
                subject_id=item.subject_id,
                raid=item.raid,
                status=item.status,
                created_at=item.created_at,
                override_parameters_present=item.override_parameters_present,
                campaign_id=item.campaign_id,
                capture_code=item.capture_code,
            )
            for item in page.items
        ],
        next_cursor=page.next_cursor,
    )
