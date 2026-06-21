"""Application handler for the `list_runs` query slice.

Reads `proj_run_summary` via the cross-BC
`infrastructure.list_query.make_list_query_handler` factory. Two
optional filters (status + plan_id) plus cursor pagination,
declared as `ScalarFilter` specs; the factory composes only the
WHERE fragments for filters the caller actually passed (sargable,
indexable; replaces the legacy `$N IS NULL OR column = $N` smart-
logic pattern documented in the factory module).

`subject_id` and `raid` flow through to the result row from the
genesis event; both are nullable (Plan-only Runs without a Subject;
ISO-23527 RAiD optional).

BOLA: command-name gating only. Per-row scoping deferred until ReBAC
(see `memory/project_deferred.md`).
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol, cast
from uuid import UUID

from cora.infrastructure.kernel import Kernel
from cora.infrastructure.list_query import ScalarFilter, make_list_query_handler
from cora.infrastructure.routing import NIL_SENTINEL_ID
from cora.run.errors import UnauthorizedError
from cora.run.features.list_runs.query import ListRuns, RunStatusFilter


@dataclass(frozen=True)
class RunSummaryItem:
    """One row from the run projection.

    `override_parameters_present` reflects whether
    RunStarted's `override_parameters` payload was non-empty
    (operator customized parameters at start time). Default FALSE
    on legacy rows + on Runs started with no overrides. The full
    overrides + effective_parameters dicts live on the event;
    `get_run` surfaces them on demand.

    `campaign_id` (Campaign Watch #10) is the Campaign
    this Run is a member of (at-start via `RunStarted.campaign_id`,
    or post-hoc via `RunAddedToCampaign`). NULL for standalone Runs
    and for Runs whose membership was removed via
    `RunRemovedFromCampaign`. Surfaces the `?campaign_id=` filter on
    `list_runs`.
    """

    run_id: UUID
    name: str
    plan_id: UUID
    subject_id: UUID | None
    raid: str | None
    status: RunStatusFilter
    created_at: datetime
    running_since: datetime | None
    override_parameters_present: bool
    campaign_id: UUID | None


@dataclass(frozen=True)
class RunListPage:
    """A page of run summaries plus the cursor for the next page."""

    items: list[RunSummaryItem]
    next_cursor: str | None


class Handler(Protocol):
    """Callable interface every list_runs handler implements."""

    async def __call__(
        self,
        query: ListRuns,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> RunListPage: ...


_SELECT_COLUMNS = (
    "run_id, name, plan_id, subject_id, raid, status, created_at, running_since, "
    "override_parameters_present, campaign_id"
)


def _row_to_item(row: Any) -> RunSummaryItem:
    return RunSummaryItem(
        run_id=row["run_id"],
        name=str(row["name"]),
        plan_id=row["plan_id"],
        subject_id=row["subject_id"],
        raid=str(row["raid"]) if row["raid"] is not None else None,
        status=cast("RunStatusFilter", str(row["status"])),
        created_at=row["created_at"],
        running_since=row["running_since"],
        override_parameters_present=bool(row["override_parameters_present"]),
        campaign_id=row["campaign_id"],
    )


def _log_fields(query: ListRuns) -> dict[str, Any]:
    return {
        "status": query.status,
        "plan_id": str(query.plan_id) if query.plan_id else None,
        "campaign_id": str(query.campaign_id) if query.campaign_id else None,
    }


def bind(deps: Kernel) -> Handler:
    """Build a list_runs handler closed over the shared deps."""
    return make_list_query_handler(
        deps,
        query_name="ListRuns",
        log_prefix="list_runs",
        unauthorized_error=UnauthorizedError,
        table="proj_run_summary",
        select_columns=_SELECT_COLUMNS,
        time_column="created_at",
        id_column="run_id",
        filters=[
            ScalarFilter(attr="status"),
            ScalarFilter(attr="plan_id"),
            ScalarFilter(attr="campaign_id"),
        ],
        row_to_item=_row_to_item,
        item_cursor_at=lambda item: item.created_at,
        item_cursor_id=lambda item: item.run_id,
        page_from=lambda items, next_cursor: RunListPage(items=items, next_cursor=next_cursor),
        extract_log_fields=_log_fields,
    )


__all__ = [
    "Handler",
    "RunListPage",
    "RunSummaryItem",
    "bind",
]
