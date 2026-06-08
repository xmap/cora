"""Application handler for the `list_calibrations` query slice.

Reads `proj_calibration_summary` via the cross-BC
`infrastructure.list_query.make_list_query_handler` factory. Five
optional filters: two scalar (`target_id`, `quantity`)
plus two set-membership on scalar columns (`latest_revision_statuses`,
`latest_revision_source_kinds`). Cursor pagination on
`(defined_at, calibration_id)`.

BOLA: command-name gating only. Per-row scoping deferred until ReBAC
(per `memory/project_authz_future.md`).

Latest-revision columns (`latest_revision_status`,
`latest_revision_source_kind`) are denormalised onto
`proj_calibration_summary` by the projection writer so this slice
doesn't need to JOIN against the per-revision table. Empty calibrations
(no revisions appended yet) carry NULL for both columns; the filter
factory treats NULL as not-matching any list filter.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol
from uuid import UUID

from cora.calibration.errors import UnauthorizedError
from cora.calibration.features.list_calibrations.query import ListCalibrations
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.list_query import (
    ColumnInFilter,
    ScalarFilter,
    make_list_query_handler,
)
from cora.infrastructure.routing import NIL_SENTINEL_ID
from cora.shared.identity import ActorId


@dataclass(frozen=True)
class CalibrationSummaryItem:
    """One row from the calibration projection."""

    calibration_id: UUID
    target_id: UUID
    quantity: str
    operating_point: dict[str, Any]
    description: str | None
    defined_at: datetime
    last_revised_at: datetime
    defined_by: ActorId
    revision_count: int
    latest_revision_status: str | None
    latest_revision_source_kind: str | None


@dataclass(frozen=True)
class CalibrationListPage:
    """A page of calibration summaries plus the cursor for the next page."""

    items: list[CalibrationSummaryItem]
    next_cursor: str | None


class Handler(Protocol):
    """Callable interface every list_calibrations handler implements."""

    async def __call__(
        self,
        query: ListCalibrations,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> CalibrationListPage: ...


_SELECT_COLUMNS = (
    "calibration_id, target_id, quantity, operating_point, "
    "description, defined_at, last_revised_at, defined_by, "
    "revision_count, latest_revision_status, latest_revision_source_kind"
)


def _row_to_item(row: Any) -> CalibrationSummaryItem:
    return CalibrationSummaryItem(
        calibration_id=row["calibration_id"],
        target_id=row["target_id"],
        quantity=str(row["quantity"]),
        operating_point=dict(row["operating_point"]),
        description=(str(row["description"]) if row["description"] is not None else None),
        defined_at=row["defined_at"],
        last_revised_at=row["last_revised_at"],
        defined_by=ActorId(row["defined_by"]),
        revision_count=int(row["revision_count"]),
        latest_revision_status=(
            str(row["latest_revision_status"])
            if row["latest_revision_status"] is not None
            else None
        ),
        latest_revision_source_kind=(
            str(row["latest_revision_source_kind"])
            if row["latest_revision_source_kind"] is not None
            else None
        ),
    )


def _log_fields(query: ListCalibrations) -> dict[str, Any]:
    return {
        "target_id": (str(query.target_id) if query.target_id else None),
        "quantity": query.quantity,
        "latest_revision_statuses": (
            list(query.latest_revision_statuses) if query.latest_revision_statuses else None
        ),
        "latest_revision_source_kinds": (
            list(query.latest_revision_source_kinds) if query.latest_revision_source_kinds else None
        ),
    }


def bind(deps: Kernel) -> Handler:
    """Build a list_calibrations handler closed over the shared deps."""
    return make_list_query_handler(
        deps,
        query_name="ListCalibrations",
        log_prefix="list_calibrations",
        unauthorized_error=UnauthorizedError,
        table="proj_calibration_summary",
        select_columns=_SELECT_COLUMNS,
        time_column="defined_at",
        id_column="calibration_id",
        filters=[
            ScalarFilter(attr="target_id"),
            ScalarFilter(attr="quantity"),
            ColumnInFilter(attr="latest_revision_statuses", column="latest_revision_status"),
            ColumnInFilter(
                attr="latest_revision_source_kinds",
                column="latest_revision_source_kind",
            ),
        ],
        row_to_item=_row_to_item,
        item_cursor_at=lambda item: item.defined_at,
        item_cursor_id=lambda item: item.calibration_id,
        page_from=lambda items, next_cursor: CalibrationListPage(
            items=items, next_cursor=next_cursor
        ),
        extract_log_fields=_log_fields,
    )


__all__ = [
    "CalibrationListPage",
    "CalibrationSummaryItem",
    "Handler",
    "bind",
]
