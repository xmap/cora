"""The `AddAssetAlternateIdentifier` command, intent dataclass for this slice.

`asset_id` is the target Asset aggregate. `alternate_identifier` is
the full `AlternateIdentifier` VO (kind + value) to add to the
asset's identifier set. The decider rejects a duplicate
`(kind, value)` pair (strict-not-idempotent) and rejects when the
asset is Decommissioned (mirrors the `add_asset_port` lifecycle
guard).
"""

from dataclasses import dataclass
from uuid import UUID

from cora.equipment.aggregates.asset import AlternateIdentifier


@dataclass(frozen=True)
class AddAssetAlternateIdentifier:
    """Add an alternate identifier to an existing Asset's identifier set.

    The identifier is the full `AlternateIdentifier` VO (kind + value).
    The decider's strict-not-idempotent guard rejects a duplicate
    `(kind, value)` pair already on the asset; the lifecycle guard
    rejects when the asset is Decommissioned.
    """

    asset_id: UUID
    alternate_identifier: AlternateIdentifier
