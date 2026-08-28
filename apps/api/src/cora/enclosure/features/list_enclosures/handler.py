"""Application handler for the `list_enclosures` query slice.

Reads `proj_enclosure_summary` via the cross-BC
`infrastructure.list_query.make_list_query_handler` factory. Three
optional scalar filters (`lifecycle` / `permit_status` /
`facility_code`) plus cursor pagination, declared as `ScalarFilter`
specs matching the projection's two indexes. Cursor pagination is
keyed on `(registered_at, enclosure_id)`.

BOLA: command-name gating only. Per-row scoping deferred until ReBAC
(see `memory/project_deferred.md`).

Carries both clocks from the projection (`last_permit_status_changed_at`
+ `last_source_observed_at`); see
`cora.enclosure.projections.enclosure` for why neither may substitute
for the other.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol
from uuid import UUID

from cora.enclosure.errors import UnauthorizedError
from cora.enclosure.features.list_enclosures.query import (
    LifecycleFilter,
    ListEnclosures,
    PermitStatusFilter,
)
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.list_query import ScalarFilter, make_list_query_handler
from cora.infrastructure.routing import NIL_SENTINEL_ID


@dataclass(frozen=True)
class EnclosureSummaryItem:
    """One row from the enclosure projection."""

    enclosure_id: UUID
    name: str
    facility_code: str
    lifecycle: LifecycleFilter
    permit_status: PermitStatusFilter
    registered_at: datetime
    registered_by: UUID
    last_permit_status_changed_at: datetime | None
    """CORA's ingest time of the last permit-status CHANGE. Advances
    only on a change, so a stale value means "no transition since",
    never "not observed since"."""
    last_permit_status_reason: str | None
    last_trigger: str | None
    last_source_kind: str | None
    last_source_id: str | None
    last_source_observed_at: datetime | None
    """The substrate's own time for the reading behind the last change,
    or `None` when the substrate reported none (the ordinary case at
    APS 2-BM). Never a substitute for `last_permit_status_changed_at`."""
    decommissioned_at: datetime | None
    decommissioned_by: UUID | None


@dataclass(frozen=True)
class EnclosureListPage:
    """A page of enclosure summaries plus the cursor for the next page."""

    items: list[EnclosureSummaryItem]
    next_cursor: str | None


class Handler(Protocol):
    """Callable interface every list_enclosures handler implements."""

    async def __call__(
        self,
        query: ListEnclosures,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> EnclosureListPage: ...


_SELECT_COLUMNS = (
    "enclosure_id, name, facility_code, lifecycle, permit_status, "
    "registered_at, registered_by, "
    "last_permit_status_changed_at, last_permit_status_reason, last_trigger, "
    "last_source_kind, last_source_id, last_source_observed_at, "
    "decommissioned_at, decommissioned_by"
)


def _row_to_item(row: Any) -> EnclosureSummaryItem:
    return EnclosureSummaryItem(
        enclosure_id=row["enclosure_id"],
        name=str(row["name"]),
        facility_code=str(row["facility_code"]),
        lifecycle=row["lifecycle"],
        permit_status=row["permit_status"],
        registered_at=row["registered_at"],
        registered_by=row["registered_by"],
        last_permit_status_changed_at=row["last_permit_status_changed_at"],
        last_permit_status_reason=(
            str(row["last_permit_status_reason"])
            if row["last_permit_status_reason"] is not None
            else None
        ),
        last_trigger=str(row["last_trigger"]) if row["last_trigger"] is not None else None,
        last_source_kind=(
            str(row["last_source_kind"]) if row["last_source_kind"] is not None else None
        ),
        last_source_id=str(row["last_source_id"]) if row["last_source_id"] is not None else None,
        last_source_observed_at=row["last_source_observed_at"],
        decommissioned_at=row["decommissioned_at"],
        decommissioned_by=row["decommissioned_by"],
    )


def _log_fields(query: ListEnclosures) -> dict[str, Any]:
    return {
        "lifecycle": query.lifecycle,
        "permit_status": query.permit_status,
        "facility_code": query.facility_code,
    }


def bind(deps: Kernel) -> Handler:
    """Build a list_enclosures handler closed over the shared deps."""
    return make_list_query_handler(
        deps,
        query_name="ListEnclosures",
        log_prefix="list_enclosures",
        unauthorized_error=UnauthorizedError,
        table="proj_enclosure_summary",
        select_columns=_SELECT_COLUMNS,
        time_column="registered_at",
        id_column="enclosure_id",
        filters=[
            ScalarFilter(attr="lifecycle"),
            ScalarFilter(attr="permit_status"),
            ScalarFilter(attr="facility_code"),
        ],
        row_to_item=_row_to_item,
        item_cursor_at=lambda item: item.registered_at,
        item_cursor_id=lambda item: item.enclosure_id,
        page_from=lambda items, next_cursor: EnclosureListPage(
            items=items, next_cursor=next_cursor
        ),
        extract_log_fields=_log_fields,
    )


__all__ = [
    "EnclosureListPage",
    "EnclosureSummaryItem",
    "Handler",
    "bind",
]
