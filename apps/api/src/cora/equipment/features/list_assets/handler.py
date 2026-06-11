"""Application handler for the `list_assets` query slice.

Reads `proj_equipment_asset_summary` via the cross-BC
`infrastructure.list_query.make_list_query_handler` factory.
Three optional filters (tier + lifecycle + parent_id) plus cursor
pagination on `(created_at, asset_id)`.

BOLA: command-name gating only. Per-row scoping deferred until ReBAC
(see `memory/project_deferred.md`).
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol, cast
from uuid import UUID

from cora.equipment.errors import UnauthorizedError
from cora.equipment.features.list_assets.query import (
    AssetLifecycleFilter,
    AssetTierFilter,
    ListAssets,
)
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.list_query import ScalarFilter, make_list_query_handler
from cora.infrastructure.routing import NIL_SENTINEL_ID


@dataclass(frozen=True)
class AssetSummaryItem:
    """One row from the asset projection."""

    asset_id: UUID
    name: str
    tier: AssetTierFilter
    lifecycle: AssetLifecycleFilter
    parent_id: UUID | None
    created_at: datetime


@dataclass(frozen=True)
class AssetListPage:
    """A page of asset summaries plus the cursor for the next page."""

    items: list[AssetSummaryItem]
    next_cursor: str | None


class Handler(Protocol):
    """Callable interface every list_assets handler implements."""

    async def __call__(
        self,
        query: ListAssets,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> AssetListPage: ...


_SELECT_COLUMNS = "asset_id, name, tier, lifecycle, parent_id, created_at"


def _row_to_item(row: Any) -> AssetSummaryItem:
    return AssetSummaryItem(
        asset_id=row["asset_id"],
        name=str(row["name"]),
        tier=cast("AssetTierFilter", str(row["tier"])),
        lifecycle=cast("AssetLifecycleFilter", str(row["lifecycle"])),
        parent_id=row["parent_id"],
        created_at=row["created_at"],
    )


def _log_fields(query: ListAssets) -> dict[str, Any]:
    return {
        "tier": query.tier,
        "lifecycle": query.lifecycle,
        "parent_id": str(query.parent_id) if query.parent_id else None,
    }


def bind(deps: Kernel) -> Handler:
    """Build a list_assets handler closed over the shared deps."""
    return make_list_query_handler(
        deps,
        query_name="ListAssets",
        log_prefix="list_assets",
        unauthorized_error=UnauthorizedError,
        table="proj_equipment_asset_summary",
        select_columns=_SELECT_COLUMNS,
        time_column="created_at",
        id_column="asset_id",
        filters=[
            ScalarFilter(attr="tier"),
            ScalarFilter(attr="lifecycle"),
            ScalarFilter(attr="parent_id"),
        ],
        row_to_item=_row_to_item,
        item_cursor_at=lambda item: item.created_at,
        item_cursor_id=lambda item: item.asset_id,
        page_from=lambda items, next_cursor: AssetListPage(items=items, next_cursor=next_cursor),
        extract_log_fields=_log_fields,
    )


__all__ = [
    "AssetListPage",
    "AssetSummaryItem",
    "Handler",
    "bind",
]
