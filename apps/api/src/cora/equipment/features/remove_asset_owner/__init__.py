"""Vertical slice for the `RemoveAssetOwner` command.

Removes an institutional owner block by `name` from an existing
Asset's owners set; strict-not-idempotent: an unknown name surfaces
as 404 rather than silent no-op. Allows removing the last owner
(aggregate cardinality is 0-n; the PIDINST 1-n cardinality is a
serializer-time gate per [[project-asset-owner-design]] Lock 7).
The lifecycle guard mirrors `add_asset_owner`: a Decommissioned
asset rejects owner mutations.

Module-as-namespace surface:

    from cora.equipment.features import remove_asset_owner

    cmd = remove_asset_owner.RemoveAssetOwner(
        asset_id=...,
        owner_name=AssetOwnerName("HZB"),
    )
    handler = remove_asset_owner.bind(deps)
    await handler(cmd, principal_id=..., correlation_id=...)
"""

from cora.equipment.features.remove_asset_owner import tool
from cora.equipment.features.remove_asset_owner.command import RemoveAssetOwner
from cora.equipment.features.remove_asset_owner.decider import decide
from cora.equipment.features.remove_asset_owner.handler import Handler, bind
from cora.equipment.features.remove_asset_owner.route import router

__all__ = [
    "Handler",
    "RemoveAssetOwner",
    "bind",
    "decide",
    "router",
    "tool",
]
