"""Vertical slice for the `AddAssetOwner` command.

Adds a single `AssetOwner` (PIDINST v1.0 Property 5 owner block) to
an existing Asset's owner set; strict-not-idempotent on owner name:
a duplicate name surfaces as 409 rather than silent no-op. The
lifecycle guard mirrors `add_asset_alternate_identifier`: a
Decommissioned asset rejects owner mutations.

Module-as-namespace surface:

    from cora.equipment.features import add_asset_owner

    cmd = add_asset_owner.AddAssetOwner(
        asset_id=...,
        owner=AssetOwner(name=AssetOwnerName("HZB")),
    )
    handler = add_asset_owner.bind(deps)
    await handler(cmd, principal_id=..., correlation_id=...)

The `add_asset_alternate_identifier` precedent is followed verbatim
for the slice topology (POST-style action endpoint, strict-not-
idempotent, shared lifecycle-guard error class with the sibling
remove slice). See [[project-asset-owner-design]] Locks 5, 6, 7.
"""

from cora.equipment.features.add_asset_owner import tool
from cora.equipment.features.add_asset_owner.command import AddAssetOwner
from cora.equipment.features.add_asset_owner.decider import decide
from cora.equipment.features.add_asset_owner.handler import Handler, bind
from cora.equipment.features.add_asset_owner.route import router

__all__ = [
    "AddAssetOwner",
    "Handler",
    "bind",
    "decide",
    "router",
    "tool",
]
