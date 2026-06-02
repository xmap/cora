"""The `ListAssets` query — intent dataclass for keyset-paginated
list of assets from the projection.

Three optional filters: level (hierarchy tier), lifecycle (state),
parent_id (direct children of). Combine for queries like "all
Active Devices under this Unit". Cursor encodes (created_at, asset_id).
"""

from dataclasses import dataclass
from typing import Literal
from uuid import UUID

AssetLevelFilter = Literal[
    "Enterprise",
    "Site",
    "Area",
    "Unit",
    "Component",
    "Device",
]

AssetLifecycleFilter = Literal[
    "Commissioned",
    "Active",
    "Maintenance",
    "Decommissioned",
]


@dataclass(frozen=True)
class ListAssets:
    """Read a keyset-paginated page of assets from the projection."""

    cursor: str | None = None
    """Opaque base64 cursor from a previous page's `next_cursor`."""

    limit: int = 50
    """Page size cap. Default 50, max 100 (route enforces)."""

    level: AssetLevelFilter | None = None
    """Optional level filter (one of the AssetLevel enum values)."""

    lifecycle: AssetLifecycleFilter | None = None
    """Optional lifecycle filter."""

    parent_id: UUID | None = None
    """Optional `parent_id` filter — returns DIRECT children of the
    given asset. Pass `None` (omit) for "any parent". The current
    projection is flat, so transitive descendants require multiple
    queries; that's a future projection (`proj_equipment_asset_subtree`)
    when use cases demand it."""
