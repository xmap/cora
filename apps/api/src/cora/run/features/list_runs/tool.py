"""MCP tool for the `list_runs` query slice."""

from collections.abc import Callable
from datetime import datetime
from typing import Annotated, Any
from uuid import UUID

from mcp.server.fastmcp import Context, FastMCP
from pydantic import BaseModel, Field

from cora.infrastructure.mcp_principal import get_mcp_principal_id
from cora.infrastructure.observability import current_correlation_id
from cora.infrastructure.routing import get_mcp_surface_id
from cora.run.aggregates.run import RUN_NAME_MAX_LENGTH
from cora.run.features.list_runs.handler import Handler
from cora.run.features.list_runs.query import ListRuns, RunStatusFilter

_RAID_MAX_LENGTH = 2048


class RunSummaryRow(BaseModel):
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
            "True iff the Run was started with operator-supplied "
            "override_parameters. The full overrides + "
            "effective_parameters dicts are loaded on demand via `get_run`."
        ),
    )
    campaign_id: UUID | None = Field(
        default=None,
        description=(
            "Campaign this Run is a member of (at-start or post-hoc). NULL for standalone Runs."
        ),
    )
    capture_code: str | None = Field(
        default=None,
        description=(
            "Deployment-declared capture identifier a witnessed genesis "
            "stamps onto external_refs (slice 13). NULL for a Conducted "
            "Run. NOT the observed capture file path: that value is "
            "personal data, resolved per-run via the `get_run` tool, "
            "never surfaced on this bulk list."
        ),
    )


class RunListOutput(BaseModel):
    """Structured output of the `list_runs` MCP tool."""

    items: list[RunSummaryRow]
    next_cursor: str | None = None


def register(mcp: FastMCP, *, get_handler: Callable[[], Handler]) -> None:
    """Register the `list_runs` tool on the given MCP server."""

    @mcp.tool(
        name="list_runs",
        description=(
            "Cursor-paginated list of runs (Plan + optional Subject "
            "execution instances). Optional `status` filter accepts: "
            "Running, Held, Completed, Aborted, Stopped, Truncated. "
            "Optional `plan_id` filter narrows to Runs bound to one "
            "Plan. Optional `campaign_id` filter narrows to Runs that "
            "are members of one Campaign. Pass `cursor` from a previous "
            "page's `next_cursor` to fetch the next page."
        ),
    )
    async def list_runs_tool(  # pyright: ignore[reportUnusedFunction]
        ctx: Context[Any, Any, Any],
        cursor: Annotated[
            str | None,
            Field(description="Opaque cursor from a previous response."),
        ] = None,
        limit: Annotated[
            int,
            Field(ge=1, le=100, description="Page size cap (max 100)."),
        ] = 50,
        status: Annotated[
            RunStatusFilter | None,
            Field(description="Optional status filter; omit to list all."),
        ] = None,
        plan_id: Annotated[
            UUID | None,
            Field(description="Optional Plan-id filter."),
        ] = None,
        campaign_id: Annotated[
            UUID | None,
            Field(description="Optional Campaign-id filter."),
        ] = None,
    ) -> RunListOutput:
        handler = get_handler()
        page = await handler(
            ListRuns(
                cursor=cursor,
                limit=limit,
                status=status,
                plan_id=plan_id,
                campaign_id=campaign_id,
            ),
            principal_id=get_mcp_principal_id(ctx),
            correlation_id=current_correlation_id(),
            surface_id=get_mcp_surface_id(),
        )
        return RunListOutput(
            items=[
                RunSummaryRow(
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
