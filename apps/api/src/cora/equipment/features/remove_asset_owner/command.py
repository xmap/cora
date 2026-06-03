"""The `RemoveAssetOwner` command, intent dataclass for this slice.

`asset_id` is the target Asset aggregate. `owner_name` is the
`AssetOwnerName` VO that keys the removal per
[[project-asset-owner-design]] Lock 5: operator commands say
"remove HZB", not "remove HZB with contact X and identifier Y". The
decider rejects an unknown name (strict-not-idempotent) and rejects
when the asset is Decommissioned.
"""

from dataclasses import dataclass
from uuid import UUID

from cora.equipment.aggregates.asset import AssetOwnerName


@dataclass(frozen=True)
class RemoveAssetOwner:
    """Remove an institutional owner from an existing Asset's owners set.

    Keyed on `owner_name` only. Removing the last owner is allowed:
    the aggregate stores 0-n owners; PIDINST 1-n MANDATORY cardinality
    is enforced at the serializer boundary, not here.
    """

    asset_id: UUID
    owner_name: AssetOwnerName
