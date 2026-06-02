"""Vertical slice for the `RemoveAssetAlternateIdentifier` command.

Mirror of `add_asset_alternate_identifier`. Removes an alternate
identifier from an Asset by exact `(kind, value)` pair; rejects
when the asset is Decommissioned or no such pair exists.

The `add_asset_port` / `remove_asset_port` precedent is followed
verbatim for the slice topology (POST-style action endpoint,
strict-not-idempotent, dedicated decommissioned-guard error).
"""

from cora.equipment.features.remove_asset_alternate_identifier import tool
from cora.equipment.features.remove_asset_alternate_identifier.command import (
    RemoveAssetAlternateIdentifier,
)
from cora.equipment.features.remove_asset_alternate_identifier.decider import decide
from cora.equipment.features.remove_asset_alternate_identifier.handler import Handler, bind
from cora.equipment.features.remove_asset_alternate_identifier.route import router

__all__ = [
    "Handler",
    "RemoveAssetAlternateIdentifier",
    "bind",
    "decide",
    "router",
    "tool",
]
