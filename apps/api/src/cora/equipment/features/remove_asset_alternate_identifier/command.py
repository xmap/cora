"""The `RemoveAssetAlternateIdentifier` command - intent dataclass for this slice."""

from dataclasses import dataclass
from uuid import UUID

from cora.equipment.aggregates.asset import AlternateIdentifier


@dataclass(frozen=True)
class RemoveAssetAlternateIdentifier:
    """Remove an alternate identifier from an existing Asset's identifier set.

    The identifier is matched on the exact `(kind, value)` pair. The
    decider rejects when the asset is Decommissioned (mirrors the
    `remove_asset_port` lifecycle guard) and rejects when no such
    pair exists on the asset (strict-not-idempotent, symmetric with
    add).
    """

    asset_id: UUID
    alternate_identifier: AlternateIdentifier
