"""Application handler for the `list_procedures` query slice.

Reads `proj_operation_procedure_summary` via the cross-BC
`infrastructure.list_query.make_list_query_handler` factory. Four
optional filters: three scalar (`status` / `kind` / `parent_run_id`)
plus one array-membership over the GIN-indexed `target_asset_ids`
column (singular `target_asset_id` query field matched against the
plural array). Cursor pagination on `(registered_at, procedure_id)`.

`last_status_changed_at` / `last_status_reason` / `interrupted_at` /
`activity_logbook_id` flow through to the result row: nullable until the
respective transition / lazy-open lands.

BOLA: command-name gating only. Per-row scoping deferred until ReBAC.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol
from uuid import UUID

from cora.infrastructure.kernel import Kernel
from cora.infrastructure.list_query import (
    ArrayContainsFilter,
    ScalarFilter,
    make_list_query_handler,
)
from cora.infrastructure.routing import NIL_SENTINEL_ID
from cora.operation.errors import UnauthorizedError
from cora.operation.features.list_procedures.query import ListProcedures


@dataclass(frozen=True)
class ProcedureSummaryItem:
    """One row from the procedure projection."""

    procedure_id: UUID
    name: str
    kind: str
    target_asset_ids: list[UUID]
    parent_run_id: UUID | None
    status: str
    activity_logbook_id: UUID | None
    registered_at: datetime
    last_status_changed_at: datetime | None
    last_status_reason: str | None
    interrupted_at: datetime | None
    iteration_count: int


@dataclass(frozen=True)
class ProcedureListPage:
    """A page of procedure summaries plus the cursor for the next page."""

    items: list[ProcedureSummaryItem]
    next_cursor: str | None


class Handler(Protocol):
    """Callable interface every list_procedures handler implements."""

    async def __call__(
        self,
        query: ListProcedures,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> ProcedureListPage: ...


_SELECT_COLUMNS = (
    "procedure_id, name, kind, target_asset_ids, parent_run_id, status, "
    "activity_logbook_id, registered_at, "
    "last_status_changed_at, last_status_reason, interrupted_at, iteration_count"
)


def _row_to_item(row: Any) -> ProcedureSummaryItem:
    return ProcedureSummaryItem(
        procedure_id=row["procedure_id"],
        name=str(row["name"]),
        kind=str(row["kind"]),
        target_asset_ids=list(row["target_asset_ids"]),
        parent_run_id=row["parent_run_id"],
        status=str(row["status"]),
        activity_logbook_id=row["activity_logbook_id"],
        registered_at=row["registered_at"],
        last_status_changed_at=row["last_status_changed_at"],
        last_status_reason=(
            str(row["last_status_reason"]) if row["last_status_reason"] is not None else None
        ),
        interrupted_at=row["interrupted_at"],
        iteration_count=int(row["iteration_count"]),
    )


def _log_fields(query: ListProcedures) -> dict[str, Any]:
    return {
        "status": query.status,
        "kind": query.kind,
        "parent_run_id": str(query.parent_run_id) if query.parent_run_id else None,
        "target_asset_id": str(query.target_asset_id) if query.target_asset_id else None,
    }


def bind(deps: Kernel) -> Handler:
    """Build a list_procedures handler closed over the shared deps."""
    return make_list_query_handler(
        deps,
        query_name="ListProcedures",
        log_prefix="list_procedures",
        unauthorized_error=UnauthorizedError,
        table="proj_operation_procedure_summary",
        select_columns=_SELECT_COLUMNS,
        time_column="registered_at",
        id_column="procedure_id",
        filters=[
            ScalarFilter(attr="status"),
            ScalarFilter(attr="kind"),
            ScalarFilter(attr="parent_run_id"),
            ArrayContainsFilter(attr="target_asset_id", column="target_asset_ids"),
        ],
        row_to_item=_row_to_item,
        item_cursor_at=lambda item: item.registered_at,
        item_cursor_id=lambda item: item.procedure_id,
        page_from=lambda items, next_cursor: ProcedureListPage(
            items=items, next_cursor=next_cursor
        ),
        extract_log_fields=_log_fields,
    )


__all__ = [
    "Handler",
    "ProcedureListPage",
    "ProcedureSummaryItem",
    "bind",
]
