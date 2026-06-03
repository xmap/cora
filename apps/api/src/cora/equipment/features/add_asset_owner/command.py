"""The `AddAssetOwner` command, intent dataclass for this slice.

`asset_id` is the target Asset aggregate. `owner` is the full
`AssetOwner` VO (name + optional contact + paired
identifier/identifier_type) to add to the asset's owners set. The
decider rejects a duplicate `name` (strict-not-idempotent per Lock
6) and rejects when the asset is Decommissioned (mirrors the
`add_asset_alternate_identifier` lifecycle guard).
"""

from dataclasses import dataclass
from uuid import UUID

from cora.equipment.aggregates.asset import AssetOwner


@dataclass(frozen=True)
class AddAssetOwner:
    """Add an institutional owner block to an existing Asset's owners set.

    The owner is the full `AssetOwner` VO (name + optional contact +
    paired identifier/identifier_type). The decider's strict-not-
    idempotent guard rejects a duplicate `name` already on the asset;
    the lifecycle guard rejects when the asset is Decommissioned.
    """

    asset_id: UUID
    owner: AssetOwner
